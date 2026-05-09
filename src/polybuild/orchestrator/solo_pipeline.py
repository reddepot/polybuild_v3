"""Solo pipeline — single-voice short-circuit (M2B.2).

Skips the consensus-only phases (Phase 2 parallel generation, Phase 3
scoring, Phase 5 critic-fixer-verifier triade) and runs a single
configured adapter end-to-end. Phase -1 (privacy), Phase 0 (spec),
Phase 4 (audit), Phase 6 (validation), Phase 7 (commit), Phase 8
(production smoke) and Phase 9 (cleanup) all still run via the
top-level orchestrator — the strategy only controls Phase 1 → Phase 5.

Use cases:
  * one-shot iterations where multi-voice arbitrage is overkill
    (cosmetic refactors, doc updates, simple bug fixes),
  * cost-sensitive runs (1 LLM call vs 3-5),
  * fast-feedback dev loops (no Phase 5 fix iterations).

Trade-offs:
  * No cross-voice disagreement signal → less robust on edge cases.
  * No automatic P0 fix loop → on a Phase 4 P0 finding the run aborts
    rather than dispatching the triade. Re-run in consensus mode
    (default) to recover.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from polybuild.models import (
    FixReport,
    GateResults,
    Severity,
    Status,
    VoiceConfig,
    VoiceScore,
)
from polybuild.orchestrator.pipeline_strategy import (
    CheckpointFn,
    StrategyOutcome,
)

if TYPE_CHECKING:
    from polybuild.models import RiskProfile, Spec

logger = structlog.get_logger()


# Default builder for the solo pipeline. Anthropic Claude Code CLI is the most
# capable single-voice adapter available locally (no third-party API key
# required). Constructor accepts an override for tests and CLI customisation.
_DEFAULT_VOICE_ID = "claude-opus-4.7"
_DEFAULT_FAMILY = "anthropic"


class SoloPipeline:
    """Single-voice pipeline used when ``run_polybuild(strategy=SoloPipeline())``
    or ``polybuild run --solo`` is invoked.

    Constructor parameters allow callers to pick a different adapter when
    Claude is unavailable or when the task profile suggests another voice
    (e.g. Codex GPT-5.5 for low-level optimisation work).
    """

    name = "solo"

    def __init__(
        self,
        voice_id: str = _DEFAULT_VOICE_ID,
        family: str = _DEFAULT_FAMILY,
        timeout_sec: int = 720,
    ) -> None:
        self.voice_id = voice_id
        self.family = family
        self.timeout_sec = timeout_sec

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
        del project_ctx, artifacts_dir  # not used; kept for protocol parity

        # Late attribute lookup so test code that calls
        # ``mock.patch("polybuild.orchestrator.<phase>", ...)`` still
        # intercepts the calls — same trick as ConsensusPipeline.
        import polybuild.orchestrator as _orch

        # ── Phase 1: voice selection (single voice, no Phase 1 algorithm) ──
        voice = VoiceConfig(
            voice_id=self.voice_id,
            family=self.family,
            role="builder",
            timeout_sec=self.timeout_sec,
        )
        save_checkpoint(
            run_id, "phase1",
            {"voices": [voice.model_dump()], "strategy": self.name},
            project_root,
        )

        # ── Phase 2: single-voice generation (no parallel, no limiter) ──
        from polybuild.adapters import get_builder

        builder = get_builder(voice.voice_id)
        logger.info(
            "solo_phase_2_start",
            run_id=run_id,
            voice_id=voice.voice_id,
        )
        builder_result = await builder.generate(spec, voice)
        save_checkpoint(
            run_id, "phase2",
            {"results": [builder_result.model_dump(mode="json")],
             "strategy": self.name},
            project_root,
        )

        if builder_result.status != Status.OK:
            logger.error(
                "solo_phase_2_voice_failed",
                voice_id=voice.voice_id,
                status=builder_result.status,
                error=builder_result.error,
            )
            return StrategyOutcome(
                voices=[voice],
                builder_results=[builder_result],
                scores=[],
                aborted=True,
                abort_reason=f"solo_voice_failed:{builder_result.status}",
            )

        # ── Phase 3: scoring SKIPPED — single voice is the winner. ──
        # Stub a VoiceScore so downstream code that iterates ``scores``
        # (PolybuildRun aggregation) keeps working.
        #
        # POLYLENS run #4 P1 (Grok 4.3): the previous stub used
        # ``score=1.0`` + all-green gates which made a solo run look
        # like a perfect 1.0-score run in dashboards and metric
        # exports. Now ``score=0.0`` + ``is_solo_stub=True`` so any
        # consumer that wants to compute averages or "% of P0 audits
        # surfaced" can explicitly skip the stub. Gates are still
        # populated with neutral values so a downstream gate-checker
        # doesn't ``KeyError`` on a ``None``.
        stub_score = VoiceScore(
            voice_id=voice.voice_id,
            score=0.0,
            gates=GateResults(
                acceptance_pass_ratio=0.0,
                bandit_clean=True,
                mypy_strict_clean=True,
                ruff_clean=True,
                coverage_score=0.0,
                gitleaks_clean=True,
                gitleaks_findings_count=0,
                diff_minimality=1.0,
            ),
            disqualified=False,
            is_solo_stub=True,
        )
        save_checkpoint(
            run_id, "phase3",
            {"scores": [stub_score.model_dump()], "skipped": True,
             "strategy": self.name},
            project_root,
        )

        # ── Phase 3b: grounding (KEPT — POLYLENS-FIX-5 P1). ──
        # Earlier versions skipped grounding in solo mode; gpt-5.5
        # POLYLENS audit flagged this as P1 because hallucinated imports
        # would slip past Phase 4 audit too (Phase 4 doesn't re-run
        # ``grounding_disqualifies``). Solo now runs Phase 3b on the
        # single candidate and aborts when ≥2 hallucinations are found,
        # mirroring the consensus pipeline's eligibility filter.
        grounding = await _orch.phase_3b_grounding([builder_result], project_root)
        save_checkpoint(
            run_id, "phase3b",
            {vid: [f.model_dump(mode="json") for f in fs]
             for vid, fs in grounding.items()},
            project_root,
        )
        gfindings = grounding.get(builder_result.voice_id, [])
        dq, dq_reason = _orch.grounding_disqualifies(gfindings)
        if dq:
            logger.error(
                "solo_phase_3b_grounding_disqualified",
                run_id=run_id,
                voice_id=builder_result.voice_id,
                reason=dq_reason,
                hint="Re-run in consensus mode to engage multi-voice arbitration.",
            )
            return StrategyOutcome(
                voices=[voice],
                builder_results=[builder_result],
                scores=[stub_score],
                grounding=grounding,
                winner_result=builder_result,
                winner_score=stub_score,
                aborted=True,
                abort_reason=f"solo_phase_3b_disqualified:{dq_reason}",
            )

        # ── Phase 4: audit (KEPT — safety check on the single candidate). ──
        audit = await _orch.phase_4_audit(
            builder_result,
            spec.profile_id,
            risk_profile,
            config_root=config_root,
        )
        save_checkpoint(
            run_id, "phase4",
            audit.model_dump(mode="json"),
            project_root,
        )

        # Solo cannot run the triade fix loop, so a Phase 4 P0 finding is
        # unrecoverable — abort and let the user re-run with the
        # consensus pipeline (which would dispatch Phase 5 to fix it).
        p0_findings = [f for f in audit.findings if f.severity == Severity.P0]
        if p0_findings:
            logger.error(
                "solo_phase_4_p0_unrecoverable",
                run_id=run_id,
                p0_count=len(p0_findings),
                hint="Re-run in consensus mode (default) to engage the Phase 5 fix loop.",
            )
            return StrategyOutcome(
                voices=[voice],
                builder_results=[builder_result],
                scores=[stub_score],
                grounding=grounding,
                winner_result=builder_result,
                winner_score=stub_score,
                audit=audit,
                aborted=True,
                abort_reason="solo_phase_4_p0_no_triade",
            )

        # ── Phase 5: triade SKIPPED in solo. Stub a completed FixReport. ──
        fix_report = FixReport(status="completed", results=[])
        save_checkpoint(
            run_id, "phase5",
            {"fix_report": fix_report.model_dump(mode="json"),
             "skipped": True, "strategy": self.name},
            project_root,
        )

        return StrategyOutcome(
            voices=[voice],
            builder_results=[builder_result],
            scores=[stub_score],
            grounding=grounding,
            winner_result=builder_result,
            winner_score=stub_score,
            audit=audit,
            fix_report=fix_report,
        )


__all__ = ["SoloPipeline"]
