"""Phase 6 — Final validation gates (general + domain-specific).

General gates: pytest, mypy --strict, ruff, bandit, gitleaks (re-run after Phase 5 fixes).

Domain gates (Round 4 finalisé) — convergence 5/6 :
    - validate_mcp: subprocess JSON-RPC stdio, initialize + tools/list + Pydantic schema
    - validate_sqlite_db: PRAGMA integrity_check + WAL mode + schema diff
    - validate_qdrant_collection: get_collection + dim match + sample query
    - validate_fts5_golden: golden queries with min_hits
    - validate_rag_smoke: chunk hash stability + golden retrieval

Decision Round 4: domain gate failure → BLOCKS commit (Phase 7). Aucun warn-only.
Convergence 5/6 (Grok, Qwen, Kimi, Gemini, ChatGPT bloquant ; DeepSeek nuance vers warn
pour SQLite optionnel mais s'aligne sur bloquant pour MCP/Qdrant/RAG).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import structlog
import yaml

from polybuild.models import (
    BuilderResult,
    Spec,
    ValidationVerdict,
)
from polybuild.phases.phase_3_score import run_general_gates

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# DOMAIN GATES MAP (Round 4 finalisé)
# ────────────────────────────────────────────────────────────────

# Default profile→gates mapping (loaded from routing.yaml at runtime if present).
DOMAIN_GATES_BY_PROFILE: dict[str, list[str]] = {
    "mcp_schema_change": ["mcp", "sqlite", "fts5"],
    "rag_ingestion_eval": ["sqlite", "fts5", "qdrant", "rag"],
    "parsing_pdf_medical": ["rag"],
    "oai_pmh_scraping": ["sqlite"],
    "module_standard_known": [],
    "module_inedit_critique": [],
    "helia_algo": [],
    "medical_low": [],
    "medical_medium": [],
    "medical_high": [],
    "devops_iac_scripts": [],
    "refactor_mecanique": [],
    "llm_as_judge": [],
    "post_polylens_fix": [],
    "documentation_adr": [],
}


def _load_domain_gates_from_routing(routing_path: Path | None = None) -> dict[str, list[str]]:
    """Override default mapping with routing.yaml if it has a `domain_gates_by_profile` key."""
    if routing_path is None:
        routing_path = Path(__file__).resolve().parents[3] / "config" / "routing.yaml"
    if not routing_path.exists():
        return DOMAIN_GATES_BY_PROFILE

    try:
        data = yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return DOMAIN_GATES_BY_PROFILE

    overrides: dict[str, list[str]] = {}
    profiles = data.get("profiles", {})
    for profile_id, profile_config in profiles.items():
        gates = profile_config.get("domain_gates")
        if isinstance(gates, list):
            overrides[profile_id] = list(gates)

    return {**DOMAIN_GATES_BY_PROFILE, **overrides}


# ────────────────────────────────────────────────────────────────
# DOMAIN GATE RUNNER (Round 4 finalisé)
# ────────────────────────────────────────────────────────────────


async def _run_single_domain_gate(
    gate_name: str,
    workdir: Path,
    gate_config: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Run a single domain gate by name. Returns (passed, errors).

    `gate_config` carries gate-specific parameters loaded from spec.yaml or routing.yaml
    (e.g. `mcp.server_cmd`, `sqlite.db_path`, `qdrant.collection`).
    """
    cfg = gate_config or {}

    if gate_name == "mcp":
        from polybuild.domain_gates.validate_mcp import validate_mcp_server

        server_cmd = cfg.get("server_cmd", ["uv", "run", "python", "-m", "server"])
        expected_tools = set(cfg.get("expected_tools", []))
        mcp_result = await validate_mcp_server(
            server_cmd=server_cmd,
            cwd=workdir,
            expected_tools=expected_tools or None,
            timeout_s=float(cfg.get("timeout_s", 30.0)),
            extra_env=cfg.get("extra_env"),
            golden_tool_call=cfg.get("golden_tool_call"),
        )
        return mcp_result.passed, mcp_result.errors

    if gate_name == "sqlite":
        from polybuild.domain_gates.validate_sqlite import validate_sqlite_db

        db_path = cfg.get("db_path")
        if not isinstance(db_path, str | Path):
            return False, ["sqlite_gate_no_db_path_configured"]
        sqlite_result = validate_sqlite_db(
            db_path=db_path,
            schema_snapshot_path=cfg.get("schema_snapshot_path"),
            require_wal=bool(cfg.get("require_wal", True)),
        )
        return sqlite_result.passed, sqlite_result.errors

    if gate_name == "qdrant":
        from polybuild.domain_gates.validate_qdrant import validate_qdrant_collection

        url = cfg.get("url", "http://localhost:6333")
        collection = cfg.get("collection")
        if not isinstance(collection, str):
            return False, ["qdrant_gate_no_collection_configured"]
        qdrant_result = await validate_qdrant_collection(
            qdrant_url=url,
            collection=collection,
            expected_dim=int(cfg.get("expected_dim", 768)),
            min_points=int(cfg.get("min_points", 1)),
            vector_name=cfg.get("vector_name"),
        )
        return qdrant_result.passed, qdrant_result.errors

    if gate_name == "fts5":
        from polybuild.domain_gates.validate_fts5 import validate_fts5_golden

        fts_db_path = cfg.get("db_path")
        fts_table = cfg.get("fts_table")
        golden_path = cfg.get("golden_path")
        if not (
            isinstance(fts_db_path, str | Path)
            and isinstance(fts_table, str)
            and isinstance(golden_path, str | Path)
        ):
            return False, ["fts5_gate_missing_config"]
        fts5_result = validate_fts5_golden(
            db_path=fts_db_path,
            fts_table=fts_table,
            golden_path=golden_path,
            require_golden_file=bool(cfg.get("require_golden_file", True)),
        )
        # Round 6 fix [fts5-skipped] (Audit 1 P1): when skipped=True, the gate
        # didn't actually validate anything. Surface it explicitly in the
        # signals so phase_6 notes mention "skipped" rather than just "passed".
        signals = list(fts5_result.errors) + list(fts5_result.failures)
        if fts5_result.skipped:
            signals.append("fts5_skipped_dev_mode")
        return fts5_result.passed, signals

    if gate_name == "rag":
        from polybuild.domain_gates.validate_rag import validate_rag_smoke

        runtime = cfg.get("_runtime", {})
        rag_result = validate_rag_smoke(
            chunker_fn=runtime.get("chunker_fn"),
            sample_text=cfg.get("sample_text", ""),
            golden_retrieval_path=cfg.get("golden_retrieval_path"),
            retrieval_fn=runtime.get("retrieval_fn"),
        )
        return rag_result.passed, rag_result.errors

    return False, [f"unknown_gate: {gate_name}"]


