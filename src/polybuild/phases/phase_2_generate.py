"""Phase 2 — Parallel generation by 3 orthogonal voices.

asyncio.gather with return_exceptions=True ensures that one voice failing
doesn't crash the others. A voice that times out or fails is dropped, but
the run continues with the remaining 2 (acquis convergent rounds 1-4).

Round 8 fix [P2-limiter] (5/6 audits convergence — Grok, Kimi, DeepSeek,
ChatGPT, implicite Gemini Q2):
    The TODO from round 4 was never closed. Phase 2 was launching all
    voices via raw asyncio.gather, bypassing CLILimiter entirely. Result:
    on the first multi-voice run with shared providers (e.g. claude-code +
    claude-haiku via API), 429 throttles cascade → multiple voices FAILED
    → n_ok < 2 → run abort.

    Now each generate() call goes through limiter.run(provider, factory,
    Priority.P0) which serialises per-provider work using semaphores
    configured in config/concurrency_limits.yaml. Semaphores are per
    family (anthropic, openai, etc.), so different providers still run in
    parallel — only same-family voices serialise.
"""

from __future__ import annotations

import asyncio
import pathlib

import structlog

from polybuild.adapters import get_builder
from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.concurrency.limiter import CLILimiter, Priority
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


async def phase_2_generate(
    spec: Spec,
    voices: list[VoiceConfig],
    limiter: CLILimiter | None = None,
) -> list[BuilderResult]:
    """Run all builder voices in parallel under provider-aware concurrency limits.

    Args:
        spec: canonical spec from Phase 0.
        voices: list of voice configs from Phase 1.
        limiter: optional pre-built CLILimiter (test injection).
                 Defaults to CLILimiter.from_yaml(profile=spec.profile_id).

    Returns:
        list of BuilderResult (one per voice, including TIMEOUT/FAILED ones).
    """
    logger.info(
        "phase_2_start",
        run_id=spec.run_id,
        voices=[v.voice_id for v in voices],
    )

    if limiter is None:
        limiter = CLILimiter.from_yaml(profile=spec.profile_id)

    builders = [(v, get_builder(v.voice_id)) for v in voices]

    # Each task wraps the generate() call in limiter.run() so that voices
    # sharing the same provider family serialise via a semaphore. Voices on
    # different providers still run truly in parallel.
    #
    # We use Priority.P0 because Phase 2 is the critical path: a throttle
    # here means the run cannot proceed. P0 has a 180s wait timeout on the
    # semaphore (vs 30s for P1) — appropriate for the long-running CLI calls.
    async def _bounded_generate(
        cfg: VoiceConfig, builder: BuilderProtocol
    ) -> BuilderResult:
        # provider_or_voice accepts both family ("claude") and voice_id
        # ("claude-opus-4.7"); _resolve_provider in CLILimiter handles both.
        provider = cfg.family or cfg.voice_id

        async def _call() -> BuilderResult:
            return await builder.generate(spec, cfg)

        # Round 10.1 fix [Kimi P1 #8]: forward the per-voice timeout to the
        # limiter as exec_timeout_s. Without this the limiter's default
        # 1800s ceiling masked the 720s/360s budgets configured in
        # ``config/timeouts.yaml`` and a stuck CLI could block the run for
        # 30 min instead of the expected 12.
        return await limiter.run(
            provider_or_voice=provider,
            coro_factory=_call,
            priority=Priority.P0,
            exec_timeout_s=float(cfg.timeout_sec),
        )

    tasks = [_bounded_generate(cfg, builder) for cfg, builder in builders]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    normalized: list[BuilderResult] = []
    null_path = pathlib.Path("/dev/null")
    for (cfg, _), r in zip(builders, results, strict=True):
        if isinstance(r, BuilderResult):
            normalized.append(r)
        elif isinstance(r, BaseException):
            logger.error(
                "phase_2_voice_exception",
                voice_id=cfg.voice_id,
                error=str(r),
                error_type=type(r).__name__,
            )
            normalized.append(
                BuilderResult(
                    voice_id=cfg.voice_id,
                    family=cfg.family,
                    code_dir=null_path,
                    tests_dir=null_path,
                    diff_patch=null_path,
                    self_metrics=SelfMetrics(
                        loc=0,
                        complexity_cyclomatic_avg=0.0,
                        test_to_code_ratio=0.0,
                        todo_count=0,
                        imports_count=0,
                        functions_count=0,
                    ),
                    duration_sec=0.0,
                    status=Status.FAILED,
                    error=f"{type(r).__name__}: {r}",
                )
            )

    n_ok = sum(1 for r in normalized if r.status == Status.OK)
    if n_ok < 2:
        logger.warning(
            "phase_2_insufficient_voices",
            n_ok=n_ok,
            n_total=len(normalized),
        )

    # Surface per-provider stats from limiter for post-run analysis
    try:
        stats = limiter.stats_summary()
        logger.info("phase_2_concurrency_stats", run_id=spec.run_id, **stats)
    except Exception as e:
        logger.debug("phase_2_concurrency_stats_failed", error=str(e))

    logger.info(
        "phase_2_done",
        run_id=spec.run_id,
        n_ok=n_ok,
        n_failed=len(normalized) - n_ok,
    )
    return normalized
