"""Validate SQLite database integrity (round 4 — convergence).

Checks (Kimi + DeepSeek + ChatGPT convergence):
    - PRAGMA integrity_check returns "ok"
    - PRAGMA journal_mode is "wal" (production requirement)
    - Schema diff vs reference snapshot (if provided)
    - Foreign key integrity (PRAGMA foreign_key_check empty)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class SQLiteGateResult(BaseModel):
    """Result of SQLite validation."""

    passed: bool
    integrity_ok: bool = False
    journal_mode: str = ""
    schema_diff: list[str] = []
    fk_violations: int = 0
    errors: list[str] = []


def _read_schema(conn: sqlite3.Connection) -> dict[str, str]:
    """Read all CREATE statements indexed by object name."""
    cur = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type IN ('table','index','view','trigger') "
        "AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0]: row[1] or "" for row in cur.fetchall()}


def validate_sqlite_db(
    db_path: str | Path,
    expected_journal_mode: str = "wal",
    schema_snapshot_path: str | Path | None = None,
    require_wal: bool = True,
) -> SQLiteGateResult:
    """Run integrity, journal mode, and schema diff checks on a SQLite DB.

    Args:
        db_path: Path to the SQLite file.
        expected_journal_mode: Expected journal_mode (typically "wal" for prod).
        schema_snapshot_path: Optional path to a JSON snapshot for diff.
        require_wal: If True, non-WAL journal mode triggers failure.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return SQLiteGateResult(passed=False, errors=[f"db_not_found: {db_path}"])

    errors: list[str] = []
    integrity_ok = False
    journal_mode = ""
    fk_violations = 0
    schema_diff: list[str] = []

    try:
        # Round 5 fix [F] (Audit 4 P0): `?mode=ro` alone fails on WAL prod DBs
        # because SQLite still tries to manage -wal/-shm sidecar files. Adding
        # `immutable=1` tells SQLite the file/sidecars won't change, allowing
        # truly read-only access to a production WAL DB mounted RO via Docker.
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        return SQLiteGateResult(passed=False, errors=[f"open_failed: {e}"])

    try:
        # ── PRAGMA integrity_check ──────────────────────────────────
        cur = conn.execute("PRAGMA integrity_check")
        result = cur.fetchone()
        if result and result[0] == "ok":
            integrity_ok = True
        else:
            errors.append(f"integrity_check_failed: {result}")

        # ── PRAGMA journal_mode ─────────────────────────────────────
        cur = conn.execute("PRAGMA journal_mode")
        journal_mode = (cur.fetchone() or [""])[0].lower()
        if require_wal and journal_mode != expected_journal_mode.lower():
            errors.append(
                f"journal_mode={journal_mode} (expected {expected_journal_mode})"
            )

        # ── PRAGMA foreign_key_check ────────────────────────────────
        cur = conn.execute("PRAGMA foreign_key_check")
        fk_rows = cur.fetchall()
        fk_violations = len(fk_rows)
        if fk_violations > 0:
            errors.append(f"foreign_key_violations: {fk_violations}")

        # ── Schema diff ─────────────────────────────────────────────
        if schema_snapshot_path:
            import json

            snap_path = Path(schema_snapshot_path)
            if not snap_path.exists():
                # Round 5 (Audit 3): missing snapshot → fail explicitly, don't pass silently
                errors.append(f"schema_snapshot_not_found: {snap_path}")
            else:
                expected_schema = json.loads(snap_path.read_text(encoding="utf-8"))
                actual_schema = _read_schema(conn)

                removed = set(expected_schema) - set(actual_schema)
                added = set(actual_schema) - set(expected_schema)
                changed = {
                    name
                    for name in set(expected_schema) & set(actual_schema)
                    if expected_schema[name].strip() != actual_schema[name].strip()
                }
                if removed:
                    schema_diff.append(f"removed: {sorted(removed)}")
                    errors.append(f"schema_objects_removed: {sorted(removed)}")
                if changed:
                    # Round 5 fix [I] (Audit 3 P1): changed schema = breaking change
                    # too. The whole point of the gate is non-régression schéma.
                    schema_diff.append(f"changed: {sorted(changed)}")
                    errors.append(f"schema_objects_changed: {sorted(changed)}")
                if added:
                    # Adding new objects remains non-breaking → log only
                    schema_diff.append(f"added: {sorted(added)}")

    finally:
        conn.close()

    passed = not errors
    logger.info(
        "sqlite_gate_done",
        passed=passed,
        integrity_ok=integrity_ok,
        journal_mode=journal_mode,
        fk_violations=fk_violations,
    )

    return SQLiteGateResult(
        passed=passed,
        integrity_ok=integrity_ok,
        journal_mode=journal_mode,
        schema_diff=schema_diff,
        fk_violations=fk_violations,
        errors=errors,
    )
