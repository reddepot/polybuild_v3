"""Phase 8 — Production smoke (Round 4 Faille 4 finalisé).

Convergence round 4 (6/6) sur Option B :
    1. git tag `polybuild/run-{run_id}-pre` AVANT toute modification prod.
    2. Worktree Git séparé + Docker staging avec ports décalés (+10000) et
       volumes de prod montés en `:ro`.
    3. Phase 8 smoke = 5 minutes de monitoring + N requêtes golden.
    4. Sur échec → rollback automatique via `git reset --hard <tag-pre>`.

Désaccord majeur sur le seuil de dégradation accepté :
    - DeepSeek : 0% strict (réponses bit-à-bit identiques sur RAG déterministe).
    - Grok / Qwen / Kimi / Gemini / ChatGPT : 5% latence + 0% erreur protocolaire.
Compromis retenu : 0% MCP errors + 5% latence p95 + 0% missing critical results.

Phase 9 cleanup (bonus Gemini) intégrée comme bloc `finally:` strict.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# MODELS
# ────────────────────────────────────────────────────────────────


class GoldenQuery(BaseModel):
    """A single golden query for production smoke."""

    name: str
    method: str
    params: dict[str, Any] = {}
    expected_status: int = 200
    expected_min_results: int | None = None  # for list-returning queries
    expected_hash: str | None = None  # bit-exact match if RAG deterministic


class SmokeQueryResult(BaseModel):
    """Outcome of a single golden query."""

    query_name: str
    passed: bool
    latency_ms: float
    error: str | None = None
    response_hash: str | None = None


class SmokeVerdict(BaseModel):
    """Final verdict from Phase 8 production smoke."""

    passed: bool
    n_queries: int
    n_passed: int
    error_rate: float  # fraction of failed queries
    latency_p95_ms: float
    error_rate_threshold: float
    latency_increase_threshold: float
    query_results: list[SmokeQueryResult]
    rollback_triggered: bool = False
    notes: list[str] = []


# ────────────────────────────────────────────────────────────────
# GIT TAG / ROLLBACK HELPERS
# ────────────────────────────────────────────────────────────────


_GIT_BIN = shutil.which("git") or "/usr/bin/git"


def _git(args: list[str], cwd: Path | str = ".") -> tuple[int, str]:
    """Run a git command synchronously, return (returncode, output).

    Round 6 [I/O sync] (Audit 6 Kimi): callers in async code paths must use
    `_git_async()` or wrap this call in `asyncio.to_thread()`. The sync
    version is preserved for tests and CLI tools that don't have a loop.

    Round 10 fix [S603/S607]: resolve git binary at import time via
    shutil.which() to avoid PATH hijack vector. shell=False (default).
    """
    proc = subprocess.run(  # noqa: S603 — args list, no shell, binary resolved
        [_GIT_BIN, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


async def _git_async(args: list[str], cwd: Path | str = ".") -> tuple[int, str]:
    """Async-friendly git wrapper — runs the sync git call in a worker thread.

    Round 6 fix [I/O sync] (Audit 6 Kimi P1): subprocess.run() blocks the
    asyncio event loop. On a 45-min smoke run with periodic git ops
    (rollback / tag / status), this can stall sample loops. asyncio.to_thread
    delegates the blocking call without releasing the GIL on git itself
    (which is fine — git is fast).
    """
    return await asyncio.to_thread(_git, args, cwd)


def tag_pre_run(run_id: str, repo_dir: Path | str = ".") -> str:
    """Create a `polybuild/run-{run_id}-pre` tag at HEAD for rollback."""
    tag = f"polybuild/run-{run_id}-pre"
    rc, out = _git(["tag", "-f", tag, "HEAD"], cwd=repo_dir)
    if rc != 0:
        logger.warning("pre_tag_failed", tag=tag, output=out)
    else:
        logger.info("pre_tag_created", tag=tag)
    return tag


def rollback_to_tag(tag: str, repo_dir: Path | str = ".", force_clean: bool = False) -> bool:
    """Hard-reset to a tag and remove untracked artefacts.

    Round 5 [T] + Round 6 [T2]:
      - Round 5 added the dirty-tree guard but defaulted `force_clean=True`,
        which 4/6 round-6 audits flagged as a P0: the default bypassed the
        very protection the guard was meant to provide. Phase 8 was calling
        `rollback_to_tag(rollback_tag, repo_dir)` without specifying the
        flag, so a smoke failure during a 45-min run could destroy
        uncommitted dev work on the main branch.
      - Round 6: `force_clean=False` by default. Callers must opt-in
        explicitly, and only when they know the rollback target is a
        dedicated staging worktree (not the main repo).
    """
    rc_status, status_out = _git(["status", "--porcelain"], cwd=repo_dir)
    if rc_status == 0 and status_out and not force_clean:
        logger.error(
            "rollback_refused_dirty_worktree",
            tag=tag,
            uncommitted=status_out[:300],
            hint=(
                "Phase 8 found uncommitted local work and refused to rollback. "
                "Either commit/stash your changes, or pass force_clean=True "
                "explicitly (only safe in a dedicated staging worktree)."
            ),
        )
        return False

    rc, out = _git(["reset", "--hard", tag], cwd=repo_dir)
    if rc != 0:
        logger.error("rollback_failed", tag=tag, output=out)
        return False

    # Only clean untracked files when caller has confirmed it's safe.
    if force_clean:
        rc_clean, _clean_out = _git(["clean", "-fd"], cwd=repo_dir)
        if rc_clean != 0:
            logger.warning("git_clean_failed_after_rollback", tag=tag)

    logger.warning("rollback_completed", tag=tag, force_cleaned=force_clean)
    return True


# ────────────────────────────────────────────────────────────────
# GOLDEN QUERY EXECUTION
# ────────────────────────────────────────────────────────────────


async def _execute_golden(
    endpoint_url: str,
    query: GoldenQuery,
    timeout_s: float = 10.0,
) -> SmokeQueryResult:
    """Execute a single golden query against an HTTP/JSON-RPC endpoint."""
    try:
        import httpx
    except ImportError:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=0.0,
            error="httpx_unavailable",
        )

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": query.method,
        "params": query.params,
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(endpoint_url, json=payload)
        latency_ms = (time.time() - t0) * 1000.0
    except httpx.HTTPError as e:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=(time.time() - t0) * 1000.0,
            error=f"http_error: {e}",
        )

    if resp.status_code != query.expected_status:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=latency_ms,
            error=f"status={resp.status_code} != expected={query.expected_status}",
        )

    try:
        body = resp.json()
    except json.JSONDecodeError:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=latency_ms,
            error="invalid_json_response",
        )

    if "error" in body:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=latency_ms,
            error=f"jsonrpc_error: {body['error']}",
        )

    response_hash: str | None = None
    result = body.get("result", {})

    # Min results check (for list-returning queries)
    if query.expected_min_results is not None:
        # Try common list locations
        items = None
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            for key in ("items", "results", "tools", "articles", "data"):
                if isinstance(result.get(key), list):
                    items = result[key]
                    break
        if items is None or len(items) < query.expected_min_results:
            return SmokeQueryResult(
                query_name=query.name,
                passed=False,
                latency_ms=latency_ms,
                error=f"min_results not met (got {len(items) if items else 0})",
            )

    # Hash match (for fully deterministic responses)
    if query.expected_hash is not None:
        canonical = json.dumps(result, sort_keys=True, ensure_ascii=False)
        response_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if response_hash != query.expected_hash:
            return SmokeQueryResult(
                query_name=query.name,
                passed=False,
                latency_ms=latency_ms,
                response_hash=response_hash,
                error="hash_mismatch_with_baseline",
            )

    return SmokeQueryResult(
        query_name=query.name,
        passed=True,
        latency_ms=latency_ms,
        response_hash=response_hash,
    )


# ────────────────────────────────────────────────────────────────
# PHASE 8 ENTRY
# ────────────────────────────────────────────────────────────────


async def phase_8_production_smoke(
    endpoint_url: str,
    golden_queries: list[GoldenQuery],
    baseline_latency_p95_ms: float | None = None,
    error_rate_threshold: float = 0.0,  # 0% MCP errors (round 4 strict)
    latency_increase_threshold: float = 0.05,  # 5% latency degradation
    monitoring_window_s: int = 300,  # 5 minutes (round 4)
    sample_interval_s: int = 30,
    rollback_tag: str | None = None,
    repo_dir: Path | str = ".",
    rollback_force_clean: bool = False,
) -> SmokeVerdict:
    """Run production smoke test against deployed staging endpoint.

    Procedure:
        1. For `monitoring_window_s` seconds, sample golden queries every
           `sample_interval_s` seconds.
        2. Aggregate error rate and p95 latency.
        3. Compare to thresholds. If exceeded → trigger rollback (if tag provided).

    Args:
        endpoint_url: JSON-RPC endpoint of the staging MCP/server.
        golden_queries: List of golden queries to execute repeatedly.
        baseline_latency_p95_ms: If provided, latency_increase_threshold is
                                 measured against this value.
        error_rate_threshold: Maximum acceptable error rate (default 0.0 = strict).
        latency_increase_threshold: Maximum acceptable latency increase fraction.
        monitoring_window_s: Total monitoring duration (default 5 min).
        sample_interval_s: Time between full golden suite executions.
        rollback_force_clean: Round 6 [T2]: when True, allows `git clean -fd`
                              after rollback. Default False — only enable when
                              rolling back inside a dedicated staging worktree.
        rollback_tag: If provided and smoke fails, run `git reset --hard <tag>`.
        repo_dir: Repository directory for the rollback.
    """
    logger.info(
        "phase_8_start",
        endpoint=endpoint_url,
        n_queries=len(golden_queries),
        window_s=monitoring_window_s,
    )

    all_results: list[SmokeQueryResult] = []
    end_time = time.time() + monitoring_window_s

    while time.time() < end_time:
        # Round 10.2 fix [Kimi RX-004]: return_exceptions=True so a single
        # query raising a non-HTTP exception (ValueError/TypeError on a
        # malformed param) does not blow up the whole gather and lose all
        # other results.
        gathered: list[SmokeQueryResult | BaseException] = await asyncio.gather(
            *(_execute_golden(endpoint_url, q) for q in golden_queries),
            return_exceptions=True,
        )
        round_results: list[SmokeQueryResult] = []
        for q, r in zip(golden_queries, gathered, strict=True):
            if isinstance(r, SmokeQueryResult):
                round_results.append(r)
            else:
                logger.warning(
                    "phase_8_golden_exception_demoted_to_failed",
                    query=q.name,
                    error=f"{type(r).__name__}: {r}",
                )
                round_results.append(
                    SmokeQueryResult(
                        query_name=q.name,
                        passed=False,
                        latency_ms=0.0,
                        error=f"{type(r).__name__}: {r}",
                    )
                )
        all_results.extend(round_results)

        # Early abort if catastrophic
        recent_errors = sum(1 for r in round_results if not r.passed)
        if recent_errors == len(round_results) and recent_errors > 0:
            logger.error("phase_8_catastrophic_round_aborting_early")
            break

        await asyncio.sleep(sample_interval_s)

    n_total = len(all_results)
    n_passed = sum(1 for r in all_results if r.passed)
    error_rate = (n_total - n_passed) / n_total if n_total else 1.0
    latencies = sorted(r.latency_ms for r in all_results if r.passed)
    # Round 5 fix [R]: proper p95 — `int(0.95 * 20) = 19` was the max, not p95.
    # Use ceil(0.95 * n) - 1 (standard "nearest rank" method).
    # Round 6 fix [math-import] (Audit 5 Grok P1): math now imported at top-level.
    p95_idx = max(0, math.ceil(0.95 * len(latencies)) - 1) if latencies else 0
    latency_p95 = latencies[p95_idx] if latencies else 0.0

    notes: list[str] = []
    failed_queries: list[str] = []

    threshold_hit_error = error_rate > error_rate_threshold
    if threshold_hit_error:
        notes.append(f"error_rate {error_rate:.3f} > threshold {error_rate_threshold:.3f}")
        failed_queries = sorted({r.query_name for r in all_results if not r.passed})
        notes.append(f"failed_queries: {failed_queries[:5]}")

    threshold_hit_latency = False
    # Round 5 fix: skip latency check if baseline too small (network jitter swamp)
    if baseline_latency_p95_ms is not None and baseline_latency_p95_ms > 10.0:
        increase = (latency_p95 - baseline_latency_p95_ms) / baseline_latency_p95_ms
        if increase > latency_increase_threshold:
            threshold_hit_latency = True
            notes.append(
                f"latency_p95 {latency_p95:.1f}ms vs baseline "
                f"{baseline_latency_p95_ms:.1f}ms (+{increase:.1%}) > "
                f"threshold +{latency_increase_threshold:.1%}"
            )

    passed = not (threshold_hit_error or threshold_hit_latency)
    rollback_triggered = False

    if not passed and rollback_tag:
        # Round 6 fix [I/O sync] (Audit 6 Kimi P1): rollback_to_tag runs git
        # subprocess synchronously. Delegating to a worker thread keeps the
        # event loop responsive (important on long-running smoke runs).
        rollback_triggered = await asyncio.to_thread(
            rollback_to_tag,
            rollback_tag,
            repo_dir,
            rollback_force_clean,
        )
        if rollback_triggered:
            notes.append(f"rollback_executed to {rollback_tag}")
        else:
            notes.append(f"ROLLBACK_FAILED tag={rollback_tag} — manual intervention")

    logger.info(
        "phase_8_done",
        passed=passed,
        n_total=n_total,
        n_passed=n_passed,
        error_rate=round(error_rate, 4),
        latency_p95_ms=round(latency_p95, 1),
        rollback=rollback_triggered,
    )

    return SmokeVerdict(
        passed=passed,
        n_queries=n_total,
        n_passed=n_passed,
        error_rate=error_rate,
        latency_p95_ms=latency_p95,
        error_rate_threshold=error_rate_threshold,
        latency_increase_threshold=latency_increase_threshold,
        query_results=all_results,
        rollback_triggered=rollback_triggered,
        notes=notes,
    )


# ────────────────────────────────────────────────────────────────
# PHASE 9 CLEANUP (Bonus Gemini)
# ────────────────────────────────────────────────────────────────


def phase_9_cleanup(
    run_id: str,
    staging_dir: Path | str | None = None,
    docker_containers: list[str] | None = None,
    repo_dir: Path | str = ".",
) -> dict[str, Any]:
    """Always-run cleanup. Removes staging worktree, kills containers, prunes cache.

    Should be called from a `finally:` block in the orchestrator regardless of
    run outcome (Gemini's bonus, accepted by all 6 round-4 models implicitly).
    """
    report: dict[str, Any] = {
        "containers_removed": 0,
        "worktree_removed": False,
        "uv_cache_cleaned": False,
        "errors": [],
    }

    # 1. Remove staging Docker containers
    docker_bin = shutil.which("docker")
    for container in docker_containers or []:
        if not docker_bin:
            report["errors"].append("docker_bin_not_found")
            continue
        rc = subprocess.run(  # noqa: S603 — args list, no shell, binary resolved
            [docker_bin, "rm", "-f", container],
            capture_output=True,
            check=False,
        ).returncode
        if rc == 0:
            report["containers_removed"] += 1
        else:
            report["errors"].append(f"docker_rm_failed: {container}")

    # 2. Remove git worktree
    if staging_dir:
        staging_path = Path(staging_dir)
        if staging_path.exists():
            rc, _out = _git(
                ["worktree", "remove", "-f", str(staging_path)], cwd=repo_dir
            )
            if rc == 0:
                report["worktree_removed"] = True
            else:
                # Force fallback: rm -rf the directory + worktree prune
                try:
                    shutil.rmtree(staging_path)
                    _git(["worktree", "prune"], cwd=repo_dir)
                    report["worktree_removed"] = True
                except OSError as e:
                    report["errors"].append(f"rmtree_failed: {e}")

    # 3. Clean uv cache (best-effort, non-blocking).
    # M2B.0 follow-up: ``uv cache clean`` deadlocks for minutes when invoked as
    # a subprocess under an outer ``uv run`` (the parent holds a cache lock the
    # child waits on). Skip the call entirely when ``UV_RUN_RECURSION`` /
    # ``VIRTUAL_ENV`` indicate we are inside a ``uv run`` invocation, and add a
    # short timeout as a defence-in-depth for any other deadlock cause. A slow
    # / locked uv cache leaves ``uv_cache_cleaned=False`` in the report and an
    # informative entry in ``errors`` instead of blocking phase 9.
    uv_bin = shutil.which("uv")
    inside_uv_run = (
        os.environ.get("UV_RUN_RECURSION_DEPTH") is not None
        or os.environ.get("VIRTUAL_ENV") is not None
    )
    if uv_bin and not inside_uv_run:
        try:
            rc = subprocess.run(  # noqa: S603 — args list, binary resolved
                [uv_bin, "cache", "clean"],
                capture_output=True,
                check=False,
                timeout=10,
            ).returncode
            report["uv_cache_cleaned"] = rc == 0
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            report["errors"].append("uv_cache_clean_timeout")
    elif inside_uv_run:
        report["errors"].append("uv_cache_clean_skipped_inside_uv_run")

    logger.info("phase_9_cleanup_done", run_id=run_id, **report)
    return report


async def phase_9_cleanup_async(
    run_id: str,
    staging_dir: Path | str | None,
    docker_containers: list[str] | None,
    repo_dir: Path | str = ".",
) -> dict[str, Any]:
    """Async wrapper around phase_9_cleanup.

    Round 6 fix [I/O sync] (Audit 6 Kimi P1): when called from an async
    context (the orchestrator's outer finally), the sync version blocks the
    event loop on `subprocess.run("docker rm")` and `shutil.rmtree()`.
    Delegating to a worker thread keeps the loop responsive — important if
    other tasks are still running (e.g. status polling, log streaming).
    """
    return await asyncio.to_thread(
        phase_9_cleanup,
        run_id=run_id,
        staging_dir=staging_dir,
        docker_containers=docker_containers,
        repo_dir=repo_dir,
    )


__all__ = [
    "GoldenQuery",
    "SmokeQueryResult",
    "SmokeVerdict",
    "phase_8_production_smoke",
    "phase_9_cleanup",
    "rollback_to_tag",
    "tag_pre_run",
]


# ────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT (Round 5 fix [A] — unanimous: deploy_staging.sh
# was calling `python -m polybuild.phases.phase_8_prod_smoke`
# but the module had no __main__).
# ────────────────────────────────────────────────────────────────


def _load_golden_file(path: str | Path) -> list[GoldenQuery]:
    """Load and validate a golden queries JSON file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Golden file must contain a JSON list: {path}")
    return [GoldenQuery.model_validate(item) for item in raw]


async def _amain() -> int:
    """Async entrypoint usable from `python -m polybuild.phases.phase_8_prod_smoke`."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="polybuild-phase-8",
        description="POLYBUILD Phase 8 production smoke (round 4/5 finalized).",
    )
    parser.add_argument("--endpoint", required=True, help="JSON-RPC URL")
    parser.add_argument("--golden", required=True, help="Path to golden queries JSON")
    parser.add_argument(
        "--rollback-tag",
        default=None,
        help="Git tag to roll back to on failure (default: no rollback)",
    )
    parser.add_argument(
        "--repo-dir", default=".", help="Repo dir for rollback (default: cwd)"
    )
    parser.add_argument(
        "--window-s", type=int, default=300, help="Monitoring window seconds"
    )
    parser.add_argument(
        "--sample-interval-s",
        type=int,
        default=30,
        help="Time between full golden suite executions",
    )
    parser.add_argument("--baseline-p95-ms", type=float, default=None)
    parser.add_argument(
        "--error-rate-threshold", type=float, default=0.0, help="0.0=strict"
    )
    parser.add_argument("--latency-increase-threshold", type=float, default=0.05)
    parser.add_argument(
        "--rollback-force-clean",
        action="store_true",
        help=(
            "Round 6 [T2]: allow `git clean -fd` after rollback. Use ONLY when "
            "the rollback target is a dedicated staging worktree (default off)."
        ),
    )
    args = parser.parse_args()

    try:
        goldens = _load_golden_file(args.golden)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        # CLI entrypoint — direct stderr output is the expected UX here.
        sys.stderr.write(
            json.dumps({"error": f"golden_load_failed: {e}"}) + "\n"
        )
        return 2

    verdict = await phase_8_production_smoke(
        endpoint_url=args.endpoint,
        golden_queries=goldens,
        baseline_latency_p95_ms=args.baseline_p95_ms,
        error_rate_threshold=args.error_rate_threshold,
        latency_increase_threshold=args.latency_increase_threshold,
        monitoring_window_s=args.window_s,
        sample_interval_s=args.sample_interval_s,
        rollback_tag=args.rollback_tag,
        repo_dir=args.repo_dir,
        rollback_force_clean=args.rollback_force_clean,
    )
    sys.stdout.write(verdict.model_dump_json(indent=2) + "\n")
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))
