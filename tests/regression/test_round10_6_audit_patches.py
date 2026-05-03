"""Régression POLYLENS round 10.6 — Zone B orchestrator patches.

Findings convergents Gemini ZB-01..06 (avec Kimi RX-301-06).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────
# ZB-01 + Kimi RX-301-06 — _SHUTDOWN_DRAIN_TASKS per run_id
# ──────────────────────────────────────────────────────────────────────


class TestShutdownDrainPerRunId:
    def test_registry_is_dict(self) -> None:
        from polybuild.orchestrator import _SHUTDOWN_DRAIN_TASKS
        assert isinstance(_SHUTDOWN_DRAIN_TASKS, dict)

    def test_module_uses_setdefault_pattern(self) -> None:
        src = Path("src/polybuild/orchestrator/__init__.py").read_text()
        assert "_SHUTDOWN_DRAIN_TASKS.setdefault(run_id" in src
        assert "_SHUTDOWN_DRAIN_TASKS.pop(run_id" in src


# ──────────────────────────────────────────────────────────────────────
# ZB-02 — Phase 8 SSRF allowlist
# ──────────────────────────────────────────────────────────────────────


class TestPhase8SsrfGuard:
    def test_orchestrator_validates_phase_8_url(self) -> None:
        src = Path("src/polybuild/orchestrator/__init__.py").read_text()
        assert "POLYBUILD_PHASE_8_ALLOWLIST" in src
        assert "POLYBUILD_PHASE_8_ALLOW_LOCAL" in src
        assert "169.254." in src
        assert "phase_8_endpoint scheme not allowed" in src


# ──────────────────────────────────────────────────────────────────────
# ZB-03 — generate_run_id collision resistance
# ──────────────────────────────────────────────────────────────────────


class TestRunIdEntropyHardened:
    def test_run_id_suffix_is_16_hex(self) -> None:
        from polybuild.orchestrator import generate_run_id
        for _ in range(8):
            rid = generate_run_id()
            assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{6}_[0-9a-f]{16}$", rid)

    def test_run_id_uniqueness(self) -> None:
        from polybuild.orchestrator import generate_run_id
        ids = {generate_run_id() for _ in range(64)}
        assert len(ids) == 64


# ──────────────────────────────────────────────────────────────────────
# ZB-06 — spec_yaml_path traversal
# ──────────────────────────────────────────────────────────────────────


class TestSpecYamlPathTraversalGuard:
    def test_orchestrator_resolves_and_validates_spec_path(self) -> None:
        src = Path("src/polybuild/orchestrator/__init__.py").read_text()
        assert "spec_yaml_path escapes project_root" in src
        assert "is_relative_to(project_root_resolved)" in src
