"""Adapter — POLYBUILD ``BuilderResult`` + ``VoiceScore`` → DEVCODE ``Vote`` (M2A.1).

DEVCODE-Vote v1 expects a list of ``Vote`` (each one ranks the options) and
a ``DecisionContext`` (priority, options, deterministic seed). POLYBUILD
produces a list of ``BuilderResult`` (one per voice, possibly some FAILED)
plus a list of ``VoiceScore`` (gate verdicts + scalar score).

This module is a **pure function** with no side-effects, no network and no
LLM calls — the heavy math is done by ``devcode.aggregation.devcode_vote_v1``
once we have the votes.

## Heuristic ranking

DEVCODE asks each voice to rank the options (= candidates = OK voices). We
do not have cross-voice evaluation in POLYBUILD, so we synthesise a
*consensus heuristic*: every voice ranks the candidates by their gate
score, descending, with a deterministic alphabetical tie-break on
``voice_id``. Each voice also reports the same ``confidences`` map (one
value per option, equal to that option's gate score).

Under this heuristic the Schulze step is degenerate (all voices agree) and
DEVCODE-Vote v1's value-add reduces to:

  * family collusion penalty (cosine similarity on output embeddings —
    None here for now, so the penalty is inactive),
  * reputation weighting (Glicko-2 mu/RD per voice / domain / task_type),
  * cross-cultural supermajority check (P0/P1/P2 require ≥1 non-Western
    voice).

That is still strictly more information than the bare ``max(score)``
picker the naive scorer uses, which is the M2A trade-off the user agreed
to (option β reformulée).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from devcode.models import (
    DecisionContext,
    Family,
    Priority,
    Vote,
)

from polybuild.models import PrivacyLevel, Status

if TYPE_CHECKING:
    from polybuild.models import BuilderResult, Spec, VoiceScore


# DEVCODE's ``OptionId`` is ``TypeAlias = int`` but mypy can't see through
# the ``devcode`` override (no ``py.typed`` marker), so we use plain ``int``
# locally to keep strict typing at the POLYBUILD boundary.
OptionId = int


# POLYBUILD family strings → DEVCODE ``Family`` enum. Kept exhaustive on
# purpose: any new POLYBUILD family must be explicitly mapped here so the
# reputation store and the collusion penalty get the right grouping.
_FAMILY_MAP: dict[str, Family] = {
    "anthropic": Family.ANTHROPIC,
    "openai": Family.OPENAI,
    "google": Family.GOOGLE,
    "mistral": Family.MISTRAL,
    "moonshot": Family.MOONSHOT,
    "deepseek": Family.DEEPSEEK,
    "minimax": Family.MINIMAX,
    "xiaomi": Family.XIAOMI,
    # OpenRouter family slugs used by POLYBUILD adapters/__init__.py
    "zai": Family.ZHIPU,
    "qwen": Family.ALIBABA,
}


def _polybuild_family_to_devcode(family: str) -> Family:
    """Translate a POLYBUILD family string to a DEVCODE :class:`Family`.

    Raises:
        ValueError: when no mapping exists. We refuse to silently bucket an
            unknown family because DEVCODE's collusion penalty relies on
            correct family grouping (Round 5 / Round 8 anti-pattern: silent
            fallback hides cross-voice collusion).
    """
    try:
        return _FAMILY_MAP[family]
    except KeyError as e:
        raise ValueError(
            f"DEVCODE Family mapping missing for POLYBUILD family {family!r}. "
            "Add it to scoring/devcode_adapter._FAMILY_MAP or upstream "
            "devcode.models.Family."
        ) from e


# Privacy / sensitivity → DEVCODE Priority. POLYBUILD doesn't have
# free-form priorities, so we drive Priority from the spec's risk profile.
_PRIORITY_MAP: dict[PrivacyLevel, Priority] = {
    PrivacyLevel.HIGH: Priority.P0,
    PrivacyLevel.MEDIUM: Priority.P1,
    PrivacyLevel.LOW: Priority.P2,
}


def builder_results_to_devcode_votes(
    results: list[BuilderResult],
    voice_scores: list[VoiceScore],
    spec: Spec,
) -> tuple[list[Vote], DecisionContext]:
    """Map POLYBUILD Phase 2 + Phase 3 outputs to DEVCODE inputs.

    Args:
        results: Phase 2 outputs. ``Status.FAILED`` voices are dropped — a
            failed voice has no candidate code to vote on.
        voice_scores: Phase 3 gate verdicts. Used as the ranking heuristic
            described in the module docstring.
        spec: validated Phase 0 spec. ``run_id`` becomes the
            ``decision_id``, ``profile_id`` becomes the ``domain``,
            and the privacy level drives the ``Priority``.

    Returns:
        ``(votes, ctx)`` ready for ``devcode.aggregation.devcode_vote_v1``.

    Raises:
        ValueError: if no voice succeeded (no candidate to vote on) or if
            a family is missing from ``_FAMILY_MAP``.
    """
    ok_results = [r for r in results if r.status == Status.OK]
    if not ok_results:
        raise ValueError(
            "builder_results_to_devcode_votes: no Status.OK BuilderResult to vote on"
        )

    # Stable, deterministic mapping: voice_id → option index in [0, n).
    voice_ids = [r.voice_id for r in ok_results]
    options: list[OptionId] = list(range(len(voice_ids)))
    voice_to_option: dict[str, OptionId] = {
        v: i for i, v in enumerate(voice_ids)
    }

    # Score lookup. Voices missing from ``voice_scores`` (defensive — should
    # not happen in practice) get a 0.0 score so they sort to the bottom.
    score_map: dict[str, float] = {s.voice_id: s.score for s in voice_scores}

    # Consensus heuristic: every voice produces the same score-descending
    # ranking. Tie-break by ``voice_id`` for determinism so two runs on the
    # same inputs produce identical Votes.
    ranking_voice_ids = sorted(
        voice_ids,
        key=lambda v: (-score_map.get(v, 0.0), v),
    )
    consensus_ranking: list[OptionId] = [
        voice_to_option[v] for v in ranking_voice_ids
    ]

    # Per-option confidence = that option's gate score. All voices report
    # the same map (no cross-evaluation).
    confidence_map: dict[OptionId, float] = {
        voice_to_option[v]: score_map.get(v, 0.0) for v in voice_ids
    }

    votes = [
        Vote(
            voice_id=r.voice_id,
            family=_polybuild_family_to_devcode(r.family),
            ranked_options=consensus_ranking,
            confidences=confidence_map,
            evidence=[],
            output_embedding=None,
        )
        for r in ok_results
    ]

    priority = _PRIORITY_MAP.get(spec.risk_profile.sensitivity, Priority.P1)
    ctx = DecisionContext(
        decision_id=spec.run_id,
        domain=spec.profile_id,
        task_type="code_generation",
        priority=priority,
        options=options,
        seed=42,
    )

    return votes, ctx


def option_to_voice_id(
    winner_option: OptionId | None,
    ok_results: list[BuilderResult],
) -> str | None:
    """Translate a DEVCODE winner option index back to a POLYBUILD ``voice_id``.

    Used by ``DevcodeScorer`` to surface the winner inside ``ScoredResult.
    winner_voice_id`` so the consensus pipeline can pick the matching
    ``BuilderResult`` without re-walking the option mapping.

    Returns ``None`` when DEVCODE returned ``Decision.winner=None`` (tied
    decision that fell into Phase E tie-breaking but produced no winner).
    """
    if winner_option is None:
        return None
    if not (0 <= winner_option < len(ok_results)):
        return None
    return ok_results[winner_option].voice_id


__all__ = [
    "builder_results_to_devcode_votes",
    "option_to_voice_id",
]
