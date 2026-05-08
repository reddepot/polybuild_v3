"""POLYBUILD scoring strategies (M2A).

Public API:

  * ``ScorerProtocol`` — typing.Protocol any scorer must implement.
  * ``ScoredResult`` — unified Pydantic output (consumed by
    ``polybuild.orchestrator.consensus_pipeline``).

The naive scorer (current behaviour) and the DEVCODE-backed scorer
land in M2A.2 (modules ``naive_scorer`` and ``devcode_scorer``) and
register here when imported.
"""

from __future__ import annotations

from polybuild.scoring.protocol import (
    ScoredResult as ScoredResult,
)
from polybuild.scoring.protocol import (
    ScorerProtocol as ScorerProtocol,
)

__all__ = ["ScoredResult", "ScorerProtocol"]
