"""Régression POLYLENS round 10 — patches du multi-axes audit 2026-05-03.

Couvre :
    [SAST-001] orchestrator.py importe asyncio (3 sites de _handle_shutdown_signal
                et run_polybuild)
    [SAST-008] datetime.now(UTC) partout, plus de utcnow()
    [round-9-P1-1] Phase 3b ast.parse async + timeout 8s
    [round-9-P1-3] limiter wait_for(coro_factory()) avec exec_timeout
    [round-9-P1-5] adapters CLI : start_new_session=True (Linux/macOS)
    [round-9-P1-2] Phase 5 fixer doit créer un test régression (snapshot pre/post)
"""

from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path

import pytest

import polybuild.orchestrator as orch
from polybuild.concurrency.limiter import CLILimiter, ConcurrencyError, Priority
from polybuild.phases.phase_3b_grounding import _AST_PARSE_TIMEOUT_S, GroundingEngine

ADAPTER_FILES = [
    "claude_code.py",
    "codex_cli.py",
    "gemini_cli.py",
    "kimi_cli.py",
]


# ──────────────────────────────────────────────────────────────────────
# SAST-001 — asyncio import in orchestrator
# ──────────────────────────────────────────────────────────────────────


class TestSast001AsyncioImport:
    def test_orchestrator_module_imports_cleanly(self) -> None:
        # If asyncio were missing the module-level function defs would crash on
        # name resolution at first call; importing the module already succeeded
        # in the test session, but we re-check the symbol explicitly.
        assert hasattr(orch, "asyncio")
        assert orch.asyncio.get_event_loop_policy is not None

    def test_handle_shutdown_signal_callable(self) -> None:
        assert callable(orch._handle_shutdown_signal)

    def test_orchestrator_source_has_asyncio_import(self) -> None:
        src = Path(orch.__file__).read_text()
        assert re.search(r"^import asyncio$", src, re.MULTILINE), (
            "asyncio must be imported at module top level"
        )


# ──────────────────────────────────────────────────────────────────────
# SAST-008 — datetime.now(UTC) instead of utcnow()
# ──────────────────────────────────────────────────────────────────────


class TestSast008DatetimeUtcAware:
    def test_orchestrator_no_utcnow_calls(self) -> None:
        src = Path(orch.__file__).read_text()
        assert "utcnow()" not in src, (
            "datetime.utcnow() removed in Python 3.13 — use datetime.now(UTC)"
        )

    def test_run_id_is_utc_timestamp(self) -> None:
        rid = orch.generate_run_id()
        # YYYY-MM-DD_HHMMSS_xxxx pattern, no timezone suffix needed but the
        # underlying datetime must be tz-aware (verified by the absence of
        # utcnow above).
        assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{6}_[0-9a-f]+$", rid), rid


# ──────────────────────────────────────────────────────────────────────
# round-9-P1-1 — Phase 3b ast.parse async wrapper bounded
# ──────────────────────────────────────────────────────────────────────


class TestRound9AstParseTimeout:
    def test_engine_exposes_async_check_path(self) -> None:
        assert callable(GroundingEngine.check_file_async)
        assert callable(GroundingEngine.check_directory_async)

    def test_timeout_constant_is_reasonable(self) -> None:
        assert 1.0 < _AST_PARSE_TIMEOUT_S < 30.0

    @pytest.mark.asyncio
    async def test_async_path_returns_p0_finding_on_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force a timeout by patching the sync check_file to sleep > timeout.
        engine = GroundingEngine(tmp_path)
        py_file = tmp_path / "victim.py"
        py_file.write_text("x = 1\n")

        import time as _time

        def slow_check(self_, py, voice):  # noqa: ARG001
            _time.sleep(_AST_PARSE_TIMEOUT_S + 0.5)
            return []

        monkeypatch.setattr(GroundingEngine, "check_file", slow_check)

        findings = await engine.check_file_async(py_file, "v1")
        assert any(f.kind == "syntax_error" and "timeout" in f.detail for f in findings)


# ──────────────────────────────────────────────────────────────────────
# round-9-P1-3 — CLILimiter exec_timeout_s prevents semaphore leak
# ──────────────────────────────────────────────────────────────────────


class TestRound9CLILimiterExecTimeout:
    def test_run_signature_exposes_exec_timeout(self) -> None:
        sig = inspect.signature(CLILimiter.run)
        assert "exec_timeout_s" in sig.parameters
        assert sig.parameters["exec_timeout_s"].default == 1800.0

    @pytest.mark.asyncio
    async def test_hung_coro_releases_semaphore_via_timeout(
        self, tmp_path: Path
    ) -> None:
        limiter = CLILimiter(limits={"claude": 1})

        async def _hangs_forever() -> str:
            await asyncio.sleep(60)
            return "never"

        with pytest.raises(ConcurrencyError, match="exec timeout"):
            await limiter.run(
                provider_or_voice="claude",
                coro_factory=_hangs_forever,
                priority=Priority.P1,
                exec_timeout_s=0.2,
            )

        # Semaphore must have been released — a follow-up call should not
        # block on the long-since-cancelled coroutine.
        async def _quick() -> str:
            return "ok"

        result = await limiter.run(
            provider_or_voice="claude",
            coro_factory=_quick,
            priority=Priority.P1,
            exec_timeout_s=5.0,
        )
        assert result == "ok"


# ──────────────────────────────────────────────────────────────────────
# round-9-P1-5 — adapters CLI use start_new_session for SIGINT propagation
# ──────────────────────────────────────────────────────────────────────


class TestRound9StartNewSession:
    @pytest.mark.parametrize("fname", ADAPTER_FILES)
    def test_adapter_passes_start_new_session(self, fname: str) -> None:
        path = Path(__file__).resolve().parents[2] / "src/polybuild/adapters" / fname
        src = path.read_text()
        # Each create_subprocess_exec block should opt into a new session on
        # POSIX so the orchestrator's os.killpg can cleanly tear down child
        # processes spawned by the CLI tool.
        n_spawn = src.count("asyncio.create_subprocess_exec(")
        n_session = src.count('start_new_session=(sys.platform != "win32")')
        assert n_spawn > 0, f"{fname}: expected at least one subprocess spawn"
        assert n_session == n_spawn, (
            f"{fname}: {n_spawn} spawns but only {n_session} declare start_new_session"
        )


# ──────────────────────────────────────────────────────────────────────
# round-9-P1-2 — Phase 5 fixer test enforcement (snapshot mechanism wired)
# ──────────────────────────────────────────────────────────────────────


class TestRound9FixerTestEnforcement:
    def test_phase_5_snapshots_tests_dir_before_fixer(self) -> None:
        from polybuild.phases import phase_5_triade

        src = Path(phase_5_triade.__file__).read_text()
        assert "pre_fixer_test_files" in src
        assert "post_fixer_test_files" in src
        assert "regression test" in src.lower()
