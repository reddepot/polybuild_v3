"""Audit runner — execute one audit job (M2C.2).

For each :class:`~polybuild.audit.queue.AuditQueueEntry` the runner:

  1. picks a Western+Chinese voice pair via :func:`pick_voice_pair`,
  2. extracts the commit's ``git diff HEAD~1`` (plafonné à
     :data:`MAX_DIFF_LINES`, plan §M2C.2),
  3. asks each voice in parallel to audit the diff on POLYLENS axes
     A (sécurité), C (tests) and G (adversarial),
  4. parses the structured JSON-Lines reply into
     :class:`~polybuild.audit.backlog.BacklogFinding` objects,
  5. returns the deduped findings list.

Each voice call is bounded by :data:`VOICE_TIMEOUT_S`. A timeout, a
non-zero exit, an unparseable reply or any other ``OSError`` returns
**zero findings silently** — anti-pattern #16 (voice imbalance bias)
is handled by rotation; anti-pattern #20 (monoculture) by the
W+CN pair invariant; a flaky single voice should never block the
audit pipeline.

The voice caller is **injectable** for testing. ``default_voice_caller``
shells out to the matching CLI binary (``codex``, ``gemini``, ``kimi``)
or to the OpenRouter HTTP API for the Chinese pool. Tests pass an
async lambda that returns canned JSON.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import structlog

from polybuild.audit.backlog import (
    Axis,
    BacklogFinding,
    Severity,
    compute_fingerprint,
)
from polybuild.audit.queue import AuditQueueEntry
from polybuild.audit.rotation import VoicePair, pick_voice_pair

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# CONSTANTS (plan §M2C.2)
# ────────────────────────────────────────────────────────────────

VOICE_TIMEOUT_S = 30.0
MAX_DIFF_LINES = 200
MAX_COST_USD = 0.30
DEFAULT_AXES: tuple[Axis, ...] = ("A_security", "C_tests", "G_adversarial")


# ────────────────────────────────────────────────────────────────
# VOICE CALLER PROTOCOL
# ────────────────────────────────────────────────────────────────

# A VoiceCaller takes (voice_id, prompt) and returns the voice's raw
# textual output. Implementations MUST honour ``VOICE_TIMEOUT_S``
# themselves (the runner does not wrap it again — would double the
# wall-clock budget per audit).
VoiceCaller = Callable[[str, str], Awaitable[str]]


async def default_voice_caller(voice_id: str, prompt: str) -> str:
    """Default implementation: subprocess CLI for Western voices,
    OpenRouter HTTP for Chinese voices.

    Returns an empty string on any failure (timeout, non-zero exit,
    network error). A failed voice produces no findings — the rotation
    will reach the next one on the next audit cycle.
    """
    if voice_id.startswith(("codex-", "gemini-", "kimi-")):
        return await _call_western_cli(voice_id, prompt)
    if "/" in voice_id:  # OpenRouter slug (provider/model form)
        return await _call_openrouter(voice_id, prompt)
    logger.warning("audit_voice_unknown", voice_id=voice_id)
    return ""


def _western_cli_command(voice_id: str) -> list[str] | None:
    """Map a voice_id to a subprocess argv (None if the binary is missing)."""
    if voice_id == "codex-gpt-5.5":
        if not shutil.which("codex"):
            return None
        return [
            "codex",
            "-m",
            "gpt-5.5",
            "-c",
            "model_reasoning_effort=high",
            "exec",
            "--skip-git-repo-check",
            "--",
        ]
    if voice_id == "gemini-3.1-pro":
        if not shutil.which("gemini"):
            return None
        return ["gemini", "-m", "gemini-3.1-pro-preview", "-y"]
    if voice_id == "kimi-k2.6":
        if not shutil.which("kimi"):
            return None
        return [
            "kimi",
            "--quiet",
            "--yolo",
            "--thinking",
            "--max-steps-per-turn",
            "25",
            "-p",
        ]
    return None


async def _call_western_cli(voice_id: str, prompt: str) -> str:
    """Spawn the matching CLI binary, send the prompt as the last argv,
    capture stdout. Silently returns ``""`` on any failure.
    """
    argv = _western_cli_command(voice_id)
    if argv is None:
        return ""
    argv = [*argv, prompt]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout_b, _stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=VOICE_TIMEOUT_S,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await asyncio.sleep(0)  # let kill propagate
            logger.warning("audit_voice_timeout", voice_id=voice_id)
            return ""
        return stdout_b.decode("utf-8", errors="replace")
    except (OSError, FileNotFoundError):
        return ""


async def _call_openrouter(voice_id: str, prompt: str) -> str:
    """Call the OpenRouter chat-completions endpoint.

    Reads the API key from ``OPENROUTER_API_KEY`` env var. Returns ``""``
    on any failure (missing key, timeout, non-2xx, missing httpx).
    """
    import os

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("audit_openrouter_no_key", voice_id=voice_id)
        return ""

    try:
        import httpx
    except ImportError:
        return ""

    payload: dict[str, Any] = {
        "model": voice_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=VOICE_TIMEOUT_S) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code != 200:
            logger.warning(
                "audit_openrouter_non_200",
                voice_id=voice_id,
                status=resp.status_code,
            )
            return ""
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        text = choices[0].get("message", {}).get("content", "")
        if not isinstance(text, str):
            return ""
        return text
    except (httpx.HTTPError, ValueError, KeyError):
        return ""


# ────────────────────────────────────────────────────────────────
# DIFF EXTRACTION
# ────────────────────────────────────────────────────────────────


def extract_commit_diff(
    repo_path: Path,
    commit_sha: str,
    *,
    max_lines: int = MAX_DIFF_LINES,
) -> str:
    """Return ``git show <sha>`` output truncated to ``max_lines`` lines.

    A truncation marker is appended when the diff exceeds the budget so
    voices know they are seeing a partial view.
    """
    git_bin = shutil.which("git")
    if git_bin is None:
        return ""
    try:
        out = subprocess.run(  # noqa: S603 — args list, no shell, binary resolved
            [git_bin, "show", "--unified=3", "--format=fuller", commit_sha],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""

    if out.returncode != 0:
        return ""

    lines = out.stdout.splitlines()
    if len(lines) <= max_lines:
        return out.stdout

    truncated = lines[:max_lines]
    truncated.append(
        f"... [truncated {len(lines) - max_lines} more diff lines, "
        f"audit budget = {max_lines} lines]"
    )
    return "\n".join(truncated)


# ────────────────────────────────────────────────────────────────
# PROMPT
# ────────────────────────────────────────────────────────────────

_AUDIT_PROMPT_TEMPLATE = """\
You are a code auditor running on commit {commit_sha} of repository
{repo_path}. Produce a JSON-Lines list of findings, one finding per
line, no surrounding prose.

