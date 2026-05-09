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

import structlog
from pydantic import BaseModel, ConfigDict

from polybuild.audit.queue import QueueLock, audit_dir, lock_path

logger = structlog.get_logger()

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
    # POLYLENS run #4 P2 (Perplexity): the table was de-synced from
    # ``config/routing.yaml`` — the following slugs are referenced as
    # active phase-2 voices but had no pricing entry, silently booking
    # $0 (post-run #3 fix changed that to ``None`` + warning, but the
    # warning fires on every run for each slug). Adding them here closes
    # the loop. Prices below are the public OpenRouter listings as of
    # 2026-05-09; bump alongside any future routing.yaml additions.
    "deepseek/deepseek-v4-pro":     (0.65,  2.20),
    "deepseek/deepseek-v4-flash":   (0.20,  0.60),
    "x-ai/grok-4.20":               (3.00, 15.00),
    "mistral/devstral-2":           (0.50,  1.50),
    "qwen/qwen3.6-coder":           (0.40,  1.20),
}

# POLYLENS run #3 P2 (Gemini + Qwen + DeepSeek convergent): the
# ``_UNKNOWN_PRICING = (0.0, 0.0)`` fallback was removed because
# silently booking $0 for unpriced voices distorted budget review.
# ``estimate_usd`` now returns ``None`` for unknown slugs and the
# summary renders that as ``-`` so the operator sees explicit gaps in
# the pricing table instead of a misleading green column.


def cost_log_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "cost_log.jsonl"


VoicePool = Literal["western", "chinese", "unknown"]


class VoiceCostEntry(BaseModel):
    """One audit-time voice call cost record.

    POLYLENS run #3 P2 (Gemini + Qwen + DeepSeek convergent):
    ``estimated_usd`` is now ``float | None``. ``None`` flags an
    unpriced voice (slug missing from ``_OPENROUTER_PRICING``); the
    summary table renders ``-`` for those rows so the operator sees
    explicit "we don't know" rather than a misleading ``$0.00`` that
    could mask budget dérive.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    voice_id: str
    pool: VoicePool
    commit_sha: str | None = None
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    estimated_usd: float | None = 0.0
    latency_s: float | None = None
    success: bool = True
    timestamp: datetime


def estimate_usd(
    voice_id: str,
    tokens_prompt: int | None,
    tokens_completion: int | None,
) -> float | None:
    """Compute USD cost for a voice call given token counts.

    Returns ``0.0`` when token counts are missing (no work was done so
    cost is genuinely zero). Returns **``None``** when the voice slug
    is not in ``_OPENROUTER_PRICING`` (the cost is unknown — silently
    booking it as $0 distorts monthly budget review). Never raises.

    POLYLENS run #2 P2 (gemini): OpenRouter occasionally returns token
    counts as strings; the multiplication would otherwise raise
    ``TypeError`` and crash the cost-log writer. Coerce defensively to
    ``int`` and fall back to 0.0 on any conversion failure.

    POLYLENS run #3 P2 (Gemini + Qwen + DeepSeek convergent): the
    previous fallback ``(0.0, 0.0)`` masked unpriced voices. Now we
    distinguish "no tokens consumed" (``0.0``) from "no pricing
    available" (``None``).
    """
    if tokens_prompt is None or tokens_completion is None:
        return 0.0
    try:
        in_tok = int(tokens_prompt)
        out_tok = int(tokens_completion)
    except (TypeError, ValueError):
        return 0.0
    pricing = _OPENROUTER_PRICING.get(voice_id)
    if pricing is None:
        logger.warning(
            "cost_log_voice_not_priced",
            voice_id=voice_id,
            hint=(
                "Add the voice to _OPENROUTER_PRICING to record real "
                "spend. Until then this call is logged as estimated_usd=None."
            ),
        )
        return None
    in_per_1m, out_per_1m = pricing
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
    """Return cost entries newer than ``since`` (newest first).

    POLYLENS run #2 P2 (Kimi finding #8): unparseable lines are no
    longer skipped silently — a warning surfaces the first 80 chars of
    the bad line and the parse error so a future schema-version drift
    is visible to the operator instead of degrading dashboards
    silently. The line is still skipped (forward-compatibility), but
    the operator gets a signal.
    """
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
            except ValueError as e:
                logger.warning(
                    "cost_log_unparseable_line",
                    line_first_80=line[:80],
                    error=str(e)[:200],
                )
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

    POLYLENS run #3 P2: when an entry has ``estimated_usd=None`` (slug
    missing from the pricing table) the row's USD column renders as
    ``-`` and the voice flag ``has_unpriced_calls`` surfaces in a
    warning footer. This avoids the previous behaviour where unpriced
    voices were quietly booked at $0 and inflated the apparent
    "savings" of switching to CLI-paid voices.
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
    voices_with_unpriced = []
    for voice_id, calls in by_voice.items():
        priced = [c for c in calls if c.estimated_usd is not None]
        unpriced_count = len(calls) - len(priced)
        usd = sum(c.estimated_usd for c in priced if c.estimated_usd is not None)
        total_usd += usd
        n = len(calls)
        ok = sum(1 for c in calls if c.success)
        toks_in = sum(c.tokens_prompt or 0 for c in calls)
        toks_out = sum(c.tokens_completion or 0 for c in calls)
        rows.append((voice_id, n, ok, toks_in, toks_out, usd, unpriced_count))
        if unpriced_count > 0:
            voices_with_unpriced.append((voice_id, unpriced_count))
    rows.sort(key=lambda r: r[5], reverse=True)

    lines = [
        f"# POLYLENS audit cost — window={window}, "
        f"cutoff={cutoff.isoformat() if cutoff else 'all-time'}",
        "",
        f"Total calls: {total_calls} | Total priced USD: ${total_usd:.4f}",
        "",
        f"{'voice':<32} {'calls':>5} {'ok':>4} "
        f"{'tok_in':>9} {'tok_out':>9} {'USD':>9}",
        "-" * 72,
    ]
    for voice_id, n, ok, toks_in, toks_out, usd, unpriced in rows:
        usd_str = "-" if unpriced == n else f"{usd:>9.4f}"
        lines.append(
            f"{voice_id:<32} {n:>5} {ok:>4} "
            f"{toks_in:>9} {toks_out:>9} {usd_str:>9}"
        )
    if voices_with_unpriced:
        lines.append("")
        lines.append("⚠ unpriced voices (cost shown as '-' — add to "
                     "_OPENROUTER_PRICING):")
        for voice_id, unpriced in voices_with_unpriced:
            lines.append(f"  {voice_id} ({unpriced} call(s))")
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
