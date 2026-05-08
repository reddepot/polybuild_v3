"""Persistent LLM response cache (FEAT-3).

Convergent /avis recommendation from gemini-3.1-pro + glm-5.1 — neither
was on the explicit candidate list but both ranked it top-5.

Use case: developer iterating on the audit prompt. Without the cache,
every re-run of the same commit redownloads / re-calls every voice
(~10-30s, 2 voices). With the cache: identical (voice_id, prompt,
params) tuples return in microseconds from local SQLite.

Cache key = SHA-256(voice_id || \\0 || prompt || \\0 || params_json).
Changing the prompt or any param invalidates the cache; the user does
NOT need to flush manually after a runner refactor.

Disabled per-call via env ``POLYBUILD_LLM_CACHE_DISABLE=1``.
Disabled globally by deleting ``~/.polybuild/audit/llm_cache.db``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from polybuild.audit.queue import audit_dir

logger = structlog.get_logger()


def cache_db_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "llm_cache.db"


# A module-level lock guards the lazy-init connection cache. Each
# (db_path, thread) pair gets its own ``sqlite3.Connection`` because
# stdlib SQLite connections are not safe to share across threads
# without ``check_same_thread=False`` plus a coarse lock.
_CONN_LOCK = threading.Lock()
_CONN_CACHE: dict[Path, sqlite3.Connection] = {}


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """Return a cached connection for ``db_path`` (one per process)."""
    with _CONN_LOCK:
        existing = _CONN_CACHE.get(db_path)
        if existing is not None:
            return existing
        db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage txns explicitly
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                key          TEXT PRIMARY KEY,
                voice_id     TEXT NOT NULL,
                response     TEXT NOT NULL,
                cached_at    TEXT NOT NULL,
                tokens_total INTEGER,
                latency_s    REAL
            ) WITHOUT ROWID
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS llm_cache_voice "
            "ON llm_cache(voice_id, cached_at)"
        )
        _CONN_CACHE[db_path] = conn
        return conn


def make_cache_key(
    voice_id: str,
    prompt: str,
    params: dict[str, Any] | None = None,
) -> str:
    """SHA-256 hex digest over ``(voice_id, prompt, sorted_params)``.

    ``params`` is canonicalised via ``json.dumps(sort_keys=True)`` so a
    semantically identical params dict produces the same key regardless
    of insertion order.
    """
    h = hashlib.sha256()
    h.update(voice_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt.encode("utf-8"))
    h.update(b"\x00")
    if params:
        h.update(json.dumps(params, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()


def cache_disabled() -> bool:
    """Check the per-call disable flag."""
    return os.environ.get("POLYBUILD_LLM_CACHE_DISABLE", "0") == "1"


def cache_get(
    key: str,
    *,
    cache_dir: Path | None = None,
) -> str | None:
    """Return the cached response for ``key`` or ``None`` on miss / disable."""
    if cache_disabled():
        return None
    db = cache_db_path(cache_dir)
    if not db.exists():
        return None
    try:
        conn = _get_conn(db)
        row = conn.execute(
            "SELECT response FROM llm_cache WHERE key = ?",
            (key,),
        ).fetchone()
    except sqlite3.Error as e:
        logger.warning("llm_cache_get_failed", error=str(e), key_first_8=key[:8])
        return None
    return row[0] if row else None


def cache_put(
    key: str,
    *,
    voice_id: str,
    response: str,
    tokens_total: int | None = None,
    latency_s: float | None = None,
    cache_dir: Path | None = None,
) -> None:
    """Insert or replace the entry for ``key``.

    Best-effort: any sqlite error is logged and swallowed — the cache
    must never block the audit pipeline.
    """
    if cache_disabled():
        return
    db = cache_db_path(cache_dir)
    try:
        conn = _get_conn(db)
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache
                (key, voice_id, response, cached_at, tokens_total, latency_s)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                voice_id,
                response,
                datetime.now(UTC).isoformat(),
                tokens_total,
                latency_s,
            ),
        )
    except sqlite3.Error as e:
        logger.warning(
            "llm_cache_put_failed",
            error=str(e),
            voice_id=voice_id,
            key_first_8=key[:8],
        )


def cache_stats(cache_dir: Path | None = None) -> dict[str, Any]:
    """Return aggregate stats for the cache: row count, voices, size on disk."""
    db = cache_db_path(cache_dir)
    if not db.exists():
        return {"rows": 0, "voices": 0, "size_bytes": 0}
    try:
        conn = _get_conn(db)
        row_count = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        voice_count = conn.execute(
            "SELECT COUNT(DISTINCT voice_id) FROM llm_cache"
        ).fetchone()[0]
    except sqlite3.Error as e:
        return {"error": str(e), "rows": 0, "voices": 0, "size_bytes": 0}
    size = 0
    with contextlib.suppress(OSError):
        size = db.stat().st_size
    return {"rows": int(row_count), "voices": int(voice_count), "size_bytes": int(size)}


def cache_clear(cache_dir: Path | None = None) -> int:
    """Delete every entry. Returns the number of rows removed."""
    db = cache_db_path(cache_dir)
    if not db.exists():
        return 0
    try:
        conn = _get_conn(db)
        before = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        conn.execute("DELETE FROM llm_cache")
        conn.execute("VACUUM")
    except sqlite3.Error as e:
        logger.warning("llm_cache_clear_failed", error=str(e))
        return 0
    return int(before)


__all__ = [
    "cache_clear",
    "cache_db_path",
    "cache_disabled",
    "cache_get",
    "cache_put",
    "cache_stats",
    "make_cache_key",
]