async def run_domain_gates(
    workdir: Path,
    profile_id: str,
    gate_configs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all domain gates applicable to the profile.

    Returns a dict {gate_name: {"passed": bool, "errors": [...]}}.
    """
    mapping = _load_domain_gates_from_routing()
    gates = mapping.get(profile_id, [])
    results: dict[str, dict[str, Any]] = {}

    for gate in gates:
        cfg = (gate_configs or {}).get(gate, {})
        passed, errors = await _run_single_domain_gate(gate, workdir, cfg)
        results[gate] = {"passed": passed, "errors": errors}
        logger.info("domain_gate_result", gate=gate, passed=passed, n_errors=len(errors))

    return results


# ────────────────────────────────────────────────────────────────
# SPEC HASH VERIFICATION (anti spec drift mid-run)
# ────────────────────────────────────────────────────────────────


def verify_spec_hash(spec: Spec, run_dir: Path) -> bool:
    """Verify the spec hash hasn't changed since Phase 0c."""
    spec_file = run_dir / "spec_final.json"
    if not spec_file.exists():
        return False
    canonical = json.dumps(
        json.loads(spec_file.read_text()),
        sort_keys=True,
        ensure_ascii=False,
    )
    current_hash = hashlib.sha256(canonical.encode()).hexdigest()
    return current_hash == spec.spec_hash


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_6_validate(
    spec: Spec,
    winner: BuilderResult,
    artifacts_dir: Path = Path(".polybuild/runs"),
    domain_gate_configs: dict[str, dict[str, Any]] | None = None,
) -> ValidationVerdict:
    """Run all final validation gates.

    Round 4 decision: domain gate failure BLOCKS commit (no warn-only).
    """
    logger.info("phase_6_start", run_id=spec.run_id)

    workdir = winner.code_dir.parent

    # General gates (re-run after Phase 5 fixes)
    general = await run_general_gates(workdir)

    # Domain gates (round 4 finalisé)
    domain_results = await run_domain_gates(workdir, spec.profile_id, domain_gate_configs)
    domain_passed = all(r["passed"] for r in domain_results.values())

    # Spec hash verification (drift detection)
    run_dir = artifacts_dir / spec.run_id
    spec_ok = verify_spec_hash(spec, run_dir)

    notes: list[str] = []
    if not spec_ok:
        notes.append("Spec drift detected: hash mismatch")
    if not domain_passed:
        failed = [k for k, v in domain_results.items() if not v["passed"]]
        notes.append(f"Domain gates failed: {failed}")
        for gate, r in domain_results.items():
            if not r["passed"]:
                for err in r.get("errors", [])[:3]:
                    notes.append(f"  [{gate}] {err}")

    passed = (
        general.acceptance_pass_ratio == 1.0
        and general.bandit_clean
        and general.mypy_strict_clean
        and general.ruff_clean
        and general.gitleaks_clean
        and domain_passed
        and spec_ok
    )

    logger.info(
        "phase_6_done",
        passed=passed,
        spec_drift=not spec_ok,
        domain_passed=domain_passed,
        n_domain_gates=len(domain_results),
    )

    return ValidationVerdict(
        passed=passed,
        general_gates=general,
        domain_gates_passed=domain_passed,
        domain_gates_results={k: v["passed"] for k, v in domain_results.items()},
        spec_drift_detected=not spec_ok,
        notes=notes,
    )
