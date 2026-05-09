"""DevcodeScorer — Schulze pondéré bayésien Glicko-2 (M2A.2, opt-in).

Layer on top of :class:`NaiveScorer`:

  1. NaiveScorer runs the gates and produces ``voice_scores``.
  2. ``builder_results_to_devcode_votes`` maps the OK results + scores to
     ``devcode.models.Vote`` plus a ``DecisionContext``.
  3. ``devcode.aggregation.devcode_vote_v1`` runs Schulze (with family
     collusion penalty + Glicko-2 reputation weighting + cross-cultural
     supermajority check) and returns a ``Decision``.
  4. The Schulze winner option is mapped back to a ``voice_id``; the
     decision's ``confidence`` and ``requires_polylens_review`` flags
     surface inside the returned :class:`ScoredResult`.

Activated via ``--scorer=devcode`` on the CLI or by passing
``ConsensusPipeline(scorer=DevcodeScorer())`` programmatically. In the
default ``--scorer=naive`` path this module is never imported.

The reputation store is pluggable: callers can pass a persistent
:class:`devcode.reputation_sqlite.SQLiteReputationStore` for longitudinal
Glicko-2 ratings, or rely on the in-memory default for stateless runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from polybuild.models import Status
from polybuild.scoring.naive_scorer import NaiveScorer
from polybuild.scoring.protocol import ScoredResult

if TYPE_CHECKING:
    from devcode.reputation import ReputationStore

    from polybuild.models import BuilderResult, Spec

logger = structlog.get_logger()


class DevcodeScorer:
    """Multi-voice arbitrage via DEVCODE-Vote v1.

    Importing this class does NOT pull in ``devcode``; the dependency is
    only required when ``score()`` is awaited or when a custom store is
    constructed inline. This keeps the optional ``[devcode]`` extra truly
    optional.

    Constructor parameters:

      store: optional ``devcode.reputation.ReputationStore`` for persistent
        Glicko-2 ratings. Defaults to ``InMemoryReputationStore`` (no
        persistence — Glicko priors only). Pass ``SQLiteReputationStore``
        in production to accumulate per-voice / per-domain reputation.

      naive_fallback: NaiveScorer instance used to pre-compute
        ``voice_scores``. Injected for test isolation; defaults to a fresh
        ``NaiveScorer()``.
    """

    name = "devcode"

    def __init__(
        self,
        store: ReputationStore | None = None,
        naive_fallback: NaiveScorer | None = None,
    ) -> None:
        if store is None:
            # Lazy import — keeps the module importable without devcode.
            from devcode.reputation import InMemoryReputationStore

            store = InMemoryReputationStore()
        self.store = store
        self.naive = naive_fallback or NaiveScorer()

    async def score(
        self,
        results: list[BuilderResult],
        spec: Spec,
    ) -> ScoredResult:
        # Step 1: run the naive gate scorer to get per-voice gate
        # verdicts (PolybuildRun aggregation downstream still consumes
        # ``voice_scores``).
        naive_result = await self.naive.score(results, spec)

        ok_results = [r for r in results if r.status == Status.OK]
        if len(ok_results) < 2:
            # DEVCODE needs at least two voices to arbitrate. With one or
            # zero candidates the naive winner-by-eligibility-filter is
            # already optimal — abstain and let the consensus pipeline
            # apply its filter.
            return ScoredResult(
                voice_scores=naive_result.voice_scores,
                winner_voice_id=None,
                confidence=naive_result.confidence,
                requires_polylens_review=False,
                scorer_name="devcode_no_quorum",
                debug_data={"reason": "fewer_than_two_ok_voices"},
            )

        # Lazy imports — pulling devcode in only when actually needed
        # (M2A.3 contract). The adapter and the math kernel both raise
        # ImportError if the optional ``[devcode]`` extra is not installed.
        from devcode.aggregation import devcode_vote_v1

        from polybuild.scoring.devcode_adapter import (
            builder_results_to_devcode_votes,
            option_to_voice_id,
        )

        # POLYLENS run #3 P1 (qwen3.6-max-preview): an unmapped POLYBUILD
        # family (e.g. ``"xai"`` if a Grok voice is added to a profile
        # without first updating ``_FAMILY_MAP``) raised a bare
        # ``ValueError`` from ``builder_results_to_devcode_votes`` that
        # bubbled to the orchestrator and aborted the entire run.
        # Graceful degradation: catch the mapping failure, fall back to
        # naive abstain (``winner_voice_id=None``) so the consensus
        # pipeline's eligibility filter still picks a winner.
        try:
            votes, ctx = builder_results_to_devcode_votes(
                results, naive_result.voice_scores, spec
            )
            # devcode_vote_v1 is CPU-bound math (no I/O); call it directly
            # rather than dispatching to a thread.
            decision = devcode_vote_v1(votes, ctx, self.store)
        except ValueError as e:
            logger.warning(
                "devcode_scorer_unmapped_family_or_invalid_input",
                run_id=spec.run_id,
                error=str(e)[:300],
                hint=(
                    "Falling back to naive abstain. Add the missing "
                    "POLYBUILD family to scoring/devcode_adapter._FAMILY_MAP."
                ),
            )
            return ScoredResult(
                voice_scores=naive_result.voice_scores,
                winner_voice_id=None,
                confidence=naive_result.confidence,
                requires_polylens_review=False,
                scorer_name="devcode_unmapped_family",
                debug_data={"reason": "unmapped_family_or_invalid_input",
                            "error": str(e)[:300]},
            )

        winner_voice_id = option_to_voice_id(decision.winner, ok_results)

        debug: dict[str, Any] = {
            "phase_resolved": decision.phase_resolved,
            "schulze_ranking": list(decision.schulze_ranking),
            "weights_applied": dict(decision.weights_applied),
            "family_collusion_penalties": [
                dict(p) for p in decision.family_collusion_penalties
            ],
            "arbitre_if_split": decision.arbitre_if_split,
        }

        return ScoredResult(
            voice_scores=naive_result.voice_scores,
            winner_voice_id=winner_voice_id,
            confidence=decision.confidence,
            requires_polylens_review=decision.requires_polylens_review,
            scorer_name=self.name,
            debug_data=debug,
        )


__all__ = ["DevcodeScorer"]
