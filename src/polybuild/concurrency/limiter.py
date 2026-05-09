"""CLI concurrency limiter with severity-aware back-pressure.

Round 4 convergence (6/6):
    - One asyncio.Semaphore per provider family.
    - Conservative defaults; overridable via concurrency_limits.yaml or env vars.
    - Severity-differentiated waits:
        P0 → wait up to 180s, no fallback (medical safety: would change family).
        P1 → wait up to 30s, then fallback to OpenRouter if `fallback_fn` provided.
        P2 → if locked, drop the voice immediately (binôme suffit).
        P3 → drop immediately if any contention.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar

import structlog
import yaml

logger = structlog.get_logger()

T = TypeVar("T")


# ────────────────────────────────────────────────────────────────
# PRIORITY & ERRORS
# ────────────────────────────────────────────────────────────────


class Priority(StrEnum):
    """Request severity for back-pressure decisions."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ConcurrencyError(RuntimeError):
    """Raised when a request cannot be served due to throttling/saturation."""

    def __init__(self, provider: str, reason: str):
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason


# ────────────────────────────────────────────────────────────────
# THROTTLE DETECTION
# ────────────────────────────────────────────────────────────────


_THROTTLE_PATTERN = re.compile(
    r"rate.?limit|429|quota|throttl|too\s+many\s+requests|retry-after|reset\s+in",
    re.IGNORECASE,
)


# ────────────────────────────────────────────────────────────────
# YAML CONFIG SCHEMA (Round 10.1 fix [R5/R10])
# ────────────────────────────────────────────────────────────────


from pydantic import BaseModel, Field, ValidationError, field_validator  # noqa: E402


class ConcurrencyLimitsConfig(BaseModel):
    """Validated schema for ``config/concurrency_limits.yaml``.

    Round 10.1 fix [R5 + R10] (5/6 conv: Grok / Qwen / Gemini / DeepSeek /
    Kimi): the previous implementation used ``yaml.safe_load`` directly and
    silently fell back to defaults on any malformed value (e.g.
    ``claude: "deux"``). Now we validate the YAML against a Pydantic model
    and surface validation errors so config drift is caught at boot rather
    than at first use.
    """

    limits: dict[str, int] = Field(default_factory=dict)
    profile_boosts: dict[str, dict[str, int]] = Field(default_factory=dict)

    @field_validator("limits")
    @classmethod
    def _validate_limits(cls, v: dict[str, int]) -> dict[str, int]:
        for provider, n in v.items():
            if not isinstance(provider, str) or not provider:
                raise ValueError(f"provider name must be non-empty str, got {provider!r}")
            if not isinstance(n, int) or n < 1 or n > 64:
                raise ValueError(
                    f"limit for {provider!r} must be int in [1, 64], got {n!r}"
                )
        return v


def is_throttle_error(message: str) -> bool:
    """Return True if `message` looks like a rate-limit/throttle error."""
    return bool(_THROTTLE_PATTERN.search(message or ""))


# ────────────────────────────────────────────────────────────────
# DEFAULT LIMITS (Round 4 averaged convergence)
# ────────────────────────────────────────────────────────────────


_DEFAULT_LIMITS: dict[str, int] = {
    "claude": 2,      # Grok=2, Qwen=3, Kimi=2, Gemini=2, ChatGPT=1, DeepSeek=3 → median=2
    "codex": 2,       # Grok=3, Qwen=3, Kimi=2, Gemini=2, ChatGPT=1, DeepSeek=4 → median=2
    "gemini": 4,      # Grok=2, Qwen=5, Kimi=3, Gemini=4, ChatGPT=1, DeepSeek=8 → median=4
    "kimi": 1,        # Grok=3, Qwen=2, Kimi=2, Gemini=1, ChatGPT=1, DeepSeek=5 → median=1.5 → 1 conservative
    "openrouter": 3,  # ChatGPT=3, DeepSeek=irrelevant, default=3
    "mistral": 2,     # EU direct API, generous
    "ollama": 1,      # Local Ollama, single-threaded inference
}


# Override boost for high-throughput profiles (HELIA_algo, code_inedit_critique)
_PROFILE_BOOST: dict[str, dict[str, int]] = {
    "helia_algo": {"codex": 2, "gemini": 2, "openrouter": 4},
    "module_inedit_critique": {"codex": 2, "gemini": 2, "openrouter": 4},
}


# ────────────────────────────────────────────────────────────────
# CLILimiter
# ────────────────────────────────────────────────────────────────


