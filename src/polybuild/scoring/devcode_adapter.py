"""Adapter — POLYBUILD ``BuilderResult`` + ``VoiceScore`` → DEVCODE ``Vote`` (M2A.1).

DEVCODE-Vote v1 expects a list of ``Vote`` (each one ranks the options) and
a ``DecisionContext`` (priority, options, deterministic seed). POLYBUILD
produces a list of ``BuilderResult`` (one per voice, possibly some FAILED)
plus a list of ``VoiceScore`` (gate verdicts + scalar score).

This module is a **pure function** with no side-effects, no network and no
LLM calls — the heavy math is done by ``devcode.aggregation.devcode_vote_v1``
once we have the votes.

The ``devcode`` package is an optional dependency (extra ``[devcode]``);
imports happen lazily inside the public functions so the module loads
cleanly even when ``devcode`` is not installed. Only callers that actually
invoke the functions pay the import cost (and trigger an :class:`ImportError`
if the extra is missing).

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
  * cross-cultural supermajority check (P0/P1/P2 require >=1 non-Western
    voice).

That is still strictly more information than the bare ``max(score)``
picker the naive scorer uses, which is the M2A trade-off the user agreed
to (option beta reformulee).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polybuild.models import PrivacyLevel, Status

if TYPE_CHECKING:
    from devcode.models import DecisionContext, OptionId, Vote

    from polybuild.models import BuilderResult, Spec, VoiceScore
else:
    # Runtime fallback for the type alias when ``devcode`` is not
    # installed (the optional ``[devcode]`` extra is missing). Module-
    # level annotations evaluate strings under ``from __future__ import
    # annotations``, so this path only matters for runtime ``isinstance``
    # / ``OptionId(value)`` calls — which we don't make.
    OptionId = int


# POLYBUILD family strings → DEVCODE ``Family`` enum value. Stored as
# plain strings here so the map can be defined without importing devcode;
# the string is converted to ``devcode.models.Family`` at use site.
# Kept exhaustive on purpose: any new POLYBUILD family must be explicitly
# mapped here so the reputation store and the collusion penalty get the
# right grouping. Unknown families raise — silent fallback would hide
# cross-voice collusion (Round 5 / Round 8 anti-pattern).
_FAMILY_MAP: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "mistral": "mistral",
    "moonshot": "moonshot",
    "deepseek": "deepseek",
    "minimax": "minimax",
    "xiaomi": "xiaomi",
    # OpenRouter family slugs used by polybuild.adapters.__init__
    "zai": "zhipu",
    "qwen": "alibaba",
    # POLYLENS run #3 P1 (KIMI Agent Swarm): the Ollama local adapter
    # (``adapters/ollama_local.py``) sets ``family="alibaba"`` directly
    # rather than ``"qwen"``. Both should map to the same DEVCODE
    # ``Family.ALIBABA`` so a Qwen voice via Ollama and a Qwen voice
    # via OpenRouter are treated as the same provider for the
    # cross-cultural supermajority check. Without this entry, Ollama
    # Qwen runs raised ``ValueError`` and crashed ``--scorer=devcode``
    # (or fell back to naive abstain via the v3.2.4 try/except).
    "alibaba": "alibaba",
    # NOTE: ``"xai"`` (Grok via OpenRouter, ``adapters/__init__.py:83``)
    # is intentionally absent. devcode v1.0 ``Family`` enum does not
    # include ``xai`` — adding it here would still raise
    # ``Family("xai")`` downstream. Until devcode publishes a Family
    # entry for xAI, Grok voices fall through to the naive-abstain
    # fallback wired in ``DevcodeScorer.score`` (POLYLENS run #3 P1).
}


# POLYBUILD privacy level → DEVCODE Priority value. Same lazy-string
# approach as _FAMILY_MAP.
_PRIORITY_MAP: dict[PrivacyLevel, str] = {
    PrivacyLevel.HIGH: "P0",
    PrivacyLevel.MEDIUM: "P1",
    PrivacyLevel.LOW: "P2",
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
        ImportError: if the ``devcode`` extra is not installed.
        ValueError: if no voice succeeded (no candidate to vote on) or if
            a family is missing from ``_FAMILY_MAP``.
    """
    # Lazy import — only callers that actually use DEVCODE pay the cost,
    # and the module imports cleanly even without the extra.
    from devcode.models import (
        DecisionContext,
        Family,
        Priority,
        Vote,
    )

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

    # Per-option confidence = that option's gate score, normalised to
    # [0, 1] (the POLYBUILD score formula tops out around 100; DEVCODE's
    # ``Vote.confidences`` validator rejects anything outside [0, 1]).
    # Empty inputs yield 0.0 by clamping rather than NaN.
    confidence_map: dict[OptionId, float] = {
        voice_to_option[v]: max(0.0, min(1.0, score_map.get(v, 0.0) / 100.0))
        for v in voice_ids
    }

    votes = [
        Vote(
            voice_id=r.voice_id,
            family=Family(_polybuild_family_to_devcode_str(r.family)),
            ranked_options=consensus_ranking,
            confidences=confidence_map,
            evidence=[],
            output_embedding=None,
        )
        for r in ok_results
    ]

    priority_str = _PRIORITY_MAP.get(spec.risk_profile.sensitivity, "P1")
    ctx = DecisionContext(
        decision_id=spec.run_id,
        domain=spec.profile_id,
        task_type="code_generation",
        priority=Priority(priority_str),
        options=options,
        seed=42,
    )

    return votes, ctx


def _polybuild_family_to_devcode_str(family: str) -> str:
    """Translate a POLYBUILD family string to the DEVCODE ``Family`` value.

    Returns the string value (e.g. ``"anthropic"``); the caller wraps it
    in ``devcode.models.Family(...)`` at the call site.

    Raises:
        ValueError: when no mapping exists.
    """
    try:
        return _FAMILY_MAP[family]
    except KeyError as e:
        raise ValueError(
            f"DEVCODE Family mapping missing for POLYBUILD family {family!r}. "
            "Add it to scoring/devcode_adapter._FAMILY_MAP or upstream "
            "devcode.models.Family."
        ) from e


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
