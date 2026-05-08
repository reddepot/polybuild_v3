"""Canonical consensus pipeline (Phase 1 → Phase 5).

Extracted from :func:`polybuild.orchestrator._run_polybuild_inner` in
M2B.0. Behaviour is byte-identical to the prior in-line implementation —
only the surrounding control-flow is now expressed via the
:class:`~polybuild.orchestrator.pipeline_strategy.PipelineStrategy`
protocol so that ``SoloPipeline`` (M2B.2) can plug into the same
orchestrator without conditional branches.

Phase functions are looked up dynamically through the
``polybuild.orchestrator`` module so that test code that calls
``unittest.mock.patch("polybuild.orchestrator.<phase>", ...)`` continues
to intercept the calls. The orchestrator module re-exports the phase
callables for exactly this reason.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from polybuild.orchestrator.pipeline_strategy import (
    CheckpointFn,
    StrategyOutcome,
)

if TYPE_CHECKING:
    from polybuild.models import RiskProfile, Spec

logger = structlog.get_logger()


class ConsensusPipeline:
    """Default multi-voice pipeline: parallel generate → score → audit → fix.

    Mirrors the historical orchestrator behaviour. Returns an
    ``aborted`` outcome (without raising) whenever:

      * no candidate survives the eligibility / grounding filter, or
      * the chosen winner is missing from ``builder_results`` (data-flow
        bug, defensive guard kept from the prior implementation), or
      * Phase 5 returns ``blocked_p0``.
    """

    name = "consensus"

    async def run(
        self,
        *,
        spec: Spec,
        risk_profile: RiskProfile,
        project_root: Path,
        project_ctx: dict[str, Any] | None,
        artifacts_dir: Path,
        run_id: str,
        config_root: Path,
        save_checkpoint: CheckpointFn,
    ) -> StrategyOutcome:
        del project_ctx, artifacts_dir  # not used directly; kept for protocol

        # Late attribute lookup so mock.patch on the orchestrator module
        # intercepts every call — see module docstring.
        import polybuild.orchestrator as _orch

        # ── Phase 1: voice selection ──
        voices = await _orch.select_voices(spec, config_root=config_root)
        save_checkpoint(
            run_id, "phase1",
            {"voices": [v.model_dump() for v in voices]},
            project_root,
        )

        # ── Phase 2: parallel generation ──
        builder_results = await _orch.phase_2_generate(spec, voices)
        save_checkpoint(
            run_id, "phase2",
            {"results": [r.model_dump(mode="json") for r in builder_results]},
            project_root,
        )

        # ── Phase 3: scoring ──
        scores = await _orch.phase_3_score(builder_results)
        save_checkpoint(
            run_id, "phase3",
            {"scores": [s.model_dump() for s in scores]},
            project_root,
        )

        # ── Phase 3b: grounding ──
        grounding = await _orch.phase_3b_grounding(builder_results, project_root)
        save_checkpoint(
            run_id, "phase3b",
            {vid: [f.model_dump(mode="json") for f in fs]
             for vid, fs in grounding.items()},
            project_root,
        )

        # Determine winner: highest score, not disqualified, no critical
        # grounding finding.
        # Round 10.1 fix [Kimi P0 #4]: previously we only counted P0
        # (syntax) findings. The audit pointed out that the spec rule
        # "≥2 hallucinated imports = disqualification" lives in
        # ``grounding_disqualifies`` and was never wired into the
        # eligibility check. A builder with two hallucinations could
        # therefore still be picked as winner. We now apply the canonical
        # disqualification rule from phase_3b.
        eligible = []
        for s in scores:
            if s.disqualified:
                continue
            gfindings = grounding.get(s.voice_id, [])
            dq, dq_reason = _orch.grounding_disqualifies(gfindings)
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
            return StrategyOutcome(
                voices=voices,
                builder_results=builder_results,
                scores=scores,
                grounding=grounding,
                aborted=True,
                abort_reason="no_eligible_winner",
            )

        winner_score = eligible[0]
        winner_result = next(
            (r for r in builder_results if r.voice_id == winner_score.voice_id),
            None,
        )
        if winner_result is None:
            logger.error(
                "winner_voice_id_not_in_builder_results",
                winner=winner_score.voice_id,
            )
            return StrategyOutcome(
                voices=voices,
                builder_results=builder_results,
                scores=scores,
                grounding=grounding,
                winner_score=winner_score,
                aborted=True,
                abort_reason="winner_voice_id_not_in_builder_results",
            )

        # ── Phase 4: audit ──
        audit = await _orch.phase_4_audit(
            winner_result,
            spec.profile_id,
            risk_profile,
            config_root=config_root,
        )
        save_checkpoint(
            run_id, "phase4",
            audit.model_dump(mode="json"),
            project_root,
        )

        # ── Phase 5: triade ──
        fix_report = await _orch.phase_5_dispatch(audit, winner_result, risk_profile)
        save_checkpoint(
            run_id, "phase5",
            fix_report.model_dump(mode="json"),
            project_root,
        )

        if fix_report.status == "blocked_p0":
            logger.error("polybuild_blocked_p0", run_id=run_id)
            return StrategyOutcome(
                voices=voices,
                builder_results=builder_results,
                scores=scores,
                grounding=grounding,
                winner_result=winner_result,
                winner_score=winner_score,
                audit=audit,
                fix_report=fix_report,
                aborted=True,
                abort_reason="phase_5_blocked_p0",
            )

        return StrategyOutcome(
            voices=voices,
            builder_results=builder_results,
            scores=scores,
            grounding=grounding,
            winner_result=winner_result,
            winner_score=winner_score,
            audit=audit,
            fix_report=fix_report,
        )


__all__ = ["ConsensusPipeline"]
