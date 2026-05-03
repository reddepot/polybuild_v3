"""Validate FTS5 full-text index via golden queries (round 4).

Convergence (Kimi + DeepSeek): 3 golden queries with expected minimum hits.
The golden set is loaded from a JSON fixture path; tolerates non-existence
in early dev (returns warn-level result) but BLOCKS in mcp_schema_change /
rag_ingestion_eval profiles where the fixture is mandatory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class FTS5GateResult(BaseModel):
    """Result of FTS5 golden query validation."""

    passed: bool
    fts_table: str
    n_queries: int = 0
    n_passed: int = 0
    failures: list[str] = []
    errors: list[str] = []
    # Round 6 fix [fts5-skipped] (Audit 1 P1): explicit boolean for "tests
    # were not actually run". Phase 6 must check this to avoid mistaking a
    # dev-mode skip for a real validation pass.
    skipped: bool = False


def validate_fts5_golden(
    db_path: str | Path,
    fts_table: str,
    golden_path: str | Path,
    require_golden_file: bool = True,
) -> FTS5GateResult:
    """Run a set of FTS5 golden queries and check minimum hit counts.

    Golden file format (JSON list):
        [
          {"query": "amiante", "min_hits": 5, "max_hits": 10000},
          {"query": "burnout", "min_hits": 3}
        ]

    Args:
        db_path: SQLite DB path.
        fts_table: Name of the FTS5 virtual table (e.g. "articles_fts").
        golden_path: Path to JSON golden queries.
        require_golden_file: If True, missing file → fail. If False → warn-only.
    """
    db_path = Path(db_path)
    golden_path = Path(golden_path)

    if not db_path.exists():
        return FTS5GateResult(
            passed=False, fts_table=fts_table, errors=[f"db_not_found: {db_path}"]
        )

    if not golden_path.exists():
        if require_golden_file:
            return FTS5GateResult(
                passed=False,
                fts_table=fts_table,
                errors=[f"golden_file_not_found: {golden_path}"],
            )
        # Round 5 fix [H] (Audits 3+5): even in optional mode, signal the skip
        # so phase_6 can surface it in notes (was hidden as passed=True silently).
        # Round 6 [fts5-skipped]: also set skipped=True so phase_6 can
        # distinguish "real pass" from "dev-mode skip".
        logger.warning("fts5_golden_file_missing_skipping", path=str(golden_path))
        return FTS5GateResult(
            passed=True,
            fts_table=fts_table,
            errors=[],
            failures=["GOLDEN_SKIPPED_DEV_MODE"],
            skipped=True,
        )

    try:
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        if not isinstance(golden, list):
            return FTS5GateResult(
                passed=False,
                fts_table=fts_table,
                errors=["golden_file_not_a_list"],
            )
    except json.JSONDecodeError as e:
        return FTS5GateResult(
            passed=False, fts_table=fts_table, errors=[f"golden_parse_error: {e}"]
        )

    # Round 5 fix [H] (Audit 3 P2): empty golden = no actual test = fail.
    # Spec round 4 said "3 golden queries". Reject below that threshold.
    if len(golden) < 3 and require_golden_file:
        return FTS5GateResult(
            passed=False,
            fts_table=fts_table,
            n_queries=len(golden),
            errors=[
                f"golden_queries_below_minimum: got {len(golden)}, need >=3 "
                f"per round 4 spec"
            ],
        )

    failures: list[str] = []
    n_passed = 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        return FTS5GateResult(
            passed=False, fts_table=fts_table, errors=[f"open_failed: {e}"]
        )

    try:
        for entry in golden:
            query = str(entry.get("query", "")).strip()
            min_hits = int(entry.get("min_hits", 1))
            max_hits = entry.get("max_hits")  # optional

            if not query:
                continue

            try:
                # fts_table is a structural identifier loaded from the
                # user-controlled YAML config, not user input. SQLite FTS5
                # cannot bind table names parametrically, so an f-string is
                # the only option. Both ruff (S608) and bandit (B608) are
                # silenced here with that justification.
                cur = conn.execute(
                    f"SELECT COUNT(*) FROM {fts_table} WHERE {fts_table} MATCH ?",  # noqa: S608  # nosec B608
                    (query,),
                )
                n_hits = int(cur.fetchone()[0])
            except sqlite3.Error as e:
                failures.append(f"query={query!r} sqlite_error={e}")
                continue

            if n_hits < min_hits:
                failures.append(f"query={query!r} hits={n_hits} < min={min_hits}")
            elif max_hits is not None and n_hits > int(max_hits):
                failures.append(f"query={query!r} hits={n_hits} > max={max_hits}")
            else:
                n_passed += 1
    finally:
        conn.close()

    passed = not failures
    logger.info(
        "fts5_gate_done",
        passed=passed,
        table=fts_table,
        n_passed=n_passed,
        n_total=len(golden),
    )

    return FTS5GateResult(
        passed=passed,
        fts_table=fts_table,
        n_queries=len(golden),
        n_passed=n_passed,
        failures=failures,
    )