Audited axes: {axes}.

Severity scale: P0 (security exploit / data loss / opposable code
defect) > P1 (correctness bug, blocking) > P2 (smell, technical
debt) > P3 (style / DX nit). Be conservative: emit fewer findings
of higher quality rather than many P3 noise lines.

Required JSON shape per line (strict, no trailing commas, no
extra keys):

  {{
    "axis": "A_security | C_tests | G_adversarial",
    "severity": "P0 | P1 | P2 | P3",
    "file": "<repo-relative path>",
    "line": <int or null>,
    "message": "<one-sentence problem description>"
  }}

Diff under audit (max {max_lines} lines, truncated if longer):

```diff
{diff}
```

If you find nothing, output exactly the empty string. Do NOT explain.
"""


def _build_prompt(entry: AuditQueueEntry, diff: str, axes: tuple[Axis, ...]) -> str:
    return _AUDIT_PROMPT_TEMPLATE.format(
        commit_sha=entry.commit_sha,
        repo_path=str(entry.repo_path),
        axes=", ".join(axes),
        max_lines=MAX_DIFF_LINES,
        diff=diff,
    )


# ────────────────────────────────────────────────────────────────
# OUTPUT PARSING
# ────────────────────────────────────────────────────────────────

_VALID_AXES = frozenset(Axis.__args__)  # type: ignore[attr-defined]
_VALID_SEVERITIES = frozenset(Severity.__args__)  # type: ignore[attr-defined]
_JSON_LINE_RE = re.compile(r"^\s*\{.*\}\s*$")


def _parse_voice_output(
    raw: str,
    voice_id: str,
    commit_sha: str,
) -> list[BacklogFinding]:
    """Parse JSON-Lines output into ``BacklogFinding``s.

    Tolerant: skips lines that aren't JSON, lines missing required
    keys, lines with invalid axis or severity values. A garbage line
    never poisons the rest.
    """
    findings: list[BacklogFinding] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or not _JSON_LINE_RE.match(line):
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        axis_raw = obj.get("axis")
        severity_raw = obj.get("severity")
        file = obj.get("file")
        message = obj.get("message")
        line_no_raw = obj.get("line")
        if (
            not isinstance(axis_raw, str)
            or axis_raw not in _VALID_AXES
            or not isinstance(severity_raw, str)
            or severity_raw not in _VALID_SEVERITIES
            or not isinstance(file, str)
            or not isinstance(message, str)
        ):
            continue
        # mypy can now narrow ``axis_raw`` / ``severity_raw`` to the Literal
        # type via these explicit casts (Pydantic also re-validates).
        axis: Axis = axis_raw  # type: ignore[assignment]
        severity: Severity = severity_raw  # type: ignore[assignment]
        line_no = line_no_raw if isinstance(line_no_raw, int) else None
        fingerprint = compute_fingerprint(
            commit_sha=commit_sha,
            file=file,
            line=line_no,
            axis=axis,
            message=message,
        )
        findings.append(
            BacklogFinding(
                fingerprint=fingerprint,
                commit_sha=commit_sha,
                file=file,
                line=line_no,
                axis=axis,
                severity=severity,
                message=message,
                voice=voice_id,
            )
        )
    return findings


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def audit_commit(
    entry: AuditQueueEntry,
    *,
    voice_caller: VoiceCaller | None = None,
    state_dir: Path | None = None,
    axes: tuple[Axis, ...] = DEFAULT_AXES,
) -> list[BacklogFinding]:
    """Run a full POLYLENS hook audit for one queued commit.

    Args:
        entry: queued commit (sha + repo path).
        voice_caller: optional injection for tests; defaults to
            ``default_voice_caller``.
        state_dir: rotation state directory (tests pass a tmp path).
        axes: POLYLENS axes to audit. Default per-plan A+C+G.

    Returns:
        Combined ``BacklogFinding`` list from both voices. The runner
        does NOT persist findings — the caller (the ``audit drain``
        subcommand, M2C.1) decides whether to write to the backlog and
        whether to fire P0/P1 notifications (M2C.3).
    """
    caller = voice_caller or default_voice_caller
    pair: VoicePair = pick_voice_pair(state_dir=state_dir)

    diff = extract_commit_diff(entry.repo_path, entry.commit_sha)
    if not diff:
        logger.info(
            "audit_diff_empty",
            commit_sha=entry.commit_sha,
            voices=pair.as_list(),
        )
        return []

    prompt = _build_prompt(entry, diff, axes)

    logger.info(
        "audit_start",
        commit_sha=entry.commit_sha,
        voices=pair.as_list(),
        diff_lines=len(diff.splitlines()),
        axes=list(axes),
    )

    # Run both voices in parallel — anti-pattern #18 (bash orchestrator
    # fragile): asyncio.gather with return_exceptions so one failure
    # never poisons the other.
    western_task = caller(pair.western, prompt)
    chinese_task = caller(pair.chinese, prompt)
    raw_western, raw_chinese = await asyncio.gather(
        western_task, chinese_task, return_exceptions=True,
    )

    findings: list[BacklogFinding] = []
    if isinstance(raw_western, str):
        findings.extend(
            _parse_voice_output(raw_western, pair.western, entry.commit_sha)
        )
    elif isinstance(raw_western, BaseException):
        logger.warning(
            "audit_western_voice_exception",
            voice_id=pair.western,
            error=str(raw_western),
        )

    if isinstance(raw_chinese, str):
        findings.extend(
            _parse_voice_output(raw_chinese, pair.chinese, entry.commit_sha)
        )
    elif isinstance(raw_chinese, BaseException):
        logger.warning(
            "audit_chinese_voice_exception",
            voice_id=pair.chinese,
            error=str(raw_chinese),
        )

    logger.info(
        "audit_done",
        commit_sha=entry.commit_sha,
        findings_count=len(findings),
        p0_count=sum(1 for f in findings if f.severity == "P0"),
        p1_count=sum(1 for f in findings if f.severity == "P1"),
    )
    return findings


__all__ = [
    "DEFAULT_AXES",
    "MAX_COST_USD",
    "MAX_DIFF_LINES",
    "VOICE_TIMEOUT_S",
    "VoiceCaller",
    "audit_commit",
    "default_voice_caller",
    "extract_commit_diff",
]
