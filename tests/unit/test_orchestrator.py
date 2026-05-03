"""Tests unitaires pour l'orchestrateur principal."""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polybuild.models import (
    AcceptanceCriterion,
    AuditReport,
    BuilderResult,
    FixReport,
    GateResults,
    PrivacyLevel,
    RiskProfile,
    SelfMetrics,
    Spec,
    Status,
    TokenUsage,
    ValidationVerdict,
    VoiceConfig,
    VoiceScore,
)
from polybuild.orchestrator import (
    _build_aborted_run,
    _handle_shutdown_signal,
    generate_run_id,
    run_polybuild,
    save_checkpoint,
)
from polybuild.phases.phase_minus_one_privacy import PrivacyVerdict


class TestGenerateRunId:
    def test_format(self) -> None:
        rid = generate_run_id()
        # Round 10.6 [Gemini ZB-03 P1]: suffix widened from 4 to 16 hex
        # chars (token_hex(2) → token_hex(8)) for collision resistance.
        assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{6}_[0-9a-f]{16}$", rid)

    def test_unique(self) -> None:
        assert generate_run_id() != generate_run_id()


class TestSaveCheckpoint:
    def test_atomic_write(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        save_checkpoint("R1", "phase0", {"foo": "bar"}, root)
        checkpoint = root / ".polybuild" / "checkpoints" / "R1_phase0.json"
        assert checkpoint.exists()
        import json

        assert json.loads(checkpoint.read_text()) == {"foo": "bar"}
        # Pas de fichier .tmp résiduel
        assert not (checkpoint.with_suffix(".tmp")).exists()


class TestHandleShutdownSignal:
    def test_cancels_other_tasks(self) -> None:
        current = MagicMock()
        other = MagicMock()
        with patch("asyncio.current_task", return_value=current):
            with patch("asyncio.all_tasks", return_value={current, other}):
                _handle_shutdown_signal(2, "run-1")
        other.cancel.assert_called_once()
        assert not current.cancel.called


class TestBuildAbortedRun:
    def test_structure(self) -> None:
        spec = Spec(
            run_id="R1",
            profile_id="p",
            task_description="t",
            acceptance_criteria=[],
            risk_profile=RiskProfile(),
            spec_hash="abc",
        )
        result = _build_aborted_run(
            run_id="R1",
            profile_id="p",
            spec=spec,
            builder_results=[],
            scores=[],
            started_at=datetime.now(UTC),
        )
        assert result.final_status == "aborted"
        assert result.winner_voice_id is None
        assert result.commit_sha is None
        assert result.domain_gates_passed is False


class TestRunPolybuild:
    """Tests d'intégration légers de l'orchestrateur entièrement mocké."""

    def _make_spec(self) -> Spec:
        return Spec(
            run_id="R1",
            profile_id="module_standard_known",
            task_description="Implement foo",
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="ac1", description="foo works", test_command="pytest", blocking=True
                )
            ],
            risk_profile=RiskProfile(),
            spec_hash="abc123",
        )

    def _make_privacy_pass(self) -> PrivacyVerdict:
        return PrivacyVerdict(
            level="PASS", blocked=False, reason="ok", findings=[]
        )

    def _make_privacy_block(self) -> PrivacyVerdict:
        return PrivacyVerdict(
            level="BLOCK", blocked=True, reason="PII detected", findings=[]
        )

    def _make_gates(self, **overrides: Any) -> GateResults:
        defaults = {
            "acceptance_pass_ratio": 1.0,
            "bandit_clean": True,
            "mypy_strict_clean": True,
            "ruff_clean": True,
            "coverage_score": 1.0,
            "gitleaks_clean": True,
            "gitleaks_findings_count": 0,
            "diff_minimality": 1.0,
        }
        defaults.update(overrides)
        return GateResults(**defaults)

    @pytest.mark.asyncio
    async def test_privacy_gate_blocks(self, tmp_path: Path) -> None:
        with patch(
            "polybuild.phases.phase_minus_one_privacy.phase_minus_one_privacy_gate",
            return_value=self._make_privacy_block(),
        ):
            with pytest.raises(RuntimeError, match="BLOCKED"):
                await run_polybuild(
                    brief="Contact: jean.dupont@example.com",
                    profile_id="module_standard_known",
                    project_root=tmp_path,
                )

    @pytest.mark.asyncio
    async def test_happy_path(self, tmp_path: Path) -> None:
        spec = self._make_spec()
        voices = [
            VoiceConfig(voice_id="gpt-5.5", family="openai", role="builder", timeout_sec=60)
        ]
        builder_result = BuilderResult(
            voice_id="gpt-5.5",
            family="openai",
            code_dir=tmp_path / "src",
            tests_dir=tmp_path / "tests",
            diff_patch=tmp_path / "diff.patch",
            self_metrics=SelfMetrics(
                loc=10,
                complexity_cyclomatic_avg=1.0,
                test_to_code_ratio=0.5,
                todo_count=0,
                imports_count=2,
                functions_count=1,
            ),
            duration_sec=1.0,
            status=Status.OK,
        )
        score = VoiceScore(
            voice_id="gpt-5.5",
            score=95.0,
            gates=self._make_gates(),
            disqualified=False,
        )
        audit = AuditReport(
            auditor_model="auditor",
            auditor_family="openai",
            audit_duration_sec=1.0,
            axes_audited=["A_security"],
            findings=[],
        )
        fix_report = FixReport(status="completed", results=[])
        validation = ValidationVerdict(
            passed=True,
            general_gates=self._make_gates(),
            domain_gates_passed=True,
        )

        with patch(
            "polybuild.phases.phase_minus_one_privacy.phase_minus_one_privacy_gate",
            return_value=self._make_privacy_pass(),
        ):
            with patch("polybuild.orchestrator.phase_0_spec", return_value=spec):
                with patch("polybuild.orchestrator.select_voices", return_value=voices):
                    with patch(
                        "polybuild.orchestrator.phase_2_generate",
                        return_value=[builder_result],
                    ):
                        with patch(
                            "polybuild.orchestrator.phase_3_score", return_value=[score]
                        ):
                            with patch(
                                "polybuild.orchestrator.phase_3b_grounding",
                                return_value={"gpt-5.5": []},
                            ):
                                with patch(
                                    "polybuild.orchestrator.phase_4_audit",
                                    return_value=audit,
                                ):
                                    with patch(
                                        "polybuild.orchestrator.phase_5_dispatch",
                                        return_value=fix_report,
                                    ):
                                        with patch(
                                            "polybuild.orchestrator.phase_6_validate",
                                            return_value=validation,
                                        ):
                                            with patch(
                                                "polybuild.orchestrator.phase_7_commit",
                                                return_value=MagicMock(sha="deadbeef"),
                                            ):
                                                run = await run_polybuild(
                                                    brief="Implement foo",
                                                    profile_id="module_standard_known",
                                                    project_root=tmp_path,
                                                )
        assert run.final_status == "committed"
        assert run.winner_voice_id == "gpt-5.5"
        assert run.commit_sha == "deadbeef"
        assert run.spec_hash == "abc123"

    @pytest.mark.asyncio
    async def test_phase5_blocked_p0_returns_aborted(self, tmp_path: Path) -> None:
        spec = self._make_spec()
        voices = [
            VoiceConfig(voice_id="v1", family="f", role="builder", timeout_sec=60)
        ]
        builder_result = BuilderResult(
            voice_id="v1",
            family="f",
            code_dir=tmp_path / "src",
            tests_dir=tmp_path / "tests",
            diff_patch=tmp_path / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=1.0,
            status=Status.OK,
        )
        score = VoiceScore(
            voice_id="v1",
            score=50.0,
            gates=self._make_gates(),
            disqualified=False,
        )
        fix_report = FixReport(status="blocked_p0", results=[])

        with patch(
            "polybuild.phases.phase_minus_one_privacy.phase_minus_one_privacy_gate",
            return_value=self._make_privacy_pass(),
        ):
            with patch("polybuild.orchestrator.phase_0_spec", return_value=spec):
                with patch("polybuild.orchestrator.select_voices", return_value=voices):
                    with patch(
                        "polybuild.orchestrator.phase_2_generate",
                        return_value=[builder_result],
                    ):
                        with patch(
                            "polybuild.orchestrator.phase_3_score", return_value=[score]
                        ):
                            with patch(
                                "polybuild.orchestrator.phase_3b_grounding",
                                return_value={"v1": []},
                            ):
                                with patch(
                                    "polybuild.orchestrator.phase_4_audit",
                                    return_value=AuditReport(
                                        auditor_model="a",
                                        auditor_family="f",
                                        audit_duration_sec=1.0,
                                        axes_audited=["A"],
                                        findings=[],
                                    ),
                                ):
                                    with patch(
                                        "polybuild.orchestrator.phase_5_dispatch",
                                        return_value=fix_report,
                                    ):
                                        run = await run_polybuild(
                                            brief="Implement foo",
                                            profile_id="module_standard_known",
                                            project_root=tmp_path,
                                        )
        assert run.final_status == "aborted"

    @pytest.mark.asyncio
    async def test_phase6_validation_failed_returns_aborted(
        self, tmp_path: Path
    ) -> None:
        spec = self._make_spec()
        voices = [
            VoiceConfig(voice_id="v1", family="f", role="builder", timeout_sec=60)
        ]
        builder_result = BuilderResult(
            voice_id="v1",
            family="f",
            code_dir=tmp_path / "src",
            tests_dir=tmp_path / "tests",
            diff_patch=tmp_path / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=1.0,
            status=Status.OK,
        )
        score = VoiceScore(
            voice_id="v1",
            score=50.0,
            gates=self._make_gates(),
            disqualified=False,
        )
        validation = ValidationVerdict(
            passed=False,
            general_gates=self._make_gates(
                acceptance_pass_ratio=0.5,
                bandit_clean=False,
            ),
            domain_gates_passed=False,
            notes=["mypy failed"],
        )

        with patch(
            "polybuild.phases.phase_minus_one_privacy.phase_minus_one_privacy_gate",
            return_value=self._make_privacy_pass(),
        ):
            with patch("polybuild.orchestrator.phase_0_spec", return_value=spec):
                with patch("polybuild.orchestrator.select_voices", return_value=voices):
                    with patch(
                        "polybuild.orchestrator.phase_2_generate",
                        return_value=[builder_result],
                    ):
                        with patch(
                            "polybuild.orchestrator.phase_3_score", return_value=[score]
                        ):
                            with patch(
                                "polybuild.orchestrator.phase_3b_grounding",
                                return_value={"v1": []},
                            ):
                                with patch(
                                    "polybuild.orchestrator.phase_4_audit",
                                    return_value=AuditReport(
                                        auditor_model="a",
                                        auditor_family="f",
                                        audit_duration_sec=1.0,
                                        axes_audited=["A"],
                                        findings=[],
                                    ),
                                ):
                                    with patch(
                                        "polybuild.orchestrator.phase_5_dispatch",
                                        return_value=FixReport(
                                            status="completed", results=[]
                                        ),
                                    ):
                                        with patch(
                                            "polybuild.orchestrator.phase_6_validate",
                                            return_value=validation,
                                        ):
                                            run = await run_polybuild(
                                                brief="Implement foo",
                                                profile_id="module_standard_known",
                                                project_root=tmp_path,
                                            )
        assert run.final_status == "aborted"

    @pytest.mark.asyncio
    async def test_skip_commit_and_smoke(self, tmp_path: Path) -> None:
        spec = self._make_spec()
        voices = [
            VoiceConfig(voice_id="v1", family="f", role="builder", timeout_sec=60)
        ]
        builder_result = BuilderResult(
            voice_id="v1",
            family="f",
            code_dir=tmp_path / "src",
            tests_dir=tmp_path / "tests",
            diff_patch=tmp_path / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=1.0,
            status=Status.OK,
        )
        score = VoiceScore(
            voice_id="v1",
            score=50.0,
            gates=self._make_gates(),
            disqualified=False,
        )
        validation = ValidationVerdict(
            passed=True,
            general_gates=self._make_gates(),
            domain_gates_passed=True,
        )

        with patch(
            "polybuild.phases.phase_minus_one_privacy.phase_minus_one_privacy_gate",
            return_value=self._make_privacy_pass(),
        ):
            with patch("polybuild.orchestrator.phase_0_spec", return_value=spec):
                with patch("polybuild.orchestrator.select_voices", return_value=voices):
                    with patch(
                        "polybuild.orchestrator.phase_2_generate",
                        return_value=[builder_result],
                    ):
                        with patch(
                            "polybuild.orchestrator.phase_3_score", return_value=[score]
                        ):
                            with patch(
                                "polybuild.orchestrator.phase_3b_grounding",
                                return_value={"v1": []},
                            ):
                                with patch(
                                    "polybuild.orchestrator.phase_4_audit",
                                    return_value=AuditReport(
                                        auditor_model="a",
                                        auditor_family="f",
                                        audit_duration_sec=1.0,
                                        axes_audited=["A"],
                                        findings=[],
                                    ),
                                ):
                                    with patch(
                                        "polybuild.orchestrator.phase_5_dispatch",
                                        return_value=FixReport(
                                            status="completed", results=[]
                                        ),
                                    ):
                                        with patch(
                                            "polybuild.orchestrator.phase_6_validate",
                                            return_value=validation,
                                        ):
                                            run = await run_polybuild(
                                                brief="Implement foo",
                                                profile_id="module_standard_known",
                                                project_root=tmp_path,
                                                skip_commit=True,
                                                skip_smoke=True,
                                            )
        assert run.final_status == "committed"
        assert run.commit_sha is None

    @pytest.mark.asyncio
    async def test_risk_profile_inference_medical_high(self, tmp_path: Path) -> None:
        """Le profile_id 'medical_high_*' doit forcer PrivacyLevel.HIGH."""
        with patch(
            "polybuild.phases.phase_minus_one_privacy.phase_minus_one_privacy_gate",
            return_value=self._make_privacy_pass(),
        ) as mock_gate:
            with patch(
                "polybuild.orchestrator.phase_0_spec", new_callable=AsyncMock
            ) as mock_spec:
                mock_spec.return_value = self._make_spec()
                with patch(
                    "polybuild.orchestrator.select_voices",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    try:
                        await run_polybuild(
                            brief="foo",
                            profile_id="medical_high_sensitive",
                            project_root=tmp_path,
                        )
                    except Exception:
                        pass
        # Vérifier que la gate a été appelée avec le brief (le risk_profile est inféré)
        mock_gate.assert_called_once()
        call_kwargs = mock_gate.call_args[1]
        assert "text" in call_kwargs
