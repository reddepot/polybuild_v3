"""Adapters package — exposes BuilderProtocol implementations and a factory.

Usage:
    from polybuild.adapters import get_builder
    builder = get_builder("claude-opus-4.7")
"""

from __future__ import annotations

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.adapters.claude_code import ClaudeCodeAdapter
from polybuild.adapters.codex_cli import CodexCLIAdapter
from polybuild.adapters.gemini_cli import GeminiCLIAdapter
from polybuild.adapters.kimi_cli import KimiCLIAdapter
from polybuild.adapters.mistral_eu import MistralEUAdapter
from polybuild.adapters.ollama_local import OllamaLocalAdapter
from polybuild.adapters.openrouter import OpenRouterAdapter

__all__ = [
    "BuilderProtocol",
    "ClaudeCodeAdapter",
    "CodexCLIAdapter",
    "GeminiCLIAdapter",
    "KimiCLIAdapter",
    "MistralEUAdapter",
    "OllamaLocalAdapter",
    "OpenRouterAdapter",
    "get_builder",
]


# ────────────────────────────────────────────────────────────────
# FACTORY
# ────────────────────────────────────────────────────────────────


def get_builder(voice_id: str) -> BuilderProtocol:
    """Return the right adapter for a given voice_id.

    Voice ID conventions:
        - "claude-opus-4.7", "claude-sonnet-4.6", "claude-haiku-4.5"
        - "gpt-5.5", "gpt-5.5-pro", "gpt-5.4", "gpt-5.3-codex"
        - "gemini-3.1-pro", "gemini-3.1-flash"
        - "kimi-k2.6"
        - "deepseek/deepseek-v4-pro" (OR), "deepseek/deepseek-v4-flash" (OR)
        - "x-ai/grok-4.20" (OR)
        - "z-ai/glm-5.1" (OR — ZhipuAI 智谱)
        - "qwen/qwen3.6-max-preview" / "qwen/qwen3.6-coder" (OR — Alibaba 阿里)
        - "moonshotai/kimi-k2.6" (OR — fallback when kimi CLI down)
        - "minimax/minimax-m2.7" (OR — MiniMax 稀宇科技)
        - "xiaomi/mimo-v2.5-pro" (OR — Xiaomi 小米)
        - "mistral/devstral-2" (Mistral EU direct, NOT OR)
        - "qwen2.5-coder:14b-int4" (Ollama local)
        - "qwen2.5-coder:7b-int4" (Ollama local)
    """
    # ── Anthropic Claude Code CLI ──
    if voice_id.startswith("claude-"):
        model = voice_id.removeprefix("claude-")  # "opus-4.7"
        return ClaudeCodeAdapter(model=model)

    # ── OpenAI Codex CLI ──
    if voice_id.startswith("gpt-"):
        return CodexCLIAdapter(model=voice_id)

    # ── Google Gemini CLI ──
    if voice_id.startswith("gemini-"):
        return GeminiCLIAdapter(model=f"{voice_id}-preview" if "pro" in voice_id else voice_id)

    # ── Moonshot Kimi CLI ──
    if voice_id.startswith("kimi-"):
        model = voice_id.removeprefix("kimi-")  # "k2.6"
        return KimiCLIAdapter(model=model)

    # ── Mistral EU direct (BEFORE OpenRouter check, key on "mistral/") ──
    if voice_id.startswith("mistral/"):
        slug = voice_id.removeprefix("mistral/")  # "devstral-2"
        return MistralEUAdapter(slug=slug)

    # ── OpenRouter (DeepSeek, xAI/Grok) ──
    if voice_id.startswith("deepseek/"):
        return OpenRouterAdapter(slug=voice_id, family="deepseek")
    if voice_id.startswith("x-ai/"):
        return OpenRouterAdapter(slug=voice_id, family="xai")

    # ── Round 10.8 prod-launch fix: Chinese voices via OpenRouter
    # (cheap + diversity per POLYLENS v3 cross-cultural convergence) ──
    if voice_id.startswith("z-ai/"):  # GLM (ZhipuAI/智谱)
        return OpenRouterAdapter(slug=voice_id, family="zai")
    if voice_id.startswith("qwen/"):  # Qwen (Alibaba/阿里)
        return OpenRouterAdapter(slug=voice_id, family="qwen")
    if voice_id.startswith("moonshotai/"):  # Kimi via OR (when CLI down)
        return OpenRouterAdapter(slug=voice_id, family="moonshot")
    if voice_id.startswith("minimax/"):  # MiniMax (上海稀宇科技)
        return OpenRouterAdapter(slug=voice_id, family="minimax")
    if voice_id.startswith("xiaomi/"):  # MiMo (Xiaomi/小米)
        return OpenRouterAdapter(slug=voice_id, family="xiaomi")

    # ── Ollama local ──
    if voice_id.startswith("qwen") and ":" in voice_id:
        return OllamaLocalAdapter(slug=voice_id)

    raise ValueError(f"Unknown voice_id: {voice_id!r}")
