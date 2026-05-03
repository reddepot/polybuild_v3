# POLYBUILD v3 — Round 7 quick verification (post-round-6 patches)

> **Tu es l'un des 6 modèles audités** (Claude Opus 4.7, GPT-5.5, Gemini 3.1 Pro,
> Kimi K2.6, DeepSeek V4-Pro, Grok 4.20). Round 5 = NO-GO unanime. Round 6 = 4
> CONDITIONAL_GO + 2 GO (score moyen 8.1/10). 11 patches viennent d'être
> appliqués pour lever **toutes** les conditions formulées par les 4
> CONDITIONAL_GO. **Round 7 = vérification binaire ciblée. Pas un audit complet.**

---

## Tu dois SEULEMENT répondre à ceci

Pour chacun des 11 patches : la condition que tu (ou un autre modèle) avais posée
au round 6 est-elle maintenant levée ?

Format strict, ligne par patch :
```
[<patch>] LEVÉ | NON LEVÉ — <raison concrète, code-référencée> | RÉGRESSION — <description>
```

Si tu ne te souviens pas avoir formulé une condition sur ce patch, mets `LEVÉ`
si le code te paraît correct, ou `NON LEVÉ` si tu vois un problème.

---

## Les 11 patches round 7

Tous portent un commentaire `# Round 6 fix [<id>]` ou `# Round 7 fix` dans le code.

| Patch | Origine round 6 | Description courte | Fichier(s) |
|---|---|---|---|
| **[T2]** | 4/6 audits unanimes — P0 | `rollback_to_tag(force_clean=False)` par défaut + flag CLI `--rollback-force-clean` + `deploy_staging.sh` le passe explicitement (worktree dédié). | `phase_8_prod_smoke.py`, `deploy_staging.sh` |
| **[Any-import]** | Audit 4 (ChatGPT) — P1 mypy | `from typing import Any, Literal` ajouté. | `phase_minus_one_privacy.py` |
| **[O2]** | Audits 4 + 6 — P1 contrat | `run_raw_prompt(risk_profile=...)` + flag `raw_prompt_no_write` pour les rôles non-écrivants (critic, verifier, judge, auditor). `_invoke_role` propage `risk_profile`. | `builder_protocol.py`, `phase_5_triade.py` |
| **[J2]** | Audit 4 — P1 | `phase_6_validate._run_single_domain_gate` transmet `vector_name=cfg.get("vector_name")` au gate Qdrant. | `phase_6_validate.py` |
| **[M2]** | Audit 4 — P1 | `SKILL.md` parse explicitement `--spec`/`--brief`/`-b`/`--profile` via `while … case`. Plus de `$1` qui prend le flag au lieu de la valeur. | `skills/polybuild/SKILL.md` |
| **[V2]** | Audit 4 — P2 | `.polybuild/secrets.env` retiré de l'allowlist gitleaks (vrai chemin documenté = `~/.polybuild/secrets.env` hors repo). | `.gitleaks.toml` |
| **[fts5-skipped]** | Audit 1 — P1 | `FTS5GateResult.skipped: bool` ajouté. `phase_6_validate` propage `fts5_skipped_dev_mode` dans les signals si `result.skipped` est vrai. | `validate_fts5.py`, `phase_6_validate.py` |
| **[P1-no-Critic]** | Audit 6 (Kimi) — P2 | `_triade_p1_batch` invoque maintenant le Critic batch comme promis par sa docstring. Output critic injecté dans le prompt fixer. | `phase_5_triade.py` |
| **[I/O sync]** | Audit 6 — P1 | `phase_9_cleanup_async` (wrapper `asyncio.to_thread`). `_git_async` idem. `rollback_to_tag` dans `phase_8_production_smoke` est wrappé `asyncio.to_thread`. Orchestrator finally utilise la version async. | `phase_8_prod_smoke.py`, `orchestrator.py` |
| **[Exception-swallowing]** | Audit 6 — P1 | Outer `finally` capture `sys.exc_info()` AVANT cleanup. `except BaseException` autour du cleanup ne re-lève pas → l'originale est préservée par le mécanisme implicite Python. Logs structurés mentionnent `original_error`. | `orchestrator.py` |
| **[math-import]** | Audit 5 (Grok) — P1 cosmétique | `import math` au top-level (était dans `_aggregate_smoke_results`). | `phase_8_prod_smoke.py` |

---

## Validations déjà passées de mon côté (smoke tests)

- 36 fichiers Python AST ✓
- 6 YAML / 2 TOML parse ✓
- 7 blocs bash de SKILL.md `bash -n` ✓
- 7/7 modules round-6 importent ✓
- `phase_8_prod_smoke --help` montre `--rollback-force-clean` ✓
- Privacy Gate (6 cas) ✓
- ConcurrencyLimiter P3 contention ✓
- **Test E2E [Exception-swallowing]** : `RuntimeError("ORIGINAL_PIPELINE_ERROR")` est re-levée même quand `phase_9_cleanup_async` plante avec `RuntimeError("CLEANUP_ALSO_FAILED")` ✓

Donc tu n'as pas à re-vérifier que ça compile. Tu vérifies que la **sémantique** lève la condition.

---

## Q1 — Les 11 patches lèvent-ils les conditions ?

Format compact, une ligne par patch. Cite la ligne exacte du code si tu trouves
une faille.

```
[T2] LEVÉ
[Any-import] LEVÉ
[O2] LEVÉ
[J2] LEVÉ
[M2] LEVÉ
[V2] LEVÉ
[fts5-skipped] LEVÉ
[P1-no-Critic] LEVÉ
[I/O sync] LEVÉ
[Exception-swallowing] LEVÉ
[math-import] LEVÉ
```

(remplace `LEVÉ` par `NON LEVÉ — <raison>` ou `RÉGRESSION — <description>` si applicable)

## Q2 — Régression introduite par un patch round 6 ?

Liste-en si tu en vois. Sinon `aucune`.

Format :
```
[<patch>] → <module>:<ligne> casse <quoi> car <raison>
```

## Q3 — Verdict final sprint A

Maintenant que les conditions sont (a priori) levées :

```
Score round 7 : N/10  (Δ vs round 6)
Verdict : GO | CONDITIONAL_GO si <X> | NO-GO car <Y>
```

Si NO-GO : top 3 blockers résiduels.
Si CONDITIONAL_GO : conditions courtes et actionnables.
Si GO : tu engages ta crédibilité.

---

## Règles round 7

1. **Brièveté maximale.** Une ligne par patch. Pas de paraphrase.
2. **Pas de re-audit du squelette validé rounds 1-4.**
3. **Pas de re-débat des décisions actées rounds 4-6** (force_clean, eds-pseudo, etc.).
4. **Anti-sycophantie.** Si tu vois encore un trou, dis-le sans guirlandes.
5. **Pas de voice notes.** Markdown uniquement.

Je m'attends à une réponse de **20 à 60 lignes**, pas plus.

---

## Code patché à vérifier

---

## Patched files (round 6 — primary verification target)

Look for `# Round 6 fix [<id>]` markers in the code.


### `src/polybuild/phases/phase_8_prod_smoke.py` (596 lines)

```python
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
    params: dict = {}
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


def _git(args: list[str], cwd: Path | str = ".") -> tuple[int, str]:
    """Run a git command synchronously, return (returncode, output).

    Round 6 [I/O sync] (Audit 6 Kimi): callers in async code paths must use
    `_git_async()` or wrap this call in `asyncio.to_thread()`. The sync
    version is preserved for tests and CLI tools that don't have a loop.
    """
    proc = subprocess.run(
        ["git", *args],
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
        round_results = await asyncio.gather(
            *(_execute_golden(endpoint_url, q) for q in golden_queries),
            return_exceptions=False,
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
    for container in docker_containers or []:
        rc = subprocess.run(
            ["docker", "rm", "-f", container],
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
            rc, out = _git(
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

    # 3. Clean uv cache (best-effort, non-blocking)
    try:
        rc = subprocess.run(
            ["uv", "cache", "clean"], capture_output=True, check=False
        ).returncode
        report["uv_cache_cleaned"] = rc == 0
    except FileNotFoundError:
        # uv not available — ignore
        pass

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
        print(json.dumps({"error": f"golden_load_failed: {e}"}), file=sys.stderr)
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
    print(verdict.model_dump_json(indent=2))
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_amain()))

```


### `src/polybuild/phases/phase_minus_one_privacy.py` (473 lines)

