"""Safe file write helper for adapter ``_parse_response`` paths.

Round 10.8 fix [ChatGPT A-01 + Kimi A-01/A-02, 2/5 cross-voice P0 audit]:
the ``OllamaLocalAdapter._parse_response`` and ``MistralEUAdapter._parse_response``
methods share the same path-traversal vulnerability that was patched in
``OpenRouterAdapter._parse_response`` during Round 10.7 — but the fix was
never propagated. An external 5-voice audit (ChatGPT + Kimi independently)
confirmed both paths are still exploitable.

This module factors the defence into a reusable helper so future adapters
inherit the protection without duplicating the logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from polybuild.audit._atomic_io import atomic_write_text

logger = structlog.get_logger()


def write_files_to_worktree(
    files: Any,
    worktree: Path,
    *,
    adapter_name: str = "adapter",
) -> int:
    """Write LLM-emitted files into ``worktree`` with full path defence.

    Defends against:
      * **Path traversal** — ``rel_path`` is LLM-controlled. ``worktree / rel_path``
        resolves any absolute right-hand-side to itself (``Path('a/b') / '/etc/x'``
        ≡ ``Path('/etc/x')``); ``..`` segments also escape. We resolve the
        full path and require ``is_relative_to(worktree.resolve())``.
      * **Type confusion** — non-string ``rel_path`` or ``source`` would crash
        ``write_text`` with ``TypeError``. Skip and log instead.
      * **Non-mapping ``files``** — caller may pass ``None``/``list``/``str``
        if upstream JSON shape was wrong. Treated as empty.

    Args:
        files: should be a ``dict[str, str]`` from the LLM response. Anything
            else is logged and skipped.
        worktree: the output directory. Must already exist (or be creatable
            by the caller) — this helper does not enforce that.
        adapter_name: tag for log events so downstream observability knows
            which adapter triggered the write.

    Returns:
        Number of files successfully written.
    """
    if not isinstance(files, dict):
        logger.warning(
            f"{adapter_name}_files_not_mapping",
            files_type=type(files).__name__,
        )
        return 0

    worktree_resolved = worktree.resolve()
    written = 0

    for rel_path, source in files.items():
        if not isinstance(rel_path, str) or not isinstance(source, str):
            logger.warning(
                f"{adapter_name}_skip_invalid_file_entry",
                rel_path=str(rel_path)[:120],
                rel_path_type=type(rel_path).__name__,
                source_type=type(source).__name__,
            )
            continue
        try:
            abs_path = (worktree / rel_path).resolve()
        except (OSError, ValueError) as e:
            logger.warning(
                f"{adapter_name}_path_resolve_failed",
                rel_path=rel_path,
                error=str(e),
            )
            continue
        if not abs_path.is_relative_to(worktree_resolved):
            logger.warning(
                f"{adapter_name}_path_traversal_blocked",
                rel_path=rel_path,
                abs_path=str(abs_path),
            )
            continue
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        # POLYLENS run #3 P1 (KIMI Agent Swarm): the previous in-place
        # ``write_text`` truncated the destination before writing. A
        # SIGKILL or OOM mid-write left a half-empty file with no
        # backup, which then went straight to the worktree's git
        # commit. Atomic write via ``mkstemp + fsync + replace``
        # guarantees either the old content (if interrupted) or the
        # new content (if completed) — never a half-flushed mix.
        # POLYLENS run #4 P3 (Perplexity): pass ``parent_mode=0o755``
        # so the worktree subdirectory is readable by the user's
        # reviewer / CI runner. The audit-subsystem default of 0o700
        # would surprise downstream pipelines that expect normal
        # source-tree perms.
        atomic_write_text(abs_path, source, parent_mode=0o755)
        written += 1

    return written


__all__ = ["write_files_to_worktree"]
