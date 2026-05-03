"""Régression Round 10.8 follow-up — CLI adapters parse JSON stdout and write files.

Codex CLI 0.128 and Claude CLI v2 no longer write files themselves; they emit
the model's output as text on stdout. These tests verify that the adapters
parse the JSON payload (including markdown-wrapped JSON) and write files via
``write_files_to_worktree``, with proper fallback metrics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polybuild.adapters.claude_code import ClaudeCodeAdapter
from polybuild.adapters.codex_cli import CodexCLIAdapter
from polybuild.models import (
    AcceptanceCriterion,
    RiskProfile,
    Spec,
    Status,
    VoiceConfig,
)


def _make_spec() -> Spec:
    return Spec(
        run_id="test-run-001",
        profile_id="test_profile",
        task_description="Write a calculator module.",
        constraints=["mypy strict"],
        acceptance_criteria=[
            AcceptanceCriterion(
                id="ac1",
                description="add(1,2) == 3",
                test_command="pytest",
            ),
        ],
        risk_profile=RiskProfile(),
    )


def _make_cfg() -> VoiceConfig:
    return VoiceConfig(
        voice_id="test/v1",
        family="openai",
        role="builder",
        timeout_sec=60,
    )


# ──────────────────────────────────────────────────────────────────────
# CodexCLIAdapter
# ──────────────────────────────────────────────────────────────────────


class TestCodexCLIParseOutput:
    def test_json_direct_writes_files(self, tmp_path: Path) -> None:
        adapter = CodexCLIAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        payload = {
            "files": {
                "src/calc.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
                "tests/test_calc.py": (
                    "from calc import add\n\n"
                    "def test_add() -> None:\n    assert add(1, 2) == 3\n"
                ),
            },
            "self_metrics": {
                "loc": 4,
                "complexity_cyclomatic_avg": 1.0,
                "test_to_code_ratio": 1.0,
                "todo_count": 0,
                "imports_count": 0,
                "functions_count": 1,
            },
        }
        raw = json.dumps(payload)

        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert (worktree / "src" / "calc.py").exists()
        assert (worktree / "tests" / "test_calc.py").exists()
        assert result.self_metrics.loc == 4

    def test_json_fenced_markdown_writes_files(self, tmp_path: Path) -> None:
        adapter = CodexCLIAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        payload = {
            "files": {
                "src/foo.py": "x = 1\n",
            },
            "self_metrics": {},
        }
        raw = f"Here is the result:\n```json\n{json.dumps(payload)}\n```\nEnjoy!"

        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert (worktree / "src" / "foo.py").read_text() == "x = 1\n"
        assert result.status == Status.OK

    def test_malformed_json_no_crash_zero_files(self, tmp_path: Path) -> None:
        adapter = CodexCLIAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        raw = "this is not json { broken"
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert len(list(worktree.rglob("*.py"))) == 0

    def test_non_dict_json_no_crash(self, tmp_path: Path) -> None:
        adapter = CodexCLIAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        raw = json.dumps(["just", "a", "list"])
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert len(list(worktree.rglob("*.py"))) == 0

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        adapter = CodexCLIAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        payload = {
            "files": {
                "../escape.py": "evil",
                "src/ok.py": "ok",
            },
            "self_metrics": {},
        }
        raw = json.dumps(payload)
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert not (tmp_path / "escape.py").exists()
        assert (worktree / "src" / "ok.py").exists()

    def test_fallback_estimate_metrics_when_self_metrics_absent(self, tmp_path: Path) -> None:
        adapter = CodexCLIAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        (worktree / "src" / "bar.py").write_text("def bar() -> None:\n    pass\n")
        (worktree / "tests" / "test_bar.py").write_text("def test_bar() -> None:\n    pass\n")

        payload = {
            "files": {},
        }
        raw = json.dumps(payload)
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert result.self_metrics.loc == 2  # bar.py has 2 lines


# ──────────────────────────────────────────────────────────────────────
# ClaudeCodeAdapter
# ──────────────────────────────────────────────────────────────────────


class TestClaudeCodeParseOutput:
    def test_json_direct_writes_files(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        payload = {
            "files": {
                "src/calc.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
                "tests/test_calc.py": (
                    "from calc import add\n\n"
                    "def test_add() -> None:\n    assert add(1, 2) == 3\n"
                ),
            },
            "self_metrics": {
                "loc": 4,
                "complexity_cyclomatic_avg": 1.0,
                "test_to_code_ratio": 1.0,
                "todo_count": 0,
                "imports_count": 0,
                "functions_count": 1,
            },
        }
        raw = json.dumps(payload)

        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert (worktree / "src" / "calc.py").exists()
        assert (worktree / "tests" / "test_calc.py").exists()
        assert result.self_metrics.loc == 4

    def test_json_fenced_markdown_writes_files(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        payload = {
            "files": {
                "src/foo.py": "x = 1\n",
            },
            "self_metrics": {},
        }
        raw = f"Sure!\n```\n{json.dumps(payload)}\n```\nDone."

        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert (worktree / "src" / "foo.py").read_text() == "x = 1\n"
        assert result.status == Status.OK

    def test_malformed_json_no_crash_zero_files(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        raw = "random text without braces"
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert len(list(worktree.rglob("*.py"))) == 0

    def test_non_dict_json_no_crash(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        raw = '"just a string"'
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert len(list(worktree.rglob("*.py"))) == 0

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        # Round 10.8 POLYLENS [Codex C_tests-01 P2]: use a tmp-scoped
        # absolute path so we can really assert it was NOT written.
        outside = tmp_path / "outside_evil.txt"
        payload = {
            "files": {
                str(outside): "should never land here",
                "src/ok.py": "ok",
            },
            "self_metrics": {},
        }
        raw = json.dumps(payload)
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert not outside.exists(), (
            "absolute path outside worktree must be blocked by safe_write"
        )
        assert (worktree / "src" / "ok.py").exists()

    def test_fallback_estimate_metrics_when_self_metrics_absent(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "src").mkdir()
        (worktree / "tests").mkdir()

        (worktree / "src" / "baz.py").write_text("def baz() -> None:\n    pass\n")
        (worktree / "tests" / "test_baz.py").write_text("def test_baz() -> None:\n    pass\n")

        payload = {
            "files": {},
        }
        raw = json.dumps(payload)
        result = adapter._parse_output(raw, worktree, _make_cfg(), 1.0)

        assert result.status == Status.OK
        assert result.self_metrics.loc == 2  # baz.py has 2 lines