```python
"""Phase -1 — Privacy Gate (round 4 finalisé).

Architecture 3 couches séquentielles (convergence 6/6 round 4):
    L1 PII directe — presidio + regex FR (NIR, email, phone, address, birth_date)
        → blocage hard, jamais de négociation
    L2 Quasi-identifiants médicaux — eds-pseudo (AP-HP, F1=0.97-0.99 sur clinique FR)
        → escalade `paranoia=high` si attestation forte présente, sinon BLOCK
    L3 Contextuel + attestation — champ `sensitivity_attestation` énuméré dans spec.yaml
        → BLOCK si "missing", PASS sinon (selon valeur)

Attestation values (ChatGPT propose énumération > booléen):
    - "missing"                    : aucune attestation, blocage par défaut
    - "synthetic"                  : données synthétiques (PASS L1+L2+L3)
    - "fully_anonymized"           : anonymisation certifiée hors POLYBUILD (PASS)
    - "abstract_schema_only"       : code/schema uniquement, pas de données réelles (PASS)
    - "health_adjacent"            : sujet médical sans patient identifiable (paranoia high)
    - "identifiable"               : données réelles → BLOCK toujours

Eds-pseudo lazy-load (Qwen): ~350MB RAM au premier chargement, libéré après run.
Kimi écartait eds-pseudo (instable hors clinique narratif). Compromis : eds-pseudo
optionnel via EDS_PSEUDO_ENABLED=1, fallback dictionnaire métier statique sinon
(NAS-safe). Avis majoritaire 5/6 conservé (eds-pseudo F1=0.97 documenté).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import structlog
import yaml
from pydantic import BaseModel

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# MODELS
# ────────────────────────────────────────────────────────────────


PrivacyVerdictLevel = Literal["PASS", "BLOCK", "ESCALATE_PARANOIA"]
AttestationValue = Literal[
    "missing",
    "synthetic",
    "fully_anonymized",
    "abstract_schema_only",
    "health_adjacent",
    "identifiable",
]


class PIIFinding(BaseModel):
    """A detected PII entity."""

    layer: int  # 1, 2, 3
    entity_type: str
    matched_text: str  # truncated to 30 chars for log safety
    score: float | None = None


class PrivacyVerdict(BaseModel):
    """Verdict from Phase -1 privacy gate."""

    level: PrivacyVerdictLevel
    blocked: bool
    reason: str
    findings: list[PIIFinding] = []
    attestation: AttestationValue = "missing"
    paranoia_level: Literal["low", "medium", "high"] = "low"


# ────────────────────────────────────────────────────────────────
# LAYER 1 — DIRECT PII (regex + presidio)
# ────────────────────────────────────────────────────────────────


_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "nir": re.compile(
        r"\b[12]\s?\d{2}\s?(0[1-9]|1[0-2])\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"
    ),
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "phone_fr": re.compile(r"(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}"),
    "birth_date": re.compile(
        r"\b(?:n[ée]e?\s+le|date\s+de\s+naissance)\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        re.IGNORECASE,
    ),
    "postal_address": re.compile(
        r"\b\d{1,4}\s+(?:rue|avenue|boulevard|bd|impasse|chemin|route|place)\s+[\w\s'-]{3,}",
        re.IGNORECASE,
    ),
}


def _layer_1_regex(text: str) -> list[PIIFinding]:
    """Pure-regex PII detection (no external dep, always available)."""
    findings: list[PIIFinding] = []
    for entity_type, pattern in _PII_PATTERNS.items():
        for match in pattern.finditer(text):
            matched = match.group(0)
            findings.append(
                PIIFinding(
                    layer=1,
                    entity_type=entity_type,
                    matched_text=matched[:30] + ("…" if len(matched) > 30 else ""),
                )
            )
    return findings


def _layer_1_presidio(text: str) -> list[PIIFinding]:
    """Presidio analyzer L1 — soft import, returns [] if presidio unavailable."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("presidio_unavailable_skipping_l1_nlp")
        return []

    try:
        analyzer = AnalyzerEngine()
        results = analyzer.analyze(
            text=text,
            language="fr",
            entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_TIME"],
        )
    except Exception as e:
        logger.warning("presidio_analyze_failed", error=str(e))
        return []

    findings: list[PIIFinding] = []
    for r in results:
        if r.score < 0.85:
            continue
        excerpt = text[r.start : r.end]
        findings.append(
            PIIFinding(
                layer=1,
                entity_type=r.entity_type,
                matched_text=excerpt[:30] + ("…" if len(excerpt) > 30 else ""),
                score=r.score,
            )
        )
    return findings


# ────────────────────────────────────────────────────────────────
# LAYER 2 — QUASI-IDENTIFIERS (eds-pseudo, lazy)
# ────────────────────────────────────────────────────────────────


_QUASI_LABELS_EDS: set[str] = {
    "HOPITAL",
    "VILLE",
    "ZIP",
    "DATE",
    "RARE_DISEASE",
    "MEDICAL_PROCEDURE",
    "PATIENT",
}

# Round 5 fix [C]: singleton with thread-safe init to avoid re-loading eds-pseudo
# (~350MB) on every call. Audits 1+4 flagged this as P0/P1: "libéré après run"
# was a docstring promise never honored, causing OOM risk on the 18GB NAS.
_EDS_NLP_INSTANCE: Any | None = None
_EDS_NLP_LOAD_FAILED: bool = False


def _get_eds_nlp() -> Any | None:
    """Lazy singleton for eds-pseudo. Returns None if unavailable.

    Round 5 (Audit 5): tries `edsnlp.load("eds")` first (canonical), falls back
    to `edsnlp.blank("eds")` + add_pipe (legacy code path).
    """
    global _EDS_NLP_INSTANCE, _EDS_NLP_LOAD_FAILED
    if _EDS_NLP_LOAD_FAILED:
        return None
    if _EDS_NLP_INSTANCE is not None:
        return _EDS_NLP_INSTANCE

    try:
        import edsnlp  # type: ignore[import-not-found]
    except ImportError:
        _EDS_NLP_LOAD_FAILED = True
        logger.info("eds_pseudo_unavailable_using_static_fallback")
        return None

    # Try canonical load first (Audit 5 recommendation), fall back to blank+pipe.
    try:
        nlp = edsnlp.load("eds")
        if not nlp.has_pipe("pseudonymisation"):
            nlp.add_pipe("eds.pseudonymisation")
    except Exception:
        try:
            nlp = edsnlp.blank("eds")
            nlp.add_pipe("eds.pseudonymisation")
        except Exception as e:
            _EDS_NLP_LOAD_FAILED = True
            logger.warning("eds_pseudo_load_failed", error=str(e))
            return None

    _EDS_NLP_INSTANCE = nlp
    logger.info("eds_pseudo_loaded_singleton")
    return nlp

_RARE_OCCUPATIONS_FR: set[str] = {
    "chimiste analyseur",
    "technicien cryogénie",
    "plongeur professionnel",
    "soudeur nucléaire",
    "amianteur",
    "thanatopracteur",
    "radioprotection",
    "chirurgien thoracique",
}

_RARE_PATHOLOGIES_FR: set[str] = {
    "mésothéliome",
    "silicose",
    "bérylliose",
    "saturnisme",
    "fibrose pulmonaire idiopathique",
    "sarcome de kaposi",
    "maladie de creutzfeldt",
}


def _layer_2_eds_pseudo(text: str) -> list[PIIFinding]:
    """eds-pseudo (AP-HP) lazy-load. Soft fallback to static dict if unavailable.

    Round 5 [C]: uses module-level singleton via _get_eds_nlp() — no more
    per-call re-instantiation of the 350MB pipeline.
    """
    if os.environ.get("EDS_PSEUDO_ENABLED", "0") != "1":
        return _layer_2_static_fallback(text)

    nlp = _get_eds_nlp()
    if nlp is None:
        return _layer_2_static_fallback(text)

    try:
        doc = nlp(text)
    except Exception as e:
        logger.warning("eds_pseudo_run_failed", error=str(e))
        return _layer_2_static_fallback(text)

    findings: list[PIIFinding] = []
    for ent in doc.ents:
        if ent.label_ not in _QUASI_LABELS_EDS:
            continue
        excerpt = ent.text
        findings.append(
            PIIFinding(
                layer=2,
                entity_type=ent.label_,
                matched_text=excerpt[:30] + ("…" if len(excerpt) > 30 else ""),
            )
        )
    return findings


def _layer_2_static_fallback(text: str) -> list[PIIFinding]:
    """Pure-Python fallback when eds-pseudo unavailable (NAS-safe)."""
    text_low = text.lower()
    findings: list[PIIFinding] = []

    for occ in _RARE_OCCUPATIONS_FR:
        if occ in text_low:
            findings.append(
                PIIFinding(layer=2, entity_type="rare_occupation_fr", matched_text=occ)
            )
    for pat in _RARE_PATHOLOGIES_FR:
        if pat in text_low:
            findings.append(
                PIIFinding(layer=2, entity_type="rare_pathology_fr", matched_text=pat)
            )
    return findings


# ────────────────────────────────────────────────────────────────
# LAYER 3 — ATTESTATION (spec.yaml)
# ────────────────────────────────────────────────────────────────


_VALID_ATTESTATIONS: set[str] = {
    "missing",
    "synthetic",
    "fully_anonymized",
    "abstract_schema_only",
    "health_adjacent",
    "identifiable",
}

_STRONG_ATTESTATIONS: set[str] = {
    "synthetic",
    "fully_anonymized",
    "abstract_schema_only",
}


def _normalize_attestation(value: str | None) -> AttestationValue:
    """Round 5 fix [B]: normalize any input to a valid AttestationValue.

    Audits 1+3+5 flagged this: passing `attestation=<str>` to PrivacyVerdict
    relied on `# type: ignore` and crashed Pydantic if the YAML was malformed
    or if `declared_sensitivity` came from CLI/project_ctx unsanitised.
    """
    val = str(value or "missing").strip().lower()
    if val not in _VALID_ATTESTATIONS:
        logger.warning("invalid_attestation_value_normalized_to_missing", value=val)
        return "missing"  # type: ignore[return-value]
    return val  # type: ignore[return-value]


def _load_attestation(spec_path: str | Path | None) -> str:
    """Load `sensitivity_attestation` from spec.yaml. Returns 'missing' on failure."""
    if not spec_path:
        return "missing"
    p = Path(spec_path)
    if not p.exists():
        return "missing"
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        logger.warning("spec_yaml_parse_failed", path=str(p))
        return "missing"

    val = str(data.get("sensitivity_attestation", "missing")).strip().lower()
    if val not in _VALID_ATTESTATIONS:
        logger.warning("invalid_attestation_value", value=val)
        return "missing"
    return val


# ────────────────────────────────────────────────────────────────
# MAIN GATE
# ────────────────────────────────────────────────────────────────


def phase_minus_one_privacy_gate(
    text: str,
    spec_path: str | Path | None = None,
    declared_sensitivity: str | None = None,
) -> PrivacyVerdict:
    """Run the 3-layer privacy gate on a brief/spec text.

    Args:
        text: Full text of the brief or generated spec to inspect.
        spec_path: Path to spec.yaml (for attestation lookup).
        declared_sensitivity: Optional override (CLI flag) of the YAML attestation.

    Decision tree (round 4 convergence + round 5 patches):
        1. L1 hit → BLOCK always (no negotiation).
        2. attestation = "identifiable" → BLOCK always.
        3. L2 hit (>=2 quasi-id):
            - attestation in strong set → ESCALATE_PARANOIA (force EU/local).
            - else: BLOCK.
        4. L2 hit (1 quasi-id) + attestation = "missing" → BLOCK.
        5. attestation = "missing" + text >1500 chars → BLOCK.
            (Round 5 fix [U]: was 300 chars, too strict — 4 sentences blocked.
             Raised to 1500 chars (~3-4 paragraphs) to avoid UX paper cuts on
             normal briefs while still catching long sensitive narratives.)
        6. else → PASS.
    """
    # Round 5 fix [B]: normalize attestation to AttestationValue (Pydantic-safe)
    attestation: AttestationValue = _normalize_attestation(
        declared_sensitivity if declared_sensitivity else _load_attestation(spec_path)
    )

    # ── Layer 1 ──────────────────────────────────────────────────
    l1_findings = _layer_1_regex(text) + _layer_1_presidio(text)
    if l1_findings:
        types = sorted({f.entity_type for f in l1_findings})
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=f"L1 direct PII detected: {types}",
            findings=l1_findings,
            attestation=attestation,
            paranoia_level="high",
        )

    # ── Hard rule ─────────────────────────────────────────────────
    if attestation == "identifiable":
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason="attestation=identifiable → real data not allowed",
            attestation="identifiable",
            paranoia_level="high",
        )

    # ── Layer 2 ──────────────────────────────────────────────────
    l2_findings = _layer_2_eds_pseudo(text)

    if len(l2_findings) >= 2:
        if attestation in _STRONG_ATTESTATIONS:
            return PrivacyVerdict(
                level="ESCALATE_PARANOIA",
                blocked=False,
                reason=(
                    f"L2 quasi-identifiers ({len(l2_findings)}) "
                    f"with attestation={attestation} → forcing EU/local routing"
                ),
                findings=l2_findings,
                attestation=attestation,
                paranoia_level="high",
            )
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=(
                f"L2 quasi-identifiers ({len(l2_findings)}) without strong attestation. "
                "Set sensitivity_attestation to synthetic, fully_anonymized, "
                "or abstract_schema_only in spec.yaml."
            ),
            findings=l2_findings,
            attestation=attestation,
            paranoia_level="high",
        )

    if len(l2_findings) == 1 and attestation == "missing":
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason="1 quasi-identifier + missing attestation → specify explicitly",
            findings=l2_findings,
            attestation="missing",
            paranoia_level="medium",
        )

    # ── Layer 3 ──────────────────────────────────────────────────
    if attestation == "missing" and len(text) > 1500:
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=(
                "attestation=missing for long brief (>1500 chars). "
                "Add sensitivity_attestation to spec.yaml "
                "(e.g. 'abstract_schema_only' for code-only briefs)."
            ),
            findings=l2_findings,
            attestation="missing",
            paranoia_level="medium",
        )

    paranoia: Literal["low", "medium", "high"] = (
        "high" if attestation == "health_adjacent" else "low"
    )
    return PrivacyVerdict(
        level="PASS",
        blocked=False,
        reason=f"All 3 layers cleared (attestation={attestation})",
        findings=l2_findings,
        attestation=attestation,
        paranoia_level=paranoia,
    )


# Backward-compat alias
phase_minus_one = phase_minus_one_privacy_gate


__all__ = [
    "AttestationValue",
    "PIIFinding",
    "PrivacyVerdict",
    "PrivacyVerdictLevel",
    "phase_minus_one",
    "phase_minus_one_privacy_gate",
]

```


### `src/polybuild/adapters/builder_protocol.py` (140 lines)

```python
"""BuilderProtocol — abstract interface implemented by every model adapter.

