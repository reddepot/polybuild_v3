"""Concurrency limiting per CLI provider (Round 4 Faille 3).

Convergence 6/6 round 4:
    - asyncio.Semaphore per CLI provider (claude, codex, gemini, kimi, openrouter)
    - Differentiated back-pressure by severity:
        P0 → wait until acquired (hard timeout, no fallback for medical safety)
        P1 → wait then fallback to OpenRouter equivalent if available
        P2/P3 → drop the voice or fallback immediately
    - Throttle detection via stderr/stdout patterns (429, rate.?limit, retry-after)
    - Limits configurable via concurrency_limits.yaml (defaults conservative)

Defaults (round 4 average across the 6 models):
    claude=2, codex=2, gemini=4, kimi=1, openrouter=3
"""

from polybuild.concurrency.limiter import (
    CLILimiter,
    ConcurrencyError,
    Priority,
    is_throttle_error,
)

__all__ = ["CLILimiter", "ConcurrencyError", "Priority", "is_throttle_error"]
