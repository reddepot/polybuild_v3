"""Régression Round 10.8 follow-up — Phase 3 score must be > 0 for valid code.

When a builder writes correct Python code + pytest tests into a worktree,
Phase 3 must run the gates successfully and produce a non-zero score.
Previously, missing ``PYTHONPATH=src`` caused import errors → 0 tests passed
→ hard disqualification (acceptance_pass_ratio < 0.5) → score = 0.0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from polybuild.models import BuilderResult, GateResults, SelfMetrics, Status
from polybuild.phases.phase_3_score import (
    compute_score,
    is_disqualified,
    run_general_gates,
)


_CALC_PY = '''\
def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Return the difference of two integers."""
    return a - b
'''

_TEST_CALC_PY = '''\
from calc import add, subtract


def test_add() -> None:
    assert add(1, 2) == 3
    assert add(-1, 1) == 0


def test_subtract() -> None:
    assert subtract(5, 3) == 2
    assert subtract(0, 0) == 0
'''


@pytest.mark.asyncio
async def test_run_general_gates_passes_for_valid_code(tmp_path: Path) -> None:
    """A clean worktree with valid code should pass all gates."""
    workdir = tmp_path / "wt"
    (workdir / "src").mkdir(parents=True)
    (workdir / "tests").mkdir(parents=True)

    (workdir / "src" / "calc.py").write_text(_CALC_PY)
    (workdir / "tests" / "test_calc.py").write_text(_TEST_CALC_PY)

    gates = await run_general_gates(workdir)

    assert gates.acceptance_pass_ratio > 0, (
        f"pytest failed: {gates.raw_outputs.get('pytest', '')}"
    )
    assert gates.mypy_strict_clean is True, (
        f"mypy failed: {gates.raw_outputs.get('mypy', '')}"
    )
    assert gates.ruff_clean is True, (
        f"ruff failed: {gates.raw_outputs.get('ruff', '')}"
    )
    assert gates.bandit_clean is True, (
        f"bandit failed: {gates.raw_outputs.get('bandit', '')}"
    )


@pytest.mark.asyncio
async def test_phase_3_score_nonzero_for_valid_code(tmp_path: Path) -> None:
    """End-to-end: a valid BuilderResult must receive a score > 0."""
    workdir = tmp_path / "wt"
    (workdir / "src").mkdir(parents=True)
    (workdir / "tests").mkdir(parents=True)

    (workdir / "src" / "calc.py").write_text(_CALC_PY)
    (workdir / "tests" / "test_calc.py").write_text(_TEST_CALC_PY)

    result = BuilderResult(
        voice_id="test_kimi",
        family="kimi",
        code_dir=workdir / "src",
        tests_dir=workdir / "tests",
        diff_patch=workdir / "diff.patch",
        self_metrics=SelfMetrics(
            loc=10,
            complexity_cyclomatic_avg=1.0,
            test_to_code_ratio=0.8,
            todo_count=0,
            imports_count=0,
            functions_count=2,
        ),
        duration_sec=1.0,
        status=Status.OK,
    )

    gates = await run_general_gates(workdir)
    dq, reason = is_disqualified(result, gates)
    score = 0.0 if dq else compute_score(result, gates)

    assert dq is False, (
        f"Unexpected disqualification: {reason}\n"
        f"pytest output: {gates.raw_outputs.get('pytest', '')}"
    )
    assert score > 0, (
        f"Score should be > 0 for valid code, got {score}.\n"
        f"Gates: {gates}"
    )
