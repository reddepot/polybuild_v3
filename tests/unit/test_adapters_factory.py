"""Tests unitaires pour la factory d'adapters et l'instanciation."""

from __future__ import annotations

import pytest

from polybuild.adapters import get_builder
from polybuild.adapters.builder_protocol import BuilderProtocol


class TestGetBuilder:
    """La factory get_builder doit router correctement chaque voice_id."""

    @pytest.mark.parametrize(
        "voice_id,expected_family,expected_name_prefix",
        [
            ("claude-opus-4.7", "anthropic", "claude_code_opus"),
            ("claude-sonnet-4.6", "anthropic", "claude_code_sonnet"),
            ("claude-haiku-4.5", "anthropic", "claude_code_haiku"),
            ("gpt-5.5", "openai", "codex_cli_gpt_5_5"),
            ("gpt-5.5-pro", "openai", "codex_cli_gpt_5_5_pro"),
            ("gpt-5.4", "openai", "codex_cli_gpt_5_4"),
            ("gpt-5.3-codex", "openai", "codex_cli_gpt_5_3_codex"),
            ("gemini-3.1-pro", "google", "gemini_cli_gemini_3_1_pro"),
            ("gemini-3.1-flash", "google", "gemini_cli_gemini_3_1_flash"),
            ("kimi-k2.6", "moonshot", "kimi_cli_k2_6"),
            ("mistral/devstral-2", "mistral", "mistral_eu_devstral_2"),
            ("deepseek/deepseek-v4-pro", "deepseek", "openrouter_deepseek_deepseek_v4_pro"),
            ("deepseek/deepseek-v4-flash", "deepseek", "openrouter_deepseek_deepseek_v4_flash"),
            ("x-ai/grok-4.20", "xai", "openrouter_x_ai_grok_4_20"),
            ("qwen2.5-coder:14b-int4", "alibaba", "ollama_local_qwen2_5_coder_14b_int4"),
            ("qwen2.5-coder:7b-int4", "alibaba", "ollama_local_qwen2_5_coder_7b_int4"),
        ],
    )
    def test_known_voice_ids(
        self, voice_id: str, expected_family: str, expected_name_prefix: str
    ) -> None:
        builder = get_builder(voice_id)
        assert isinstance(builder, BuilderProtocol)
        assert builder.family == expected_family
        assert builder.name.startswith(expected_name_prefix)

    def test_unknown_voice_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown voice_id"):
            get_builder("unknown-model-v99")

    def test_claude_model_slug_parsing(self) -> None:
        from polybuild.adapters.claude_code import ClaudeCodeAdapter

        b = get_builder("claude-opus-4.7")
        assert isinstance(b, ClaudeCodeAdapter)
        assert b.model == "opus-4.7"

    def test_gemini_pro_gets_preview_suffix(self) -> None:
        from polybuild.adapters.gemini_cli import GeminiCLIAdapter

        b = get_builder("gemini-3.1-pro")
        assert isinstance(b, GeminiCLIAdapter)
        # Le code ajoute -preview pour les modèles "pro"
        assert b.model == "gemini-3.1-pro-preview"

    def test_qwen_requires_colon(self) -> None:
        """qwen sans ':' ne matche pas le pattern ollama."""
        with pytest.raises(ValueError):
            get_builder("qwen2.5-coder")
