#!/usr/bin/env python3
"""Benchmark orchestration overhead — Consensus vs Solo (FEAT-4).

Measures the WALL-CLOCK cost the orchestrator adds on top of the LLM
calls themselves. The bench mocks every LLM-bound step (builder
generate, Phase 3 score, Phase 4 audit) with a controllable sleep so
the difference between modes is purely orchestration overhead — flock
acquisition, asyncio scheduling, model_dump_json, checkpoint writes,
etc.

Why this matters: killing criterion K3 (``--solo overhead >120s per
task``) is supposed to be measured against real LLM calls, but the
orchestration baseline needs to be near-zero to make K3 attainable.
This bench validates that.

Usage:

    uv run python scripts/bench_strategy_overhead.py
    uv run python scripts/bench_strategy_overhead.py --runs 20 --sleep-ms 50

Output: CSV to stdout + a summary table at the end.

NOTE: this does NOT exercise the real audit subsystem (``polybuild
audit drain``). For audit-side benchmarking, run::

    uv run python -m pytest tests/integration/test_m2_audit_hook.py \\
        --durations=20

against a real ``--scorer=devcode`` run.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

from polybuild.models import (
    AuditReport,
    BuilderResult,
    GateResults,
    RiskProfile,
    SelfMetrics,
    Spec,
    Status,
    VoiceConfig,
    VoiceScore,
)
from polybuild.orchestrator import ConsensusPipeline, SoloPipeline


def _make_spec(run_id: str = "bench-1") -> Spec:
    return Spec(
        run_id=run_id,
        profile_id="module_standard_known",
        task_description="bench",
        acceptance_criteria=[],
        risk_profile=RiskProfile(),
        spec_hash="sha256:bench",
    )


def _make_builder_result(voice_id: str, family: str = "anthropic") -> BuilderResult:
    return BuilderResult(
        voice_id=voice_id,
        family=family,
        code_dir=Path("/dev/null"),
        tests_dir=Path("/dev/null"),
        diff_patch=Path("/dev/null"),
        self_metrics=SelfMetrics(
            loc=10,
            complexity_cyclomatic_avg=1.0,
            test_to_code_ratio=0.5,
            todo_count=0,
            imports_count=2,
            functions_count=1,
        ),
        duration_sec=0.001,
        status=Status.OK,
    )


def _make_voice_score(voice_id: str, score: float = 90.0) -> VoiceScore:
    return VoiceScore(
        voice_id=voice_id,
        score=score,
        gates=GateResults(
            acceptance_pass_ratio=1.0,
            bandit_clean=True,
            mypy_strict_clean=True,
            ruff_clean=True,
            coverage_score=1.0,
            gitleaks_clean=True,
            gitleaks_findings_count=0,
            diff_minimality=1.0,
        ),
        disqualified=False,
    )


def _make_audit() -> AuditReport:
    return AuditReport(
        auditor_model="bench",
        auditor_family="bench",
        audit_duration_sec=0.0,
        axes_audited=["A_security"],
        findings=[],
        metrics={},
    )


def _patch_orchestrator(monkeypatch_attrs: list, sleep_ms: float) -> None:
    """Install monkey patches on ``polybuild.orchestrator`` for the bench.

    Each patch returns a deterministic stub after a configurable sleep
    (modelling LLM latency). All patches reverted via the
    ``monkeypatch_attrs`` list at teardown.
    """
    import polybuild.orchestrator as _orch
    from polybuild import adapters

    sleep_s = sleep_ms / 1000.0

    async def _slow_select_voices(spec, config_root):  # type: ignore[no-untyped-def]
        del spec, config_root
        await asyncio.sleep(sleep_s / 5)
        return [
            VoiceConfig(voice_id=v, family="anthropic", role="builder")
            for v in ("claude-opus-4.7", "gpt-5.5", "kimi-k2.6")
        ]

    async def _slow_phase_2_generate(spec, voices):  # type: ignore[no-untyped-def]
        del spec
        await asyncio.sleep(sleep_s)
        return [_make_builder_result(v.voice_id, v.family) for v in voices]

    async def _slow_phase_3_score(results):  # type: ignore[no-untyped-def]
        await asyncio.sleep(sleep_s / 2)
        return [_make_voice_score(r.voice_id) for r in results]

    async def _slow_phase_3b_grounding(results, project_root):  # type: ignore[no-untyped-def]
        del project_root
        await asyncio.sleep(sleep_s / 5)
        return {r.voice_id: [] for r in results}

    async def _slow_phase_4_audit(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        await asyncio.sleep(sleep_s / 2)
        return _make_audit()

    async def _slow_phase_5_dispatch(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        await asyncio.sleep(sleep_s / 4)
        from polybuild.models import FixReport

        return FixReport(status="completed", results=[])

    # Solo path: builder.generate is called directly.
    builder = AsyncMock()
    builder.generate = AsyncMock(
        return_value=_make_builder_result("claude-opus-4.7"),
    )

    async def _builder_generate(spec, voice):  # type: ignore[no-untyped-def]
        del spec, voice
        await asyncio.sleep(sleep_s)
        return _make_builder_result("claude-opus-4.7")

    builder.generate = _builder_generate

    def fake_get_builder(_voice_id: str) -> object:
        return builder

    monkeypatch_attrs.extend([
        ("select_voices", _orch.select_voices),
        ("phase_2_generate", _orch.phase_2_generate),
        ("phase_3_score", _orch.phase_3_score),
        ("phase_3b_grounding", _orch.phase_3b_grounding),
        ("phase_4_audit", _orch.phase_4_audit),
        ("phase_5_dispatch", _orch.phase_5_dispatch),
    ])
    _orch.select_voices = _slow_select_voices  # type: ignore[assignment]
    _orch.phase_2_generate = _slow_phase_2_generate  # type: ignore[assignment]
    _orch.phase_3_score = _slow_phase_3_score  # type: ignore[assignment]
    _orch.phase_3b_grounding = _slow_phase_3b_grounding  # type: ignore[assignment]
    _orch.phase_4_audit = _slow_phase_4_audit  # type: ignore[assignment]
    _orch.phase_5_dispatch = _slow_phase_5_dispatch  # type: ignore[assignment]
    monkeypatch_attrs.append(("get_builder", adapters.get_builder))
    adapters.get_builder = fake_get_builder  # type: ignore[assignment]


def _restore_orchestrator(monkeypatch_attrs: list) -> None:
    import polybuild.orchestrator as _orch
    from polybuild import adapters

    for name, original in monkeypatch_attrs:
        if name == "get_builder":
            adapters.get_builder = original  # type: ignore[assignment]
        else:
            setattr(_orch, name, original)


async def _bench_one_run(
    pipeline_name: str,
    sleep_ms: float,
    project_root: Path,
) -> tuple[float, str]:
    """Run one pipeline + return (wall_clock_seconds, status)."""
    if pipeline_name == "consensus":
        pipeline = ConsensusPipeline()
    elif pipeline_name == "solo":
        pipeline = SoloPipeline()  # type: ignore[assignment]
    else:
        raise ValueError(pipeline_name)

    spec = _make_spec()

    t0 = time.perf_counter()
    outcome = await pipeline.run(
        spec=spec,
        risk_profile=spec.risk_profile,
        project_root=project_root,
        project_ctx=None,
        artifacts_dir=project_root / "runs",
        run_id=spec.run_id,
        config_root=project_root / "config",
        save_checkpoint=lambda *a, **kw: None,
    )
    elapsed = time.perf_counter() - t0
    status = "aborted" if outcome.aborted else "ok"
    return elapsed, status


async def _bench_main(runs: int, sleep_ms: float) -> None:
    import tempfile

    monkeypatch_attrs: list = []
    _patch_orchestrator(monkeypatch_attrs, sleep_ms)
    try:
        rows: list[tuple[str, int, float, str]] = []
        for mode in ("consensus", "solo"):
            for i in range(runs):
                with tempfile.TemporaryDirectory() as td:
                    elapsed, status = await _bench_one_run(
                        mode, sleep_ms, Path(td)
                    )
                rows.append((mode, i, elapsed * 1000.0, status))
    finally:
        _restore_orchestrator(monkeypatch_attrs)

    # CSV stdout.
    writer = csv.writer(sys.stdout)
    writer.writerow(["mode", "run", "wall_clock_ms", "status"])
    for row in rows:
        writer.writerow(row)

    # Summary.
    print()
    print("# Summary (per-mode wall-clock ms; sleep_ms baseline = "
          f"{sleep_ms} per LLM-bound step):")
    for mode in ("consensus", "solo"):
        durations = [r[2] for r in rows if r[0] == mode]
        statuses = [r[3] for r in rows if r[0] == mode]
        success_rate = statuses.count("ok") / len(statuses) * 100.0
        print(
            f"  {mode:>10s}  median={statistics.median(durations):7.1f} ms  "
            f"mean={statistics.mean(durations):7.1f}  "
            f"min={min(durations):7.1f}  max={max(durations):7.1f}  "
            f"success={success_rate:.0f}%"
        )

    # K3 indicator: solo - consensus delta.
    solo = [r[2] for r in rows if r[0] == "solo"]
    cons = [r[2] for r in rows if r[0] == "consensus"]
    print()
    print(
        "# K3 orchestration delta (solo - consensus, median): "
        f"{statistics.median(solo) - statistics.median(cons):+.1f} ms"
    )
    print(
        "# Note: K3 threshold is 120 s per task on REAL LLM runs. "
        "This bench measures pure orchestration overhead; LLM latency "
        "dominates in production."
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    p.add_argument("--runs", type=int, default=10, help="runs per pipeline")
    p.add_argument(
        "--sleep-ms",
        type=float,
        default=20.0,
        help="simulated LLM latency per step (ms)",
    )
    args = p.parse_args()
    asyncio.run(_bench_main(args.runs, args.sleep_ms))
    return 0


if __name__ == "__main__":
    sys.exit(main())
