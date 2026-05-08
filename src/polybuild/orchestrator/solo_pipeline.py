"""Solo pipeline — single-voice short-circuit (skeleton).

Created in M2B.0 as a placeholder so the strategy routing in
:mod:`polybuild.orchestrator` is exercised end-to-end without committing
to a particular implementation. The real body lands in **M2B.2** and
will:

* skip Phase 1 (voice selection) and pick a single configured adapter
  (default: Claude Code),
* skip Phase 2 (parallel generation) by invoking ``_run_single_voice``,
* skip Phase 3 (scoring) and Phase 5 (triade fix) — the single
  candidate is the winner by construction,
* still call Phase 6 (validation gates) and Phase 7 (commit) via the
  top-level orchestrator.

Until then any caller that explicitly opts into the solo strategy gets
a clear ``NotImplementedError`` rather than silent fallback behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from polybuild.orchestrator.pipeline_strategy import (
    CheckpointFn,
    StrategyOutcome,
)

if TYPE_CHECKING:
    from polybuild.models import RiskProfile, Spec


class SoloPipeline:
    """Placeholder for the single-voice pipeline. Body delivered in M2B.2."""

    name = "solo"

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
        del (
            spec,
            risk_profile,
            project_root,
            project_ctx,
            artifacts_dir,
            run_id,
            config_root,
            save_checkpoint,
        )
        raise NotImplementedError(
            "SoloPipeline is a placeholder for M2B.0 (Strategy Pattern "
            "refactor). Full implementation lands in M2B.2."
        )


__all__ = ["SoloPipeline"]
