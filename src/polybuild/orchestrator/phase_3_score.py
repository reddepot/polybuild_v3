"""Compatibility re-export — Phase 3 scoring lives in polybuild.phases.phase_3_score.

The test suite imports from `polybuild.orchestrator.phase_3_score` to mirror
how callers conceptually group the orchestrator's phases. This module is a
thin shim that re-exports the canonical implementation so both import paths
work without code duplication.
"""

from polybuild.phases.phase_3_score import (
    _parse_coverage,
    _parse_gitleaks_count,
    _parse_pytest_ratio,
    compute_score,
    is_disqualified,
    phase_3_score,
    run_command,
    run_general_gates,
)

__all__ = [
    "_parse_coverage",
    "_parse_gitleaks_count",
    "_parse_pytest_ratio",
    "compute_score",
    "is_disqualified",
    "phase_3_score",
    "run_command",
    "run_general_gates",
]
