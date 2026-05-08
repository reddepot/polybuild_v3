"""NaiveScorer — current Phase 3 behaviour wrapped in ``ScorerProtocol`` (M2A.2).

The naive scorer keeps the historical scoring algorithm verbatim:

  * run general gates (pytest, mypy, ruff, bandit, gitleaks, coverage)
    on each candidate's worktree,
  * disqualify on hard rules (todo > 3, gitleaks > 0, acceptance < 0.5),
  * compute the deterministic score formula (35*acceptance + 15*bandit
    + 15*mypy + 10*ruff + 10*coverage + 10*gitleaks + 5*diff_minimality
    minus penalties),
  * sort descending.

This module is a thin adapter over ``polybuild.orchestrator.phase_3_score``
so test suites that ``mock.patch("polybuild.orchestrator.phase_3_score",
...)`` keep intercepting the call.

The scorer **abstains** on winner selection — ``ScoredResult.winner_voice_id``
is always ``None`` for the naive path. The consensus pipeline then runs
its canonical eligibility filter (highest non-disqualified score that
survives Phase 3b grounding) to pick the winner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polybuild.scoring.protocol import ScoredResult

if TYPE_CHECKING:
    from polybuild.models import BuilderResult, Spec


class NaiveScorer:
    """Default scorer — gates + score formula, no cross-voice arbitration."""

    name = "naive"

    async def score(
        self,
        results: list[BuilderResult],
        spec: Spec,
    ) -> ScoredResult:
        del spec  # not used by the naive formula

        # Late attribute lookup so existing tests that
        # ``mock.patch("polybuild.orchestrator.phase_3_score", ...)`` keep
        # intercepting the call inside the consensus pipeline.
        import polybuild.orchestrator as _orch

        voice_scores = await _orch.phase_3_score(results)

        # Confidence proxy for the naive path: the winner's score
        # normalised onto [0.0, 1.0]. The score formula tops out at 100,
        # so dividing by 100 keeps things linear and easy to compare with
        # DEVCODE's ``Decision.confidence``.
        if voice_scores:
            top_score = max(s.score for s in voice_scores)
            confidence = max(0.0, min(1.0, top_score / 100.0))
        else:
            confidence = 0.0

        return ScoredResult(
            voice_scores=voice_scores,
            winner_voice_id=None,
            confidence=confidence,
            requires_polylens_review=False,
            scorer_name=self.name,
        )


__all__ = ["NaiveScorer"]