@dataclass
class _ProviderStats:
    """Lightweight runtime stats for instrumentation."""

    invocations: int = 0
    throttle_events: int = 0
    fallback_events: int = 0
    drops: int = 0
    total_wait_s: float = 0.0


@dataclass
class CLILimiter:
    """Per-provider asyncio.Semaphore concurrency limiter.

    Usage:
        limiter = CLILimiter.from_yaml(profile="helia_algo")
        result = await limiter.run(
            "claude",
            lambda: my_async_call(),
            priority=Priority.P0,
            fallback_fn=lambda: openrouter_call(),
        )
    """

    limits: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_LIMITS))
    _semaphores: dict[str, asyncio.Semaphore] = field(default_factory=dict, init=False)
    # Round 5 fix [Q]: keep an explicit in-flight counter to support a real
    # "any contention" semantics for P3 (sem.locked() only fires when fully
    # saturated, missing the partial-contention case).
    _inflight: dict[str, int] = field(default_factory=dict, init=False)
    _stats: dict[str, _ProviderStats] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._rebuild_semaphores()

    def _rebuild_semaphores(self) -> None:
        self._semaphores = {k: asyncio.Semaphore(max(1, v)) for k, v in self.limits.items()}
        for k in self.limits:
            self._stats.setdefault(k, _ProviderStats())
            self._inflight.setdefault(k, 0)

    @classmethod
    def from_yaml(
        cls,
        path: str | Path | None = None,
        profile: str | None = None,
    ) -> CLILimiter:
        """Build from `config/concurrency_limits.yaml`. Falls back to defaults.

        Round 5 fix [Y] (Audit 5 P2): `parents[3]` breaks when installed as a
        wheel. Now tries env var → explicit path → walking up from cwd → fallback.
        """
        limits = dict(_DEFAULT_LIMITS)

        candidate_paths: list[Path] = []
        if path is not None:
            candidate_paths.append(Path(path))
        env_root = os.environ.get("POLYBUILD_CONFIG_ROOT")
        if env_root:
            candidate_paths.append(Path(env_root) / "concurrency_limits.yaml")
        # Source-tree default (editable install)
        candidate_paths.append(
            Path(__file__).resolve().parents[3] / "config" / "concurrency_limits.yaml"
        )
        # Walk up from cwd for installed cases
        cwd = Path.cwd()
        for ancestor in [cwd, *cwd.parents][:5]:
            candidate_paths.append(ancestor / "config" / "concurrency_limits.yaml")

        resolved: Path | None = next(
            (p for p in candidate_paths if p.exists()), None
        )
        if resolved is not None:
            try:
                raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
                # Round 10.1 fix [R5/R10]: Pydantic-validated load. A typo
                # like ``claude: "deux"`` now raises ValidationError instead
                # of silently falling back to defaults.
                cfg = ConcurrencyLimitsConfig.model_validate(raw)
                limits.update(cfg.limits)
                logger.debug("concurrency_yaml_loaded", path=str(resolved))
            except yaml.YAMLError as e:
                logger.error("concurrency_yaml_parse_failed", error=str(e))
                raise
            except ValidationError as e:
                logger.error(
                    "concurrency_yaml_validation_failed",
                    error=str(e),
                    path=str(resolved),
                )
                raise
        else:
            logger.info("concurrency_yaml_not_found_using_defaults")

        if profile and profile in _PROFILE_BOOST:
            for k, v in _PROFILE_BOOST[profile].items():
                limits[k] = max(limits.get(k, 0), v)

        return cls(limits=limits)

    # ── Acquisition logic ──────────────────────────────────────────────

    def _resolve_provider(self, name_or_voice: str) -> str:
        """Map a voice id (e.g. `claude-opus-4.7`) to a provider family key."""
        if "/" in name_or_voice:
            family = name_or_voice.split("/", maxsplit=1)[0].lower()
            mapping = {
                "deepseek": "openrouter",
                "x-ai": "openrouter",
                "qwen": "openrouter",
                "openrouter": "openrouter",
                "mistral": "mistral",
            }
            return mapping.get(family, "openrouter")
        if name_or_voice.startswith("claude"):
            return "claude"
        if name_or_voice.startswith(("gpt", "codex")):
            return "codex"
        if name_or_voice.startswith("gemini"):
            return "gemini"
        if name_or_voice.startswith("kimi"):
            return "kimi"
        if name_or_voice.startswith("qwen") and ":" in name_or_voice:
            return "ollama"
        return name_or_voice

    async def run(
        self,
        provider_or_voice: str,
        coro_factory: Callable[[], Awaitable[T]],
        priority: Priority = Priority.P1,
        fallback_fn: Callable[[], Awaitable[T]] | None = None,
        exec_timeout_s: float = 1800.0,
    ) -> T:
        """Execute `coro_factory()` under the provider's semaphore.

        Args:
            provider_or_voice: Either a family name ("claude") or a voice id ("claude-opus-4.7").
            coro_factory: Zero-arg callable returning a fresh coroutine each call.
                          Using a factory (not a coroutine) lets us retry/fallback safely.
            priority: P0..P3 — controls wait timeout and fallback behaviour.
            fallback_fn: Optional fallback factory used for P1/P2 only.

        Raises:
            ConcurrencyError on P0 timeout, or unrecoverable throttle.
        """
        provider = self._resolve_provider(provider_or_voice)
        sem = self._semaphores.get(provider)
        if sem is None:
            # Unknown provider: run unrestricted (no limiter applied)
            logger.debug("concurrency_unknown_provider_passthrough", provider=provider)
            return await coro_factory()

        stats = self._stats.setdefault(provider, _ProviderStats())

        # Severity-aware acquisition
        wait_timeout = {
            Priority.P0: 180.0,
            Priority.P1: 30.0,
            Priority.P2: 5.0,
            Priority.P3: 0.0,
        }[priority]

        # Round 5 fix [Q] (Audit 5 P0): the docstring promised
        # "P3 → drop immediately if any contention", but `sem.locked()` only
        # returns True when fully saturated (value=0). With claude=2, one busy
        # slot = `sem.locked()=False` → P3 was passing instead of dropping.
        # Use the explicit in-flight counter to detect partial contention.
        if priority == Priority.P3 and self._inflight.get(provider, 0) > 0:
            stats.drops += 1
            raise ConcurrencyError(provider, "P3 dropped on any contention")

        t0 = time.time()
        try:
            await asyncio.wait_for(
                sem.acquire(),
                timeout=wait_timeout if wait_timeout > 0 else 0.001,
            )
        except TimeoutError as err:
            wait = time.time() - t0
            stats.total_wait_s += wait

            if priority == Priority.P0:
                # No fallback for P0 (would change model family → medical/audit safety risk)
                raise ConcurrencyError(
                    provider,
                    f"P0 timeout after {wait:.1f}s — manual intervention required",
                ) from err
            if priority in (Priority.P1, Priority.P2) and fallback_fn is not None:
                stats.fallback_events += 1
                logger.warning(
                    "concurrency_fallback_triggered",
                    provider=provider,
                    priority=priority.value,
                    waited_s=round(wait, 1),
                )
                return await fallback_fn()
            stats.drops += 1
            raise ConcurrencyError(
                provider,
                f"{priority.value} timeout after {wait:.1f}s, no fallback configured",
            ) from err

        wait = time.time() - t0
        stats.total_wait_s += wait
        stats.invocations += 1
        # Round 5 fix [Q]: track in-flight count for P3 contention detection.
        self._inflight[provider] = self._inflight.get(provider, 0) + 1

        try:
            # Round 10 fix [CLI hung semaphore leak] (Claude + Grok round 9 P1):
            # Without a hard execution timeout, a stuck CLI subprocess (claude
            # code, codex, gemini) holds the semaphore forever — subsequent
            # P0/P1 requests time out on acquisition rather than on the actual
            # hung call. wait_for ensures the semaphore is released even when
            # the coroutine hangs at a subprocess boundary.
            return await asyncio.wait_for(coro_factory(), timeout=exec_timeout_s)
        except TimeoutError as err:
            stats.drops += 1
            logger.error(
                "concurrency_exec_timeout",
                provider=provider,
                exec_timeout_s=exec_timeout_s,
                priority=priority.value,
            )
            raise ConcurrencyError(
                provider,
                f"exec timeout after {exec_timeout_s:.0f}s — likely hung CLI subprocess",
            ) from err
        except Exception as e:
            if is_throttle_error(str(e)):
                stats.throttle_events += 1
                logger.warning(
                    "concurrency_throttle_detected",
                    provider=provider,
                    error=str(e)[:200],
                )
            raise
        finally:
            self._inflight[provider] = max(0, self._inflight.get(provider, 1) - 1)
            sem.release()

    # ── Instrumentation ────────────────────────────────────────────────

    def stats_summary(self) -> dict[str, dict[str, Any]]:
        """Return current stats for logging/ADR generation."""
        return {
            provider: {
                "invocations": s.invocations,
                "throttle_events": s.throttle_events,
                "fallback_events": s.fallback_events,
                "drops": s.drops,
                "total_wait_s": round(s.total_wait_s, 2),
            }
            for provider, s in self._stats.items()
        }
