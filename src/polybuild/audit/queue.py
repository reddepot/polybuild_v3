"""Audit queue + lock — pending commits to audit (M2C.0).

The queue is a simple JSONL file at ``~/.polybuild/audit_queue.jsonl``.
Each line is one :class:`AuditQueueEntry`. The post-commit git hook
appends an entry as soon as a commit lands; ``polybuild audit drain``
consumes them one by one. A user can also enqueue manually:

    >>> append_queue_entry(AuditQueueEntry(commit_sha="...", repo_path="..."))

## Concurrency model

Two processes can race here: the post-commit hook (single-threaded per
commit, but multiple commits can land in quick succession on the same
or sibling branches) and ``polybuild audit drain`` (consumes the queue
in a tight loop). We acquire an exclusive ``fcntl.flock`` on a
sentinel file (``~/.polybuild/audit.lock``) for any read-modify-write
operation. ``flock`` is per-file-descriptor on macOS / Linux and
auto-releases on process exit, so a crashed drain never wedges the queue.

The lock is **per-file**, not per-entry. We accept this trade-off: the
queue is small (hundreds of entries at most before a drain) and lock
contention is bounded by the speed of file I/O.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Literal

from pydantic import BaseModel, ConfigDict, Field

from polybuild.audit._atomic_io import atomic_write_text

# Default base directory ─ user-overridable via env for tests / multi-user
# machines. ``~/.polybuild/audit/`` keeps the audit artefacts isolated
# from runtime checkpoints which live under ``<project>/.polybuild/``.
DEFAULT_AUDIT_DIR = Path.home() / ".polybuild" / "audit"


def audit_dir(override: Path | None = None) -> Path:
    """Resolve the audit base directory.

    Resolution order:
      1. ``override`` argument (explicit, used by tests).
      2. ``POLYBUILD_AUDIT_DIR`` environment variable.
      3. ``~/.polybuild/audit/``.

    The directory is created lazily (mode 0700) so first-time use after
    install does not require manual setup.

    POLYLENS-FIX-8 P1: ``Path.mkdir(mode=0o700)`` only applies the mode
    to a freshly created directory. If the directory already existed
    (e.g. user ran an older polybuild that created it 0o755), the mode
    bits stayed permissive. We unconditionally chmod the resolved path
    to 0o700 so a re-run normalises the permissions.
    """
    if override is not None:
        target = override
    else:
        env = os.environ.get("POLYBUILD_AUDIT_DIR")
        target = Path(env) if env else DEFAULT_AUDIT_DIR
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Force-tighten if the directory pre-existed with looser perms.
    # Best-effort: any OSError (e.g. directory belongs to a different
    # user, read-only filesystem) is swallowed — the audit pipeline
    # never blocks on cosmetic perm issues.
    with contextlib.suppress(OSError):
        target.chmod(0o700)
    return target


def queue_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "audit_queue.jsonl"


def lock_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "audit.lock"


class AuditQueueEntry(BaseModel):
    """One pending audit job — a commit waiting to be reviewed.

    Fields are intentionally narrow; the runner pulls extra context
    (diff, file list, voice rotation state) from the repo and the
    rotation file at drain time. Storing the diff inline would explode
    the queue size for large commits.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    commit_sha: str = Field(min_length=7, max_length=64)
    repo_path: Path
    branch: str | None = None
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["pending"] = "pending"


class QueueLock:
    """Context manager wrapping :func:`fcntl.flock`.

    Usage::

        with QueueLock():
            # Inside the lock — safe to read+modify the queue file.
            ...

    Pass ``shared=True`` for read-only operations to allow concurrent
    drain readers; pass ``shared=False`` (default) for any write or
    drain-and-truncate.

    Acquisition is **blocking** by default. Pass ``timeout_s`` to fail
    fast: a runner that cannot acquire the lock in N seconds raises
    ``TimeoutError`` and the caller can decide to skip this drain
    cycle rather than queue up.
    """

    def __init__(
        self,
        path: Path | None = None,
        shared: bool = False,
        timeout_s: float | None = None,
    ) -> None:
        self.path = path or lock_path()
        self.shared = shared
        self.timeout_s = timeout_s
        self._fd: IO[bytes] | None = None

    def __enter__(self) -> QueueLock:
        # Ensure the directory exists (the lock file is itself a sentinel).
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._fd = self.path.open("ab+")
        flags = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
        if self.timeout_s is not None:
            self._acquire_with_timeout(flags)
        else:
            fcntl.flock(self._fd.fileno(), flags)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._fd is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None

    def _acquire_with_timeout(self, flags: int) -> None:
        """Non-blocking acquire poll until ``timeout_s`` elapses."""
        import time

        if self._fd is None:  # pragma: no cover — set in __enter__
            raise RuntimeError("QueueLock fd not initialised")
        deadline = time.monotonic() + (self.timeout_s or 0)
        while True:
            try:
                fcntl.flock(self._fd.fileno(), flags | fcntl.LOCK_NB)
                return
            except OSError as e:
                if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"audit lock not acquired within {self.timeout_s}s "
                        f"(path={self.path})"
                    ) from e
                time.sleep(0.05)


