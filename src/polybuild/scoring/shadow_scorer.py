"""Shadow scorer — run NaiveScorer + DevcodeScorer in parallel .

The shadow scorer always **returns the naive result as the live
winner** — it never changes the actual run output. In parallel it
computes the DEVCODE result and logs any divergence to
``~/.polybuild/scorer_shadow.jsonl``.

Use case: calibrate the DEVCODE scorer against the naive scorer in
production runs without risking pipeline failure if DEVCODE produces
a worse winner. After a few weeks of shadow data, the user can decide
whether to flip the default to ``--scorer=devcode``.

Activated via ``--scorer=devcode-shadow`` on the CLI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict

from polybuild.audit.queue import QueueLock, audit_dir, lock_path
from polybuild.scoring.naive_scorer import NaiveScorer
from polybuild.scoring.protocol import ScoredResult

if TYPE_CHECKING:
    from polybuild.models import BuilderResult, Spec

logger = structlog.get_logger()


def shadow_log_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "scorer_shadow.jsonl"


class DivergenceState(StrEnum):
    """Qualitative bucket for a scorer comparison.

    a plain ``str`` field accepted any value;
    a typo in ``_classify_divergence`` would have been silently
    persisted. ``StrEnum`` gives Pydantic a closed value set so the
    bucket stays consistent over time.

    States:
      * ``ALIGNED`` — both scorers picked the same winner.
      * ``PICKED_DIFFERENT`` — real divergence (different winners).
      * ``DEVCODE_ABSTAINED`` — DEVCODE returned None (no quorum /
        low confidence). Naïve still has a winner via eligibility.
      * ``NAIVE_ABSTAINED`` — rare — naïve had nothing eligible while
        DEVCODE found a winner.
      * ``BOTH_ABSTAINED`` — nobody picked. Not a divergence.
    """

    ALIGNED = "aligned"
    PICKED_DIFFERENT = "picked_different"
    DEVCODE_ABSTAINED = "devcode_abstained"
    NAIVE_ABSTAINED = "naive_abstained"
    BOTH_ABSTAINED = "both_abstained"


class ShadowDivergence(BaseModel):
    """One scorer comparison record (closed schema).

    the previous
    ``diverged: bool`` field conflated three distinct states. The
    ``divergence_state`` enum was introduced to separate them so the
    operator can filter abstain-noise out of weekly reports.

    /P3: the run
    #4 ``diverged`` semantic flip (strict ``picked_different`` only)
    silently broke historic dashboards that aggregated ``diverged=True``
    on the older permissive contract. ``schema_version`` now bumps to
    ``2`` with a strict ``Literal[2]`` type so any consumer can detect
    the boundary and migrate. Records persisted by v3.2.4 (or earlier)
    have ``schema_version=1`` — readers MUST treat the two cohorts as
    incompatible until backfilled.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    run_id: str
    profile_id: str
    naive_winner: str | None
    naive_confidence: float
    devcode_winner: str | None
    devcode_confidence: float
    devcode_requires_polylens_review: bool
    diverged: bool
    divergence_state: DivergenceState = DivergenceState.ALIGNED
    voices_in_panel: list[str]
    timestamp: datetime


