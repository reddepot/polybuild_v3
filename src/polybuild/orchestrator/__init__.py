"""POLYBUILD v3 main orchestrator.

Chains all phases in sequence with checkpoint persistence.
Top-level entry point invoked by the CLI (`polybuild run ...`).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


# Round 10.2 fix [Kimi RX-001]: tasks created by the shutdown handler are
# tracked here so run_polybuild() can await them explicitly in its finally
# block, instead of relying on a fire-and-forget pattern.
_SHUTDOWN_DRAIN_TASKS: list[asyncio.Task[None]] = []


def _handle_shutdown_signal(sig: int, run_id: str) -> None:
    """Round 9 [SIGINT]: react to Ctrl+C / SIGTERM by cancelling all asyncio
    tasks of the current run. The orchestrator's outer `finally:` block then
    runs phase_9_cleanup_async before the process exits.

    Round 10.1 fix [R3 — graceful shutdown] (4/5 conv: Grok, Gemini, DeepSeek,
    Kimi): a plain ``task.cancel()`` does not propagate into coroutines
    wrapped in ``asyncio.shield()``. We additionally schedule a fallback
    ``gather(..., return_exceptions=True)`` with a short timeout so that
    even shielded tasks get a chance to wind down before the finally block
    runs. The shutdown_event is also exposed via module-level state so
    cooperative loops in long phases can opt-in to early exit.
    """
    logger.warning(
        "shutdown_signal_received",
        signal=sig,
        run_id=run_id,
        hint="Cancelling tasks; phase_9 cleanup will run before exit.",
    )
    current = asyncio.current_task()
    pending: list[asyncio.Task[Any]] = []
    for task in asyncio.all_tasks():
        if task is not current:
            task.cancel()
            pending.append(task)

    # Best-effort cooperative drain — bounded so we never block cleanup.
    # Round 10.2 fix [Kimi RX-001 P0]: do NOT fire-and-forget the drain.
    # Schedule it on the running loop and stash the resulting Task so the
    # outer ``finally`` block in run_polybuild can await it before invoking
    # phase_9 cleanup. We still suppress RuntimeError for the corner case
    # where the loop is already closing (no possible drain).
    if pending:
        async def _drain() -> None:
            await asyncio.wait(pending, timeout=2.0)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Loop is already closing → cancellation is the best we can do.
            return
        # Module-level registry so run_polybuild() can collect the task and
        # await it explicitly. RUF006: no fire-and-forget.
        _SHUTDOWN_DRAIN_TASKS.append(loop.create_task(_drain()))


def save_checkpoint(
    run_id: str, phase: str, payload: dict[str, Any], root: Path
) -> None:
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

    ts = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{ts}_{suffix}"


# ────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ────────────────────────────────────────────────────────────────


async def run_polybuild(
    brief: str,
    profile_id: str,
    project_root: Path = Path(),
    risk_profile: RiskProfile | None = None,
    project_ctx: dict[str, Any] | None = None,
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
    started_at = datetime.now(UTC)
    artifacts_dir = project_root / ".polybuild" / "runs"

    # Round 9 fix [SIGINT] (3-conv: Claude + ChatGPT + Grok):
    #   Without explicit signal handling, asyncio cancels the inner task on
    #   Ctrl+C but the cleanup block in `finally:` only runs because Python's
    #   exception machinery propagates KeyboardInterrupt — and only IF the
    #   cancellation reaches a yield point. In tmux background runs, users
    #   killing the session send SIGTERM rather than SIGINT, and SIGTERM is
    #   not caught by asyncio's default handler → process killed without
    #   cleanup → orphan worktrees + Docker containers.
    #
    #   We register signal handlers on the running loop that schedule a
    #   graceful cancellation. The `finally:` below then runs phase_9
    #   cleanup synchronously before the process exits.
    import signal as _signal

    loop = asyncio.get_running_loop()
    _signals_registered: list[int] = []
    if sys.platform != "win32":
        for sig in (_signal.SIGINT, _signal.SIGTERM):
            sig_int = int(sig)

            def _make_handler(s: int) -> Callable[[], None]:
                def _handler() -> None:
                    _handle_shutdown_signal(s, run_id)

                return _handler

            try:
                loop.add_signal_handler(sig_int, _make_handler(sig_int))
                _signals_registered.append(sig_int)
            except (NotImplementedError, RuntimeError):
                logger.debug("signal_handler_unsupported", signal=sig_int)

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
        # Unregister signal handlers BEFORE running cleanup so a second Ctrl+C
        # during cleanup doesn't loop. Exit will be handled by Python normally.
        for registered_sig in _signals_registered:
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.remove_signal_handler(registered_sig)

        # Round 10.2 fix [Kimi RX-001 P0]: drain tasks scheduled by the
        # shutdown signal handler (cf. ``_handle_shutdown_signal``). Without
        # this await, asyncio raises "Task was destroyed but it is pending"
        # warnings AND the cooperative drain effectively becomes
        # fire-and-forget — so a coroutine guarded by ``asyncio.shield()``
        # would survive into phase_9 cleanup.
        drain_tasks = list(_SHUTDOWN_DRAIN_TASKS)
        _SHUTDOWN_DRAIN_TASKS.clear()
        if drain_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*drain_tasks, return_exceptions=True),
                    timeout=3.0,
                )
            except (TimeoutError, asyncio.CancelledError) as exc:
                logger.warning("shutdown_drain_timeout", error=str(exc))

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
        except BaseException as cleanup_exc:
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
    project_ctx: dict[str, Any] | None,
    skip_commit: bool,
    skip_smoke: bool,
) -> PolybuildRun:
    """Inner pipeline (Phase -1 → Phase 8). Phase 9 lives in the outer finally."""

    if risk_profile is None:
        # Default: low sensitivity unless profile suggests otherwise
        if "medical_high" in profile_id:
            sensitivity = PrivacyLevel.HIGH
        elif "medical_medium" in profile_id:
            sensitivity = PrivacyLevel.MEDIUM
        else:
            sensitivity = PrivacyLevel.LOW
        risk_profile = RiskProfile(
            sensitivity=sensitivity,
            code_inedit_critique=("inedit_critique" in profile_id),
            requires_probe=("inedit_critique" in profile_id or "helia" in profile_id),
            excludes_openrouter=(sensitivity == PrivacyLevel.HIGH),
            excludes_us_cn_models=(sensitivity == PrivacyLevel.HIGH),
        )

    logger.info("polybuild_start", run_id=run_id, profile=profile_id)

    # ── Phase -1: privacy gate (Round 4 finalisé + Round 8 [Privacy-AGENTS]) ──
    from polybuild.phases.phase_minus_one_privacy import phase_minus_one_privacy_gate

    # spec.yaml lookup: convention is the brief file living next to spec.yaml,
    # or an explicit spec_yaml_path passed in via project_ctx.
    spec_yaml_path = (project_ctx or {}).get("spec_yaml_path")
    declared_sensitivity = (project_ctx or {}).get("declared_sensitivity")

    # Round 8 fix [Privacy-AGENTS] (4/6 audits round 8 P0 — Grok, Qwen, ChatGPT,
    # Kimi): the gate must scan the FULL prompt context, not just the brief.
    # Adapters inject AGENTS.md and project_ctx into the LLM prompt AFTER the
    # gate runs, so PII hidden in those documents would bypass the gate
    # entirely. Concatenate them here.
    # Round 10 fix [R1 — prompt injection via AGENTS.md] (6/6 convergence:
    # Grok, Qwen, Gemini, DeepSeek, ChatGPT, Kimi): both AGENTS.md and the
    # caller-supplied project_ctx text are sanitized through
    # ``sanitize_prompt_context`` before being concatenated. HTML/Markdown
    # comments, XML processing instructions, zero-width Unicode and obvious
    # "ignore previous instructions" directives are stripped. Suspicious
    # patterns that survive are logged so an external auditor can investigate.
    from polybuild.security.prompt_sanitizer import sanitize_prompt_context

    additional_context_parts: list[str] = []
    agents_md_path = project_root / "AGENTS.md"
    if agents_md_path.exists():
        try:
            agents_md_clean = sanitize_prompt_context(
                agents_md_path.read_text(encoding="utf-8")
            )
            if agents_md_clean:
                additional_context_parts.append(
                    "<AGENTS_MD>\n" + agents_md_clean + "\n</AGENTS_MD>"
                )
        except OSError as e:
            logger.warning("phase_minus_one_agents_md_read_failed", error=str(e))

    project_ctx_text = (project_ctx or {}).get("extra_context_for_opus")
    if project_ctx_text:
        ctx_clean = sanitize_prompt_context(str(project_ctx_text))
        if ctx_clean:
            additional_context_parts.append(
                "<PROJECT_CONTEXT>\n" + ctx_clean + "\n</PROJECT_CONTEXT>"
            )

    additional_context = (
        "\n".join(additional_context_parts) if additional_context_parts else None
    )

    privacy_verdict = phase_minus_one_privacy_gate(
        text=brief,
        spec_path=spec_yaml_path,
        declared_sensitivity=declared_sensitivity,
        additional_context=additional_context,
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
    # phase_0_spec expects a textual context (str). The orchestrator-level
    # project_ctx is a dict; extract the textual hint we want to feed Opus.
    project_ctx_for_spec = str((project_ctx or {}).get("extra_context_for_opus", ""))
    spec = await phase_0_spec(
        run_id=run_id,
        brief=brief,
        profile_id=profile_id,
        risk_profile=risk_profile,
        project_ctx=project_ctx_for_spec,
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
    # Round 10.1 fix [Kimi P0 #4]: previously we only counted P0 (syntax)
    # findings. The audit pointed out that the spec rule "≥2 hallucinated
    # imports = disqualification" lives in ``grounding_disqualifies`` and
    # was never wired into the eligibility check. A builder with two
    # hallucinations could therefore still be picked as winner. We now apply
    # the canonical disqualification rule from phase_3b.
    from polybuild.phases.phase_3b_grounding import grounding_disqualifies

    eligible = []
    for s in scores:
        if s.disqualified:
            continue
        gfindings = grounding.get(s.voice_id, [])
        dq, dq_reason = grounding_disqualifies(gfindings)
        if dq:
            logger.warning(
                "grounding_disqualified_winner_candidate",
                voice_id=s.voice_id,
                reason=dq_reason,
            )
            continue
        eligible.append(s)
    if not eligible:
        logger.error("no_eligible_winner")
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
        )

    winner_score = eligible[0]
    winner_result = next(
        (r for r in builder_results if r.voice_id == winner_score.voice_id),
        None,
    )
    if winner_result is None:
        logger.error("winner_voice_id_not_in_builder_results", winner=winner_score.voice_id)
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
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
    # Round 9 fix [Kimi-domain-gates] (Kimi P0): the orchestrator was calling
    # phase_6_validate(spec, winner_result, artifacts_dir) without passing
    # domain_gate_configs. Result: every domain gate (MCP, SQLite, Qdrant,
    # FTS5, RAG) received None → empty config → silent failure on profiles
    # like mcp_schema_change or rag_ingestion_eval. Kimi found this by
    # cross-referencing AGENTS.md ↔ implementation; 8 audit rounds had only
    # looked at gates individually, never the wiring.
    domain_gate_configs = (project_ctx or {}).get("domain_gate_configs")
    validation = await phase_6_validate(
        spec, winner_result, artifacts_dir, domain_gate_configs=domain_gate_configs
    )
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
        duration_total_sec=(datetime.now(UTC) - started_at).total_seconds(),
        tokens=TokenUsage(),  # TODO: aggregate from adapters
        cost_eur_marginal=0.0,  # TODO: compute from usage
        final_status="committed",
        commit_sha=None,
        started_at=started_at,
        completed_at=None,
    )

    # ── Phase 7: commit ──
    if not skip_commit:
        # Round 8 [P7-isolation]: pass winner_result so Phase 7 can scope
        # the commit to LLM artefacts only (not dev's concurrent work).
        commit_info = await phase_7_commit(
            run, project_root, winner_result=winner_result
        )
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
                error_rate_threshold=float(
                    project_ctx.get("phase_8_error_threshold", 0.0)
                ),
                latency_increase_threshold=float(
                    project_ctx.get("phase_8_latency_threshold", 0.05)
                ),
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

    run.completed_at = datetime.now(UTC)
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
    spec: Any,
    builder_results: list[Any],
    scores: list[Any],
    started_at: datetime,
    **_kwargs: Any,
) -> PolybuildRun:
    """Build a PolybuildRun in aborted state for early exits.

    Extra kwargs (audit, fix_report) are accepted for API compatibility with
    callers but unused in the abort summary — they live on disk via checkpoints.
    """
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
        duration_total_sec=(datetime.now(UTC) - started_at).total_seconds(),
        tokens=TokenUsage(),
        cost_eur_marginal=0.0,
        final_status="aborted",
        commit_sha=None,
        started_at=started_at,
        completed_at=datetime.now(UTC),
    )
