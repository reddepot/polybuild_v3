"""Atomic file-write helper shared across audit subsystems.

POLYLENS run #2 P0: ``mark_entry_processed`` rewrote the queue file
in-place via ``Path.write_text``. A crash between truncate and full
flush would lose every unprocessed entry — exactly the failure mode
POLYLENS-FIX-3 set out to prevent. The fix factors the same atomic
write that :mod:`polybuild.audit.rotation` already uses for its state
file into a small reusable helper, so any audit module that needs to
replace a file's contents does so via temp + ``Path.replace`` + dir
fsync rather than truncate-in-place.

Atomicity model:

    1. ``mkstemp`` in the destination directory (same filesystem so
       ``rename`` cannot cross devices, no EXDEV).
    2. Write the full payload, ``flush`` + ``fsync`` the file fd.
    3. ``Path.replace`` — atomic on POSIX.
    4. Best-effort ``fsync`` of the parent directory so the rename is
       durable across power loss.

A failure between steps 1 and 3 leaves the original file untouched and
the temp file is unlinked. After step 3 the new contents are visible.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def atomic_write_text(
    path: Path,
    payload: str,
    *,
    parent_mode: int = 0o700,
) -> None:
    """Replace ``path`` with ``payload`` atomically.

    Args:
        path: destination file path.
        payload: text to write.
        parent_mode: mode for the parent directory if it has to be
            created. Defaults to ``0o700`` because the helper grew up
            in the audit subsystem (per-user state, secrets-adjacent).
            POLYLENS run #4 P3 (Perplexity): callers writing to a
            shared worktree (eg. ``polybuild.security.safe_write``)
            override to ``0o755`` so CI runners and reviewers can
            still read the generated directory.

    POLYLENS run #5 P2 (Gemini): ``tempfile.mkstemp`` always creates
    the temp file at hard-coded ``0o600`` regardless of the parent
    mode, so the ``parent_mode=0o755`` worktree fix only opened the
    directory but left every emitted file unreadable to the user's
    CI / reviewer accounts. We now derive the **file** mode from the
    parent: 0o755 dir → 0o644 file, 0o700 dir → 0o600 file. Applied
    after ``Path.replace`` so the final destination has the right
    mode (the mid-flight tmp file remains 0o600 — no leak window).
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=parent_mode)

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise

    # POLYLENS run #5 P2: mkstemp's 0o600 default is right for audit
    # state but wrong for shared worktrees. Mirror the parent's
    # readable bits so a 0o755 directory yields a 0o644 file.
    file_mode = 0o644 if parent_mode == 0o755 else 0o600
    with contextlib.suppress(OSError):
        path.chmod(file_mode)

    with contextlib.suppress(OSError):
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


__all__ = ["atomic_write_text"]
