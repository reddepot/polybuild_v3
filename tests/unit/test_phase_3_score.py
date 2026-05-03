"""Tests unitaires pour Phase 3 — Deterministic scoring (parsers + formula)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from polybuild.models import BuilderResult, GateResults, SelfMetrics, Status, VoiceScore
from polybuild.orchestrator.phase_3_score import (
    _parse_coverage,
    _parse_gitleaks_count,
    _parse_pytest_ratio,
    compute_score,
    is_disqualified,
    phase_3_score,
    run_command,
    run_general_gates,
)


class TestRunCommand:
    @pytest.mark.asyncio
    async def test_echo_command(self, tmp_path: Path) -> None:
        rc, stdout, stderr = await run_command("echo hello", tmp_path, timeout=5)
        assert rc == 0
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_timeout_returns_minus_one(self, tmp_path: Path) -> None:
        rc, stdout, stderr = await run_command("sleep 10", tmp_path, timeout=0)
        # timeout=0 déclenche immédiatement le timeout dans asyncio.wait_for
        # le process est killé
        assert rc == -1
        assert "Timeout" in stderr


class TestParsePytestRatio:
    def test_json_report_valid(self, tmp_path: Path) -> None:
        report = tmp_path / ".pytest.json"
        report.write_text(json.dumps({"summary": {"passed": 8, "total": 10}}))
        assert _parse_pytest_ratio(report, "") == 0.8

    def test_json_missing_fallback_stdout(self) -> None:
        stdout = "tests/test_x.py::test_a PASSED\n5 passed, 1 failed in 0.1s"
        assert _parse_pytest_ratio(Path("/nonexistent"), stdout) == 5 / 6

    def test_no_json_no_match_returns_zero(self) -> None:
        assert _parse_pytest_ratio(Path("/nonexistent"), "no tests ran") == 0.0

    def test_zero_total_returns_zero(self, tmp_path: Path) -> None:
        report = tmp_path / ".pytest.json"
        report.write_text(json.dumps({"summary": {"passed": 0, "total": 0}}))
        assert _parse_pytest_ratio(report, "") == 0.0


class TestParseCoverage:
    def test_total_line_parsed(self) -> None:
        stdout = "TOTAL\t 120\t  12\t 90%\n"
        assert _parse_coverage(stdout) == 0.9

    def test_no_match_returns_zero(self) -> None:
        assert _parse_coverage("") == 0.0


class TestParseGitleaksCount:
    def test_list_with_findings(self, tmp_path: Path) -> None:
        report = tmp_path / ".gitleaks.json"
        report.write_text(json.dumps([{"Description": "AWS key"}, {"Description": "GCP key"}]))
        assert _parse_gitleaks_count(report) == 2

    def test_missing_file_returns_zero(self) -> None:
        assert _parse_gitleaks_count(Path("/nonexistent")) == 0

    def test_invalid_json_returns_zero(self, tmp_path: Path) -> None:
        report = tmp_path / ".gitleaks.json"
        report.write_text("not json")
        assert _parse_gitleaks_count(report) == 0


class TestIsDisqualified:
    def test_status_not_ok(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.TIMEOUT,
        )
        dq, reason = is_disqualified(result, GateResults(
            acceptance_pass_ratio=1.0, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
        ))
        assert dq is True
        assert "timeout" in (reason or "").lower()

    def test_todo_count_above_threshold(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=5, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        dq, reason = is_disqualified(result, GateResults(
            acceptance_pass_ratio=1.0, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
        ))
        assert dq is True
        assert "TODO" in (reason or "")

    def test_gitleaks_finding(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        dq, reason = is_disqualified(result, GateResults(
            acceptance_pass_ratio=1.0, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=False, gitleaks_findings_count=1, diff_minimality=1.0,
        ))
        assert dq is True
        assert "secret" in (reason or "").lower()

    def test_acceptance_ratio_below_half(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        dq, reason = is_disqualified(result, GateResults(
            acceptance_pass_ratio=0.3, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
        ))
        assert dq is True
        assert "0.30" in (reason or "")

    def test_passes(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=2, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        dq, reason = is_disqualified(result, GateResults(
            acceptance_pass_ratio=0.9, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
        ))
        assert dq is False
        assert reason is None


class TestComputeScore:
    def test_perfect_score(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        gates = GateResults(
            acceptance_pass_ratio=1.0, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
            pro_gap_penalty=0.0, domain_score=0.0,
        )
        # base = 35+15+15+10+10+10+5 = 100
        assert compute_score(result, gates) == 100.0

    def test_minimum_zero(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=100, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        gates = GateResults(
            acceptance_pass_ratio=0.0, bandit_clean=False, mypy_strict_clean=False, ruff_clean=False,
            coverage_score=0.0, gitleaks_clean=False, gitleaks_findings_count=10, diff_minimality=0.0,
            pro_gap_penalty=1.0, domain_score=0.0,
        )
        assert compute_score(result, gates) == 0.0

    def test_domain_score_bonus(self) -> None:
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=Path("/tmp"), tests_dir=Path("/tmp"),
            diff_patch=Path("/tmp"), self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=0.0, status=Status.OK,
        )
        gates = GateResults(
            acceptance_pass_ratio=1.0, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
            pro_gap_penalty=0.0, domain_score=1.0,
        )
        assert compute_score(result, gates) == 115.0


class TestPhase3Score:
    @pytest.mark.asyncio
    async def test_sorts_descending(self, tmp_path: Path) -> None:
        # Créer deux worktrees factices
        wt1 = tmp_path / "wt1"
        wt2 = tmp_path / "wt2"
        for wt in (wt1, wt2):
            (wt / "src").mkdir(parents=True)
            (wt / "tests").mkdir(parents=True)

        results = [
            BuilderResult(
                voice_id="v1", family="f", code_dir=wt1 / "src", tests_dir=wt1 / "tests",
                diff_patch=wt1 / "diff.patch", self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
                duration_sec=1.0, status=Status.OK,
            ),
            BuilderResult(
                voice_id="v2", family="f", code_dir=wt2 / "src", tests_dir=wt2 / "tests",
                diff_patch=wt2 / "diff.patch", self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
                duration_sec=1.0, status=Status.OK,
            ),
        ]

        fake_gates = GateResults(
            acceptance_pass_ratio=1.0, bandit_clean=True, mypy_strict_clean=True, ruff_clean=True,
            coverage_score=1.0, gitleaks_clean=True, gitleaks_findings_count=0, diff_minimality=1.0,
        )

        with patch(
            "polybuild.orchestrator.phase_3_score.run_general_gates", new_callable=AsyncMock
        ) as mock_gates:
            mock_gates.return_value = fake_gates
            scores = await phase_3_score(results)

        assert len(scores) == 2
        assert scores[0].score >= scores[1].score

    @pytest.mark.asyncio
    async def test_disqualified_status_zero_score(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        tests = tmp_path / "tests"
        tests.mkdir()
        result = BuilderResult(
            voice_id="v1", family="f", code_dir=src,
            tests_dir=tests, diff_patch=tmp_path / "diff.patch",
            self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=1.0, status=Status.FAILED,
        )
        # Pas besoin de mock car le status != OK short-circuite avant run_general_gates
        scores = await phase_3_score([result])
        assert scores[0].disqualified is True
        assert scores[0].score == 0.0
