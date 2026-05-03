"""Validate Qdrant collection (round 4 convergence).

Checks (ChatGPT + DeepSeek convergence):
    - GET /collections/{name} returns 200 + valid config
    - vector dimension matches expected
    - points_count > 0 (or matches min_points)
    - sample search query returns results
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


def _qdrant_url_is_safe(url: str) -> bool:
    """Round 10.8 fix [ChatGPT A-04 P1] — SSRF guard for ``qdrant_url``.

    Reject:
      * non-http(s) schemes
      * private / loopback / link-local destinations (unless override env
        ``POLYBUILD_QDRANT_ALLOW_LOCAL=1`` is set, for dev/test)
      * URLs that fail to parse
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    allow_local = os.environ.get("POLYBUILD_QDRANT_ALLOW_LOCAL") == "1"
    if allow_local:
        return True
    # Resolve hostname to an IP and check address space
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        # Unresolvable host — pass through; httpx will fail loudly.
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            return False
    return True


class QdrantGateResult(BaseModel):
    """Result of Qdrant collection validation."""

    passed: bool
    collection_name: str
    points_count: int = 0
    expected_dim: int = 0
    actual_dim: int = 0
    sample_query_returned: int = 0
    errors: list[str] = []


async def validate_qdrant_collection(
    qdrant_url: str,
    collection: str,
    expected_dim: int,
    min_points: int = 1,
    sample_vector: list[float] | None = None,
    timeout_s: float = 10.0,
    vector_name: str | None = None,
) -> QdrantGateResult:
    """Validate a Qdrant collection over HTTP.

    Args:
        qdrant_url: e.g. "http://localhost:6333".
        collection: Collection name.
        expected_dim: Expected vector dimension (e.g. 768 for E5-base, 1024 for BGE-M3).
        min_points: Minimum required points_count.
        sample_vector: Optional vector for a search smoke test.
                       If None, generates a zero-vector of expected_dim.
        timeout_s: HTTP timeout per call.
        vector_name: Round 5 fix [J] (Audits 3+4): named-vector support.
                     If the collection has named vectors, must be passed
                     either explicitly here or auto-detected from config.
    """
    try:
        import httpx
    except ImportError:
        return QdrantGateResult(
            passed=False,
            collection_name=collection,
            errors=["httpx_unavailable"],
        )

    # Round 10.8 fix [ChatGPT A-04 P1, cross-voice audit]: SSRF guard.
    # ``qdrant_url`` may originate from user / config and was previously
    # used verbatim. Reject schemes other than http/https, reject
    # private/loopback/link-local addresses unless explicitly allowed.
    if not _qdrant_url_is_safe(qdrant_url):
        return QdrantGateResult(
            passed=False,
            collection_name=collection,
            errors=[f"qdrant_url_unsafe: {qdrant_url!r} blocked by SSRF guard"],
        )

    errors: list[str] = []
    points_count = 0
    actual_dim = 0
    sample_returned = 0
    detected_vector_name: str | None = vector_name

    base = qdrant_url.rstrip("/")

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        # ── GET collection ──────────────────────────────────────────
        try:
            resp = await client.get(f"{base}/collections/{collection}")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            return QdrantGateResult(
                passed=False,
                collection_name=collection,
                errors=[f"get_collection_failed: {e}"],
            )

        result = data.get("result", {})
        config = result.get("config", {}).get("params", {}).get("vectors", {})
        # Qdrant supports named vectors and unnamed default; handle both
        if isinstance(config, dict) and "size" in config:
            actual_dim = int(config.get("size", 0))
        elif isinstance(config, dict):
            # Round 5 fix [J]: track the vector name so search uses correct payload.
            for name, v_cfg in config.items():
                if isinstance(v_cfg, dict) and "size" in v_cfg:
                    detected_vector_name = detected_vector_name or str(name)
                    actual_dim = int(v_cfg["size"])
                    break

        points_count = int(result.get("points_count", 0))

        if actual_dim != expected_dim:
            errors.append(f"dim_mismatch: expected {expected_dim}, got {actual_dim}")
        if points_count < min_points:
            errors.append(f"points_count={points_count} < min_points={min_points}")

        # ── Sample search query ─────────────────────────────────────
        if not errors:
            vec = sample_vector if sample_vector else [0.0] * expected_dim
            # Round 5 fix [J]: named-vector payload format.
            search_payload: dict[str, Any] = {"limit": 3, "with_payload": False}
            if detected_vector_name:
                search_payload["vector"] = {"name": detected_vector_name, "vector": vec}
            else:
                search_payload["vector"] = vec
            try:
                resp = await client.post(
                    f"{base}/collections/{collection}/points/search",
                    json=search_payload,
                )
                resp.raise_for_status()
                hits = resp.json().get("result", [])
                sample_returned = len(hits)
                if sample_returned == 0:
                    errors.append("sample_search_returned_zero_hits")
            except httpx.HTTPError as e:
                errors.append(f"sample_search_failed: {e}")

    passed = not errors
    logger.info(
        "qdrant_gate_done",
        passed=passed,
        collection=collection,
        points=points_count,
        dim=actual_dim,
    )

    return QdrantGateResult(
        passed=passed,
        collection_name=collection,
        points_count=points_count,
        expected_dim=expected_dim,
        actual_dim=actual_dim,
        sample_query_returned=sample_returned,
        errors=errors,
    )


def validate_qdrant_collection_sync(
    qdrant_url: str,
    collection: str,
    expected_dim: int,
    min_points: int = 1,
) -> QdrantGateResult:
    """Sync wrapper for non-async callers.

    Round 5 fix [W] (Audit 5 P2): refuses to run if already inside an
    asyncio loop (was raising RuntimeError opaquely from asyncio.run).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            validate_qdrant_collection(qdrant_url, collection, expected_dim, min_points)
        )
    raise RuntimeError(
        "validate_qdrant_collection_sync called from an active event loop; "
        "use the async validate_qdrant_collection() instead"
    )
