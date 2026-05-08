"""Scorer protocol contract (M2A.0).

The historical Phase 3 scorer was hard-coded inside
``polybuild.phases.phase_3_score`` and returned a bare ``list[VoiceScore]``.
M2A turns scoring into a strategy: the consensus pipeline accepts any
``ScorerProtocol`` implementation and consumes a unified ``ScoredResult``
output. Two scorers ship with M2A.2:

  * ``NaiveScorer`` (default): refactor of the current scoring code under
    the protocol — same gates, same per-voice score, same winner-by-
    eligibility-filter logic.
  * ``DevcodeScorer`` (opt-in via ``--scorer=devcode``): maps the builder
    results to ``devcode.aggregation.devcode_vote_v1`` (Schulze pondéré
    bayésien Glicko-2) and surfaces the resulting ``Decision``.

Both scorers expose the same observable surface so the consensus pipeline
stays free of ``if scorer == "devcode": ...`` branches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

# Pydantic v2 needs ``VoiceScore`` resolved at class-creation time for
# ``ScoredResult.voice_scores: list[VoiceScore]`` to validate; it cannot
# stay inside ``TYPE_CHECKING`` like ``BuilderResult`` / ``Spec`` (which
# only appear in ``Protocol`` signatures).
from polybuild.models import VoiceScore

if TYPE_CHECKING:
    from polybuild.models import BuilderResult, Spec


class ScoredResult(BaseModel):
    """Unified output of any :class:`ScorerProtocol`.

    Fields:

      voice_scores: per-voice gate results. Always populated. ``NaiveScorer``
        fills it from the current Phase 3 gates; ``DevcodeScorer`` produces
        equivalents via the ``builder_results_to_devcode_votes`` adapter so
        downstream code (PolybuildRun aggregation) stays format-stable.

      winner_voice_id: the scorer's chosen winner. ``None`` means the
        scorer abstains and the pipeline must pick the winner itself
        through the canonical eligibility filter (highest non-disqualified
        score that survives grounding). The naive scorer abstains by
        construction; the DEVCODE scorer fills this with the Schulze winner.

      confidence: ``0.0`` to ``1.0``. ``NaiveScorer`` reports the winner's
        normalised score; ``DevcodeScorer`` reports ``Decision.confidence``
        (fraction of voices for the winner under supermajority quorum).

      requires_polylens_review: surfaced from
        ``devcode.models.Decision.requires_polylens_review``. ``True`` flags
        a tie-broken decision that should not be merged without a human or
        POLYLENS pass. The naive scorer never sets this.

      scorer_name: short identifier (``"naive"`` / ``"devcode"`` /
        ``"devcode_shadow"``) for logs and the M2-final ADR.

      debug_data: raw scorer-specific output. ``DevcodeScorer`` stores the
        full ``Decision.model_dump()`` here so post-mortems can inspect the
        Schulze matrices and the family-collusion penalties.
    """

    model_config = ConfigDict(frozen=True)

    voice_scores: list[VoiceScore]
    winner_voice_id: str | None = None
    confidence: float = 0.0
    requires_polylens_review: bool = False
    scorer_name: str = "naive"
    debug_data: dict[str, Any] = Field(default_factory=dict)


class ScorerProtocol(Protocol):
    """Strategy contract for Phase 3 scoring.

    Implementations MUST:

      * be safe to call inside an asyncio event loop (use
        ``asyncio.to_thread`` to wrap any CPU-bound math kernel),

      * preserve the per-voice ``VoiceScore`` shape so PolybuildRun
        aggregation stays untouched (M2A backward-compat invariant),

      * return ``winner_voice_id=None`` whenever the scorer wants the
        pipeline to apply its canonical eligibility filter (current
        behaviour). Non-``None`` overrides the filter.
    """

    name: str

    async def score(
        self,
        results: list[BuilderResult],
        spec: Spec,
    ) -> ScoredResult:
        """Compute per-voice scores and (optionally) the winner.

        Args:
            results: Phase 2 outputs (one entry per voice, including
                ``Status.FAILED`` ones).
            spec: validated Phase 0 spec; provides ``profile_id``,
                ``risk_profile`` and the acceptance criteria the scorer
                may consult.

        Returns:
            A :class:`ScoredResult` consumed by the consensus pipeline.
        """
        ...


__all__ = ["ScoredResult", "ScorerProtocol"]