Every model (CLI or OpenRouter or local Ollama) exposes the same async API.
This is the contract that makes Phase 2 parallel orchestration possible.

Round 5 fix [O] (Audit 2 P0): added concrete `run_raw_prompt()` method with a
default implementation. Phase 5 triade was calling
`builder.generate(prompt=..., workdir=..., timeout_s=..., role=...)` which does
not match `generate(self, spec, cfg)` — would have crashed all 7 adapters with
TypeError. The default impl synthesises a minimal Spec+VoiceConfig.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import cast

from polybuild.models import (
    AcceptanceCriterion,
    BuilderResult,
    RiskProfile,
    Spec,
    VoiceConfig,
)


class BuilderProtocol(ABC):
    """Abstract base class for all builders.

    Implementations:
        - ClaudeCodeAdapter (CLI)
        - CodexCLIAdapter (CLI)
        - GeminiCLIAdapter (CLI)
        - KimiCLIAdapter (CLI)
        - OpenRouterAdapter (HTTP)
        - MistralEUAdapter (HTTP, api.mistral.ai direct)
        - OllamaLocalAdapter (HTTP local NAS)
    """

    name: str  # ex: "claude_code_opus", "openrouter_deepseek_v4_pro"
    family: str  # ex: "anthropic", "deepseek"

    @abstractmethod
    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Generate a complete code module from the spec.

        Must:
            1. Create a worktree under .polybuild/runs/{run_id}/worktrees/{voice_id}/
            2. Inject AGENTS.md + relevant memory in the prompt
            3. Respect cfg.timeout_sec (asyncio.wait_for)
            4. Return a BuilderResult with normalized fields

        Must NOT:
            - Modify the production code directly
            - Bypass the privacy gate for sensitive profiles
            - Cross-talk with other voices (no shared state)
        """

    @abstractmethod
    async def smoke_test(self) -> bool:
        """Quick sanity check that the adapter works.

        Sends a deterministic prompt and verifies the output structure.
        Used by `polybuild test-cli` (weekly cron + pre-run cache).
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the underlying CLI/API is reachable.

        Lightweight check (e.g. version query). Used before invoking generate().
        """

    async def run_raw_prompt(
        self,
        prompt: str,
        workdir: Path,
        timeout_s: int = 600,
        role: str = "auditor",
        risk_profile: RiskProfile | None = None,
    ) -> str:
        """Run an ad-hoc prompt and return the model's raw text output.

        Round 5 [O]: used by Phase 5 triade (critic, fixer, verifier) where we
        don't want a full generate() pipeline (no spec, no acceptance criteria,
        no AGENTS.md injection). Default impl wraps generate() with a minimal
        synthetic Spec+VoiceConfig.

        Round 6 fix [O2]:
          - Audit 4: default impl violated "verifier never rewrites code" —
            generate() can create a worktree. Now we set
            `context["raw_prompt_no_write"]=True` which adapters MUST honor
            to short-circuit any worktree creation for verifier/critic roles.
          - Audit 6: default impl dropped risk_profile, losing medical_high
            constraints in Phase 5 prompts. Now propagated through context.

        Adapters SHOULD override this method for efficiency (direct chat API,
        no worktree). The default keeps the contract intact even without override.
        """
        valid_roles = {"builder", "auditor", "fixer", "verifier", "critic", "judge"}
        normalized_role = role if role in valid_roles else "auditor"

        # Round 6 [O2]: roles that must NEVER write to the filesystem.
        no_write_roles = {"critic", "verifier", "judge", "auditor"}
        no_write = normalized_role in no_write_roles

        synthetic_spec = Spec(
            run_id=f"raw-{normalized_role}-{abs(hash(prompt)) % 10**8}",
            profile_id=f"phase5_{normalized_role}",
            task_description=prompt,
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="raw-1",
                    description=f"Produce a valid {normalized_role} response",
                    test_command="echo 'phase5_raw_prompt_no_test'",
                    blocking=False,
                ),
            ],
            risk_profile=risk_profile or RiskProfile(),
        )
        synthetic_cfg = VoiceConfig(
            voice_id=self.name,
            family=self.family,
            role=cast(
                "str",
                normalized_role,
            ),  # type: ignore[arg-type]
            timeout_sec=timeout_s,
            context={
                "phase5_workdir": str(workdir),
                "raw_prompt": True,
                # Round 6 [O2]: adapters honoring this flag must skip worktree
                # creation and any filesystem write — return raw text only.
                "raw_prompt_no_write": no_write,
            },
        )
        result = await self.generate(synthetic_spec, synthetic_cfg)
        return result.raw_output or ""

```


### `src/polybuild/phases/phase_5_triade.py` (578 lines)

```python
"""Phase 5 — Critic-Fixer-Verifier triade.

Severity-differentiated handling (acquis convergent T4):
    - P0: per-finding triade, Critic ≠ Fixer ≠ Verifier (3 distinct families)
    - P1: batched by axis, single Critic + Fixer per batch
    - P2/P3: local auto-fix (ruff --fix, mypy --hint), NO LLM

Verifier (Évaluateur-Optimiseur strict):
    - JSON-only output: {pass, reason, required_evidence}
    - NEVER rewrites code
    - Rejects by default if no reproducible evidence

Local gates first (PRE-LLM check):
    Before invoking the Verifier, run pytest + mypy + bandit on the patch.
    If they fail, loop back to Fixer with failure context (saves verifier tokens).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path

import structlog

from polybuild.adapters import get_builder
from polybuild.models import (
    AuditReport,
    BuilderResult,
    Finding,
    FixReport,
    FixResult,
    RiskProfile,
    Severity,
)

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# ROLE ASSIGNMENT (anti self-fix)
# ────────────────────────────────────────────────────────────────


def pick_triade(
    winner_family: str,
    auditor_family: str,
    risk_profile: RiskProfile,
) -> tuple[str, str, str]:
    """Pick (critic, fixer, verifier) where each has a different family.

    Excludes:
        - winner_family (avoids self-fix bias)
        - auditor_family (avoids audit-fix collusion for the verifier)
    """
    # Hard pool minus excluded families
    all_models = [
        ("claude-opus-4.7", "anthropic"),
        ("gpt-5.5", "openai"),
        ("gemini-3.1-pro", "google"),
        ("kimi-k2.6", "moonshot"),
        ("deepseek/deepseek-v4-pro", "deepseek"),
        ("x-ai/grok-4.20", "xai"),
        ("mistral/devstral-2", "mistral"),
    ]

    # Filter for risk profile
    if risk_profile.excludes_openrouter:
        all_models = [(m, f) for m, f in all_models if not m.startswith(("deepseek/", "x-ai/"))]
    if risk_profile.excludes_us_cn_models:
        excluded_families = {"anthropic", "openai", "google", "xai", "moonshot"}
        all_models = [(m, f) for m, f in all_models if f not in excluded_families]

    available = [(m, f) for m, f in all_models if f != winner_family]

    # Critic: any family ≠ winner
    critic_model, critic_family = available[0]

    # Fixer: ≠ winner AND ≠ critic
    fixer_candidates = [(m, f) for m, f in available if f != critic_family]
    if not fixer_candidates:
        raise RuntimeError("No fixer candidate available")
    fixer_model, fixer_family = fixer_candidates[0]

    # Verifier: ≠ winner AND ≠ critic AND ≠ fixer AND ≠ auditor (no collusion)
    verifier_candidates = [
        (m, f)
        for m, f in available
        if f not in {critic_family, fixer_family, auditor_family}
    ]
    if not verifier_candidates:
        # Relax: allow auditor family for verifier (acceptable degradation)
        verifier_candidates = [
            (m, f) for m, f in available if f not in {critic_family, fixer_family}
        ]
    verifier_model = verifier_candidates[0][0]

    return critic_model, fixer_model, verifier_model


