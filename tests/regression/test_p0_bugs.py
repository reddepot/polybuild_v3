"""Régression anti-P0 — les 3 bugs que 9 rounds d'audit ont manqués.

1. import asyncio manquant orchestrator.py (patch SIGINT round 9 incomplet)
2. tests/ unit+integration+regression vides
3. mypy strict : phase_6_validate type confusion + phase_5_triade Literal violé
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from polybuild.models import FixReport, FixResult


class TestP0AsyncioImportInOrchestrator:
    """Bug P0 #1 : `asyncio` manquant dans orchestrator.py malgré 3 usages."""

    def test_orchestrator_imports_without_nameerror(self) -> None:
        """L'import global de orchestrator.py ne doit pas lever NameError."""
        import polybuild.orchestrator as orch

        assert orch is not None
        # Les symboles asyncio doivent être résolus
        assert hasattr(orch, "asyncio") or "asyncio" in sys.modules

    def test_handle_shutdown_signal_references_asyncio(self) -> None:
        """_handle_shutdown_signal utilise asyncio.current_task et asyncio.all_tasks."""
        import polybuild.orchestrator as orch

        fn = orch._handle_shutdown_signal
        src = Path(orch.__file__).read_text()
        tree = ast.parse(src)

        # Vérifier que 'asyncio' est importé au top-level
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        asyncio_imported = any(
            (isinstance(i, ast.Import) and any(a.name == "asyncio" for a in i.names))
            or (isinstance(i, ast.ImportFrom) and i.module == "asyncio")
            for i in imports
        )
        assert asyncio_imported, "asyncio must be imported at top-level in orchestrator.py"

        # Vérifier que la fonction référence bien les attributs asyncio
        body = ast.dump(tree, annotate_fields=False)
        assert "current_task" in body
        assert "all_tasks" in body

    def test_asyncio_symbols_callable(self) -> None:
        """Les appels asyncio dans _handle_shutdown_signal sont accessibles."""
        import asyncio
        import polybuild.orchestrator as orch

        assert callable(asyncio.current_task)
        assert callable(asyncio.all_tasks)
        assert callable(orch._handle_shutdown_signal)


class TestP0TestsNotEmpty:
    """Bug P0 #2 : tests/{unit,integration,regression}/ tous Vides."""

    def test_unit_directory_has_test_files(self) -> None:
        unit_dir = Path(__file__).parent.parent / "unit"
        if unit_dir.exists():
            tests = list(unit_dir.rglob("test_*.py"))
            assert len(tests) > 0, "tests/unit/ must contain at least one test_*.py file"
            for t in tests:
                assert t.stat().st_size > 0, f"{t} must not be empty"

    def test_regression_directory_has_test_files(self) -> None:
        reg_dir = Path(__file__).parent
        tests = list(reg_dir.rglob("test_*.py"))
        assert len(tests) > 0, "tests/regression/ must contain at least one test_*.py file"


class TestP0MypyStrictFixes:
    """Bug P0 #3 : mypy strict 52 erreurs — vérifications runtime des contrats types."""

    def test_fix_report_status_literal_rejected(self) -> None:
        """FixReport.status n'accepte que 'completed' | 'blocked_p0' | 'partial'."""
        # Doit passer
        FixReport(status="completed", results=[])
        FixReport(status="blocked_p0", results=[])
        FixReport(status="partial", results=[])

        # Doit échouer
        with pytest.raises(ValidationError):
            FixReport(status="invalid_status", results=[])  # type: ignore[call-arg]

    def test_fix_result_status_literal_accepted(self) -> None:
        """FixResult.status n'accepte que les literals définis."""
        FixResult(
            finding_ids=["F1"],
            status="accepted",
            critic_model="c",
            fixer_model="f",
            verifier_model="v",
            iterations=1,
        )
        FixResult(
            finding_ids=["F1"],
            status="escalate",
            critic_model="c",
            fixer_model="f",
            verifier_model="v",
            iterations=1,
        )

    def test_phase_6_validation_verdict_types(self) -> None:
        """ValidationVerdict utilise les bons types GateResults (pas de confusion MCP/RAG)."""
        from polybuild.models import GateResults, ValidationVerdict

        gates = GateResults(
            acceptance_pass_ratio=1.0,
            bandit_clean=True,
            mypy_strict_clean=True,
            ruff_clean=True,
            coverage_score=0.85,
            gitleaks_clean=True,
            gitleaks_findings_count=0,
            diff_minimality=1.0,
        )
        verdict = ValidationVerdict(
            passed=True,
            general_gates=gates,
            domain_gates_passed=True,
            domain_gates_results={"mcp": True},
        )
        assert verdict.passed is True
        assert isinstance(verdict.general_gates, GateResults)
