"""Validate RAG pipeline smoke (round 4 convergence).

Checks (Kimi + DeepSeek + ChatGPT):
    - Chunk hash stability: re-chunking the same input produces identical chunks.
    - Golden retrieval: known-relevant queries return expected docs in top-K.
    - Pipeline end-to-end: ingest → embed → query → results.

Implementation note: this gate is lightweight by default (hash-only). Full
golden retrieval requires the calling project to provide a golden fixture
JSON with {query, expected_doc_id, top_k} entries.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class RAGGateResult(BaseModel):
    """Result of RAG smoke validation."""

    passed: bool
    chunk_hash_stable: bool = True
    golden_top_k_passed: int = 0
    golden_total: int = 0
    errors: list[str] = []


def _hash_chunks(chunks: list[str]) -> str:
    """Produce a stable hash of a chunk list."""
    h = hashlib.sha256()
    for chunk in chunks:
        h.update(chunk.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def validate_rag_smoke(
    chunker_fn: Callable[[str], list[str]] | None = None,
    sample_text: str = "",
    golden_retrieval_path: str | Path | None = None,
    retrieval_fn: Callable[[str, int], list[str]] | None = None,
) -> RAGGateResult:
    """Run RAG smoke checks.

    Args:
        chunker_fn: Optional chunker function `text -> list[chunks]`.
                    If provided, runs hash-stability check (call twice, hashes must match).
        sample_text: Text to feed the chunker.
        golden_retrieval_path: Optional JSON file with golden retrieval cases.
            Format: [{"query": "...", "expected_doc_id": "abc", "top_k": 5}, ...]
        retrieval_fn: Function `(query, top_k) -> list[doc_id]` for golden checks.

    Returns:
        RAGGateResult.
    """
    errors: list[str] = []
    chunk_stable = True

    # Round 5 fix [G] (Audits 3+5): refuse `passed=True` when nothing was tested.
    # The previous version returned passed=True if both checks were absent —
    # a profil rag_ingestion_eval could thus validate without chunking, retrieval,
    # or any actual RAG verification. Now: at least one check must be configured.
    chunker_check_requested = chunker_fn is not None and bool(sample_text)
    golden_check_requested = golden_retrieval_path is not None
    if not (chunker_check_requested or golden_check_requested):
        return RAGGateResult(
            passed=False,
            chunk_hash_stable=False,
            errors=[
                "rag_gate_no_checks_configured: provide chunker_fn+sample_text "
                "or golden_retrieval_path (or both)"
            ],
        )

    # ── Chunk hash stability ─────────────────────────────────────────
    if chunker_check_requested:
        assert chunker_fn is not None  # narrowed by check above
        try:
            chunks_a = chunker_fn(sample_text)
            chunks_b = chunker_fn(sample_text)
            if _hash_chunks(chunks_a) != _hash_chunks(chunks_b):
                chunk_stable = False
                errors.append("chunker_non_deterministic: hash mismatch on identical input")
        except Exception as e:
            errors.append(f"chunker_failed: {type(e).__name__}: {e}")

    # ── Golden retrieval ─────────────────────────────────────────────
    n_passed = 0
    n_total = 0
    if golden_retrieval_path:
        path = Path(golden_retrieval_path)
        if not path.exists():
            errors.append(f"golden_retrieval_file_not_found: {path}")
        else:
            try:
                cases = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"golden_parse_error: {e}")
                cases = []

            n_total = len(cases)
            if cases and retrieval_fn is None:
                errors.append("golden_provided_but_retrieval_fn_missing")
            elif cases and retrieval_fn is not None:
                for case in cases:
                    query = str(case.get("query", ""))
                    expected = str(case.get("expected_doc_id", ""))
                    top_k = int(case.get("top_k", 5))
                    if not query or not expected:
                        continue
                    try:
                        retrieved = retrieval_fn(query, top_k)
                    except Exception as e:
                        errors.append(f"retrieval_failed: query={query!r} err={e}")
                        continue
                    if expected in retrieved:
                        n_passed += 1
                    else:
                        errors.append(
                            f"golden_miss: query={query!r} expected={expected} "
                            f"retrieved={retrieved[:5]}"
                        )

    passed = (not errors) and chunk_stable
    logger.info(
        "rag_gate_done",
        passed=passed,
        chunk_stable=chunk_stable,
        golden_passed=n_passed,
        golden_total=n_total,
    )

    return RAGGateResult(
        passed=passed,
        chunk_hash_stable=chunk_stable,
        golden_top_k_passed=n_passed,
        golden_total=n_total,
        errors=errors,
    )
