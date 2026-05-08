"""Audit notifier — P0/P1 immediate alerts + daily digest (M2C.3).

The runner returns a flat list of :class:`BacklogFinding`. The notifier
splits them by severity:

  * **P0 / P1** — always page the user immediately. macOS:
    ``osascript`` desktop banner; everywhere else: stderr line. The
    backlog still records the finding so the digest can show it later.
  * **P2 / P3** — silently appended to the backlog; the user sees them
    at the next ``polybuild audit digest`` invocation.

Dedup is enforced by :mod:`polybuild.audit.backlog` (7-day rolling
fingerprint window), so reruns of the same flaky audit do not page the
user twice.

The macOS ``osascript`` call is best-effort: any failure (no GUI
session, TCC denial, escape-character issues) falls back silently to
stderr — anti-pattern: a notifier that itself crashes the audit is a
worse outcome than a missed banner.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import structlog

from polybuild.audit.backlog import (
    BacklogFinding,
    Severity,
    append_findings,
    read_backlog,
)

logger = structlog.get_logger()


_NOTIFY_SEVERITIES: frozenset[Severity] = frozenset({"P0", "P1"})


def _send_macos_banner(title: str, message: str) -> bool:
    """Best-effort macOS desktop notification via ``osascript``.

    Returns ``True`` if the command exited 0, ``False`` otherwise. Any
    OSError / TimeoutExpired is swallowed silently — the notifier never
    fails the audit pipeline.
    """
    if sys.platform != "darwin":
        return False
    osascript = shutil.which("osascript")
    if osascript is None:
        return False
    # Escape double-quotes so AppleScript doesn't break out of the
    # ``display notification`` literal. AppleScript uses backslash for
    # escaping inside double-quoted strings.
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')[:480]
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')[:120]
    script = f'display notification "{safe_message}" with title "{safe_title}"'
    try:
        rc = subprocess.run(  # noqa: S603 — args list, binary resolved
            [osascript, "-e", script],
            capture_output=True,
            check=False,
            timeout=3,
        ).returncode
    except (OSError, subprocess.TimeoutExpired):
        return False
    return rc == 0


def _emit_stderr(finding: BacklogFinding) -> None:
    """Single-line stderr alert. Always works, no dependency."""
    location = finding.file
    if finding.line is not None:
        location = f"{location}:{finding.line}"
    sys.stderr.write(
        f"[POLYLENS {finding.severity}][{finding.axis}] {location} "
        f"({finding.voice}) — {finding.message}\n"
    )
    sys.stderr.flush()


def notify_findings(
    findings: Iterable[BacklogFinding],
    *,
    backlog_dir: Path | None = None,
    persist: bool = True,
) -> dict[Severity, int]:
    """Route findings to the right surface (banner + backlog) and return counts.

    Args:
        findings: as produced by :func:`audit_commit`.
        backlog_dir: override for the backlog directory (tests pass a
            tmp path).
        persist: when ``False``, skip the backlog append (used by
            ``polybuild audit dry-run`` so a test invocation never
            pollutes the real backlog).

    Returns:
        A ``{severity: count}`` mapping for the user-visible alerts.
    """
    findings_list = list(findings)
    counts: dict[Severity, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    notify_buffer: list[BacklogFinding] = []
    persist_buffer: list[BacklogFinding] = []

    for f in findings_list:
        counts[f.severity] += 1
        if f.severity in _NOTIFY_SEVERITIES:
            notify_buffer.append(f)
        persist_buffer.append(f)

    if persist and persist_buffer:
        with contextlib.suppress(OSError):
            written, deduped = append_findings(persist_buffer, backlog_dir=backlog_dir)
            logger.info(
                "audit_backlog_appended",
                written=written,
                deduped=deduped,
            )

    for f in notify_buffer:
        location = f.file if f.line is None else f"{f.file}:{f.line}"
        title = f"POLYLENS {f.severity}: {f.axis}"
        message = f"{location} ({f.voice}) — {f.message}"
        banner_ok = _send_macos_banner(title=title, message=message)
        if not banner_ok:
            _emit_stderr(f)

    return counts


# ────────────────────────────────────────────────────────────────
# DIGEST — periodic summary of P2/P3 backlog
# ────────────────────────────────────────────────────────────────


DigestWindow = Literal["yesterday", "week", "month"]


def _window_to_cutoff(window: DigestWindow) -> datetime:
    now = datetime.now(UTC)
    if window == "yesterday":
        return now - timedelta(days=1)
    if window == "week":
        return now - timedelta(days=7)
    return now - timedelta(days=30)


def build_digest(
    *,
    since: DigestWindow = "yesterday",
    backlog_dir: Path | None = None,
) -> str:
    """Build a plain-text digest of the backlog from ``since`` onwards.

    Returns a multi-line string suitable for ``print()`` or piping to
    ``mail``. Empty (zero findings in the window) returns the exact
    string ``"no findings in window"`` so the caller can short-circuit.
    """
    cutoff = _window_to_cutoff(since)
    findings = read_backlog(backlog_dir=backlog_dir, since=cutoff)
    if not findings:
        return "no findings in window"

    by_severity: dict[Severity, list[BacklogFinding]] = {
        "P0": [],
        "P1": [],
        "P2": [],
        "P3": [],
    }
    for f in findings:
        by_severity[f.severity].append(f)

    lines: list[str] = [
        f"# POLYLENS audit digest (since {since}, "
        f"window cutoff {cutoff.isoformat()})",
        "",
        f"Total findings: {len(findings)}",
        f"  P0: {len(by_severity['P0'])} | P1: {len(by_severity['P1'])} "
        f"| P2: {len(by_severity['P2'])} | P3: {len(by_severity['P3'])}",
        "",
    ]
    severities: tuple[Severity, ...] = ("P0", "P1", "P2", "P3")
    for sev in severities:
        bucket = by_severity[sev]
        if not bucket:
            continue
        lines.append(f"## {sev} ({len(bucket)})")
        for f in bucket:
            location = f.file if f.line is None else f"{f.file}:{f.line}"
            ts = f.discovered_at.strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"- [{f.axis}] {location} ({f.voice}, {ts}) — {f.message}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "DigestWindow",
    "build_digest",
    "notify_findings",
]
