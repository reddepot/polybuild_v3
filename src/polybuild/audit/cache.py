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

POLYLENS run #2 P1 (gpt-5.5 + gemini + minimax convergent): the cache
is now **opt-in** (default off) with a 7-day TTL. A successful prompt
injection that poisons one voice's response would otherwise be served
back forever from cache. The opt-in pivot also means the cache only
kicks in for users who actively want it (prompt iteration), not for
every audit run.

Enable via env ``POLYBUILD_LLM_CACHE_ENABLE=1``. Override the TTL via
``POLYBUILD_LLM_CACHE_TTL_DAYS=<int>`` (default 7).
Disabled globally by deleting ``~/.polybuild/audit/llm_cache.db``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from polybuild.audit.queue import audit_dir

logger = structlog.get_logger()


def cache_db_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "llm_cache.db"


# A module-level reentrant lock guards the lazy-init connection cache
# plus every subsequent query. ``sqlite3`` with ``check_same_thread=False``
# allows the connection object to be reached from multiple threads, but
# the underlying SQLite C API still serialises writes per connection —
# and concurrent ``cursor.execute`` on the SAME connection from two
# threads is undefined behaviour. POLYLENS run #3 P2 (codex-gpt-5.5 +
# qwen + deepseek-expert convergent): the previous comment claimed
# "(db_path, thread) pair" granularity, but ``_CONN_CACHE`` was keyed
# by ``Path`` only. The honest implementation is one connection per
# process behind a coarse module-level lock; a thread-safe re-design
# would need a connection pool. Documented and serialised.
#
# RLock (reentrant) is required because ``cache_get`` / ``cache_put`` /
# ``cache_get_with_metadata`` already hold the lock when they call
# ``_get_conn`` on a cold cache (first call after import) — that nested
# call would deadlock a plain ``threading.Lock``.
_CONN_LOCK = threading.RLock()
_CONN_CACHE: dict[Path, sqlite3.Connection] = {}


def _chmod_sqlite_files(db_path: Path) -> None:
    """Tighten permissions on the SQLite triplet.

    SQLite in WAL mode lazily creates ``.db-wal`` and ``.db-shm`` sidecars
    that hold uncommitted transactions and the shared-memory index. Both
    inherit the process umask which on default systems is world-readable
    (``0o644`` after umask 022). The cache holds verbatim audit prompts
    and voice responses — both can contain code excerpts and findings the
    user expects to keep private.

    POLYLENS run #3 P0 (Gemini + Codex + Qwen3.6-max convergent): chmod
    only the main ``.db`` left the sidecars exposed. We chmod all three
    files best-effort. Called both at init and after each write so a
    sidecar that appears later still gets locked down on the next call.
    """
    for suffix in ("", "-wal", "-shm"):
        target = db_path.with_name(db_path.name + suffix)
        if target.exists():
            with contextlib.suppress(OSError):
                target.chmod(0o600)


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """Return a cached connection for ``db_path`` (one per process).

    POLYLENS run #4 P1 (Perplexity): ``os.umask`` is process-global and
    not thread-local. The previous narrow-umask trick affected EVERY
    other thread that happened to create files during the few hundred
    microseconds the umask was tight — including unrelated artefacts in
    a multi-threaded uvicorn / gunicorn worker. Replaced with explicit
    ``chmod`` on the freshly-created files: marginally less atomic
    (the file exists at umask perms for ~ms) but doesn't punish other
    threads, and the local filesystem is single-user anyway.
    """
    with _CONN_LOCK:
        existing = _CONN_CACHE.get(db_path)
        if existing is not None:
            return existing
        db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with contextlib.suppress(OSError):
            db_path.parent.chmod(0o700)
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
        _chmod_sqlite_files(db_path)
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


def cache_enabled() -> bool:
    """Per-call enable flag.

    POLYLENS run #2 P1: defaults to **OFF**. The audit cache must be
    opt-in so a poisoned voice response cannot be served back forever
    on every subsequent run.
    """
    return os.environ.get("POLYBUILD_LLM_CACHE_ENABLE", "0") == "1"


# POLYLENS run #3 P3 (deepseek-expert): ``cache_disabled`` was a
# deprecated alias never imported anywhere in the codebase nor in tests.
# Removed; callers use :func:`cache_enabled` (with a ``not`` if they
# want the inverse).


def _cache_ttl() -> timedelta:
    """Resolved cache TTL — default 7 days, overridable via env."""
    raw = os.environ.get("POLYBUILD_LLM_CACHE_TTL_DAYS", "7")
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = 7
    # Negative or zero TTL effectively disables hits without disabling
    # writes — accepted, matches the "always miss" use case for tests.
    return timedelta(days=max(days, 0))