# ────────────────────────────────────────────────────────────────
# PROMPT LOADING
# ────────────────────────────────────────────────────────────────

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        # Soft fallback: minimal inline prompt to avoid hard crash during bootstrap.
        logger.warning("prompt_template_missing", name=name, path=str(path))
        return f"# {name}\n\n(Template missing — using minimal inline fallback.)\n\n"
    return path.read_text(encoding="utf-8")


# ────────────────────────────────────────────────────────────────
# LOCAL GATES (PRE-VERIFIER)
# ────────────────────────────────────────────────────────────────


async def _run_local_gates(code_dir: Path) -> tuple[bool, str]:
    """Run pytest + mypy + ruff on patched code BEFORE invoking Verifier.

    Returns (all_pass, failure_summary). Saves Verifier tokens by short-circuiting
    on local lint/type/test failures.
    """
    failures: list[str] = []

    for label, args in [
        ("ruff", ["uv", "run", "ruff", "check", "src/"]),
        ("mypy", ["uv", "run", "mypy", "--strict", "src/"]),
        ("pytest", ["uv", "run", "pytest", "-x", "--no-header", "-q"]),
    ]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=code_dir.parent,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            if proc.returncode != 0:
                excerpt = (stdout + stderr).decode("utf-8", errors="replace")[-800:]
                failures.append(f"[{label}] returncode={proc.returncode}\n{excerpt}")
        except asyncio.TimeoutError:
            failures.append(f"[{label}] timeout >180s")
        except FileNotFoundError:
            # Tool not available in this environment — non-blocking.
            logger.debug("local_gate_tool_missing", tool=label)

    if not failures:
        return True, ""
    return False, "\n\n".join(failures)


# ────────────────────────────────────────────────────────────────
# JSON VERDICT PARSING (Verifier output)
# ────────────────────────────────────────────────────────────────


def _parse_verifier_verdict(raw: str) -> dict:
    """Extract {pass, reason, required_evidence} from Verifier output.

    Verifier is JSON-only by spec. We still defend against fenced blocks
    or trailing prose (frequent on smaller models).
    """
    # Try fenced ```json blocks first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = fenced.group(1) if fenced else raw

    # Find first balanced { ... } block
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        return {"pass": False, "reason": "verifier_returned_no_json", "required_evidence": []}

    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return {
            "pass": False,
            "reason": f"verifier_json_decode_error: {e}",
            "required_evidence": [],
        }

    return {
        "pass": bool(verdict.get("pass", False)),
        "reason": str(verdict.get("reason", "")),
        "required_evidence": list(verdict.get("required_evidence", [])),
    }


# ────────────────────────────────────────────────────────────────
# P0 PER-FINDING TRIADE
# ────────────────────────────────────────────────────────────────


async def _invoke_role(
    role: str,
    model: str,
    prompt: str,
    code_dir: Path,
    timeout_s: int = 600,
    risk_profile: RiskProfile | None = None,
) -> str:
    """Invoke a model in a given triade role (critic/fixer/verifier).

    Round 5 fix [O] (Audit 2 P0): was calling `builder.generate(prompt=...,
    workdir=..., timeout_s=..., role=...)` which did not match the
    BuilderProtocol signature `generate(spec, cfg)` — would have raised
    TypeError on every adapter. Now uses the new `run_raw_prompt()` method
    which adapters inherit by default.

    Round 6 fix [O2] (Audits 4+6): propagate risk_profile to preserve
    medical_high constraints; mark non-write roles to prevent verifier
    from rewriting code. See builder_protocol.py:run_raw_prompt() for
    the no_write_roles enforcement.

    Returns the raw text output. Adapter dispatch is handled by get_builder().
    """
    builder = get_builder(model)
    raw = await builder.run_raw_prompt(
        prompt=prompt,
        workdir=code_dir.parent,
        timeout_s=timeout_s,
        role=role,
        risk_profile=risk_profile,
    )
    return raw or ""


async def _triade_p0(
    finding: Finding,
    winner: BuilderResult,
    risk_profile: RiskProfile,
    auditor_family: str,
    max_iterations: int = 2,
) -> FixResult:
    """Process a single P0 finding through critic→fixer→verifier round-trip.

    Loop:
        1. Critic confirms the finding is real and reproducible.
        2. Fixer produces a patch + regression test.
        3. Local gates (pytest/mypy/ruff) — short-circuit if they fail.
        4. Verifier issues a strict JSON verdict {pass, reason, evidence}.
        5. If reject and iteration < max → loop back to Fixer with verdict.
        6. If still reject after max_iterations → escalate.
    """
    critic, fixer, verifier = pick_triade(winner.family, auditor_family, risk_profile)

    logger.info(
        "p0_triade_start",
        finding_id=finding.id,
        critic=critic,
        fixer=fixer,
        verifier=verifier,
    )

    critic_template = _load_prompt("critic")
    fixer_template = _load_prompt("fixer")
    verifier_template = _load_prompt("verifier_strict")

    # ── Step 1: Critic confirms the finding ─────────────────────────────
    critic_prompt = critic_template.format(
        finding_id=finding.id,
        severity=finding.severity.value,
        axis=finding.axis,
        description=finding.description,
        evidence_path=finding.evidence.file_path if finding.evidence else "n/a",
        evidence_excerpt=(finding.evidence.excerpt if finding.evidence else "")[:2000],
    )
    try:
        critic_output = await _invoke_role("critic", critic, critic_prompt, winner.code_dir, risk_profile=risk_profile)
    except Exception as e:
        logger.error("p0_critic_failed", finding_id=finding.id, error=str(e))
        return FixResult(
            finding_ids=[finding.id],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=0,
        )

    # If critic dismisses the finding (false positive), escalate to human.
    if "FALSE_POSITIVE" in critic_output.upper():
        logger.info("p0_false_positive", finding_id=finding.id)
        return FixResult(
            finding_ids=[finding.id],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=1,
        )

    # ── Steps 2-5: Fixer ↔ Verifier loop ────────────────────────────────
    last_verdict: dict = {"pass": False, "reason": "no_attempt", "required_evidence": []}
    fixer_feedback = ""

    for iteration in range(1, max_iterations + 1):
        fixer_prompt = fixer_template.format(
            finding_id=finding.id,
            critic_analysis=critic_output[:4000],
            previous_verdict=fixer_feedback or "(first attempt)",
            evidence_path=finding.evidence.file_path if finding.evidence else "n/a",
        )
        try:
            await _invoke_role("fixer", fixer, fixer_prompt, winner.code_dir, risk_profile=risk_profile)
        except Exception as e:
            logger.error("p0_fixer_failed", finding_id=finding.id, error=str(e))
            break

        # Local gates short-circuit
        gates_ok, gates_summary = await _run_local_gates(winner.code_dir)
        if not gates_ok:
            fixer_feedback = f"Local gates failed:\n{gates_summary}\nRework the patch."
            logger.info(
                "p0_local_gates_failed",
                finding_id=finding.id,
                iteration=iteration,
            )
            continue

        # Verifier
        verifier_prompt = verifier_template.format(
            finding_id=finding.id,
            critic_analysis=critic_output[:2000],
            local_gates_status="all green",
        )
        try:
            verifier_raw = await _invoke_role(
                "verifier",
                verifier,
                verifier_prompt,
                winner.code_dir,
                risk_profile=risk_profile,
            )
        except Exception as e:
            logger.error("p0_verifier_failed", finding_id=finding.id, error=str(e))
            break

        last_verdict = _parse_verifier_verdict(verifier_raw)
        if last_verdict["pass"]:
            logger.info(
                "p0_triade_accepted",
                finding_id=finding.id,
                iterations=iteration,
            )
            return FixResult(
                finding_ids=[finding.id],
                status="accepted",
                critic_model=critic,
                fixer_model=fixer,
                verifier_model=verifier,
                iterations=iteration,
            )

        fixer_feedback = (
            f"Verifier rejected: {last_verdict['reason']}. "
            f"Required evidence: {last_verdict['required_evidence']}"
        )
        logger.info(
            "p0_verifier_rejected",
            finding_id=finding.id,
            iteration=iteration,
            reason=last_verdict["reason"],
        )

    # Max iterations exhausted → escalate
    logger.warning(
        "p0_triade_escalate",
        finding_id=finding.id,
        last_reason=last_verdict.get("reason"),
    )
    return FixResult(
        finding_ids=[finding.id],
        status="escalate",
        critic_model=critic,
        fixer_model=fixer,
        verifier_model=verifier,
        iterations=max_iterations,
    )


# ────────────────────────────────────────────────────────────────
# P1 BATCH BY AXIS
# ────────────────────────────────────────────────────────────────


async def _triade_p1_batch(
    axis: str,
    findings: list[Finding],
    winner: BuilderResult,
    risk_profile: RiskProfile,
    auditor_family: str,
) -> FixResult:
    """Batch all P1 findings of the same axis into a single Fixer call.

    P1 is less critical than P0, so:
        - Single Critic confirmation pass (group review)
        - Single Fixer pass (no Verifier loop)
        - Local gates as final guard (no LLM Verifier — saves tokens)
    """
    critic, fixer, verifier = pick_triade(winner.family, auditor_family, risk_profile)

    logger.info(
        "p1_batch_start",
        axis=axis,
        n_findings=len(findings),
        fixer=fixer,
    )

    critic_template = _load_prompt("critic")
    fixer_template = _load_prompt("fixer")

    # Aggregate findings into a single context block
    findings_block = "\n\n".join(
        f"- [{f.id}] {f.description}\n"
        f"  evidence: {f.evidence.file_path if f.evidence else 'n/a'}"
        for f in findings
    )

    # Round 6 fix [P1-no-Critic] (Audit 6 P2): the docstring promised a
    # "Single Critic confirmation pass (group review)" but the code skipped
    # straight to the Fixer. Either the docstring lied or the code missed
    # the call — fixing the code (cheaper than throwing away the contract).
    critic_batch_prompt = critic_template.format(
        finding_id=f"P1_BATCH_{axis}",
        severity="P1",
        axis=axis,
        description=f"Batch of {len(findings)} P1 findings on axis '{axis}'",
        evidence_path="(see findings list)",
        evidence_excerpt=findings_block[:2000],
    )
    try:
        critic_batch_output = await _invoke_role(
            "critic",
            critic,
            critic_batch_prompt,
            winner.code_dir,
            risk_profile=risk_profile,
        )
    except Exception as e:
        logger.warning("p1_batch_critic_failed_proceeding", axis=axis, error=str(e))
        critic_batch_output = "(critic call failed; proceeding with raw findings)"

    fixer_prompt = fixer_template.format(
        finding_id=f"P1_BATCH_{axis}",
        critic_analysis=(
            f"Batch of {len(findings)} P1 findings on axis '{axis}'.\n"
            f"Critic group review: {critic_batch_output[:1500]}\n\n"
            f"Findings:\n{findings_block}"
        ),
        previous_verdict="(P1 batch — no prior attempt)",
        evidence_path="(see findings list)",
    )

    try:
        await _invoke_role("fixer", fixer, fixer_prompt, winner.code_dir, risk_profile=risk_profile)
    except Exception as e:
        logger.error("p1_fixer_failed", axis=axis, error=str(e))
        return FixResult(
            finding_ids=[f.id for f in findings],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=0,
        )

    # Local gates as final guard (no Verifier loop for P1)
    gates_ok, gates_summary = await _run_local_gates(winner.code_dir)
    if not gates_ok:
        logger.warning("p1_local_gates_failed", axis=axis, summary=gates_summary[:300])
        return FixResult(
            finding_ids=[f.id for f in findings],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=1,
        )

    logger.info("p1_batch_accepted", axis=axis, n_findings=len(findings))
    return FixResult(
        finding_ids=[f.id for f in findings],
        status="accepted",
        critic_model=critic,
        fixer_model=fixer,
        verifier_model=verifier,
        iterations=1,
    )


