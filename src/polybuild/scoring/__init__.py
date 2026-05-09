"""POLYBUILD scoring strategies (M2A).

Public API:

  * ``ScorerProtocol`` — typing.Protocol any scorer must implement.
  * ``ScoredResult`` — unified Pydantic output (consumed by
    ``polybuild.orchestrator.consensus_pipeline``).
  * ``NaiveScorer`` — default, current Phase 3 gate-based scoring.

POLYLENS run #4 P3 (DeepSeek): the ``_load_devcode_scorer`` lazy
loader was removed. It had no callers in src/ or tests/ — the CLI
imports ``DevcodeScorer`` directly via
``polybuild.scoring.devcode_scorer`` and the optional-dependency
guard happens inside that module's lazy ``from devcode... import``
calls. Keeping the loader exported was dead public API surface.
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

__all__ = [
    "NaiveScorer",
    "ScoredResult",
    "ScorerProtocol",
    "ShadowScorer",
]
