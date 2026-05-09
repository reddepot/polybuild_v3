"""Integration tests for M2B — Strategy Pattern + ``SoloPipeline``.

Covers the externally observable contract of the new pipeline strategy
mechanism. We only mock the leaves (LLM adapters and the audit phase)
so the wiring between ``run_polybuild`` → strategy → phase functions is
exercised end-to-end.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from polybuild.models import (
    AuditReport,
    BuilderResult,
    Finding,
    SelfMetrics,
    Severity,
    Spec,
    Status,
)
from polybuild.orchestrator import (
    ConsensusPipeline,
    PipelineStrategy,
    SoloPipeline,
)
from polybuild.orchestrator.pipeline_strategy import StrategyOutcome


# ────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────


def _make_spec(tmp_path: Path) -> Spec:
    """Minimal Spec usable as ``strategy.run(spec=...)`` input."""
    from polybuild.models import RiskProfile

    return Spec(
        run_id="solo-test-1",
        profile_id="module_standard_known",
        task_description="solo mode integration test",
        acceptance_criteria=[],
        risk_profile=RiskProfile(),
        spec_hash="sha256:dummy",
    )


def _make_ok_builder_result(voice_id: str = "claude-opus-4.7") -> BuilderResult:
    """A successful BuilderResult with empty self-metrics."""
    return BuilderResult(
        voice_id=voice_id,
        family="anthropic",
        code_dir=Path("/dev/null"),
        tests_dir=Path("/dev/null"),
        diff_patch=Path("/dev/null"),
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


def _make_audit_report(
    findings: list[Finding] | None = None,
    voice_id: str = "claude-opus-4.7",
) -> AuditReport:
    return AuditReport(
        auditor_model="kimi-k2.6",
        auditor_family="moonshot",
        audit_duration_sec=2.0,
        axes_audited=["A_security"],
        findings=findings or [],
        metrics={"recall": 1.0},
    )


# ────────────────────────────────────────────────────────────────
# CONTRACT — both strategies implement PipelineStrategy
# ────────────────────────────────────────────────────────────────


class TestPipelineStrategyProtocol:
    def test_consensus_satisfies_protocol(self) -> None:
        pipeline: PipelineStrategy = ConsensusPipeline()
        assert pipeline.name == "consensus"
        assert callable(pipeline.run)

    def test_solo_satisfies_protocol(self) -> None:
        pipeline: PipelineStrategy = SoloPipeline()
        assert pipeline.name == "solo"
        assert callable(pipeline.run)

    def test_solo_voice_id_configurable(self) -> None:
        custom = SoloPipeline(voice_id="gpt-5.5", family="openai", timeout_sec=600)
        assert custom.voice_id == "gpt-5.5"
        assert custom.family == "openai"
        assert custom.timeout_sec == 600


# ────────────────────────────────────────────────────────────────
# SOLO — happy path skips phase 2/3/5, keeps phase 4
# ────────────────────────────────────────────────────────────────


class TestSoloPipelineHappyPath:
    @pytest.mark.asyncio
    async def test_skips_phase_2_3_5_and_keeps_phase_4(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polybuild import adapters

        # Mock the builder factory so no real CLI is called.
        builder_mock = MagicMock()
        builder_mock.generate = AsyncMock(return_value=_make_ok_builder_result())
        monkeypatch.setattr(
            adapters, "get_builder", MagicMock(return_value=builder_mock)
        )

        # Mock Phase 4 audit (kept in solo) — return a clean report.
        import polybuild.orchestrator as _orch

        phase_4_mock = AsyncMock(return_value=_make_audit_report())
        phase_2_mock = AsyncMock(return_value=[])
        phase_3_mock = AsyncMock(return_value=[])
        phase_5_mock = AsyncMock(return_value=None)
        monkeypatch.setattr(_orch, "phase_4_audit", phase_4_mock)
        monkeypatch.setattr(_orch, "phase_2_generate", phase_2_mock)
        monkeypatch.setattr(_orch, "phase_3_score", phase_3_mock)
        monkeypatch.setattr(_orch, "phase_5_dispatch", phase_5_mock)

        spec = _make_spec(tmp_path)
        outcome = await SoloPipeline().run(
            spec=spec,
            risk_profile=spec.risk_profile,
            project_root=tmp_path,
            project_ctx=None,
            artifacts_dir=tmp_path / "runs",
            run_id="solo-test-1",
            config_root=tmp_path / "config",
            save_checkpoint=lambda *a, **kw: None,
        )

        # Solo path skipped multi-voice phases ...
        assert phase_2_mock.await_count == 0, "phase_2_generate should be skipped"
        assert phase_3_mock.await_count == 0, "phase_3_score should be skipped"
        assert phase_5_mock.await_count == 0, "phase_5_dispatch should be skipped"

        # ... but kept the safety audit and produced a winner.
        assert phase_4_mock.await_count == 1, "phase_4_audit should run once"
        assert outcome.aborted is False
        assert outcome.winner_result is not None
        assert outcome.winner_result.voice_id == "claude-opus-4.7"
        assert outcome.fix_report is not None
        assert outcome.fix_report.status == "completed"
        assert outcome.fix_report.results == []


# ────────────────────────────────────────────────────────────────
# SOLO — abort paths
# ────────────────────────────────────────────────────────────────


class TestSoloPipelineAbortPaths:
    @pytest.mark.asyncio
    async def test_aborts_on_voice_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A FAILED BuilderResult from the single voice triggers an abort."""
        from polybuild import adapters

        failed = _make_ok_builder_result()
        failed_dict: dict[str, Any] = failed.model_dump()
        failed_dict["status"] = Status.FAILED
        failed_dict["error"] = "cli timeout"
        failed = BuilderResult(**failed_dict)

        builder_mock = MagicMock()
        builder_mock.generate = AsyncMock(return_value=failed)
        monkeypatch.setattr(
            adapters, "get_builder", MagicMock(return_value=builder_mock)
        )

        spec = _make_spec(tmp_path)
        outcome = await SoloPipeline().run(
            spec=spec,
            risk_profile=spec.risk_profile,
            project_root=tmp_path,
            project_ctx=None,
            artifacts_dir=tmp_path / "runs",
            run_id="solo-test-fail",
            config_root=tmp_path / "config",
            save_checkpoint=lambda *a, **kw: None,
        )

        assert outcome.aborted is True
        assert outcome.abort_reason is not None
        assert outcome.abort_reason.startswith("solo_voice_failed:")
        assert outcome.winner_result is None

    @pytest.mark.asyncio
    async def test_aborts_on_phase_4_p0_finding(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A P0 audit finding aborts the solo run (no triade fallback)."""
        from polybuild import adapters

        builder_mock = MagicMock()
        builder_mock.generate = AsyncMock(return_value=_make_ok_builder_result())
        monkeypatch.setattr(
            adapters, "get_builder", MagicMock(return_value=builder_mock)
        )

        # Phase 4 returns an audit with a P0 finding → solo aborts.
        p0 = Finding(
            id="solo-p0-1",
            severity=Severity.P0,
            axis="A_security",
            description="syntax error in generated code",
            auditor_model="kimi-k2.6",
            auditor_family="moonshot",
        )
        import polybuild.orchestrator as _orch

        monkeypatch.setattr(
            _orch,
            "phase_4_audit",
            AsyncMock(return_value=_make_audit_report(findings=[p0])),
        )

        spec = _make_spec(tmp_path)
        outcome = await SoloPipeline().run(
            spec=spec,
            risk_profile=spec.risk_profile,
            project_root=tmp_path,
            project_ctx=None,
            artifacts_dir=tmp_path / "runs",
            run_id="solo-test-p0",
            config_root=tmp_path / "config",
            save_checkpoint=lambda *a, **kw: None,
        )

        assert outcome.aborted is True
        assert outcome.abort_reason == "solo_phase_4_p0_no_triade"
        # POLYLENS run #3 P1 (Grok 4.3): an aborted StrategyOutcome
        # must NOT carry winner artefacts — the new invariant force-
        # nulls them via __post_init__ to prevent downstream code from
        # accidentally promoting a candidate the strategy explicitly
        # rejected. The audit findings are still surfaced so the user
        # sees why the run aborted.
        assert outcome.winner_result is None
        assert outcome.winner_score is None
        assert outcome.audit is not None
        assert any(f.severity == Severity.P0 for f in outcome.audit.findings)


# ────────────────────────────────────────────────────────────────
# StrategyOutcome — frozen dataclass
# ────────────────────────────────────────────────────────────────


class TestStrategyOutcome:
    def test_default_factories_on_aborted_path(self) -> None:
        # POLYLENS-FIX-9 P2: a non-aborted outcome MUST carry winners; an
        # aborted outcome may have any combination, so exercise defaults
        # via the abort path.
        outcome = StrategyOutcome(
            voices=[], builder_results=[], scores=[],
            aborted=True, abort_reason="test",
        )
        assert outcome.grounding == {}
        assert outcome.winner_result is None
        assert outcome.audit is None
        assert outcome.aborted is True

    def test_validator_rejects_non_aborted_without_winner(self) -> None:
        with pytest.raises(ValueError, match="missing winner artefacts"):
            StrategyOutcome(voices=[], builder_results=[], scores=[])

    def test_is_frozen(self) -> None:
        outcome = StrategyOutcome(
            voices=[], builder_results=[], scores=[],
            aborted=True, abort_reason="t",
        )
        with pytest.raises((AttributeError, Exception)):
            outcome.aborted = True  # type: ignore[misc]