def cache_get(
    key: str,
    *,
    cache_dir: Path | None = None,
) -> str | None:
    """Return the cached response for ``key`` or ``None`` on miss / disable / expiry.

    POLYLENS run #3 P2: every query holds ``_CONN_LOCK`` for the
    duration so concurrent callers (test workers, parallel audit
    drains) cannot race on the same connection's cursor.

    Public callers only need the response string. Internal call-sites
    that also want the cost metadata use the private
    :func:`_cache_get_with_metadata` helper — POLYLENS run #4 P2
    (Perplexity) flagged that exposing the tuple variant in ``__all__``
    without an actual consumer is API surface for nobody.
    """
    full = _cache_get_with_metadata(key, cache_dir=cache_dir)
    return full[0] if full is not None else None


def _cache_get_with_metadata(
    key: str,
    *,
    cache_dir: Path | None = None,
) -> tuple[str, int | None, float | None] | None:
    """Return ``(response, tokens_total, latency_s)`` or ``None`` on miss.

    POLYLENS run #3 P2 (KIMI Agent Swarm): the previous ``cache_put``
    happily wrote ``tokens_total`` and ``latency_s`` but ``cache_get``
    only read ``response`` + ``cached_at`` — the metadata columns
    became orphaned write-only data. This accessor closes the loop.

    POLYLENS run #4 P2 (Perplexity): kept private (underscore prefix,
    not in ``__all__``) until a real cost dashboard or other consumer
    actually needs the tuple form. Public ``cache_get`` calls into
    this and discards the metadata tail.
    """
    if not cache_enabled():
        return None
    db = cache_db_path(cache_dir)
    if not db.exists():
        return None
    try:
        with _CONN_LOCK:
            conn = _CONN_CACHE.get(db) or _get_conn(db)
            row = conn.execute(
                "SELECT response, cached_at, tokens_total, latency_s "
                "FROM llm_cache WHERE key = ?",
                (key,),
            ).fetchone()
    except sqlite3.Error as e:
        logger.warning("llm_cache_get_failed", error=str(e), key_first_8=key[:8])
        return None
    if not row:
        return None
    response, cached_at_str, tokens_total, latency_s = row
    try:
        cached_at = datetime.fromisoformat(cached_at_str)
    except (TypeError, ValueError):
        # Corrupted timestamp — treat as miss rather than crash.
        return None
    if datetime.now(UTC) - cached_at > _cache_ttl():
        return None
    return (
        str(response),
        int(tokens_total) if tokens_total is not None else None,
        float(latency_s) if latency_s is not None else None,
    )


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
    must never block the audit pipeline. POLYLENS run #3 P2: writes are
    serialised under ``_CONN_LOCK`` and the sidecar files are re-chmod'd
    afterwards (the WAL file may not have existed at init).
    """
    if not cache_enabled():
        return
    db = cache_db_path(cache_dir)
    try:
        with _CONN_LOCK:
            conn = _CONN_CACHE.get(db) or _get_conn(db)
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
        return
    # Sidecars may have been created on this write — re-tighten perms.
    _chmod_sqlite_files(db)


def cache_stats(cache_dir: Path | None = None) -> dict[str, Any]:
    """Return aggregate stats for the cache: row count, voices, size on disk.

    POLYLENS run #4 P1 (Perplexity + DeepSeek convergent): the previous
    version called ``_get_conn`` then issued ``execute`` without holding
    ``_CONN_LOCK`` — a concurrent ``cache_put`` from another thread (or
    a parallel ``cache_clear`` from the CLI) could race the cursor and
    produce a ``sqlite3.ProgrammingError``. Now serialised, mirroring
    ``cache_get_with_metadata`` and ``cache_put``.
    """
    db = cache_db_path(cache_dir)
    if not db.exists():
        return {"rows": 0, "voices": 0, "size_bytes": 0}
    try:
        with _CONN_LOCK:
            conn = _CONN_CACHE.get(db) or _get_conn(db)
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
    """Delete every entry. Returns the number of rows removed.

    POLYLENS run #4 P1 (Perplexity + DeepSeek convergent): now holds
    ``_CONN_LOCK`` for the whole COUNT + DELETE + VACUUM sequence so a
    concurrent ``cache_get`` cannot race on the same connection and
    so ``VACUUM`` doesn't run while another thread is mid-transaction.
    """
    db = cache_db_path(cache_dir)
    if not db.exists():
        return 0
    try:
        with _CONN_LOCK:
            conn = _CONN_CACHE.get(db) or _get_conn(db)
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
    "cache_enabled",
    "cache_get",
    "cache_put",
    "cache_stats",
    "make_cache_key",
]
