"""Pipeline execution strategy contract (M2B.0).

The top-level :func:`polybuild.orchestrator.run_polybuild` always runs
Phase -1 (privacy gate), Phase 0 (spec), Phase 6 (validation), Phase 7
(commit), Phase 8 (production smoke) and the final archival. The
``Phase 1 → Phase 5`` segment — voice selection, parallel generation,
scoring, grounding, audit, triade fix — *varies* depending on the
execution mode requested by the caller:

* ``ConsensusPipeline`` (default): the canonical multi-voice pipeline
  (current behaviour).
* ``SoloPipeline`` (M2B.2): a single-voice short-circuit that bypasses
  parallel generation, scoring and the critic-fixer-verifier triade.

This module defines the contract those pipelines share so that the
orchestrator can route between them without conditional ``if/else``
branches. It is intentionally minimal: only what the orchestrator needs
to chain Phase 6 onwards travels in :class:`StrategyOutcome`. Anything a
pipeline wants to keep private (intermediate logs, partial artefacts)
stays inside the strategy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from polybuild.models import (
        AuditReport,
        BuilderResult,
        FixReport,
        GroundingFinding,
        RiskProfile,
        Spec,
        VoiceConfig,
        VoiceScore,
    )


# Signature of ``polybuild.orchestrator.save_checkpoint``. Injected so a
# strategy can persist intermediate phase artefacts on disk without having
# to import the orchestrator module (avoids a circular import) and so test
# doubles can capture every checkpoint emitted during a run.
CheckpointFn = Callable[[str, str, dict[str, Any], Path], None]


@dataclass(frozen=True, slots=True)
class StrategyOutcome:
    """Result handed back by a :class:`PipelineStrategy` to the orchestrator.

    Carries everything the caller (the top-level orchestrator) needs to
    drive Phase 6 (validation) onwards or to build an aborted-run summary
    via :func:`polybuild.orchestrator._build_aborted_run`.

    Strategies SHOULD set ``aborted=True`` and a human-readable
    ``abort_reason`` whenever they decide the run cannot continue (no
    eligible candidate, Phase 5 returned ``blocked_p0``, etc.). The
    orchestrator never inspects the strategy beyond what this dataclass
    exposes.

    POLYLENS-FIX-9 P2: a ``__post_init__`` validator enforces the
    contract — when ``aborted=False``, ``winner_result`` and
    ``winner_score`` MUST be present (the orchestrator already checks
    this defensively but having the invariant on the dataclass itself
    catches programmer errors at construction time, with a clearer
    traceback than a downstream attribute access).
    """

    voices: list[VoiceConfig]
    builder_results: list[BuilderResult]
    scores: list[VoiceScore]
    grounding: dict[str, list[GroundingFinding]] = field(default_factory=dict)
    winner_result: BuilderResult | None = None
    winner_score: VoiceScore | None = None
    audit: AuditReport | None = None
    fix_report: FixReport | None = None
    aborted: bool = False
    abort_reason: str | None = None

    def __post_init__(self) -> None:
        if self.aborted:
            return  # any combination is allowed on the abort path
        missing = [
            name
            for name, value in (
                ("winner_result", self.winner_result),
                ("winner_score", self.winner_score),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                "StrategyOutcome contract violation: aborted=False "
                f"but missing winner artefacts: {missing}. A strategy "
                "that cannot pick a winner MUST set aborted=True with "
                "an abort_reason."
            )


class PipelineStrategy(Protocol):
    """Strategy interface for the Phase 1 → Phase 5 segment.

    Implementations decide *how* candidate code is produced and selected:
    canonical multi-voice consensus (``ConsensusPipeline``) or
    single-voice solo (``SoloPipeline``). They MUST be safe to call from
    an asyncio context and SHOULD ``save_checkpoint`` after each of their
    internal phases so that ``polybuild resume`` retains its semantics.
    """

    name: str

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
        """Execute the strategy's portion of the pipeline.

        Args:
            spec: validated Phase 0 output.
            risk_profile: privacy/sensitivity policy active for the run
                (already updated by Phase -1's ``ESCALATE_PARANOIA`` path
                if applicable).
            project_root: user's project root (for config resolution and
                grounding lookups).
            project_ctx: optional caller context (skill ``/polybuild``).
            artifacts_dir: per-run artefact directory (run logs, JSON).
            run_id: sanitised run identifier.
            config_root: directory holding ``routing.yaml`` etc.
            save_checkpoint: persistence callback ``(run_id, phase_name,
                payload_dict, project_root) -> None``.

        Returns:
            A :class:`StrategyOutcome` describing what the strategy
            produced. ``aborted=True`` instructs the orchestrator to skip
            Phase 6+ and emit a ``_build_aborted_run`` summary.
        """
        ...


__all__ = ["CheckpointFn", "PipelineStrategy", "StrategyOutcome"]
