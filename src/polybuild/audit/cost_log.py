"""Audit cost tracking — record $ + tokens per remote voice call (FEAT-1).

The audit subsystem fans out to two voices per commit. Western voices
(codex / gemini / kimi CLI) ride on the user's existing subscription
(Claude Max, ChatGPT Pro, etc.) so their marginal cost is $0. Chinese
voices via OpenRouter HTTP are pay-per-token and worth tracking for
monthly budget review.

Cost log lives next to the queue / backlog at
``~/.polybuild/audit/cost_log.jsonl``. One JSON-Lines entry per remote
voice call. The file is locked via the same ``QueueLock`` so the
post-commit hook can append without racing the drain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polybuild.audit.queue import QueueLock, audit_dir, lock_path

# OpenRouter prices in USD per 1M tokens, as of 2026-05-08. Approximate
# — providers update them; we recompute on every call so updating this
# table is a one-edit fix without touching call-sites.
#
# Source: https://openrouter.ai/models — values rounded to 0.01.
_OPENROUTER_PRICING: dict[str, tuple[float, float]] = {
    # voice_id (slug)              (in_per_1m, out_per_1m)
    "openai/gpt-5.5":               (3.00, 15.00),
    "google/gemini-3.1-pro-preview":(1.25,  5.00),
    "moonshotai/kimi-k2.6":         (0.40,  2.00),
    "z-ai/glm-5.1":                 (0.50,  2.00),
    "qwen/qwen3-max":               (1.20,  4.50),
    "qwen/qwen3.6-max-preview":     (1.20,  4.50),
    "qwen/qwen3-coder":             (0.30,  0.85),
    "qwen/qwen3-coder-plus":        (0.40,  1.20),
    "minimax/minimax-m2.7":         (0.10,  0.30),
    "minimax/m2.7":                 (0.10,  0.30),
    "xiaomi/mimo-v2.5-pro":         (0.05,  0.20),
    "anthropic/claude-opus-4-7":    (15.00, 75.00),  # rarely used by audit
}

# Default fallback if a voice slug is missing from the pricing table —
# log $0 so the entry is still recorded but the user knows it isn't
# costed (NaN would break dashboards).
_UNKNOWN_PRICING: tuple[float, float] = (0.0, 0.0)


def cost_log_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "cost_log.jsonl"


VoicePool = Literal["western", "chinese", "unknown"]


class VoiceCostEntry(BaseModel):
    """One audit-time voice call cost record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    voice_id: str
    pool: VoicePool
    commit_sha: str | None = None
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    estimated_usd: float = 0.0
    latency_s: float | None = None
    success: bool = True
    timestamp: datetime


def estimate_usd(
    voice_id: str,
    tokens_prompt: int | None,
    tokens_completion: int | None,
) -> float:
    """Compute USD cost for a voice call given token counts.

    Returns ``0.0`` if either token count is missing or the voice is not
    in the pricing table — never raises.

    POLYLENS run #2 P2 (gemini): OpenRouter occasionally returns token
    counts as strings; the multiplication would otherwise raise
    ``TypeError`` and crash the cost-log writer. Coerce defensively to
    ``int`` and fall back to 0.0 on any conversion failure.
    """
    if tokens_prompt is None or tokens_completion is None:
        return 0.0
    try:
        in_tok = int(tokens_prompt)
        out_tok = int(tokens_completion)
    except (TypeError, ValueError):
        return 0.0
    in_per_1m, out_per_1m = _OPENROUTER_PRICING.get(voice_id, _UNKNOWN_PRICING)
    return round(
        (in_tok * in_per_1m + out_tok * out_per_1m) / 1_000_000.0,
        6,
    )


def log_voice_call(
    voice_id: str,
    *,
    pool: VoicePool,
    commit_sha: str | None,
    tokens_prompt: int | None,
    tokens_completion: int | None,
    latency_s: float | None,
    success: bool,
    cost_dir: Path | None = None,
) -> VoiceCostEntry:
    """Append a cost entry to the JSONL log under exclusive lock."""
    entry = VoiceCostEntry(
        voice_id=voice_id,
        pool=pool,
        commit_sha=commit_sha,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        estimated_usd=estimate_usd(voice_id, tokens_prompt, tokens_completion),
        latency_s=latency_s,
        success=success,
        timestamp=datetime.now(UTC),
    )
    cpath = cost_log_path(cost_dir)
    with (
        QueueLock(lock_path(cost_dir)),
        cpath.open("a", encoding="utf-8") as fh,
    ):
        fh.write(entry.model_dump_json() + "\n")
    return entry


def read_cost_log(
    *,
    since: datetime | None = None,
    cost_dir: Path | None = None,
) -> list[VoiceCostEntry]:
    """Return cost entries newer than ``since`` (newest first)."""
    cpath = cost_log_path(cost_dir)
    if not cpath.exists():
        return []
    out: list[VoiceCostEntry] = []
    with QueueLock(lock_path(cost_dir), shared=True):
        for line in cpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = VoiceCostEntry.model_validate_json(line)
            except ValueError:
                continue
            if since is not None and entry.timestamp < since:
                continue
            out.append(entry)
    out.sort(key=lambda e: e.timestamp, reverse=True)
    return out


CostWindow = Literal["yesterday", "week", "month", "all"]


def _window_to_cutoff(window: CostWindow) -> datetime | None:
    if window == "all":
        return None
    now = datetime.now(UTC)
    if window == "yesterday":
        return now - timedelta(days=1)
    if window == "week":
        return now - timedelta(days=7)
    return now - timedelta(days=30)


def summarize_costs(
    *,
    window: CostWindow = "week",
    cost_dir: Path | None = None,
) -> str:
    """Plain-text summary grouped by voice, sorted by spend desc.

    Includes call count, success rate, total tokens (in+out) and
    cumulative USD. Empty windows return ``"no audit calls in window"``.
    """
    cutoff = _window_to_cutoff(window)
    entries = read_cost_log(since=cutoff, cost_dir=cost_dir)
    if not entries:
        return "no audit calls in window"

    by_voice: dict[str, list[VoiceCostEntry]] = {}
    for e in entries:
        by_voice.setdefault(e.voice_id, []).append(e)

    rows = []
    total_usd = 0.0
    total_calls = len(entries)
    for voice_id, calls in by_voice.items():
        usd = sum(c.estimated_usd for c in calls)
        total_usd += usd
        n = len(calls)
        ok = sum(1 for c in calls if c.success)
        toks_in = sum(c.tokens_prompt or 0 for c in calls)
        toks_out = sum(c.tokens_completion or 0 for c in calls)
        rows.append((voice_id, n, ok, toks_in, toks_out, usd))
    rows.sort(key=lambda r: r[5], reverse=True)

    lines = [
        f"# POLYLENS audit cost — window={window}, "
        f"cutoff={cutoff.isoformat() if cutoff else 'all-time'}",
        "",
        f"Total calls: {total_calls} | Total USD: ${total_usd:.4f}",
        "",
        f"{'voice':<32} {'calls':>5} {'ok':>4} "
        f"{'tok_in':>9} {'tok_out':>9} {'USD':>9}",
        "-" * 72,
    ]
    for voice_id, n, ok, toks_in, toks_out, usd in rows:
        lines.append(
            f"{voice_id:<32} {n:>5} {ok:>4} "
            f"{toks_in:>9} {toks_out:>9} {usd:>9.4f}"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "CostWindow",
    "VoiceCostEntry",
    "VoicePool",
    "cost_log_path",
    "estimate_usd",
    "log_voice_call",
    "read_cost_log",
    "summarize_costs",
]
