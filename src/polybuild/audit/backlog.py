"""Audit backlog — accumulated findings + dedup (M2C.0 / M2C.3).

Backlog file: ``~/.polybuild/audit/audit_backlog.jsonl``. One line per
finding. Persisted under the same exclusive lock as the queue (callers
should hold ``QueueLock`` for the duration of any append/read cycle).

Findings are deduped by ``fingerprint`` — a deterministic hash over
``(commit_sha, file, line, axis, normalized_message)``. Repeat findings
within a 7-day rolling window are dropped at append time so the user
is not paged twice for the same issue.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polybuild.audit.queue import QueueLock, audit_dir, lock_path

DEDUP_WINDOW_DAYS = 7


def backlog_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "audit_backlog.jsonl"


# Severity literals mirror POLYLENS conventions (cf.
# ``feedback_polylens_method.md``). We do NOT reuse
# ``polybuild.models.Severity`` here because the audit subsystem must
# stay a leaf module that is safe to import in any context (no
# pydantic-strict transitive deps).
Severity = Literal["P0", "P1", "P2", "P3"]
Axis = Literal[
    "A_security",
    "B_quality",
    "C_tests",
    "D_performance",
    "E_architecture",
    "F_documentation",
    "G_adversarial",
]


class BacklogFinding(BaseModel):
    """One audit finding persisted in the backlog.

    The schema is closed (``extra="forbid"``) so a future POLYLENS run
    cannot accidentally introduce ``_other`` keys (anti-pattern #15).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    fingerprint: str = Field(min_length=16, max_length=64)
    commit_sha: str
    file: str  # repo-relative path
    line: int | None = None
    axis: Axis
    severity: Severity
    message: str
    voice: str  # voice_id of the auditor that produced the finding
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def _normalize_message(message: str) -> str:
    """Lowercase + collapse whitespace + strip surrounding line refs.

    Two voices that report the same issue rarely use the exact same
    wording. Normalising before hashing makes ``fingerprint`` survive
    minor phrasing differences without merging genuinely distinct
    findings (the ``axis`` + ``file`` + ``line`` channel keeps them
    separate).
    """
    text = message.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"line\s+\d+\s*[:.]?\s*", "", text)
    return text[:500]  # bounded length to avoid pathological inputs


def compute_fingerprint(
    commit_sha: str,
    file: str,
    line: int | None,
    axis: str,
    message: str,
) -> str:
    """SHA-256-based fingerprint over the canonical finding identity."""
    h = hashlib.sha256()
    h.update(commit_sha.encode("utf-8"))
    h.update(b"\x00")
    h.update(file.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(line if line is not None else "").encode("utf-8"))
    h.update(b"\x00")
    h.update(axis.encode("utf-8"))
    h.update(b"\x00")
    h.update(_normalize_message(message).encode("utf-8"))
    return h.hexdigest()[:32]


def append_findings(
    findings: list[BacklogFinding],
    backlog_dir: Path | None = None,
    *,
    dedup_window: timedelta | None = None,
) -> tuple[int, int]:
    """Append unique findings to the backlog under exclusive lock.

    Returns a ``(written, deduped)`` tuple so callers can log how many
    duplicates were suppressed.

    Dedup window defaults to :data:`DEDUP_WINDOW_DAYS` days.
    """
    if not findings:
        return (0, 0)

    window = dedup_window or timedelta(days=DEDUP_WINDOW_DAYS)
    bpath = backlog_path(backlog_dir)
    cutoff = datetime.now(UTC) - window

    written = 0
    deduped = 0
    with QueueLock(lock_path(backlog_dir)):
        existing_fingerprints = _recent_fingerprints(bpath, cutoff)
        with bpath.open("a", encoding="utf-8") as fh:
            for f in findings:
                if f.fingerprint in existing_fingerprints:
                    deduped += 1
                    continue
                fh.write(f.model_dump_json() + "\n")
                existing_fingerprints.add(f.fingerprint)
                written += 1
    return (written, deduped)


def _recent_fingerprints(bpath: Path, cutoff: datetime) -> set[str]:
    """Return the set of fingerprints seen since ``cutoff``.

    Skips malformed JSONL lines silently — a corrupted line from a
    crashed writer should not break dedup for the rest.
    """
    if not bpath.exists():
        return set()
    out: set[str] = set()
    for line in bpath.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = BacklogFinding.model_validate_json(line)
        except ValueError:
            continue
        if entry.discovered_at >= cutoff:
            out.add(entry.fingerprint)
    return out


def read_backlog(
    backlog_dir: Path | None = None,
    *,
    severity: Severity | None = None,
    since: datetime | None = None,
) -> list[BacklogFinding]:
    """Return the backlog contents (newest first).

    Optional filters:
      severity: keep only findings of this severity.
      since: keep only findings discovered after this timestamp.
    """
    bpath = backlog_path(backlog_dir)
    if not bpath.exists():
        return []

    out: list[BacklogFinding] = []
    with QueueLock(lock_path(backlog_dir), shared=True):
        for line in bpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = BacklogFinding.model_validate_json(line)
            except ValueError:
                continue
            if severity is not None and entry.severity != severity:
                continue
            if since is not None and entry.discovered_at < since:
                continue
            out.append(entry)

    out.sort(key=lambda f: f.discovered_at, reverse=True)
    return out


__all__ = [
    "DEDUP_WINDOW_DAYS",
    "Axis",
    "BacklogFinding",
    "Severity",
    "append_findings",
    "backlog_path",
    "compute_fingerprint",
    "read_backlog",
]
