"""POLYBUILD audit subsystem (M2C) — async POLYLENS hook on every commit.

The audit subsystem is **opt-in**: ``polybuild`` runs do not trigger any
audit by default. Enabling it requires either:

  * installing the post-commit git hook explicitly via
    ``scripts/install_audit_hook.sh`` (M2C.4), or
  * running ``polybuild audit drain`` manually (M2C.1).

The hook is **never blocking**: the post-commit script schedules a
detached process and returns immediately. A failed audit voice (timeout,
quota exhausted, network error) is silently dropped per voice — the
audit itself never stops a commit, push or merge.

## Module layout

  * ``polybuild.audit.queue``    — pending-commit queue (JSONL append + flock)
  * ``polybuild.audit.backlog``  — accumulated findings (JSONL + dedup)
  * ``polybuild.audit.rotation`` — round-robin voice picker (1 W + 1 CN)
  * ``polybuild.audit.runner``   — actual audit execution (Phase 2, M2C.2)
  * ``polybuild.audit.notifier`` — P0/P1 immediate notifications (M2C.3)
  * ``polybuild.audit.cli``      — ``polybuild audit {drain,status,...}``

POLYLENS anti-patterns guarded:

  * **#15 _other inflation** — the finding schema is a strict Pydantic
    model; freeform ``_other`` keys are rejected.
  * **#20 monoculture** — every audit run picks 1 Western + 1 Chinese
    voice via ``rotation`` (cf. ``feedback_polylens_method.md`` §1.4).
  * **#21 P0 sans cross-cultural** — handled by #20 (the rotation
    guarantees CDS=1.0 on every run).
  * **#23 voice substitution outside pool** — the pool is hard-coded
    here; users cannot override it via the CLI.
"""

from __future__ import annotations

from polybuild.audit.backlog import (
    BacklogFinding as BacklogFinding,
)
from polybuild.audit.backlog import (
    append_findings as append_findings,
)
from polybuild.audit.backlog import (
    compute_fingerprint as compute_fingerprint,
)
from polybuild.audit.backlog import (
    read_backlog as read_backlog,
)
from polybuild.audit.notifier import (
    build_digest as build_digest,
)
from polybuild.audit.notifier import (
    notify_findings as notify_findings,
)
from polybuild.audit.queue import (
    AuditQueueEntry as AuditQueueEntry,
)
from polybuild.audit.queue import (
    QueueLock as QueueLock,
)
from polybuild.audit.queue import (
    append_queue_entry as append_queue_entry,
)
from polybuild.audit.queue import (
    drain_queue as drain_queue,
)
from polybuild.audit.queue import (
    mark_entry_processed as mark_entry_processed,
)
from polybuild.audit.queue import (
    read_queue as read_queue,
)
from polybuild.audit.rotation import (
    VoicePair as VoicePair,
)
from polybuild.audit.rotation import (
    pick_voice_pair as pick_voice_pair,
)
from polybuild.audit.rotation import (
    reset_rotation as reset_rotation,
)
from polybuild.audit.runner import (
    DEFAULT_AXES as DEFAULT_AXES,
)
from polybuild.audit.runner import (
    VoiceCaller as VoiceCaller,
)
from polybuild.audit.runner import (
    audit_commit as audit_commit,
)
from polybuild.audit.runner import (
    extract_commit_diff as extract_commit_diff,
)

__all__ = [
    "DEFAULT_AXES",
    "AuditQueueEntry",
    "BacklogFinding",
    "QueueLock",
    "VoiceCaller",
    "VoicePair",
    "append_findings",
    "append_queue_entry",
    "audit_commit",
    "build_digest",
    "compute_fingerprint",
    "drain_queue",
    "extract_commit_diff",
    "mark_entry_processed",
    "notify_findings",
    "pick_voice_pair",
    "read_backlog",
    "read_queue",
    "reset_rotation",
]
