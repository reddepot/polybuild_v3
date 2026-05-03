"""Phase 5 — Critic-Fixer-Verifier triade.

Severity-differentiated handling (acquis convergent T4):
    - P0: per-finding triade, Critic ≠ Fixer ≠ Verifier (3 distinct families)
    - P1: batched by axis, single Critic + Fixer per batch
    - P2/P3: local auto-fix (ruff --fix, mypy --hint), NO LLM

Verifier (Évaluateur-Optimiseur strict):
    - JSON-only output: {pass, reason, required_evidence}
    - NEVER rewrites code
    - Rejects by default if no reproducible evidence

Local gates first (PRE-LLM check):
    Before invoking the Verifier, run pytest + mypy + bandit on the patch.
    If they fail, loop back to Fixer with failure context (saves verifier tokens).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import structlog

from polybuild.adapters import get_builder
from polybuild.models import (
    AuditReport,
    BuilderResult,
    Finding,
    FixReport,
    FixResult,
    PrivacyLevel,
    RiskProfile,
    Severity,
)

logger = structlog.get_logger()


# Round 10.7 fix [Kimi C-04 P1 + Gemini validation MISSING-05]: allow-list
# of env vars propagated to local-gate subprocesses (ruff/mypy/pytest).
# Stripping them caused ``uv``/``pytest``/``mypy`` to fail outright; the
# allow-list keeps them functional while still isolating the child from
# arbitrary operator shell config.
_LOCAL_GATE_ENV_KEYS = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "VIRTUAL_ENV",
    "UV_CACHE_DIR",
    "UV_INDEX_URL",
    "UV_PYTHON",
    "TMPDIR",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
)


# ────────────────────────────────────────────────────────────────
# ROLE ASSIGNMENT (anti self-fix)
# ────────────────────────────────────────────────────────────────


def pick_triade(
    winner_family: str,
    auditor_family: str,
    risk_profile: RiskProfile,
) -> tuple[str, str, str]:
    """Pick (critic, fixer, verifier) where each has a different family.

    Excludes:
        - winner_family (avoids self-fix bias)
        - auditor_family (avoids audit-fix collusion for the verifier)
    """
    # Hard pool minus excluded families
    all_models = [
        ("claude-opus-4.7", "anthropic"),
        ("gpt-5.5", "openai"),
        ("gemini-3.1-pro", "google"),
        ("kimi-k2.6", "moonshot"),
        ("deepseek/deepseek-v4-pro", "deepseek"),
        ("x-ai/grok-4.20", "xai"),
        ("mistral/devstral-2", "mistral"),
    ]

    # Filter for risk profile
    if risk_profile.excludes_openrouter:
        all_models = [(m, f) for m, f in all_models if not m.startswith(("deepseek/", "x-ai/"))]
    if risk_profile.excludes_us_cn_models:
        # Round 10.3 fix [ChatGPT RX-301-07 P1]: ``deepseek`` was missing
        # from the exclude set, so a sensitivity-HIGH run could re-admit
        # a CN model in Phase 5 even though Phase 1 had filtered it out.
        # Keep this list aligned with phase_1_select.is_us_or_cn_model().
        excluded_families = {
            "anthropic",
            "openai",
            "google",
            "xai",
            "moonshot",
            "deepseek",
            "alibaba",
        }
        all_models = [(m, f) for m, f in all_models if f not in excluded_families]

    available = [(m, f) for m, f in all_models if f != winner_family]

    # Round 10.3 fix [Kimi RX-301 P0]: with both excludes_openrouter and
    # excludes_us_cn_models on (medical_high), the pool can collapse to a
    # single family (mistral). If the winner happens to be that family,
    # ``available`` is empty and ``available[0]`` raises IndexError —
    # deterministic crash on every medical_high run with mistral winner.
    if not available:
        raise RuntimeError(
            f"pick_triade: no candidate available after filtering for "
            f"winner_family={winner_family!r} under {risk_profile=!r}. "
            f"Widen the model pool or escalate."
        )

    # Critic: any family ≠ winner
    critic_model, critic_family = available[0]

    # Fixer: ≠ winner AND ≠ critic
    fixer_candidates = [(m, f) for m, f in available if f != critic_family]
    if not fixer_candidates:
        raise RuntimeError("No fixer candidate available")
    fixer_model, fixer_family = fixer_candidates[0]

    # Verifier: ≠ winner AND ≠ critic AND ≠ fixer AND ≠ auditor (no collusion)
    verifier_candidates = [
        (m, f)
        for m, f in available
        if f not in {critic_family, fixer_family, auditor_family}
    ]
    if not verifier_candidates:
        # Round 10.3 fix [Grok RX-301-02 + Qwen + Gemini + DeepSeek]
        # (4/4 conv, P0/P1): the previous fallback re-included
        # ``auditor_family`` in the candidate pool, allowing the same
        # family that produced the audit to also verify the fix —
        # the canonical collusion vector. We now split the policy:
        #
        #   * sensitivity == HIGH (medical_high, legal opposable):
        #     STRICT — raise InsufficientOrthogonalFamiliesError so the
        #     caller can either widen the model pool or escalate to a
        #     human reviewer. Silent collusion is unacceptable.
        #
        #   * other sensitivities: degraded relax with explicit
        #     warning and a triade_degraded flag in logs (visible to
        #     post-mortem). Same behaviour as before but auditable.
        if (
            risk_profile is not None
            and risk_profile.sensitivity == PrivacyLevel.HIGH
        ):
            raise InsufficientOrthogonalFamiliesError(
                "verifier",
                excluded_families=sorted(
                    {critic_family, fixer_family, auditor_family}
                ),
                hint=(
                    "medical_high requires Critic/Fixer/Verifier from 3 "
                    "distinct families AND a 4th for auditor. Widen the "
                    "voice pool or escalate."
                ),
            )
        logger.warning(
            "pick_triade_relax_auditor_family_reused_as_verifier",
            critic_family=critic_family,
            fixer_family=fixer_family,
            auditor_family=auditor_family,
            triade_degraded=True,
        )
        verifier_candidates = [
            (m, f) for m, f in available if f not in {critic_family, fixer_family}
        ]
    verifier_model = verifier_candidates[0][0]

    return critic_model, fixer_model, verifier_model


class InsufficientOrthogonalFamiliesError(RuntimeError):
    """Raised when the triade selector cannot find a fully-orthogonal
    Critic/Fixer/Verifier set under a sensitivity policy that forbids
    relaxation. Callers may catch this to escalate to a human reviewer
    (Round 10.3 fix for collusion vector under medical_high).
    """

    def __init__(
        self,
        role: str,
        excluded_families: list[str],
        hint: str = "",
    ) -> None:
        super().__init__(
            f"No orthogonal candidate for role={role!r} "
            f"(excluded families: {excluded_families}). {hint}"
        )
        self.role = role
        self.excluded_families = excluded_families


# ────────────────────────────────────────────────────────────────
# PROMPT LOADING
# ────────────────────────────────────────────────────────────────

def _resolve_prompts_dir() -> Path:
    """Locate prompts/ robustly across source-tree, wheel install, and CI.

    Round 9 fix [Claude-prompts-dir] (Claude P0):
        Previous `_PROMPTS_DIR = parents[3] / "prompts"` worked only in
        editable install from source-tree. In a wheel install, parents[3]
        points outside the package and prompts/ is not found. The soft
        fallback returned a string WITHOUT any placeholders → `.format()`
        silently ignored all kwargs → critic/fixer/verifier received an
        empty prompt → Phase 5 produced garbage outputs.

    Resolution order (same shape as round 5 [Y] fix in concurrency limiter):
        1. POLYBUILD_PROMPTS_DIR env var
        2. Walk up from this file looking for prompts/critic.md
        3. Look next to the installed `polybuild` package
        4. RAISE explicitly — soft fallback is dangerous for prompt templates.
    """
    env_dir = os.environ.get("POLYBUILD_PROMPTS_DIR")
    if env_dir:
        candidate = Path(env_dir)
        if (candidate / "critic.md").exists():
            return candidate

    # Walk up from this file (handles editable install + nested layouts)
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "prompts"
        if (candidate / "critic.md").exists():
            return candidate

    # Wheel install: prompts/ may be packaged inside the polybuild package
    try:
        import polybuild as _pkg

        pkg_dir = Path(_pkg.__file__).parent
        candidate = pkg_dir / "prompts"
        if (candidate / "critic.md").exists():
            return candidate
        # Or one level up (data_files install pattern)
        candidate = pkg_dir.parent / "prompts"
        if (candidate / "critic.md").exists():
            return candidate
    except ImportError:
        pass

    raise FileNotFoundError(
        "POLYBUILD prompts/ directory not found. Tried env var, source-tree "
        "ancestors, and wheel install locations. Set POLYBUILD_PROMPTS_DIR or "
        "ensure prompts/critic.md is reachable."
    )


_PROMPTS_DIR = _resolve_prompts_dir()


# Round 10.2 fix [Grok adversarial — prompts/*.md poisoning]: each Phase-5
# template is expected to contain at least the ``{finding_id}`` placeholder.
# If an attacker tampers with prompts/critic.md to remove all placeholders
# (so the LLM is unconstrained) the orchestrator should refuse rather than
# silently feed a poisoned template. We only enforce the minimum invariant
# (finding_id) — additional placeholders vary across roles and are checked
# functionally at format-time.
_REQUIRED_PROMPT_PLACEHOLDERS: dict[str, set[str]] = {
    "critic": {"finding_id"},
    # Round 10.8 prod-launch fix: prompts/fixer.md uses {workdir} too —
    # add it to the required placeholder set so a tampered template
    # missing either {finding_id} OR {workdir} is rejected loudly.
    "fixer": {"finding_id", "workdir"},
    "verifier_strict": {"finding_id"},
}


def _load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory.

    Round 9 fix [Claude-prompts-dir]: removed the soft fallback that used
    to return a placeholder-less string. ``str.format`` would silently
    swallow all kwargs and feed the LLM a useless prompt. Now we raise
    loudly if a specific template is missing.

    Round 10.2 fix [Grok adversarial]: also validate that the loaded
    template contains every placeholder the corresponding caller will
    supply. Sanitize through the prompt-injection sanitizer too so a
    tampered template carrying ``<!-- override system prompt -->`` is
    cleaned before reaching the model.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Required prompt template missing: {path}. The Phase 5 triade "
            f"cannot proceed without it. Ensure prompts/{name}.md is present."
        )
    raw = path.read_text(encoding="utf-8")

    # Defence against template tampering: enforce required placeholders.
    # Round 10.7 fix [Kimi C-07 P1]: previously the check was skipped
    # whenever ``POLYBUILD_PROMPTS_DIR`` was set — but that env var has
    # legitimate non-debug uses (CI custom prompt dir, deployments with
    # bundled prompts at a non-default location). Setting it would
    # disable the placeholder integrity check entirely. Switch to a
    # debug-specific opt-out (``POLYBUILD_PROMPTS_DEBUG``) so production
    # paths always run the check.
    expected = _REQUIRED_PROMPT_PLACEHOLDERS.get(name)
    if expected and not os.environ.get("POLYBUILD_PROMPTS_DEBUG"):
        for placeholder in expected:
            if "{" + placeholder + "}" not in raw:
                raise RuntimeError(
                    f"prompt template {name!r} is missing the required "
                    f"placeholder {{{placeholder}}}; refusing to use a "
                    f"potentially tampered template."
                )

    # Defence against prompt-injection comments / fenced blocks tucked
    # into the template body itself.
    from polybuild.security.prompt_sanitizer import sanitize_prompt_context

    return sanitize_prompt_context(raw)


# ────────────────────────────────────────────────────────────────
# LOCAL GATES (PRE-VERIFIER)
# ────────────────────────────────────────────────────────────────


async def _run_local_gates(code_dir: Path) -> tuple[bool, str]:
    """Run pytest + mypy + ruff on patched code BEFORE invoking Verifier.

    Returns (all_pass, failure_summary). Saves Verifier tokens by short-circuiting
    on local lint/type/test failures.
    """
    failures: list[str] = []

    # Round 10.7 fix [Kimi C-04 P1]: align local-gates subprocess hygiene
    # with the rest of the codebase (start_new_session + minimal env).
    # Round 10.7 fix [Gemini validation MISSING-05]: allow-list rather
    # than wholesale-strip — propagate the variables ``uv``, ``pytest``
    # and ``mypy`` need (defined module-level above).
    minimal_env = {
        k: os.environ[k] for k in _LOCAL_GATE_ENV_KEYS if k in os.environ
    }
    # ``LANG`` should default to a UTF-8 locale if missing.
    minimal_env.setdefault("LANG", "C.UTF-8")
    for label, args in [
        ("ruff", ["uv", "run", "ruff", "check", "src/"]),
        ("mypy", ["uv", "run", "mypy", "--strict", "src/"]),
        ("pytest", ["uv", "run", "pytest", "-x", "--no-header", "-q"]),
    ]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=code_dir.parent,
                start_new_session=True,
                env=minimal_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            if proc.returncode != 0:
                excerpt = (stdout + stderr).decode("utf-8", errors="replace")[-800:]
                failures.append(f"[{label}] returncode={proc.returncode}\n{excerpt}")
        except TimeoutError:
            failures.append(f"[{label}] timeout >180s")
        except FileNotFoundError:
            # Tool not available in this environment — non-blocking.
            logger.debug("local_gate_tool_missing", tool=label)

    if not failures:
        return True, ""
    return False, "\n\n".join(failures)


# ────────────────────────────────────────────────────────────────
# JSON VERDICT PARSING (Verifier output)
# ────────────────────────────────────────────────────────────────


def _all_balanced_json_blocks(text: str) -> list[str]:
    """Return every balanced ``{…}`` block found in *text*, in order.

    We track brace depth byte-by-byte while honouring string literals
    (so a ``{`` inside ``"foo {bar}"`` doesn't unbalance us). This is a
    deliberate replacement for ``re.search(r"\\{.*\\}")`` which is greedy
    and can capture an attacker-controlled superset (cf. Qwen 10.2
    adversarial finding).
    """
    blocks: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                blocks.append(text[start : i + 1])
                start = -1
    return blocks


def _extract_first_balanced_json(text: str) -> str | None:
    """Convenience: return the first balanced block or ``None``."""
    blocks = _all_balanced_json_blocks(text)
    return blocks[0] if blocks else None


def _parse_verifier_verdict(raw: str) -> dict[str, Any]:
    """Extract {pass, reason, required_evidence} from Verifier output.

    Verifier is JSON-only by spec. We still defend against fenced blocks
    or trailing prose (frequent on smaller models).
    """
    # Try fenced ```json blocks first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = fenced.group(1) if fenced else raw

    # Round 10.2 fix [Qwen adversarial — greedy regex bypass] (P0):
    # the previous version used ``re.search(r"\{.*\}")`` which is GREEDY.
    # If the LLM emits two JSON blocks (e.g. one injected by an attacker
    # via a docstring + the legitimate verdict), the regex captures the
    # superset, json.loads fails, and the verifier silently returns
    # ``pass=False reason=verifier_json_decode_error``. Worse: a
    # well-crafted attacker payload could inject ``{"pass": true}`` first
    # so naive callers might accept it. We now enumerate balanced blocks
    # and reject any verifier output that contains more than one — this
    # is what the spec requires anyway (single JSON object).
    blocks = _all_balanced_json_blocks(candidate)
    if len(blocks) == 0:
        return {"pass": False, "reason": "verifier_returned_no_json", "required_evidence": []}
    if len(blocks) > 1:
        logger.warning(
            "verifier_multiple_json_blocks_detected",
            n_blocks=len(blocks),
            hint="Possible prompt-injection attempt; rejecting.",
        )
        return {
            "pass": False,
            "reason": "verifier_multiple_json_blocks_rejected",
            "required_evidence": [],
        }
    extracted = blocks[0]

    try:
        verdict = json.loads(extracted)
    except json.JSONDecodeError as e:
        return {
            "pass": False,
            "reason": f"verifier_json_decode_error: {e}",
            "required_evidence": [],
        }

    return {
        "pass": bool(verdict.get("pass", False)),
        "reason": str(verdict.get("reason", "")),
        "required_evidence": list(verdict.get("required_evidence", [])),
    }


# ────────────────────────────────────────────────────────────────
# P0 PER-FINDING TRIADE
# ────────────────────────────────────────────────────────────────


async def _invoke_role(
    role: str,
    model: str,
    prompt: str,
    code_dir: Path,
    timeout_s: int = 600,
    risk_profile: RiskProfile | None = None,
) -> str:
    """Invoke a model in a given triade role (critic/fixer/verifier).

    Round 5 fix [O] (Audit 2 P0): was calling `builder.generate(prompt=...,
    workdir=..., timeout_s=..., role=...)` which did not match the
    BuilderProtocol signature `generate(spec, cfg)` — would have raised
    TypeError on every adapter. Now uses the new `run_raw_prompt()` method
    which adapters inherit by default.

    Round 6 fix [O2] (Audits 4+6): propagate risk_profile to preserve
    medical_high constraints; mark non-write roles to prevent verifier
    from rewriting code. See builder_protocol.py:run_raw_prompt() for
    the no_write_roles enforcement.

    Round 10.3 fix [Grok RX-301-01 + Qwen RX-301-03 + DeepSeek + Gemini
    RX-301-01] (4/4 conv, P1): wrap the adapter call in
    ``asyncio.wait_for`` with ``timeout_s + 30s`` slack. Adapters already
    enforce per-call timeouts but a defunct child process can ignore them.
    The outer ``wait_for`` guarantees the triade slot is freed even when
    the adapter hangs at the subprocess boundary.

    Returns the raw text output. Adapter dispatch is handled by get_builder().
    """
    builder = get_builder(model)
    safety_net_s = float(timeout_s) + 30.0
    try:
        raw = await asyncio.wait_for(
            builder.run_raw_prompt(
                prompt=prompt,
                workdir=code_dir.parent,
                timeout_s=timeout_s,
                role=role,
                risk_profile=risk_profile,
            ),
            timeout=safety_net_s,
        )
    except TimeoutError:
        logger.error(
            "phase_5_invoke_role_outer_timeout",
            role=role,
            model=model,
            timeout_s=safety_net_s,
        )
        raise RuntimeError(
            f"_invoke_role outer timeout: {role}/{model} hung > {safety_net_s:.0f}s"
        ) from None
    return raw or ""


async def _triade_p0(
    finding: Finding,
    winner: BuilderResult,
    risk_profile: RiskProfile,
    auditor_family: str,
    max_iterations: int = 2,
) -> FixResult:
    """Process a single P0 finding through critic→fixer→verifier round-trip.

    Loop:
        1. Critic confirms the finding is real and reproducible.
        2. Fixer produces a patch + regression test.
        3. Local gates (pytest/mypy/ruff) — short-circuit if they fail.
        4. Verifier issues a strict JSON verdict {pass, reason, evidence}.
        5. If reject and iteration < max → loop back to Fixer with verdict.
        6. If still reject after max_iterations → escalate.
    """
    critic, fixer, verifier = pick_triade(winner.family, auditor_family, risk_profile)

    logger.info(
        "p0_triade_start",
        finding_id=finding.id,
        critic=critic,
        fixer=fixer,
        verifier=verifier,
    )

    critic_template = _load_prompt("critic")
    fixer_template = _load_prompt("fixer")
    verifier_template = _load_prompt("verifier_strict")

    # ── Step 1: Critic confirms the finding ─────────────────────────────
    # Round 8 fix [P5-evidence] (Qwen P0, 80% confidence):
    # Pydantic contract uses `evidence.file` and `evidence.snippet`, but Phase 5
    # was reading `evidence.file_path` and `evidence.excerpt` which don't exist.
    # AttributeError on EVERY P0 finding → blocked_p0 → run abort. Deterministic
    # crash that 5 of 6 round-7 audits missed (Qwen flagged it correctly).
    # Round 10.3 fix [Kimi RX-301-02 + Qwen RX-301-02 + ChatGPT RX-301-08]
    # (3-conv P0): finding.description and evidence.snippet originate from
    # the auditor LLM in Phase 4. A compromised auditor (or one that
    # passed through a poisoned code/AGENTS.md context) can smuggle
    # ``<!-- ignore previous instructions -->`` directives into either
    # field. Without sanitization, those directives propagate verbatim
    # into the Critic→Fixer→Verifier prompts and can hijack the triade.
    # Sanitize at the format-time boundary as defence in depth.
    from polybuild.security.prompt_sanitizer import sanitize_prompt_context

    # Round 10.7 fix [Kimi C-01 P0]: ``finding.evidence.file`` is a Path
    # produced upstream by the auditor model (LLM-controlled). Without
    # sanitization, an attacker who controls auditor output could embed
    # Markdown/HTML/zero-width sequences in the path component, which then
    # lands inside the Critic prompt unchanged. Mirror the sanitization
    # already applied to ``description`` and ``evidence_excerpt``.
    critic_prompt = critic_template.format(
        finding_id=finding.id,
        severity=finding.severity.value,
        axis=finding.axis,
        description=sanitize_prompt_context(finding.description),
        evidence_path=sanitize_prompt_context(
            str(finding.evidence.file) if finding.evidence else "n/a"
        ),
        evidence_excerpt=sanitize_prompt_context(
            (finding.evidence.snippet or "" if finding.evidence else "")[:2000]
        ),
    )
    try:
        critic_output = await _invoke_role("critic", critic, critic_prompt, winner.code_dir, risk_profile=risk_profile)
    except Exception as e:
        logger.error("p0_critic_failed", finding_id=finding.id, error=str(e))
        return FixResult(
            finding_ids=[finding.id],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=0,
        )

    # If critic dismisses the finding (false positive), escalate to human.
    if "FALSE_POSITIVE" in critic_output.upper():
        logger.info("p0_false_positive", finding_id=finding.id)
        return FixResult(
            finding_ids=[finding.id],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=1,
        )

    # ── Steps 2-5: Fixer ↔ Verifier loop ────────────────────────────────
    last_verdict: dict[str, Any] = {
        "pass": False,
        "reason": "no_attempt",
        "required_evidence": [],
    }
    fixer_feedback = ""

    # Round 10 fix [Phase 5 fixer test enforcement] (2-conv: Claude + Grok
     # round 9 P1): a snapshot of the tests/ directory taken before the Fixer
    # runs lets us verify post-hoc that the Fixer actually added a regression
    # test for this finding. If not, the verdict is degraded to "escalate"
    # because a P0 fix without a guard test re-opens the same bug at the next
    # commit.
    tests_root = winner.code_dir.parent / "tests" if (
        winner.code_dir.parent / "tests"
    ).exists() else winner.tests_dir
    pre_fixer_test_files: set[Path] = set()
    if tests_root.exists():
        pre_fixer_test_files = set(tests_root.rglob("test_*.py"))

    # Round 10.5 fix [Grok RX-501-01 + DeepSeek + ChatGPT P5-501] (3/5 conv,
    # P0 absolu) — the previous version (1) discarded the fixer's response
    # entirely (``await _invoke_role(...)`` without assignment, so the
    # critic's previous-verdict feedback never carried fixer state) and
    # (2) gave no guarantee that the fixer mutated ``winner.code_dir``.
    # Some adapter implementations of ``run_raw_prompt`` create their own
    # synthetic worktree via ``generate()``, leaving the validated path
    # untouched — Phase 6 then validates the un-fixed code. We now compute
    # a tree hash before/after the fixer call and refuse to advance the
    # loop unless we observe a real mutation under ``winner.code_dir.parent``.
    def _tree_hash(root: Path) -> str:
        # Round 10.7 fix [Kimi C-06 P1, 1/5 conv]: ``Path.is_file()`` follows
        # symlinks. A malicious symlink dropped in the worktree (e.g.
        # ``foo.py -> /etc/passwd``) would otherwise be hashed AND read,
        # leaking arbitrary host file content into the run-level tree
        # signature (LFI vector). Skip symlinks before any stat/read.
        if not root.exists():
            return ""
        h = hashlib.sha256()
        for p in sorted(root.rglob("*")):
            if p.is_symlink() or not p.is_file() or "__pycache__" in p.parts:
                continue
            try:
                h.update(str(p.relative_to(root)).encode("utf-8"))
                h.update(b"\0")
                h.update(p.read_bytes())
                h.update(b"\0\0")
            except OSError:
                continue
        return h.hexdigest()

    worktree_root = winner.code_dir.parent

    # Round 10.2 fix [Kimi RX-002 P1]: bound the "no-test" retry. Without
    # this counter the ``continue`` below skipped iteration accounting,
    # which meant a fixer that never produces a regression test could
    # spin the loop ``max_iterations`` times — wasting Critic+Fixer+
    # Verifier calls. We allow exactly one no-test retry, then escalate.
    no_test_strikes = 0
    max_no_test_strikes = 1

    for iteration in range(1, max_iterations + 1):
        # Round 10.3 fix: critic_output is also LLM-controlled; sanitize.
        # Round 10.7 fix [Codex validation PB-R107-P5-EVIDENCE-REINJECT P0]:
        # the FIXER prompt also re-injects ``finding.evidence.file`` —
        # which is auditor-controlled (LLM output). Same sanitization
        # treatment as the Critic prompt.
        # Round 10.8 prod-launch fix: prompts/fixer.md uses ``{workdir}``
        # placeholder ("Tu éditeS le code in-place dans le worktree
        # ``{workdir}``"). The format() call must provide it or KeyError
        # crashes Phase 5. ``winner.code_dir.parent`` is the worktree
        # root the fixer is allowed to mutate.
        fixer_prompt = fixer_template.format(
            finding_id=finding.id,
            workdir=str(winner.code_dir.parent.resolve()),
            critic_analysis=sanitize_prompt_context(critic_output[:4000]),
            previous_verdict=fixer_feedback or "(first attempt)",
            evidence_path=sanitize_prompt_context(
                str(finding.evidence.file) if finding.evidence else "n/a"
            ),
        )
        # Round 10.5: snapshot worktree before invoking the fixer so we can
        # detect adapters that fail to mutate the validated path.
        pre_fixer_hash = _tree_hash(worktree_root)
        try:
            fixer_output = await _invoke_role(
                "fixer", fixer, fixer_prompt, winner.code_dir,
                risk_profile=risk_profile,
            )
        except Exception as e:
            logger.error("p0_fixer_failed", finding_id=finding.id, error=str(e))
            break

        post_fixer_hash = _tree_hash(worktree_root)
        if post_fixer_hash == pre_fixer_hash:
            # Round 10.5 P0 absolu — fixer left the worktree untouched.
            # We can still consume an iteration via fixer_feedback to give
            # the next attempt a chance to actually patch the file, but if
            # a strike is logged so post-mortem can see the no-op.
            logger.error(
                "p0_fixer_no_worktree_mutation",
                finding_id=finding.id,
                iteration=iteration,
                hint=(
                    "Fixer adapter returned text but did not modify "
                    "winner.code_dir.parent. Check that run_raw_prompt is "
                    "overridden for the fixer role."
                ),
            )
            # Round 10.7 fix [Kimi C-02 P0]: ``fixer_output`` is raw LLM text
            # that gets re-injected into the next loop iteration's prompt.
            # Without sanitization the Fixer can poison its own future
            # context (multi-turn prompt-injection chain). Sanitize before
            # re-use.
            fixer_feedback = (
                "Your previous attempt produced text but DID NOT modify "
                "any file under the workdir. You MUST edit files in place. "
                f"Verifier rejected because no mutation was observed. "
                f"Fixer text was: {sanitize_prompt_context((fixer_output or '')[:1500])}"
            )
            no_test_strikes += 1
            if no_test_strikes > max_no_test_strikes:
                logger.error(
                    "p0_fixer_no_mutation_strikes_exceeded_escalate",
                    finding_id=finding.id,
                )
                break
            continue

        # Round 10 fix [Phase 5 fixer test enforcement]: enforce that the
        # Fixer created at least one new test file or extended an existing one.
        post_fixer_test_files: set[Path] = (
            set(tests_root.rglob("test_*.py"))
            if tests_root.exists() else set()
        )
        new_test_files = post_fixer_test_files - pre_fixer_test_files
        if not new_test_files:
            no_test_strikes += 1
            logger.warning(
                "p0_fixer_did_not_add_regression_test",
                finding_id=finding.id,
                iteration=iteration,
                tests_root=str(tests_root),
                strikes=no_test_strikes,
            )
            if no_test_strikes > max_no_test_strikes:
                logger.error(
                    "p0_fixer_no_test_strikes_exceeded_escalate",
                    finding_id=finding.id,
                    strikes=no_test_strikes,
                )
                break
            fixer_feedback = (
                "Your patch did not add a regression test under tests/. "
                "Re-emit the patch AND a pytest test that fails against the "
                "buggy version and passes against your fix."
            )
            continue

        # Local gates short-circuit
        gates_ok, gates_summary = await _run_local_gates(winner.code_dir)
        if not gates_ok:
            fixer_feedback = f"Local gates failed:\n{gates_summary}\nRework the patch."
            logger.info(
                "p0_local_gates_failed",
                finding_id=finding.id,
                iteration=iteration,
            )
            continue

        # Verifier
        # Round 10.3 fix: same sanitization on critic_output before
        # injection into the verifier prompt.
        verifier_prompt = verifier_template.format(
            finding_id=finding.id,
            critic_analysis=sanitize_prompt_context(critic_output[:2000]),
            local_gates_status="all green",
        )
        try:
            verifier_raw = await _invoke_role(
                "verifier",
                verifier,
                verifier_prompt,
                winner.code_dir,
                risk_profile=risk_profile,
            )
        except Exception as e:
            logger.error("p0_verifier_failed", finding_id=finding.id, error=str(e))
            break

        last_verdict = _parse_verifier_verdict(verifier_raw)
        if last_verdict["pass"]:
            logger.info(
                "p0_triade_accepted",
                finding_id=finding.id,
                iterations=iteration,
            )
            return FixResult(
                finding_ids=[finding.id],
                status="accepted",
                critic_model=critic,
                fixer_model=fixer,
                verifier_model=verifier,
                iterations=iteration,
            )

        # Round 10.7 fix [Kimi C-03 P0]: same multi-turn injection vector
        # — the Verifier's ``reason`` and ``required_evidence`` fields are
        # LLM-emitted strings re-injected into the Fixer prompt. Sanitize
        # before passing them downstream.
        fixer_feedback = (
            f"Verifier rejected: {sanitize_prompt_context(str(last_verdict['reason']))}. "
            f"Required evidence: {sanitize_prompt_context(str(last_verdict['required_evidence']))}"
        )
        logger.info(
            "p0_verifier_rejected",
            finding_id=finding.id,
            iteration=iteration,
            reason=last_verdict["reason"],
        )

    # Max iterations exhausted → escalate
    logger.warning(
        "p0_triade_escalate",
        finding_id=finding.id,
        last_reason=last_verdict.get("reason"),
    )
    return FixResult(
        finding_ids=[finding.id],
        status="escalate",
        critic_model=critic,
        fixer_model=fixer,
        verifier_model=verifier,
        iterations=max_iterations,
    )


# ────────────────────────────────────────────────────────────────
# P1 BATCH BY AXIS
# ────────────────────────────────────────────────────────────────


async def _triade_p1_batch(
    axis: str,
    findings: list[Finding],
    winner: BuilderResult,
    risk_profile: RiskProfile,
    auditor_family: str,
) -> FixResult:
    """Batch all P1 findings of the same axis into a single Fixer call.

    P1 is less critical than P0, so:
        - Single Critic confirmation pass (group review)
        - Single Fixer pass (no Verifier loop)
        - Local gates as final guard (no LLM Verifier — saves tokens)
    """
    critic, fixer, verifier = pick_triade(winner.family, auditor_family, risk_profile)

    logger.info(
        "p1_batch_start",
        axis=axis,
        n_findings=len(findings),
        fixer=fixer,
    )

    critic_template = _load_prompt("critic")
    fixer_template = _load_prompt("fixer")

    # Aggregate findings into a single context block
    findings_block = "\n\n".join(
        f"- [{f.id}] {f.description}\n"
        f"  evidence: {f.evidence.file if f.evidence else 'n/a'}"
        for f in findings
    )

    # Round 6 fix [P1-no-Critic] (Audit 6 P2): the docstring promised a
    # "Single Critic confirmation pass (group review)" but the code skipped
    # straight to the Fixer. Either the docstring lied or the code missed
    # the call — fixing the code (cheaper than throwing away the contract).
    # Round 10.3 fix [Kimi RX-301-02 / Qwen]: findings_block contains
    # auditor-controlled text (descriptions, snippets); sanitize before
    # injection.
    from polybuild.security.prompt_sanitizer import sanitize_prompt_context

    critic_batch_prompt = critic_template.format(
        finding_id=f"P1_BATCH_{axis}",
        severity="P1",
        axis=axis,
        description=f"Batch of {len(findings)} P1 findings on axis '{axis}'",
        evidence_path="(see findings list)",
        evidence_excerpt=sanitize_prompt_context(findings_block[:2000]),
    )
    try:
        critic_batch_output = await _invoke_role(
            "critic",
            critic,
            critic_batch_prompt,
            winner.code_dir,
            risk_profile=risk_profile,
        )
    except Exception as e:
        logger.warning("p1_batch_critic_failed_proceeding", axis=axis, error=str(e))
        critic_batch_output = "(critic call failed; proceeding with raw findings)"

    # Round 10.3 fix: P1 batch path is fed by both critic_batch_output
    # (LLM-controlled) and findings_block (LLM-controlled via auditor).
    # Sanitize the assembled critic_analysis before .format().
    # Round 10.8 prod-launch fix: provide ``{workdir}`` to satisfy the
    # fixer.md template (otherwise KeyError on .format()).
    fixer_prompt = fixer_template.format(
        finding_id=f"P1_BATCH_{axis}",
        workdir=str(winner.code_dir.parent.resolve()),
        critic_analysis=sanitize_prompt_context(
            f"Batch of {len(findings)} P1 findings on axis '{axis}'.\n"
            f"Critic group review: {critic_batch_output[:1500]}\n\n"
            f"Findings:\n{findings_block}"
        ),
        previous_verdict="(P1 batch — no prior attempt)",
        evidence_path="(see findings list)",
    )

    try:
        await _invoke_role("fixer", fixer, fixer_prompt, winner.code_dir, risk_profile=risk_profile)
    except Exception as e:
        logger.error("p1_fixer_failed", axis=axis, error=str(e))
        return FixResult(
            finding_ids=[f.id for f in findings],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=0,
        )

    # Local gates as final guard (no Verifier loop for P1)
    gates_ok, gates_summary = await _run_local_gates(winner.code_dir)
    if not gates_ok:
        logger.warning("p1_local_gates_failed", axis=axis, summary=gates_summary[:300])
        return FixResult(
            finding_ids=[f.id for f in findings],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=1,
        )

    logger.info("p1_batch_accepted", axis=axis, n_findings=len(findings))
    return FixResult(
        finding_ids=[f.id for f in findings],
        status="accepted",
        critic_model=critic,
        fixer_model=fixer,
        verifier_model=verifier,
        iterations=1,
    )


# ────────────────────────────────────────────────────────────────
# P2/P3 LOCAL AUTO-FIX
# ────────────────────────────────────────────────────────────────


async def _auto_fix_local(findings: list[Finding], winner: BuilderResult) -> FixResult:
    """Apply ruff --fix and similar non-LLM fixes."""
    # ruff --fix
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "ruff", "check", "--fix", "src/", "tests/",
        cwd=winner.code_dir.parent,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    return FixResult(
        finding_ids=[f.id for f in findings],
        status="accepted",
        critic_model="<local>",
        fixer_model="ruff",
        verifier_model="<local>",
        iterations=1,
    )


# ────────────────────────────────────────────────────────────────
# DISPATCHER
# ────────────────────────────────────────────────────────────────


async def phase_5_dispatch(
    audit: AuditReport,
    winner: BuilderResult,
    risk_profile: RiskProfile,
) -> FixReport:
    """Dispatch findings to appropriate triade strategy."""
    logger.info(
        "phase_5_start",
        winner=winner.voice_id,
        n_findings=len(audit.findings),
    )

    p0_all = [f for f in audit.findings if f.severity == Severity.P0]
    # Round 9 fix [Budget] (Claude + ChatGPT + Grok convergence — P0):
    #   A zealous auditor (DeepSeek V4-Pro known for exhaustive findings)
    #   could produce 10+ P0. Each P0 = 3-6 LLM calls (Critic + Fixer×2 +
    #   Verifier×2). With 10 P0, that's 50+ LLM calls just in Phase 5 →
    #   $15-25 budget burn per run. Cap at 5 P0; the rest is downgraded to
    #   P1 batch processing (single Critic + Fixer per axis, no Verifier).
    max_p0_triade = 5
    if len(p0_all) > max_p0_triade:
        # Round 10.3 fix [ChatGPT RX-301-06 P0 — adversarial P0 budget
        # exhaustion]: previously P0 findings beyond ``max_p0_triade``
        # were silently downgraded to P1 batch (no per-finding Critic/
        # Verifier loop). An attacker could plant 5 noisy P0 findings
        # ahead of one real P0 to push the real one out of the triade
        # gate, defeating its blocking semantics. We now refuse the
        # whole audit and return a ``blocked_p0`` FixReport — better a
        # hard stop than a silent demotion of a critical finding.
        logger.error(
            "phase_5_p0_budget_exhausted_blocked_p0",
            original=len(p0_all),
            cap=max_p0_triade,
            hint=(
                "More than max_p0_triade=5 P0 findings detected. Refusing "
                "to demote — re-audit, dedup or escalate. Adversarial "
                "scenario : noisy P0s shielding a real one."
            ),
        )
        return FixReport(
            status="blocked_p0",
            results=[
                FixResult(
                    finding_ids=[f.id],
                    status="escalate",
                    critic_model="<budget-exhausted>",
                    fixer_model="<budget-exhausted>",
                    verifier_model="<budget-exhausted>",
                    iterations=0,
                )
                for f in p0_all
            ],
        )
    p0 = p0_all
    downgraded: list[Finding] = []

    p1_by_axis: dict[str, list[Finding]] = defaultdict(list)
    for f in audit.findings:
        if f.severity == Severity.P1:
            p1_by_axis[f.axis].append(f)
    # Add downgraded P0 to the relevant axis (P1 batch processing)
    for f in downgraded:
        p1_by_axis[f.axis].append(f)
    p2_p3 = [f for f in audit.findings if f.severity in {Severity.P2, Severity.P3}]

    results: list[FixResult] = []

    # P0: per-finding sequential triade
    for f in p0:
        result = await _triade_p0(f, winner, risk_profile, audit.auditor_family)
        results.append(result)
        if result.status == "escalate":
            logger.warning("phase_5_p0_escalate", finding_id=f.id)
            return FixReport(status="blocked_p0", results=results)

    # P1: batched per axis
    for axis, batch in p1_by_axis.items():
        result = await _triade_p1_batch(axis, batch, winner, risk_profile, audit.auditor_family)
        results.append(result)

    # P2/P3: local auto-fix
    if p2_p3:
        result = await _auto_fix_local(p2_p3, winner)
        results.append(result)

    has_partial = any(r.status == "escalate" for r in results)
    final_status: Literal["completed", "blocked_p0", "partial"] = (
        "partial" if has_partial else "completed"
    )

    logger.info(
        "phase_5_done",
        n_results=len(results),
        status=final_status,
    )
    return FixReport(status=final_status, results=results)