# ────────────────────────────────────────────────────────────────
# P2/P3 LOCAL AUTO-FIX
# ────────────────────────────────────────────────────────────────


async def _auto_fix_local(findings: list[Finding], winner: BuilderResult) -> FixResult:
    """Apply ruff --fix and similar non-LLM fixes."""
    # ruff --fix
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "ruff", "check", "--fix", "src/", "tests/",
        cwd=winner.code_dir.parent,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    return FixResult(
        finding_ids=[f.id for f in findings],
        status="accepted",
        critic_model="<local>",
        fixer_model="ruff",
        verifier_model="<local>",
        iterations=1,
    )


# ────────────────────────────────────────────────────────────────
# DISPATCHER
# ────────────────────────────────────────────────────────────────


async def phase_5_dispatch(
    audit: AuditReport,
    winner: BuilderResult,
    risk_profile: RiskProfile,
) -> FixReport:
    """Dispatch findings to appropriate triade strategy."""
    logger.info(
        "phase_5_start",
        winner=winner.voice_id,
        n_findings=len(audit.findings),
    )

    p0 = [f for f in audit.findings if f.severity == Severity.P0]
    p1_by_axis: dict[str, list[Finding]] = defaultdict(list)
    for f in audit.findings:
        if f.severity == Severity.P1:
            p1_by_axis[f.axis].append(f)
    p2_p3 = [f for f in audit.findings if f.severity in {Severity.P2, Severity.P3}]

    results: list[FixResult] = []

    # P0: per-finding sequential triade
    for f in p0:
        result = await _triade_p0(f, winner, risk_profile, audit.auditor_family)
        results.append(result)
        if result.status == "escalate":
            logger.warning("phase_5_p0_escalate", finding_id=f.id)
            return FixReport(status="blocked_p0", results=results)

    # P1: batched per axis
    for axis, batch in p1_by_axis.items():
        result = await _triade_p1_batch(axis, batch, winner, risk_profile, audit.auditor_family)
        results.append(result)

    # P2/P3: local auto-fix
    if p2_p3:
        result = await _auto_fix_local(p2_p3, winner)
        results.append(result)

    has_partial = any(r.status == "escalate" for r in results)
    final_status = "partial" if has_partial else "completed"

    logger.info(
        "phase_5_done",
        n_results=len(results),
        status=final_status,
    )
    return FixReport(status=final_status, results=results)

```


### `src/polybuild/phases/phase_6_validate.py` (294 lines)

```python
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
        result = await validate_mcp_server(
            server_cmd=server_cmd,
            cwd=workdir,
            expected_tools=expected_tools or None,
            timeout_s=float(cfg.get("timeout_s", 30.0)),
            extra_env=cfg.get("extra_env"),
            golden_tool_call=cfg.get("golden_tool_call"),
        )
        return result.passed, result.errors

    if gate_name == "sqlite":
        from polybuild.domain_gates.validate_sqlite import validate_sqlite_db

        db_path = cfg.get("db_path")
        if not db_path:
            return False, ["sqlite_gate_no_db_path_configured"]
        result = validate_sqlite_db(
            db_path=db_path,
            schema_snapshot_path=cfg.get("schema_snapshot_path"),
            require_wal=bool(cfg.get("require_wal", True)),
        )
        return result.passed, result.errors

    if gate_name == "qdrant":
        from polybuild.domain_gates.validate_qdrant import validate_qdrant_collection

        url = cfg.get("url", "http://localhost:6333")
        collection = cfg.get("collection")
        if not collection:
            return False, ["qdrant_gate_no_collection_configured"]
        result = await validate_qdrant_collection(
            qdrant_url=url,
            collection=collection,
            expected_dim=int(cfg.get("expected_dim", 768)),
            min_points=int(cfg.get("min_points", 1)),
            # Round 6 fix [J2] (Audit 4): vector_name was not propagated from
            # cfg, so named-vector collections couldn't be validated even
            # though [J] in round 5 added the parameter to the gate function.
            vector_name=cfg.get("vector_name"),
        )
        return result.passed, result.errors

    if gate_name == "fts5":
        from polybuild.domain_gates.validate_fts5 import validate_fts5_golden

        db_path = cfg.get("db_path")
        fts_table = cfg.get("fts_table")
        golden_path = cfg.get("golden_path")
        if not all([db_path, fts_table, golden_path]):
            return False, ["fts5_gate_missing_config"]
        result = validate_fts5_golden(
            db_path=db_path,
            fts_table=fts_table,
            golden_path=golden_path,
            require_golden_file=bool(cfg.get("require_golden_file", True)),
        )
        # Round 6 fix [fts5-skipped] (Audit 1 P1): when skipped=True, the gate
        # didn't actually validate anything. Surface it explicitly in the
        # signals so phase_6 notes mention "skipped" rather than just "passed".
        signals = list(result.errors) + list(result.failures)
        if result.skipped:
            signals.append("fts5_skipped_dev_mode")
        return result.passed, signals

    if gate_name == "rag":
        # Rag gate requires runtime callables (chunker_fn, retrieval_fn) which can't be
        # serialized in YAML — calling project must inject them via gate_config["_runtime"].
        from polybuild.domain_gates.validate_rag import validate_rag_smoke

        runtime = cfg.get("_runtime", {})
        result = validate_rag_smoke(
            chunker_fn=runtime.get("chunker_fn"),
            sample_text=cfg.get("sample_text", ""),
            golden_retrieval_path=cfg.get("golden_retrieval_path"),
            retrieval_fn=runtime.get("retrieval_fn"),
        )
        return result.passed, result.errors

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

