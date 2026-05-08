"""Tests unitaires pour Phase 1 — Voice selection (matrix + diversity)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polybuild.models import RiskProfile, Spec
from polybuild.phases.phase_1_select import (
    diversity_score,
    filter_candidates,
    is_openrouter_routed,
    is_us_or_cn_model,
    load_config,
    matrix_select,
    select_auditor,
    select_mediator,
    select_voices,
)


DIMENSIONS: dict[str, dict[str, str]] = {
    "claude-opus-4.7": {"provider": "anthropic", "architecture": "dense", "alignment": "safety", "corpus_proxy": "anthropic", "role_bias": "architect"},
    "gpt-5.5": {"provider": "openai", "architecture": "dense", "alignment": "agentic", "corpus_proxy": "openai", "role_bias": "builder"},
    "gemini-3.1-pro": {"provider": "google", "architecture": "dense", "alignment": "helpful", "corpus_proxy": "google", "role_bias": "long_context"},
    "kimi-k2.6": {"provider": "moonshot", "architecture": "moe", "alignment": "creative", "corpus_proxy": "chinese", "role_bias": "variant"},
    "deepseek/deepseek-v4-pro": {"provider": "deepseek", "architecture": "moe", "alignment": "algo", "corpus_proxy": "deepseek", "role_bias": "math"},
    "x-ai/grok-4.20": {"provider": "xai", "architecture": "dense", "alignment": "prompt", "corpus_proxy": "xai", "role_bias": "skeptic"},
    "mistral/devstral-2": {"provider": "mistral", "architecture": "dense", "alignment": "agentic", "corpus_proxy": "mistral", "role_bias": "agentic_eu"},
    "qwen2.5-coder:14b-int4": {"provider": "alibaba", "architecture": "dense", "alignment": "helpful", "corpus_proxy": "alibaba", "role_bias": "local_safe"},
    "qwen2.5-coder:7b-int4": {"provider": "alibaba", "architecture": "dense", "alignment": "helpful", "corpus_proxy": "alibaba", "role_bias": "local_atomic"},
}


class TestDiversityScore:
    def test_less_than_two_voices_zero(self) -> None:
        assert diversity_score(["gpt-5.5"], DIMENSIONS) == 0.0

    def test_identical_voices_zero(self) -> None:
        assert diversity_score(["gpt-5.5", "gpt-5.5"], DIMENSIONS) == 0.0

    def test_fully_orthogonal_five(self) -> None:
        # gpt vs kimi = provider/architecture/alignment/corpus/role tous différents
        score = diversity_score(["gpt-5.5", "kimi-k2.6"], DIMENSIONS)
        assert score == 5.0

    def test_missing_voice_skipped(self) -> None:
        score = diversity_score(["gpt-5.5", "unknown-model"], DIMENSIONS)
        assert score == 0.0  # only one known voice in pair


class TestIsUSOrCNModel:
    @pytest.mark.parametrize(
        "voice_id,expected",
        [
            ("claude-opus-4.7", True),
            ("gpt-5.5", True),
            ("gemini-3.1-pro", True),
            ("kimi-k2.6", True),
            ("deepseek/deepseek-v4-pro", True),
            ("x-ai/grok-4.20", True),
            ("mistral/devstral-2", False),
            ("qwen2.5-coder:14b-int4", False),  # local NAS Ollama
            # Round 10.8 POLYLENS [Codex A_security-02 P1] : voix
            # chinoises via OR — TOUTES doivent renvoyer True pour
            # que ``excludes_us_cn_models=True`` les exclue.
            ("qwen/qwen3.6-max-preview", True),
            ("qwen/qwen3.6-coder", True),
            ("z-ai/glm-5.1", True),
            ("moonshotai/kimi-k2.6", True),
            ("minimax/minimax-m2.7", True),
            ("xiaomi/mimo-v2.5-pro", True),
            # Mistral EU = NOT US/CN
            ("mistralai/mistral-large", False),  # actually OR-routed but EU provider
        ],
    )
    def test_us_or_cn(self, voice_id: str, expected: bool) -> None:
        assert is_us_or_cn_model(voice_id) is expected


class TestIsOpenrouterRouted:
    @pytest.mark.parametrize(
        "voice_id,expected",
        [
            ("deepseek/deepseek-v4-pro", True),
            ("x-ai/grok-4.20", True),
            ("claude-opus-4.7", False),
            ("mistral/devstral-2", False),  # Mistral EU direct, NOT OR
            ("qwen2.5-coder:14b-int4", False),  # local Ollama
            # Round 10.8 POLYLENS [Codex A_security-01 P1] : new OR
            # provider prefixes must ALL be detected.
            ("qwen/qwen3.6-max-preview", True),
            ("z-ai/glm-5.1", True),
            ("moonshotai/kimi-k2.6", True),
            ("minimax/minimax-m2.7", True),
            ("xiaomi/mimo-v2.5-pro", True),
            ("mistralai/mistral-large", True),
        ],
    )
    def test_openrouter(self, voice_id: str, expected: bool) -> None:
        assert is_openrouter_routed(voice_id) is expected


class TestFilterCandidates:
    def test_no_constraints_returns_all(self) -> None:
        pool = ["gpt-5.5", "deepseek/deepseek-v4-pro", "mistral/devstral-2"]
        rp = RiskProfile()
        assert filter_candidates(pool, rp) == pool

    def test_excludes_us_cn_keeps_local_ollama_qwen(self) -> None:
        # Round 10.8 POLYLENS [Gemini GEMINI-03 P1]: ensure that the
        # ``qwen<X>:Y`` LOCAL Ollama tag is kept under
        # ``excludes_us_cn_models=True``, while ``qwen/<anything>`` (OR
        # remote = Alibaba CN) is rejected.
        pool = [
            "qwen2.5-coder:14b-int4",  # local Ollama, must stay
            "qwen2.5-coder:7b-int4",  # local Ollama, must stay
            "qwen/qwen3.6-max-preview",  # OR Alibaba CN, must go
            "qwen/qwen3.6-coder",  # OR Alibaba CN, must go
            "z-ai/glm-5.1",  # OR ZhipuAI CN, must go
            "moonshotai/kimi-k2.6",  # OR Moonshot CN, must go
            "minimax/minimax-m2.7",  # OR MiniMax CN, must go
            "xiaomi/mimo-v2.5-pro",  # OR Xiaomi CN, must go
            "mistral/devstral-2",  # Mistral EU direct, must stay
        ]
        rp = RiskProfile(excludes_us_cn_models=True)
        out = filter_candidates(pool, rp)
        # Local Ollama Qwen + Mistral EU stay
        assert "qwen2.5-coder:14b-int4" in out
        assert "qwen2.5-coder:7b-int4" in out
        assert "mistral/devstral-2" in out
        # All Chinese OR remote MUST be filtered out
        for cn in (
            "qwen/qwen3.6-max-preview",
            "qwen/qwen3.6-coder",
            "z-ai/glm-5.1",
            "moonshotai/kimi-k2.6",
            "minimax/minimax-m2.7",
            "xiaomi/mimo-v2.5-pro",
        ):
            assert cn not in out, f"Chinese voice {cn} leaked despite excludes_us_cn_models=True"

    def test_excludes_openrouter(self) -> None:
        pool = ["gpt-5.5", "deepseek/deepseek-v4-pro", "mistral/devstral-2"]
        rp = RiskProfile(excludes_openrouter=True)
        assert filter_candidates(pool, rp) == ["gpt-5.5", "mistral/devstral-2"]

    def test_excludes_us_cn_keeps_local_qwen(self) -> None:
        pool = ["gpt-5.5", "kimi-k2.6", "qwen2.5-coder:14b-int4", "mistral/devstral-2"]
        rp = RiskProfile(excludes_us_cn_models=True)
        result = filter_candidates(pool, rp)
        assert "qwen2.5-coder:14b-int4" in result
        assert "gpt-5.5" not in result
        assert "kimi-k2.6" not in result
        assert "mistral/devstral-2" in result


class TestMatrixSelect:
    def test_valid_triad_found(self) -> None:
        candidates = ["claude-opus-4.7", "gpt-5.5", "gemini-3.1-pro", "kimi-k2.6"]
        triad = matrix_select(candidates, 2.0, DIMENSIONS)
        assert triad is not None
        assert len(triad) == 3

    def test_no_duplicate_provider_by_default(self) -> None:
        candidates = ["claude-opus-4.7", "claude-sonnet-4.6", "gpt-5.5"]
        dims = {
            **DIMENSIONS,
            "claude-sonnet-4.6": {**DIMENSIONS["claude-opus-4.7"], "role_bias": "workhorse"},
        }
        triad = matrix_select(candidates, 1.5, dims)
        # claude-opus et claude-sonnet même provider → rejeté sauf EU-compliant
        assert triad is None or len({dims[v]["provider"] for v in triad}) >= 2

    def test_eu_compliant_duplicate_provider_allowed(self) -> None:
        """Round 9 fix [Kimi-medical-providers] : triade EU peut duppliquer provider."""
        candidates = ["qwen2.5-coder:14b-int4", "qwen2.5-coder:7b-int4", "mistral/devstral-2"]
        triad = matrix_select(candidates, 1.0, DIMENSIONS)
        assert triad is not None
        providers = [DIMENSIONS[v]["provider"] for v in triad]
        # Les 2 qwen = alibaba, mistral = mistral → 2 providers distincts minimum
        assert len(set(providers)) >= 2

    def test_fixed_voices_respected(self) -> None:
        candidates = ["claude-opus-4.7", "gpt-5.5", "gemini-3.1-pro"]
        triad = matrix_select(candidates, 2.0, DIMENSIONS, fixed_voices=["claude-opus-4.7"])
        assert triad is not None
        assert "claude-opus-4.7" in triad

    def test_impossible_returns_none(self) -> None:
        candidates = ["gpt-5.5"]
        assert matrix_select(candidates, 5.0, DIMENSIONS) is None

    def test_too_many_fixed_voices_returns_none(self) -> None:
        candidates = ["gpt-5.5"]
        assert matrix_select(candidates, 0.0, DIMENSIONS, fixed_voices=["a", "b", "c", "d"]) is None

    def test_highest_diversity_selected(self) -> None:
        candidates = ["gpt-5.5", "gemini-3.1-pro", "kimi-k2.6", "deepseek/deepseek-v4-pro"]
        triad = matrix_select(candidates, 2.0, DIMENSIONS)
        assert triad is not None
        score = diversity_score(triad, DIMENSIONS)
        # Vérification faible : le score doit être au moins le minimum
        assert score >= 2.0


class TestSelectMediator:
    def test_known_profile(self, tmp_path: Path) -> None:
        # On crée un config root temporaire minimal
        cfg_root = tmp_path / "config"
        cfg_root.mkdir()
        (cfg_root / "models.yaml").write_text("{}")
        (cfg_root / "routing.yaml").write_text(
            "profiles:\n  module_standard_known:\n    mediator: claude-opus-4.7\n"
        )
        (cfg_root / "model_dimensions.yaml").write_text("{}")
        (cfg_root / "timeouts.yaml").write_text("phases:\n  phase_2_generate:\n    default_seconds: 60\n")
        mediator = select_mediator("module_standard_known", [], config_root=cfg_root)
        assert mediator == "claude-opus-4.7"

    def test_unknown_profile_returns_none(self) -> None:
        assert select_mediator("unknown_profile", []) is None

    def test_mediator_clash_returns_none(self) -> None:
        # Si mediator est dans voices_used, on retourne None
        assert select_mediator("module_standard_known", ["claude-opus-4.7"]) is None

    def test_human_mediator_preserved(self, tmp_path: Path) -> None:
        cfg_root = tmp_path / "config"
        cfg_root.mkdir()
        (cfg_root / "models.yaml").write_text("{}")
        (cfg_root / "routing.yaml").write_text(
            "profiles:\n  documentation_adr:\n    mediator: humain\n"
        )
        (cfg_root / "model_dimensions.yaml").write_text("{}")
        (cfg_root / "timeouts.yaml").write_text("phases:\n  phase_2_generate:\n    default_seconds: 60\n")
        assert select_mediator("documentation_adr", [], config_root=cfg_root) == "humain"


class TestSelectAuditor:
    def test_auditor_picked_from_pool(self, tmp_path: Path) -> None:
        cfg_root = tmp_path / "config"
        cfg_root.mkdir()
        (cfg_root / "models.yaml").write_text("{}")
        (cfg_root / "routing.yaml").write_text(
            "auditor_pools_by_winner_family:\n  anthropic:\n    - deepseek/deepseek-v4-pro\n    - gpt-5.5\n"
        )
        (cfg_root / "model_dimensions.yaml").write_text(
            "claude-opus-4.7:\n  provider: anthropic\ngpt-5.5:\n  provider: openai\n"
        )
        (cfg_root / "timeouts.yaml").write_text("phases:\n  phase_2_generate:\n    default_seconds: 60\n")
        auditor = select_auditor("claude-opus-4.7", RiskProfile(), config_root=cfg_root)
        assert auditor == "deepseek/deepseek-v4-pro"

    def test_unknown_winner_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown winner voice"):
            select_auditor("unknown-model", RiskProfile())

    def test_empty_pool_after_filter_raises(self, tmp_path: Path) -> None:
        cfg_root = tmp_path / "config"
        cfg_root.mkdir()
        (cfg_root / "models.yaml").write_text("{}")
        (cfg_root / "routing.yaml").write_text(
            "auditor_pools_by_winner_family:\n  anthropic:\n    - deepseek/deepseek-v4-pro\n"
        )
        (cfg_root / "model_dimensions.yaml").write_text("claude-opus-4.7:\n  provider: anthropic\n")
        (cfg_root / "timeouts.yaml").write_text("phases:\n  phase_2_generate:\n    default_seconds: 60\n")
        rp = RiskProfile(excludes_openrouter=True)
        with pytest.raises(RuntimeError, match="No auditor available"):
            select_auditor("claude-opus-4.7", rp, config_root=cfg_root)
