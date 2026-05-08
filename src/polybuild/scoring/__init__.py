"""POLYBUILD scoring strategies (M2A).

Public API:

  * ``ScorerProtocol`` — typing.Protocol any scorer must implement.
  * ``ScoredResult`` — unified Pydantic output (consumed by
    ``polybuild.orchestrator.consensus_pipeline``).
  * ``NaiveScorer`` — default, current Phase 3 gate-based scoring.
  * ``DevcodeScorer`` — opt-in, ``--scorer=devcode``. Imports the
    optional ``devcode`` package lazily so the naive path stays free
    of the dependency.
"""

from __future__ import annotations

from polybuild.scoring.naive_scorer import NaiveScorer as NaiveScorer
from polybuild.scoring.protocol import (
    ScoredResult as ScoredResult,
)
from polybuild.scoring.protocol import (
    ScorerProtocol as ScorerProtocol,
)
from polybuild.scoring.shadow_scorer import ShadowScorer as ShadowScorer


def _load_devcode_scorer():  # type: ignore[no-untyped-def]
    """Lazy loader for :class:`DevcodeScorer`.

    The ``devcode`` package is an optional dependency (extra
    ``[devcode]``); importing the scorer module triggers the heavy
    ``import devcode.aggregation``. Callers that stay on the naive
    scorer never pay that cost.
    """
    from polybuild.scoring.devcode_scorer import DevcodeScorer

    return DevcodeScorer


__all__ = [
    "NaiveScorer",
    "ScoredResult",
    "ScorerProtocol",
    "ShadowScorer",
    "_load_devcode_scorer",
]