class ShadowScorer:
    """Run NaiveScorer + DevcodeScorer; return naive, log DEVCODE divergence.

    Constructor params:
      naive: optional ``NaiveScorer`` instance (test injection).
      devcode_factory: callable returning a fresh ``DevcodeScorer``.
        Defaults to importing it lazily; tests can pass a mock.
      shadow_dir: override for the shadow log directory (tests use
        ``tmp_path``).
    """

    name = "devcode_shadow"

    def __init__(
        self,
        *,
        naive: NaiveScorer | None = None,
        devcode_factory: Any | None = None,
        shadow_dir: Path | None = None,
    ) -> None:
        self.naive = naive or NaiveScorer()
        self._devcode_factory = devcode_factory
        self._shadow_dir = shadow_dir

    def _build_devcode(self) -> Any:
        if self._devcode_factory is not None:
            return self._devcode_factory()
        # Lazy import — same opt-in path as ``--scorer=devcode``: if the
        # extra is missing we surface a clear error at the constructor
        # boundary so the caller (CLI) can convert it to BadParameter.
        from polybuild.scoring.devcode_scorer import DevcodeScorer

        return DevcodeScorer()

    async def score(
        self,
        results: list[BuilderResult],
        spec: Spec,
    ) -> ScoredResult:
        # Always run the naive scorer — its result is the live winner.
        naive_result = await self.naive.score(results, spec)

        # Best-effort DEVCODE shadow run. Any failure (ImportError,
        # ValueError on family mapping, RuntimeError inside the math
        # kernel) is logged and swallowed: the shadow run must NEVER
        # impact the live pipeline.
        #
        # the previous catch-all
        # ``except Exception`` swallowed ``MemoryError`` and
        # ``RecursionError`` too, masking catastrophic scorer failures
        # behind a "shadow_devcode_failed" log line. Narrowing to the
        # known scorer-side exceptions (Import / Value / Runtime /
        # Attribute / Type / OS) lets system-level errors propagate so
        # the orchestrator can take appropriate action.
        devcode_result: ScoredResult | None = None
        try:
            devcode_scorer = self._build_devcode()
            devcode_result = await devcode_scorer.score(results, spec)
        except (
            ImportError,
            ValueError,
            RuntimeError,
            AttributeError,
            TypeError,
            OSError,
        ) as e:
            logger.warning(
                "shadow_devcode_failed",
                run_id=spec.run_id,
                error=type(e).__name__,
                error_msg=str(e)[:200],
            )

        if devcode_result is not None:
            self._log_divergence(spec, results, naive_result, devcode_result)

        # Return the naive result as the live winner. The orchestrator
        # never sees the DEVCODE pick — it stays in the shadow log only.
        return ScoredResult(
            voice_scores=naive_result.voice_scores,
            winner_voice_id=naive_result.winner_voice_id,
            confidence=naive_result.confidence,
            requires_polylens_review=False,
            scorer_name=self.name,
            debug_data={
                "naive_winner_voice_id": naive_result.winner_voice_id,
                "naive_confidence": naive_result.confidence,
                "devcode_winner_voice_id": (
                    devcode_result.winner_voice_id if devcode_result else None
                ),
                "devcode_confidence": (
                    devcode_result.confidence if devcode_result else None
                ),
                "shadow_log_path": str(shadow_log_path(self._shadow_dir)),
            },
        )

    def _log_divergence(
        self,
        spec: Spec,
        results: list[BuilderResult],
        naive: ScoredResult,
        devcode: ScoredResult,
    ) -> None:
        """Append one ShadowDivergence record under exclusive lock."""
        # Naive abstains by construction (winner_voice_id=None) — the
        # live winner is whichever the consensus pipeline's eligibility
        # filter ends up picking. We approximate that by taking the
        # top-score not-disqualified entry, mirroring the pipeline.
        naive_winner_voice_id = self._derive_naive_winner(naive)
        # split the
        # divergence detection into qualitative states so abstain-noise
        # is filterable.
        #
        # the run-#3
        # fix added ``divergence_state`` but kept ``diverged=True`` for
        # ``devcode_abstained`` / ``naive_abstained`` "for backward
        # compat" — which silently re-introduced the calibration noise
        # the enum was supposed to remove. ``diverged`` is now strict:
        # ``True`` ONLY when both scorers picked DIFFERENT voices.
        # Abstain states surface via ``divergence_state`` for callers
        # that need them.
        divergence_state = self._classify_divergence(
            devcode_winner=devcode.winner_voice_id,
            naive_winner=naive_winner_voice_id,
        )
        diverged = divergence_state == DivergenceState.PICKED_DIFFERENT

        record = ShadowDivergence(
            run_id=spec.run_id,
            profile_id=spec.profile_id,
            naive_winner=naive_winner_voice_id,
            naive_confidence=naive.confidence,
            devcode_winner=devcode.winner_voice_id,
            devcode_confidence=devcode.confidence,
            devcode_requires_polylens_review=devcode.requires_polylens_review,
            diverged=diverged,
            divergence_state=divergence_state,
            voices_in_panel=[r.voice_id for r in results],
            timestamp=datetime.now(UTC),
        )
        spath = shadow_log_path(self._shadow_dir)
        try:
            with (
                QueueLock(lock_path(self._shadow_dir)),
                spath.open("a", encoding="utf-8") as fh,
            ):
                fh.write(record.model_dump_json() + "\n")
        except OSError as e:
            logger.warning(
                "shadow_log_write_failed",
                error=str(e),
                path=str(spath),
            )
            return

        if diverged:
            logger.info(
                "scorer_shadow_diverged",
                run_id=spec.run_id,
                divergence_state=divergence_state,
                naive_winner=naive_winner_voice_id,
                devcode_winner=devcode.winner_voice_id,
                devcode_confidence=devcode.confidence,
            )

    @staticmethod
    def _classify_divergence(
        *,
        devcode_winner: str | None,
        naive_winner: str | None,
    ) -> DivergenceState:
        """Map the (devcode_winner, naive_winner) tuple to a qualitative bucket.

        See :class:`DivergenceState` for the bucket semantics. Used by
        ``_log_divergence`` to record richer than a plain bool —
        abstain-noise is the dominant contributor to ``diverged=True``
        and operators want to filter it out of weekly calibration
        reports.
        """
        if devcode_winner is None and naive_winner is None:
            return DivergenceState.BOTH_ABSTAINED
        if devcode_winner is None:
            return DivergenceState.DEVCODE_ABSTAINED
        if naive_winner is None:
            return DivergenceState.NAIVE_ABSTAINED
        if devcode_winner == naive_winner:
            return DivergenceState.ALIGNED
        return DivergenceState.PICKED_DIFFERENT

    @staticmethod
    def _derive_naive_winner(naive: ScoredResult) -> str | None:
        """Approximate the consensus pipeline's eligibility filter.

        ``NaiveScorer`` abstains (winner_voice_id=None) so the pipeline
        picks the top non-disqualified score. Replicate that logic
        here for the divergence comparison — accurate enough for a
        calibration log, even if it doesn't account for grounding
        (which the live pipeline applies on top).
        """
        eligible = [s for s in naive.voice_scores if not s.disqualified]
        if not eligible:
            return None
        winner = max(eligible, key=lambda s: s.score)
        return winner.voice_id


__all__ = [
    "DivergenceState",
    "ShadowDivergence",
    "ShadowScorer",
    "shadow_log_path",
]
