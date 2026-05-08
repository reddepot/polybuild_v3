"""Tests unitaires pour _build_prompt, _setup_worktree, _parse_output, run_raw_prompt.

Couvre le Round 7 fix [O3] : bypass raw_prompt pour triade critic/fixer/verifier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from polybuild.adapters import get_builder
from polybuild.models import AcceptanceCriterion, RiskProfile, SelfMetrics, Spec, Status, VoiceConfig


def _make_spec(task_description: str = "Implement foo") -> Spec:
    return Spec(
        run_id="R1",
        profile_id="module_standard_known",
        task_description=task_description,
        acceptance_criteria=[
            AcceptanceCriterion(id="ac1", description="foo works", test_command="pytest", blocking=True)
        ],
        risk_profile=RiskProfile(),
    )


def _make_cfg(raw_prompt: bool = False) -> VoiceConfig:
    return VoiceConfig(
        voice_id="claude-opus-4.7",
        family="anthropic",
        role="builder",
        timeout_sec=60,
        context={"raw_prompt": raw_prompt},
    )


# ── Parametrize over all 7 adapters ──
ADAPTER_VOICE_IDS = [
    "claude-opus-4.7",
    "gpt-5.5",
    "gemini-3.1-pro",
    "kimi-k2.6",
    "mistral/devstral-2",
    "deepseek/deepseek-v4-pro",
    "qwen2.5-coder:14b-int4",
]


class TestBuildPromptRawBypass:
    """Round 7 fix [O3] : cfg.context['raw_prompt']=True → retourne task_description tel quel."""

    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    def test_raw_prompt_true_returns_task_description(self, voice_id: str) -> None:
        builder = get_builder(voice_id)
        spec = _make_spec(task_description="CRITIC: check this finding")
        cfg = _make_cfg(raw_prompt=True)
        worktree = Path("/tmp/fake")
        prompt = builder._build_prompt(spec, cfg, worktree)
        assert prompt == "CRITIC: check this finding"
        assert "AGENTS_MD" not in prompt
        assert "INSTRUCTIONS" not in prompt

    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    def test_raw_prompt_false_returns_structured_prompt(self, voice_id: str) -> None:
        builder = get_builder(voice_id)
        spec = _make_spec(task_description="Implement foo")
        cfg = _make_cfg(raw_prompt=False)
        worktree = Path("/tmp/fake")
        prompt = builder._build_prompt(spec, cfg, worktree)
        assert "AGENTS_MD" in prompt or "TASK" in prompt or "SPEC" in prompt or "INSTRUCTIONS" in prompt


class TestSetupWorktree:
    """_setup_worktree doit créer src/ et tests/ sous .polybuild/runs/{run_id}/worktrees/{voice_id}."""

    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    def test_creates_directories(self, voice_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        builder = get_builder(voice_id)
        spec = _make_spec()
        cfg = _make_cfg()
        # Override cwd to tmp_path so .polybuild is created there
        monkeypatch.chdir(tmp_path)
        worktree = builder._setup_worktree(spec, cfg)
        assert worktree.exists()
        assert (worktree / "src").exists()
        assert (worktree / "tests").exists()
        assert "worktrees" in str(worktree)
        assert spec.run_id in str(worktree)


class TestParseOutputAndEstimateMetrics:
    """_parse_output / _parse_response et _estimate_metrics."""

    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    def test_parse_with_self_metrics_json(self, voice_id: str, tmp_path: Path) -> None:
        builder = get_builder(voice_id)
        spec = _make_spec()
        cfg = _make_cfg()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        metrics = SelfMetrics(
            loc=42,
            complexity_cyclomatic_avg=2.5,
            test_to_code_ratio=0.8,
            todo_count=1,
            imports_count=5,
            functions_count=3,
        )

        # Round 10.8 prod-launch refactor : claude CLI v2 ne write plus
        # self_metrics.json sur disque (CLI v2 = stdout text only). Tous
        # les adapters CLI extraient désormais self_metrics depuis le
        # JSON stdout via _try_parse_json + data.get("self_metrics").
        if hasattr(builder, "_parse_output"):
            payload = json.dumps({"files_written": [], "self_metrics": metrics.model_dump()})
            result = builder._parse_output(payload, worktree, cfg, duration=1.0)
        else:
            # HTTP adapters : _parse_response extrait self_metrics du JSON de réponse
            payload = json.dumps({"files": {}, "self_metrics": metrics.model_dump()})
            result = builder._parse_response(payload, worktree, cfg, duration=1.0)

        assert result.self_metrics.loc == 42
        assert result.self_metrics.todo_count == 1
        assert result.status == Status.OK
        assert result.voice_id == cfg.voice_id

    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    def test_estimate_metrics_from_filesystem(self, voice_id: str, tmp_path: Path) -> None:
        builder = get_builder(voice_id)
        if not hasattr(builder, "_estimate_metrics"):
            pytest.skip("HTTP adapters do not implement _estimate_metrics")
        worktree = tmp_path / "wt"
        (worktree / "src").mkdir(parents=True)
        (worktree / "tests").mkdir(parents=True)
        (worktree / "src" / "foo.py").write_text("def foo(): pass\n")
        (worktree / "tests" / "test_foo.py").write_text("def test_foo(): pass\n")

        metrics = builder._estimate_metrics(worktree)
        assert metrics.loc == 1
        assert metrics.test_to_code_ratio == 1.0
        assert metrics.todo_count == 0

    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    def test_estimate_metrics_counts_todos(self, voice_id: str, tmp_path: Path) -> None:
        builder = get_builder(voice_id)
        if not hasattr(builder, "_estimate_metrics"):
            pytest.skip("HTTP adapters do not implement _estimate_metrics")
        worktree = tmp_path / "wt"
        (worktree / "src").mkdir(parents=True)
        (worktree / "src" / "foo.py").write_text("# TODO fix this\n# FIXME later\n")
        metrics = builder._estimate_metrics(worktree)
        assert metrics.todo_count == 2


class TestRunRawPrompt:
    """run_raw_prompt doit injecter raw_prompt=True et retourner le texte brut."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    async def test_run_raw_prompt_sets_bypass_flag(self, voice_id: str) -> None:
        builder = get_builder(voice_id)
        with patch.object(builder, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = AsyncMock()
            mock_gen.return_value.raw_output = "VERDICT: pass"
            mock_gen.return_value.voice_id = voice_id

            result = await builder.run_raw_prompt(
                prompt="VERIFY this",
                workdir=Path("/tmp"),
                timeout_s=30,
                role="verifier",
            )

            assert result == "VERDICT: pass"
            mock_gen.assert_awaited_once()
            _spec, cfg = mock_gen.call_args[0]
            assert cfg.context.get("raw_prompt") is True
            assert cfg.context.get("raw_prompt_no_write") is True  # verifier = no_write

    @pytest.mark.asyncio
    @pytest.mark.parametrize("voice_id", ADAPTER_VOICE_IDS)
    async def test_run_raw_prompt_for_builder_allows_write(self, voice_id: str) -> None:
        builder = get_builder(voice_id)
        with patch.object(builder, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = AsyncMock()
            mock_gen.return_value.raw_output = "OUTPUT"

            await builder.run_raw_prompt(
                prompt="FIX this",
                workdir=Path("/tmp"),
                timeout_s=30,
                role="fixer",
            )

            _spec, cfg = mock_gen.call_args[0]
            assert cfg.context.get("raw_prompt") is True
            # fixer peut écrire
            assert cfg.context.get("raw_prompt_no_write") is False