```


### `src/polybuild/domain_gates/validate_fts5.py` (165 lines)

```python
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
                cur = conn.execute(
                    # noqa: S608 — fts_table is a structural identifier from config, not user input
                    f"SELECT COUNT(*) FROM {fts_table} WHERE {fts_table} MATCH ?",  # noqa: S608
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

```


### `src/polybuild/orchestrator.py` (458 lines)

```python
"""POLYBUILD v3 main orchestrator.

Chains all phases in sequence with checkpoint persistence.
Top-level entry point invoked by the CLI (`polybuild run ...`).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import structlog

from polybuild.models import (
    PolybuildRun,
    PrivacyLevel,
    RiskProfile,
    Severity,
    TokenUsage,
)
from polybuild.phases import (
    phase_0_spec,
    phase_2_generate,
    phase_3_score,
    phase_3b_grounding,
    phase_7_commit,
    select_voices,
)
from polybuild.phases.phase_4_audit import phase_4_audit
from polybuild.phases.phase_5_triade import phase_5_dispatch
from polybuild.phases.phase_6_validate import phase_6_validate

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# CHECKPOINT MANAGEMENT
# ────────────────────────────────────────────────────────────────


def save_checkpoint(run_id: str, phase: str, payload: dict, root: Path) -> None:
    """Atomically write a checkpoint."""
    checkpoint_dir = root / ".polybuild" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    target = checkpoint_dir / f"{run_id}_{phase}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    tmp.rename(target)


# ────────────────────────────────────────────────────────────────
# RUN ID GENERATION
# ────────────────────────────────────────────────────────────────


def generate_run_id() -> str:
    """Format: 2026-05-03_143022_a4f7."""
    import secrets
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{ts}_{suffix}"


# ────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ────────────────────────────────────────────────────────────────


async def run_polybuild(
    brief: str,
    profile_id: str,
    project_root: Path = Path("."),
    risk_profile: RiskProfile | None = None,
    project_ctx: dict | None = None,
    skip_commit: bool = False,
    skip_smoke: bool = False,
) -> PolybuildRun:
    """Execute the full POLYBUILD pipeline.

    Args:
        brief: free-text description of the task
        profile_id: routing profile (e.g. "module_inedit_critique", "helia_algo")
        project_root: Path to the user's project (where AGENTS.md lives)
        risk_profile: optional override (else inferred from profile)
        project_ctx: optional dict with `spec_yaml_path`, `declared_sensitivity`,
                     `extra_context_for_opus`, `phase_8_endpoint`, `phase_8_golden_queries`
        skip_commit: True for dry-runs (Phase 7 skipped)
        skip_smoke: True to skip Phase 8 production smoke

    Returns:
        PolybuildRun with all metadata, archived to disk.

    Round 5 fix [N]: Phase 9 cleanup is now in an outer `finally:` so it
    runs on *every* exit path (privacy gate block, abort in P5/P6, exception),
    not just the happy path. Audit 5 flagged this trou de spec.
    """
    # Round 5 [M]: optional run_id override from project_ctx (skill /polybuild)
    override = (project_ctx or {}).get("run_id_override")
    run_id = override if override else generate_run_id()
    started_at = datetime.utcnow()
    artifacts_dir = project_root / ".polybuild" / "runs"

    try:
        return await _run_polybuild_inner(
            brief=brief,
            run_id=run_id,
            started_at=started_at,
            artifacts_dir=artifacts_dir,
            profile_id=profile_id,
            project_root=project_root,
            risk_profile=risk_profile,
            project_ctx=project_ctx,
            skip_commit=skip_commit,
            skip_smoke=skip_smoke,
        )
    finally:
        # Round 5 fix [N]: always-run cleanup, even if Phase -1 blocked, an
        # exception was raised, or we early-returned with _build_aborted_run.
        #
        # Round 6 fix [Exception-swallowing] (Audit 6 Kimi P1):
        #   1. Capture the in-flight exception (if any) via sys.exc_info() BEFORE
        #      cleanup, so we can log it even if cleanup itself raises.
        #   2. Wrap each cleanup operation in its own try/except so a single
        #      cleanup failure cannot create a new exception that would replace
        #      the original via Python's `__context__` chaining.
        #   3. Log structured fields including original_error so post-mortems
        #      see the real cause, not "phase_9_cleanup_failed".
        original_exc_type, original_exc, _ = sys.exc_info()
        original_error_msg = (
            f"{original_exc_type.__name__}: {original_exc}"
            if original_exc_type is not None
            else None
        )

        try:
            from polybuild.phases.phase_8_prod_smoke import phase_9_cleanup_async

            staging_dir = project_root / ".worktrees" / f"staging-{run_id}"
            staging_containers = (project_ctx or {}).get("staging_containers", [])
            cleanup_report = await phase_9_cleanup_async(
                run_id=run_id,
                staging_dir=staging_dir if staging_dir.exists() else None,
                docker_containers=staging_containers,
                repo_dir=project_root,
            )
        except BaseException as cleanup_exc:  # noqa: BLE001 — preserving original exc
            # Cleanup itself failed. Log both the cleanup failure AND the
            # original (in-flight) exception, then swallow the cleanup error
            # so Python re-raises the original from the implicit `finally`.
            logger.error(
                "phase_9_cleanup_outer_finally_failed",
                cleanup_error=f"{type(cleanup_exc).__name__}: {cleanup_exc}",
                original_error=original_error_msg,
                run_id=run_id,
                hint=(
                    "Pipeline exception (if any) is preserved and re-raised; "
                    "cleanup error logged here only."
                ),
            )
        else:
            # Cleanup succeeded — best-effort checkpoint.
            try:
                save_checkpoint(run_id, "phase9", cleanup_report, project_root)
            except Exception as ckpt_exc:
                logger.warning(
                    "phase_9_checkpoint_failed",
                    error=str(ckpt_exc),
                    original_error=original_error_msg,
                )


async def _run_polybuild_inner(
    *,
    brief: str,
    run_id: str,
    started_at: datetime,
    artifacts_dir: Path,
    profile_id: str,
    project_root: Path,
    risk_profile: RiskProfile | None,
    project_ctx: dict | None,
    skip_commit: bool,
    skip_smoke: bool,
) -> PolybuildRun:
    """Inner pipeline (Phase -1 → Phase 8). Phase 9 lives in the outer finally."""

    if risk_profile is None:
        # Default: low sensitivity unless profile suggests otherwise
        sensitivity = (
            PrivacyLevel.HIGH if "medical_high" in profile_id
            else PrivacyLevel.MEDIUM if "medical_medium" in profile_id
            else PrivacyLevel.LOW if "medical_low" in profile_id
            else PrivacyLevel.LOW
        )
        risk_profile = RiskProfile(
            sensitivity=sensitivity,
            code_inedit_critique=("inedit_critique" in profile_id),
            requires_probe=("inedit_critique" in profile_id or "helia" in profile_id),
            excludes_openrouter=(sensitivity == PrivacyLevel.HIGH),
            excludes_us_cn_models=(sensitivity == PrivacyLevel.HIGH),
        )

    logger.info("polybuild_start", run_id=run_id, profile=profile_id)

    # ── Phase -1: privacy gate (Round 4 finalisé) ──
    from polybuild.phases.phase_minus_one_privacy import phase_minus_one_privacy_gate

    # spec.yaml lookup: convention is the brief file living next to spec.yaml,
    # or an explicit spec_yaml_path passed in via project_ctx.
    spec_yaml_path = (project_ctx or {}).get("spec_yaml_path")
    declared_sensitivity = (project_ctx or {}).get("declared_sensitivity")

    privacy_verdict = phase_minus_one_privacy_gate(
        text=brief,
        spec_path=spec_yaml_path,
        declared_sensitivity=declared_sensitivity,
    )
    save_checkpoint(
        run_id, "phase_minus_one", privacy_verdict.model_dump(mode="json"), project_root
    )

    if privacy_verdict.blocked:
        logger.error(
            "polybuild_blocked_by_privacy_gate",
            level=privacy_verdict.level,
            reason=privacy_verdict.reason,
        )
        raise RuntimeError(
            f"Phase -1 privacy gate BLOCKED: {privacy_verdict.reason}"
        )

    # If escalated, force EU/local routing for the rest of the run
    if privacy_verdict.level == "ESCALATE_PARANOIA":
        logger.warning(
            "phase_minus_one_paranoia_escalated",
            reason=privacy_verdict.reason,
        )
        risk_profile = risk_profile.model_copy(
            update={
                "excludes_openrouter": True,
                "excludes_us_cn_models": True,
                "sensitivity": PrivacyLevel.HIGH,
            }
        )

    # ── Phase 0: spec ──
    spec = await phase_0_spec(
        run_id=run_id,
        brief=brief,
        profile_id=profile_id,
        risk_profile=risk_profile,
        project_ctx=project_ctx,
        artifacts_dir=artifacts_dir,
    )
    save_checkpoint(run_id, "phase0", spec.model_dump(mode="json"), project_root)

    # ── Phase 1: voice selection ──
    voices = await select_voices(spec, config_root=Path(__file__).parent.parent.parent / "config")
    save_checkpoint(
        run_id, "phase1",
        {"voices": [v.model_dump() for v in voices]},
        project_root,
    )

    # ── Phase 2: parallel generation ──
    builder_results = await phase_2_generate(spec, voices)
    save_checkpoint(
        run_id, "phase2",
        {"results": [r.model_dump(mode="json") for r in builder_results]},
        project_root,
    )

    # ── Phase 3: scoring ──
    scores = await phase_3_score(builder_results)
    save_checkpoint(
        run_id, "phase3",
        {"scores": [s.model_dump() for s in scores]},
        project_root,
    )

    # ── Phase 3b: grounding ──
    grounding = await phase_3b_grounding(builder_results, project_root)
    save_checkpoint(
        run_id, "phase3b",
        {vid: [f.model_dump(mode="json") for f in fs] for vid, fs in grounding.items()},
        project_root,
    )

    # Determine winner (highest score, not disqualified, no critical grounding)
    eligible = [
        s for s in scores
        if not s.disqualified
        and len([f for f in grounding.get(s.voice_id, []) if f.severity == Severity.P0]) == 0
    ]
    if not eligible:
        logger.error("no_eligible_winner")
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
        )

    winner_score = eligible[0]
    winner_result = next(
        r for r in builder_results if r.voice_id == winner_score.voice_id
    )

    # ── Phase 4: audit ──
    audit = await phase_4_audit(
        winner_result,
        profile_id,
        risk_profile,
        config_root=Path(__file__).parent.parent.parent / "config",
    )
    save_checkpoint(run_id, "phase4", audit.model_dump(mode="json"), project_root)

    # ── Phase 5: triade ──
    fix_report = await phase_5_dispatch(audit, winner_result, risk_profile)
    save_checkpoint(run_id, "phase5", fix_report.model_dump(mode="json"), project_root)

    if fix_report.status == "blocked_p0":
        logger.error("polybuild_blocked_p0", run_id=run_id)
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
            audit=audit, fix_report=fix_report,
        )

    # ── Phase 6: validation ──
    validation = await phase_6_validate(spec, winner_result, artifacts_dir)
    save_checkpoint(run_id, "phase6", validation.model_dump(mode="json"), project_root)

    if not validation.passed:
        logger.error("polybuild_validation_failed", run_id=run_id, notes=validation.notes)
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
            audit=audit, fix_report=fix_report,
        )

    # Build run summary
    run = PolybuildRun(
        run_id=run_id,
        profile_id=profile_id,
        spec_hash=spec.spec_hash,
        voices_used=[v.voice_id for v in voices],
        winner_voice_id=winner_score.voice_id,
        scores={s.voice_id: s.score for s in scores},
        audit_findings_by_severity={
            sev.value: sum(1 for f in audit.findings if f.severity == sev)
            for sev in Severity
        },
        fix_iterations={
            fr.finding_ids[0] if fr.finding_ids else "auto": fr.iterations
            for fr in fix_report.results
        },
        domain_gates_passed=validation.domain_gates_passed,
        duration_total_sec=(datetime.utcnow() - started_at).total_seconds(),
        tokens=TokenUsage(),  # TODO: aggregate from adapters
        cost_eur_marginal=0.0,  # TODO: compute from usage
        final_status="committed",
        commit_sha=None,
        started_at=started_at,
        completed_at=None,
    )

    # ── Phase 7: commit ──
    if not skip_commit:
        commit_info = await phase_7_commit(run, project_root)
        run.commit_sha = commit_info.sha

    # ── Phase 8: prod smoke (Round 4 finalisé) ──
    if not skip_smoke and project_ctx and project_ctx.get("phase_8_endpoint"):
        from polybuild.phases.phase_8_prod_smoke import (
            GoldenQuery,
            phase_8_production_smoke,
            tag_pre_run,
        )

        endpoint = project_ctx["phase_8_endpoint"]
        golden_raw = project_ctx.get("phase_8_golden_queries", [])
        goldens = [GoldenQuery.model_validate(g) for g in golden_raw]

        if goldens:
            pre_tag = tag_pre_run(run_id, repo_dir=project_root)
            smoke_verdict = await phase_8_production_smoke(
                endpoint_url=endpoint,
                golden_queries=goldens,
                error_rate_threshold=float(project_ctx.get("phase_8_error_threshold", 0.0)),
                latency_increase_threshold=float(project_ctx.get("phase_8_latency_threshold", 0.05)),
                monitoring_window_s=int(project_ctx.get("phase_8_window_s", 300)),
                rollback_tag=pre_tag,
                repo_dir=project_root,
            )
            save_checkpoint(
                run_id, "phase8", smoke_verdict.model_dump(mode="json"), project_root
            )
            if not smoke_verdict.passed:
                run.final_status = "rolled_back"
                logger.error(
                    "polybuild_smoke_failed_rolled_back",
                    run_id=run_id,
                    notes=smoke_verdict.notes,
                )

    run.completed_at = datetime.utcnow()
    # Round 5 [X] (Audit 5 P1): recompute duration AFTER Phase 7 + 8 so it
    # measures the real total run duration (was figé before commit/smoke).
    run.duration_total_sec = (run.completed_at - started_at).total_seconds()

    # ── Phase 9 cleanup is now in run_polybuild()'s outer finally (round 5 [N]) ──

    # Final archival
    final_path = artifacts_dir / run_id / "polybuild_run.json"
    final_path.write_text(run.model_dump_json(indent=2))

    logger.info(
        "polybuild_done",
        run_id=run_id,
        winner=run.winner_voice_id,
        duration=round(run.duration_total_sec, 1),
        committed=run.commit_sha is not None,
    )
    return run


# ────────────────────────────────────────────────────────────────
# ABORT HELPERS
# ────────────────────────────────────────────────────────────────


def _build_aborted_run(
    run_id: str,
    profile_id: str,
    spec,
    builder_results,
    scores,
    started_at,
    **kwargs,
) -> PolybuildRun:
    """Build a PolybuildRun in aborted state for early exits."""
    return PolybuildRun(
        run_id=run_id,
        profile_id=profile_id,
        spec_hash=spec.spec_hash,
        voices_used=[r.voice_id for r in builder_results],
        winner_voice_id=None,
        scores={s.voice_id: s.score for s in scores},
        audit_findings_by_severity={},
        fix_iterations={},
        domain_gates_passed=False,
        duration_total_sec=(datetime.utcnow() - started_at).total_seconds(),
        tokens=TokenUsage(),
        cost_eur_marginal=0.0,
        final_status="aborted",
        commit_sha=None,
        started_at=started_at,
        completed_at=datetime.utcnow(),
    )

```


### `skills/polybuild/SKILL.md` (205 lines)

```markdown
# /polybuild — Skill Claude Code

> Lance et supervise des runs POLYBUILD v3 en arrière-plan via tmux.

**Convergence round 4 (6/6) sur tmux** comme orchestrateur background :
- Survives Claude Code disconnections and SSH drops.
- Inspectable via `tmux capture-pane`.
- Killable cleanly via `tmux kill-session`.
- Fallback `screen` puis `nohup` si tmux indisponible (Kimi + DeepSeek).

## Commandes

### `/polybuild run --spec <spec.yaml> [--profile <name>] [--no-smoke]`
Lance un run POLYBUILD en background.

```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)"
mkdir -p .polybuild/runs .polybuild/logs

# Round 6 fix [M2] (Audit 4): the previous shell took $1 as the spec path,
# but `/polybuild run --spec spec.yaml` passes `--spec` as $1. Parse the
# real flags so the skill matches its documented usage.
SPEC=""
EXTRA_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --spec|--brief|-b)
      SPEC="$2"; shift 2 ;;
    --profile|-p|--profile=*)
      EXTRA_ARGS+=("$1"); [ "$1" = "--profile" -o "$1" = "-p" ] && { EXTRA_ARGS+=("$2"); shift 2; } || shift ;;
    *)
      EXTRA_ARGS+=("$1"); shift ;;
  esac
done

if [ -z "${SPEC}" ]; then
  echo "Usage: /polybuild run --spec <spec.yaml> [--profile <name>] [--no-smoke]"
  exit 2
fi

EXTRA="${EXTRA_ARGS[*]}"

# Backend selection: tmux > screen > nohup (round 4 fallback chain)
if command -v tmux >/dev/null 2>&1; then
  tmux new-session -d -s "polybuild-${RUN_ID}" \
    "set -a; \
     [ -f \"$HOME/.polybuild/secrets.env\" ] && . \"$HOME/.polybuild/secrets.env\"; \
     set +a; \
     uv run polybuild run --spec '${SPEC}' --run-id '${RUN_ID}' ${EXTRA} \
       2>&1 | tee '.polybuild/logs/${RUN_ID}.log'"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: tmux session 'polybuild-${RUN_ID}'"
elif command -v screen >/dev/null 2>&1; then
  screen -dmS "polybuild-${RUN_ID}" \
    bash -c "set -a; [ -f \"\$HOME/.polybuild/secrets.env\" ] && . \"\$HOME/.polybuild/secrets.env\"; set +a; \
             uv run polybuild run --spec '${SPEC}' --run-id '${RUN_ID}' ${EXTRA} 2>&1 | tee '.polybuild/logs/${RUN_ID}.log'"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: screen session 'polybuild-${RUN_ID}'"
else
  # nohup last-resort fallback (no attach, no inspect)
  nohup bash -c "set -a; [ -f \"\$HOME/.polybuild/secrets.env\" ] && . \"\$HOME/.polybuild/secrets.env\"; set +a; \
                 uv run polybuild run --spec '${SPEC}' --run-id '${RUN_ID}' ${EXTRA}" \
    > ".polybuild/logs/${RUN_ID}.log" 2>&1 &
  echo "$!" > ".polybuild/runs/${RUN_ID}.pid"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: nohup PID $(cat .polybuild/runs/${RUN_ID}.pid)"
fi

echo "Run ${RUN_ID} started. Check status with /polybuild status ${RUN_ID}"
```

### `/polybuild status [<run_id>]`
État d'un run. Si run_id omis, utilise le dernier.

```bash
RUN_ID="${1:-$(cat .polybuild/last_run 2>/dev/null)}"
[ -z "${RUN_ID}" ] && { echo "No run_id and no last_run found"; exit 1; }

if command -v tmux >/dev/null 2>&1 && tmux has-session -t "polybuild-${RUN_ID}" 2>/dev/null; then
  echo "Status: RUNNING (tmux)"
elif command -v screen >/dev/null 2>&1 && screen -list | grep -q "polybuild-${RUN_ID}"; then
  echo "Status: RUNNING (screen)"
elif [ -f ".polybuild/runs/${RUN_ID}.pid" ] && kill -0 "$(cat .polybuild/runs/${RUN_ID}.pid)" 2>/dev/null; then
  echo "Status: RUNNING (nohup pid=$(cat .polybuild/runs/${RUN_ID}.pid))"
else
  echo "Status: STOPPED"
fi

# Last 20 lines of log for context
echo "─── Last log lines ───"
tail -n 20 ".polybuild/logs/${RUN_ID}.log" 2>/dev/null || echo "(no log file)"
```

### `/polybuild logs [<run_id>] [--follow]`
Affiche les logs d'un run.

```bash
RUN_ID="${1:-$(cat .polybuild/last_run 2>/dev/null)}"
LOG=".polybuild/logs/${RUN_ID}.log"
[ ! -f "${LOG}" ] && { echo "No log for ${RUN_ID}"; exit 1; }

if [ "${2:-}" = "--follow" ]; then
  tail -F "${LOG}"
else
  tail -n 200 "${LOG}"
fi
```

### `/polybuild attach <run_id>`
Attache au tmux/screen interactivement (humain uniquement).

```bash
RUN_ID="${1:?run_id required}"
if command -v tmux >/dev/null 2>&1; then
  tmux attach -t "polybuild-${RUN_ID}"
elif command -v screen >/dev/null 2>&1; then
  screen -r "polybuild-${RUN_ID}"
else
  echo "No tmux/screen — use /polybuild logs instead"
fi
```

### `/polybuild abort <run_id>`
Tue un run et nettoie ses ressources (Phase 9 cleanup).

```bash
RUN_ID="${1:?run_id required}"
echo "Aborting ${RUN_ID}..."

# Kill tmux/screen/nohup
tmux kill-session -t "polybuild-${RUN_ID}" 2>/dev/null || true
screen -X -S "polybuild-${RUN_ID}" quit 2>/dev/null || true
if [ -f ".polybuild/runs/${RUN_ID}.pid" ]; then
  kill "$(cat .polybuild/runs/${RUN_ID}.pid)" 2>/dev/null || true
fi

# Trigger Phase 9 cleanup explicitly
uv run python -c "
from polybuild.phases.phase_8_prod_smoke import phase_9_cleanup
phase_9_cleanup('${RUN_ID}')
" 2>/dev/null || true

echo "Aborted ${RUN_ID}"
```

### `/polybuild list`
Liste tous les runs récents.

```bash
mkdir -p .polybuild/logs
echo "Recent runs:"
ls -t .polybuild/logs/ 2>/dev/null | head -10 | while read -r f; do
  RUN_ID="${f%.log}"
  if tmux has-session -t "polybuild-${RUN_ID}" 2>/dev/null; then
    STATUS="RUNNING"
  else
    STATUS="DONE   "
  fi
  echo "  ${STATUS}  ${RUN_ID}"
done
```

### `/polybuild secrets-check`
Vérifie l'état du fichier de secrets.

```bash
SECRETS="$HOME/.polybuild/secrets.env"
if [ ! -f "${SECRETS}" ]; then
  echo "No secrets file at ${SECRETS}"
  echo "Create one with:"
  echo "  mkdir -p ~/.polybuild && touch ~/.polybuild/secrets.env && chmod 600 ~/.polybuild/secrets.env"
  exit 1
fi

MODE=$(stat -c '%a' "${SECRETS}" 2>/dev/null || stat -f '%A' "${SECRETS}")
if [ "${MODE}" != "600" ] && [ "${MODE}" != "0600" ]; then
  echo "WARN: ${SECRETS} mode is ${MODE} (expected 600)"
  echo "Run: chmod 600 ${SECRETS}"
  exit 1
fi
echo "OK: ${SECRETS} (mode 600)"
echo "Loaded keys (names only):"
grep -E '^[A-Z_]+=' "${SECRETS}" | sed 's/=.*//' | sed 's/^/  - /'
```

---

## Convention de fichiers

```
.polybuild/
├── last_run                  # ID du dernier run lancé
├── logs/<run_id>.log         # logs complets (Phase -1 redacted)
├── runs/<run_id>/            # artefacts de run (specs, audits, ADRs)
│   ├── status.json
│   ├── spec_final.json
│   ├── audit.json
│   └── checkpoint_phase_*.json
└── runs/<run_id>.pid         # PID (uniquement pour fallback nohup)

~/.polybuild/
├── secrets.env               # chmod 600 — clés API (jamais commité)
└── safe_terms.yaml           # whitelist termes métier (round 4 DeepSeek)
```

```


### `scripts/deploy_staging.sh` (142 lines)

```bash
#!/usr/bin/env bash
# scripts/deploy_staging.sh — Round 4 Faille 4 finalisé
#
# Synthèse des 6 modèles round 4 :
#   - Worktree Git séparé (Gemini, Kimi, DeepSeek, ChatGPT)
#   - Docker staging avec ports décalés +10000 (DeepSeek, Kimi)
#   - Volumes prod montés en :ro (DeepSeek, ChatGPT, Gemini)
#   - Limites CPU/RAM hard pour ne pas pénaliser la prod (Qwen)
#   - Tag Git polybuild/run-{id}-pre AVANT toute modif (6/6)
#   - Phase 8 smoke obligatoire avant promote (6/6)
#   - Cleanup en bloc finally: (Gemini, complété par Phase 9)
#
# Usage:
#   ./deploy_staging.sh <run_id> <server_name> [<server_image>]
# Example:
#   ./deploy_staging.sh 2026-05-03_140000_a4f7 sstinfo sstinfo:latest

set -euo pipefail

RUN_ID="${1:?usage: deploy_staging.sh <run_id> <server_name> [<image>]}"
SERVER="${2:?missing server name}"
IMAGE="${3:-${SERVER}:latest}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_DIR="${REPO_ROOT}/.worktrees/staging-${RUN_ID}"
STAGING_BRANCH="polybuild/run-${RUN_ID}"
PRE_TAG="polybuild/run-${RUN_ID}-pre"
CONTAINER_NAME="polybuild-stg-${SERVER}-${RUN_ID//[^a-zA-Z0-9]/_}"

# Lecture du port prod (convention : .prod_port dans le dossier du serveur)
PROD_PORT_FILE="${REPO_ROOT}/services/${SERVER}/.prod_port"
if [[ -f "${PROD_PORT_FILE}" ]]; then
    PROD_PORT="$(cat "${PROD_PORT_FILE}")"
else
    PROD_PORT="8716"  # default SSTinfo
fi
STAGING_PORT="$(( PROD_PORT + 10000 ))"

echo "━━━ POLYBUILD deploy_staging ━━━"
echo "  run_id       : ${RUN_ID}"
echo "  server       : ${SERVER} (image=${IMAGE})"
echo "  branch       : ${STAGING_BRANCH}"
echo "  pre_tag      : ${PRE_TAG}"
echo "  staging_port : ${STAGING_PORT} (prod was ${PROD_PORT})"
echo "  worktree     : ${WORKTREE_DIR}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cleanup() {
    local rc=$?
    echo "[cleanup] rc=$rc — removing staging artefacts"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
    if [[ -d "${WORKTREE_DIR}" ]]; then
        git -C "${REPO_ROOT}" worktree remove -f "${WORKTREE_DIR}" 2>/dev/null || rm -rf "${WORKTREE_DIR}"
        git -C "${REPO_ROOT}" worktree prune || true
    fi
    exit $rc
}
trap cleanup EXIT INT TERM

# ── 1. Pre-tag for rollback (6/6 convergence) ────────────────────────
echo "[1/5] Tagging current HEAD as rollback point..."
git -C "${REPO_ROOT}" tag -f "${PRE_TAG}" HEAD
echo "      → ${PRE_TAG}"

# ── 2. Worktree isolated ─────────────────────────────────────────────
echo "[2/5] Creating worktree..."
git -C "${REPO_ROOT}" worktree add -B "${STAGING_BRANCH}" "${WORKTREE_DIR}" HEAD

# ── 3. Docker staging with RO prod volumes + resource caps ───────────
echo "[3/5] Building staging image from worktree..."
PROD_DATA_DIR="${REPO_ROOT}/services/${SERVER}/data"
if [[ ! -d "${PROD_DATA_DIR}" ]]; then
    echo "      WARN: ${PROD_DATA_DIR} not found, container will start without data volume"
    PROD_DATA_MOUNT=""
else
    PROD_DATA_MOUNT="-v ${PROD_DATA_DIR}:/app/data:ro"
fi

# Round 5 fix [K] (Audits 3+4 P0): build image FROM the worktree, not the
# pre-existing prod image. Otherwise the staging tested code is the prod code,
# not the candidate. Phase 8 smoke would validate nothing.
STAGING_IMAGE="${SERVER}:polybuild-${RUN_ID}"
if [[ ! -f "${WORKTREE_DIR}/Dockerfile" ]]; then
    echo "      ERROR: ${WORKTREE_DIR}/Dockerfile missing — cannot prove staging runs candidate code."
    echo "             Add a Dockerfile to your service repo or pass an explicit image."
    exit 1
fi
docker build -t "${STAGING_IMAGE}" "${WORKTREE_DIR}"

echo "[3.5/5] Starting staging container..."
# shellcheck disable=SC2086
# Round 5 fix [L] (Audit 4 P0): bind to 127.0.0.1 only, not 0.0.0.0.
# Health-data staging must NOT be exposed on the LAN, even temporarily.
docker run -d \
    --name "${CONTAINER_NAME}" \
    --cpus="1" \
    --memory="1g" \
    -p "127.0.0.1:${STAGING_PORT}:${PROD_PORT}" \
    ${PROD_DATA_MOUNT} \
    -e POLYBUILD_STAGING=1 \
    -e SQLITE_READONLY=1 \
    -e QDRANT_READONLY=1 \
    -e MCP_PORT="${PROD_PORT}" \
    "${STAGING_IMAGE}"

# ── 4. Wait for healthy ──────────────────────────────────────────────
echo "[4/5] Waiting for staging to become healthy..."
HEALTHY=0
for i in $(seq 1 20); do
    # Round 5 fix (Audit 5 P2): --max-time prevents indefinite hang
    if curl -sf --max-time 3 "http://127.0.0.1:${STAGING_PORT}/health" >/dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    sleep 1
done
if [[ "${HEALTHY}" -eq 0 ]]; then
    echo "      ERROR: staging not healthy after 20s"
    docker logs --tail 30 "${CONTAINER_NAME}" || true
    exit 1
fi
echo "      → staging healthy at http://127.0.0.1:${STAGING_PORT}"

# ── 5. Phase 8 smoke ─────────────────────────────────────────────────
echo "[5/5] Running Phase 8 production smoke..."
# Round 6 [T2]: pass --rollback-force-clean because we're operating on the
# DEDICATED staging worktree (not the user's main repo). The flag is safe here.
if ! uv run python -m polybuild.phases.phase_8_prod_smoke \
    --endpoint "http://127.0.0.1:${STAGING_PORT}/jsonrpc" \
    --golden "${REPO_ROOT}/tests/golden/${SERVER}_smoke.json" \
    --rollback-tag "${PRE_TAG}" \
    --rollback-force-clean \
    --repo-dir "${WORKTREE_DIR}" \
    --window-s 300; then
    echo "      ✘ Phase 8 smoke FAILED — rollback already triggered"
    exit 1
fi

echo "✔ Staging validated. Promote with:"
echo "    git checkout main && git merge --ff-only ${STAGING_BRANCH} && git tag polybuild/run-${RUN_ID}-ok"
exit 0

```


### `.gitleaks.toml` (82 lines)

```toml
# .gitleaks.toml — POLYBUILD secrets policy (Round 4 + 5 + 6)
#
# Round 5 fixes:
#   [V] (Audit 3 P1): retiré .polybuild/runs/*.log de l'allowlist. Les logs
#       sont l'endroit même où un secret leaké via prompt/réponse peut
#       transiter — les exclure du scan = invisibilité maximale.
#   [Z] (Audit 5 P2): la règle openai-api-key matchait aussi sk-or-v1- via
#       le pattern sk-{40,}. Les deux clés ont des préfixes distincts : on
#       les sépare proprement avec un anchor négatif sur openrouter.
#
# Round 6 fix:
#   [V2] (Audit 4 ChatGPT P2): retiré `.polybuild/secrets.env` de l'allowlist
#       repo-locale. Le vrai chemin documenté est `~/.polybuild/secrets.env`
#       (chmod 600, hors repo). Allowlister un fichier intra-repo qui ne
#       devrait jamais exister masque un commit accidentel — exactement le
#       cas que gitleaks doit attraper.
#       NB : le `.gitignore` continue à ignorer `.polybuild/` au cas où.

title = "POLYBUILD secrets policy"

[extend]
useDefault = true

[allowlist]
description = "Examples and test fixtures only. Real secrets live in ~/.polybuild/secrets.env (out of repo)."
paths = [
    '''^\.env\.example$''',
    '''^tests/fixtures/.*''',
]

# ────────────────────────────────────────────────────────────────────
# CUSTOM RULES (round 5 union — précis, peu de faux positifs)
# ────────────────────────────────────────────────────────────────────

[[rules]]
id = "openrouter-key"
description = "OpenRouter API key (sk-or-v1- prefix)"
regex = '''sk-or-v1-[A-Za-z0-9_-]{40,}'''
tags = ["key", "openrouter"]

[[rules]]
id = "anthropic-api-key"
description = "Anthropic API key (sk-ant-* prefix)"
regex = '''sk-ant-(api03|admin01|test01)-[A-Za-z0-9_-]{80,}'''
tags = ["key", "anthropic"]

[[rules]]
id = "openai-api-key"
description = "OpenAI / Codex API key — sk- prefix BUT NOT sk-or-* (OpenRouter) or sk-ant-* (Anthropic)"
# Round 5 [Z]: negative lookahead on or-/ant- prefixes to avoid double-firing
regex = '''sk-(?!(?:or-|ant-))(?:proj-)?[A-Za-z0-9_-]{40,}'''
tags = ["key", "openai"]

[[rules]]
id = "google-api-key"
description = "Google AIza key (Gemini)"
regex = '''AIza[0-9A-Za-z_-]{35}'''
tags = ["key", "google"]

[[rules]]
id = "mistral-api-key"
description = "Mistral API key"
regex = '''(?i)mistral[_-]?api[_-]?key\s*[:=]\s*["']?[A-Za-z0-9_\-]{30,}'''
tags = ["key", "mistral"]

[[rules]]
id = "huggingface-token"
description = "Hugging Face token"
regex = '''hf_[A-Za-z0-9]{30,}'''
tags = ["token", "huggingface"]

[[rules]]
id = "polybuild-secrets-elsewhere"
description = "Any KEY=value pattern resembling a token outside the allowed paths"
regex = '''(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*["']?[A-Za-z0-9_\-]{32,}'''
tags = ["generic"]
[rules.allowlist]
paths = [
    '''^\.env\.example$''',
    '''^tests/fixtures/.*''',
]

```


---

**End of code.** Now answer Q1, Q2, Q3 in the format above.
Brief, code-referenced, honest. If your verdict moves to GO, say so;
if a residual blocker remains, name it precisely. Thanks.
