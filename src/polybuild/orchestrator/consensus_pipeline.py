"""Canonical consensus pipeline (Phase 1 → Phase 5).

Extracted from :func:`polybuild.orchestrator._run_polybuild_inner` in
M2B.0. Behaviour is byte-identical to the prior in-line implementation
when used with the default ``NaiveScorer``. Pass a
:class:`~polybuild.scoring.devcode_scorer.DevcodeScorer` to enable
DEVCODE-Vote v1 arbitration (Schulze pondéré bayésien Glicko-2 +
family collusion + cross-cultural supermajority).

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
from polybuild.scoring import NaiveScorer, ScorerProtocol

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

    Constructor:

      scorer: any :class:`ScorerProtocol` implementation. Defaults to
        :class:`NaiveScorer` (current Phase 3 gate-based scoring,
        winner picked by the eligibility filter). Pass
        :class:`DevcodeScorer` for DEVCODE-Vote v1 arbitration — the
        Schulze winner overrides the eligibility filter unless the
        scorer abstains.
    """

    name = "consensus"

    def __init__(self, scorer: ScorerProtocol | None = None) -> None:
        self.scorer: ScorerProtocol = scorer or NaiveScorer()

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

        # ── Phase 3: scoring (delegated to scorer strategy, M2A) ──
        scored = await self.scorer.score(builder_results, spec)
        scores = scored.voice_scores
        save_checkpoint(
            run_id, "phase3",
            {
                "scores": [s.model_dump() for s in scores],
                "scorer_name": scored.scorer_name,
                "confidence": scored.confidence,
                "requires_polylens_review": scored.requires_polylens_review,
                "winner_voice_id_from_scorer": scored.winner_voice_id,
                "debug_data": scored.debug_data,
            },
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

        # Determine winner.
        # Two paths:
        #   * The scorer returned an explicit ``winner_voice_id`` (DEVCODE
        #     Schulze winner, M2A.2). We honour it as long as the matching
        #     ``BuilderResult`` exists and is not grounding-disqualified.
        #   * The scorer abstained (``winner_voice_id is None``, the naive
        #     case). Apply the canonical eligibility filter below — same
        #     algorithm as before M2A.
        # Round 10.1 fix [Kimi P0 #4]: ``grounding_disqualifies`` is
        # applied in BOTH paths; the spec rule "≥2 hallucinated imports
        # = disqualification" lives in ``grounding_disqualifies`` and a
        # winner with hallucinations is unsafe regardless of the scorer.
        winner_score: Any | None = None
        winner_result: Any | None = None
        abort_reason: str | None = None

        if scored.winner_voice_id is not None:
            # Scorer-picked winner.
            winner_score = next(
                (s for s in scores if s.voice_id == scored.winner_voice_id),
                None,
            )
            if winner_score is None:
                logger.error(
                    "scorer_winner_voice_id_not_in_scores",
                    winner=scored.winner_voice_id,
                    scorer=scored.scorer_name,
                )
                abort_reason = "scorer_winner_voice_id_not_in_scores"
            else:
                gfindings = grounding.get(winner_score.voice_id, [])
                dq, dq_reason = _orch.grounding_disqualifies(gfindings)
                if dq:
                    logger.warning(
                        "scorer_winner_grounding_disqualified",
                        voice_id=winner_score.voice_id,
                        reason=dq_reason,
                        scorer=scored.scorer_name,
                    )
                    abort_reason = "scorer_winner_grounding_disqualified"
                    winner_score = None

        if winner_score is None and abort_reason is None:
            # Eligibility-filter path (naive scorer abstain or scorer
            # didn't pick / its pick was disqualified upstream).
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
            if eligible:
                winner_score = eligible[0]
            else:
                logger.error("no_eligible_winner")
                abort_reason = "no_eligible_winner"

        if winner_score is None:
            return StrategyOutcome(
                voices=voices,
                builder_results=builder_results,
                scores=scores,
                grounding=grounding,
                aborted=True,
                abort_reason=abort_reason or "no_eligible_winner",
            )

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
