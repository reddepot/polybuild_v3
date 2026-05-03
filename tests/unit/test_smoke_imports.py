"""Smoke test : tous les modules de src/polybuild/ importent sans erreur."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import polybuild


def _discover_modules(package: object, prefix: str = "") -> list[str]:
    modules: list[str] = []
    for _, modname, ispkg in pkgutil.walk_packages(
        package.__path__, prefix=package.__name__ + "."
    ):
        modules.append(modname)
        if ispkg:
            try:
                sub = importlib.import_module(modname)
                modules.extend(_discover_modules(sub, ""))
            except Exception:
                pass
    return modules


MODULES = _discover_modules(polybuild)


@pytest.mark.parametrize("modname", MODULES)
def test_module_imports(modname: str) -> None:
    """Chaque module sous polybuild doit s'importer sans exception."""
    importlib.import_module(modname)


class TestPublicApiAccessible:
    """Vérification que les contrats publics sont accessibles."""

    def test_models_imports(self) -> None:
        from polybuild.models import (
            AcceptanceCriterion,
            AuditReport,
            BuilderResult,
            CommitInfo,
            Finding,
            FixReport,
            GateResults,
            GroundingFinding,
            PolybuildRun,
            PrivacyLevel,
            RiskProfile,
            SelfMetrics,
            Severity,
            Spec,
            SpecAttack,
            Status,
            TokenUsage,
            ValidationVerdict,
            VoiceConfig,
            VoiceScore,
        )

        assert AcceptanceCriterion
        assert PolybuildRun

    def test_adapters_imports(self) -> None:
        from polybuild.adapters import (
            BuilderProtocol,
            ClaudeCodeAdapter,
            CodexCLIAdapter,
            GeminiCLIAdapter,
            KimiCLIAdapter,
            MistralEUAdapter,
            OllamaLocalAdapter,
            OpenRouterAdapter,
            get_builder,
        )

        assert get_builder
        assert BuilderProtocol

    def test_phases_imports(self) -> None:
        from polybuild.phases.phase_1_select import select_voices
        from polybuild.phases.phase_3_score import phase_3_score
        from polybuild.phases.phase_5_triade import phase_5_dispatch
        from polybuild.phases.phase_6_validate import phase_6_validate
        from polybuild.phases.phase_minus_one_privacy import phase_minus_one_privacy_gate

        assert callable(phase_minus_one_privacy_gate)
        assert callable(select_voices)
        assert callable(phase_3_score)
        assert callable(phase_5_dispatch)
        assert callable(phase_6_validate)

    def test_orchestrator_imports(self) -> None:
        from polybuild.orchestrator import (
            _build_aborted_run,
            generate_run_id,
            run_polybuild,
            save_checkpoint,
        )

        assert callable(run_polybuild)
        assert callable(generate_run_id)