def append_queue_entry(
    entry: AuditQueueEntry,
    queue_dir: Path | None = None,
) -> None:
    """Append a single entry to the audit queue under exclusive lock.

    Atomic at the line level: ``fcntl.flock`` plus a single ``write()``
    call with a trailing newline guarantees no torn lines (POSIX
    ``write`` to a file opened in ``a`` mode is append-atomic up to
    PIPE_BUF, well above our entry size).
    """
    qpath = queue_path(queue_dir)
    line = entry.model_dump_json() + "\n"
    with (
        QueueLock(lock_path(queue_dir)),
        qpath.open("a", encoding="utf-8") as f,
    ):
        f.write(line)


def read_queue(
    queue_dir: Path | None = None,
) -> list[AuditQueueEntry]:
    """Return the queue contents as a list (oldest first).

    Acquires a *shared* lock so concurrent readers do not block each
    other. Skips malformed lines silently — a corrupted entry from a
    crashed writer should not break the drain.
    """
    qpath = queue_path(queue_dir)
    if not qpath.exists():
        return []
    entries: list[AuditQueueEntry] = []
    with QueueLock(lock_path(queue_dir), shared=True):
        for line in qpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(AuditQueueEntry.model_validate_json(line))
            except (ValueError, json.JSONDecodeError):
                continue
    return entries


def drain_queue(
    queue_dir: Path | None = None,
) -> Iterator[AuditQueueEntry]:
    """Return the current queue contents WITHOUT removing them.

    POLYLENS-FIX-3 P1 — replay safety. The previous version truncated
    the file before the caller iterated, so a crash mid-processing
    silently lost every unprocessed entry. The new contract:

      * ``drain_queue`` is now a snapshot read (alias of
        :func:`read_queue` for legacy callers).
      * Callers MUST call :func:`mark_entry_processed` after each
        successful audit. That function removes only that specific
        entry from the queue file under the exclusive lock.
      * On crash mid-processing, the unprocessed entries remain in
        the queue and the next ``polybuild audit drain`` replays them.
        The 7-day dedup window in :mod:`polybuild.audit.backlog`
        prevents a successfully-processed-but-not-yet-marked entry
        from being audited twice in any meaningful way.
    """
    return iter(read_queue(queue_dir))


def mark_entry_processed(
    entry: AuditQueueEntry,
    queue_dir: Path | None = None,
) -> bool:
    """Remove ``entry`` from the queue file under exclusive lock.

    Matching is by ``(commit_sha, enqueued_at)`` — the same key
    :func:`drain_queue` would use for replay. Idempotent: removing an
    already-removed entry returns ``False`` without raising.

    Returns ``True`` when the entry was found and removed, ``False``
    otherwise (queue empty, file missing, no match).
    """
    qpath = queue_path(queue_dir)
    if not qpath.exists():
        return False

    target = (entry.commit_sha, entry.enqueued_at)
    removed = False
    with QueueLock(lock_path(queue_dir)):
        if not qpath.exists():
            return False
        survivors: list[str] = []
        for line in qpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = AuditQueueEntry.model_validate_json(line)
            except (ValueError, json.JSONDecodeError):
                survivors.append(line)
                continue
            if (e.commit_sha, e.enqueued_at) == target and not removed:
                removed = True
                continue
            survivors.append(line)

        # POLYLENS run #2 P0: rewrite the queue atomically. The
        # previous in-place ``write_text`` truncated the file before
        # writing the survivors; a crash in between lost every entry
        # we had just decided to keep — the same regression
        # POLYLENS-FIX-3 was meant to prevent.
        payload = "\n".join(survivors) + "\n" if survivors else ""
        atomic_write_text(qpath, payload)

    return removed


__all__ = [
    "DEFAULT_AUDIT_DIR",
    "AuditQueueEntry",
    "QueueLock",
    "append_queue_entry",
    "audit_dir",
    "drain_queue",
    "lock_path",
    "mark_entry_processed",
    "queue_path",
    "read_queue",
]
