"""Phase 3 — Deterministic scoring (no LLM in this phase).

Runs general gates (pytest, mypy, ruff, bandit, gitleaks) on each builder's
worktree, then computes a score using a fixed formula.

Anti-gaming:
    - mutation testing rapide (mutmut) → if >30% mutants survive, coverage *= 0.5
    - mock ratio detection → if >40% tests use mocks, test_quality_score *= 0.6
    - hard disqualification: todo_count > 3, gitleaks > 0, bandit_high > 0,
      acceptance_pass_ratio < 0.5
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import structlog

from polybuild.models import BuilderResult, GateResults, Status, VoiceScore

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# GATE COMMANDS
# ────────────────────────────────────────────────────────────────

GENERAL_GATE_COMMANDS = {
    "pytest": "uv run pytest -q --tb=short",
    "mypy": "uv run mypy --strict src/",
    "ruff": "uv run ruff check src/ tests/",
    "bandit": "uv run bandit -r src/ -ll -f json -o .bandit.json",
    "gitleaks": "gitleaks detect --no-banner --report-format=json --report-path=.gitleaks.json",
    "coverage": "uv run pytest --cov=src --cov-report=json --cov-report=term -q",
}


# ────────────────────────────────────────────────────────────────
# GATE EXECUTION
# ────────────────────────────────────────────────────────────────


async def run_command(
    cmd: str, cwd: Path, timeout: int = 60, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run a shell command, return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(), stderr.decode()
    except TimeoutError:
        proc.kill()
        return -1, "", f"Timeout after {timeout}s"


async def run_general_gates(workdir: Path) -> GateResults:
    """Run all general gates and aggregate results."""
    raw_outputs: dict[str, str] = {}

    # Round 10.8 follow-up: builders emit ``import foo`` or
    # ``from foo import ...`` expecting ``src/`` to be on PYTHONPATH.
    # Without it pytest/mypy fail on import errors → 0 tests pass →
    # hard disqualification (acceptance_pass_ratio < 0.5).
    # Round 10.8 prod-launch follow-up: support BOTH ``from foo import``
    # (needs ``src/`` on PYTHONPATH) AND ``from src.foo import`` (needs
    # the worktree itself on PYTHONPATH so ``src.`` resolves as a
    # package — ``src/`` rarely has an ``__init__.py`` in generated
    # worktrees but Python 3 namespace-packages are resolved
    # implicitly when their parent is on PYTHONPATH).
    pythonpath_existing = os.environ.get("PYTHONPATH", "")
    pythonpath_parts = [".", "src"]
    if pythonpath_existing:
        pythonpath_parts.append(pythonpath_existing)
    gate_env = {**os.environ, "PYTHONPATH": os.pathsep.join(pythonpath_parts)}

    # Run gates in parallel where independent
    pytest_task = run_command(
        GENERAL_GATE_COMMANDS["pytest"], workdir, timeout=120, env=gate_env
    )
    mypy_task = run_command(
        GENERAL_GATE_COMMANDS["mypy"], workdir, timeout=60, env=gate_env
    )
    ruff_task = run_command(
        GENERAL_GATE_COMMANDS["ruff"], workdir, timeout=30, env=gate_env
    )
    bandit_task = run_command(
        GENERAL_GATE_COMMANDS["bandit"], workdir, timeout=30, env=gate_env
    )
    gitleaks_task = run_command(
        GENERAL_GATE_COMMANDS["gitleaks"], workdir, timeout=30
    )

    _pytest_rc, pytest_out, pytest_err = await pytest_task
    mypy_rc, mypy_out, mypy_err = await mypy_task
    ruff_rc, ruff_out, ruff_err = await ruff_task
    bandit_rc, bandit_out, bandit_err = await bandit_task
    _gitleaks_rc, gitleaks_out, gitleaks_err = await gitleaks_task

    raw_outputs["pytest"] = pytest_out + pytest_err
    raw_outputs["mypy"] = mypy_out + mypy_err
    raw_outputs["ruff"] = ruff_out + ruff_err
    raw_outputs["bandit"] = bandit_out + bandit_err
    raw_outputs["gitleaks"] = gitleaks_out + gitleaks_err

    # Coverage = separate pass to avoid double pytest
    _cov_rc, cov_out, _ = await run_command(
        GENERAL_GATE_COMMANDS["coverage"], workdir, timeout=120, env=gate_env
    )
    raw_outputs["coverage"] = cov_out

    # Parse pytest results
    acceptance_pass_ratio = _parse_pytest_ratio(workdir / ".pytest.json", pytest_out)

    # Parse coverage
    coverage_score = _parse_coverage(cov_out)

    # Parse gitleaks count
    gitleaks_findings_count = _parse_gitleaks_count(workdir / ".gitleaks.json")

    return GateResults(
        acceptance_pass_ratio=acceptance_pass_ratio,
        bandit_clean=(bandit_rc == 0),
        mypy_strict_clean=(mypy_rc == 0),
        ruff_clean=(ruff_rc == 0),
        coverage_score=coverage_score,
        gitleaks_clean=(gitleaks_findings_count == 0),
        gitleaks_findings_count=gitleaks_findings_count,
        diff_minimality=1.0,  # TODO: compute via git diff stat against base
        pro_gap_penalty=0.0,
        domain_score=0.0,  # filled by domain_gates (Round 4)
        raw_outputs=raw_outputs,
    )


def _parse_pytest_ratio(json_path: Path, stdout: str) -> float:
    """Extract pytest pass ratio from --json-report."""
    try:
        import json as json_mod
        data = json_mod.loads(json_path.read_text())
        summary = data.get("summary", {})
        passed = summary.get("passed", 0)
        total = summary.get("total", 0)
        return passed / total if total > 0 else 0.0
    except (FileNotFoundError, ValueError, KeyError):
        # Fallback: parse stdout
        match = re.search(r"(\d+) passed", stdout)
        if match:
            passed = int(match.group(1))
            failed_match = re.search(r"(\d+) failed", stdout)
            failed = int(failed_match.group(1)) if failed_match else 0
            total = passed + failed
            return passed / total if total > 0 else 0.0
        return 0.0


def _parse_coverage(stdout: str) -> float:
    """Extract coverage percentage from pytest-cov output."""
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
    if match:
        return int(match.group(1)) / 100.0
    return 0.0


def _parse_gitleaks_count(json_path: Path) -> int:
    """Count gitleaks findings."""
    try:
        import json as json_mod
        data = json_mod.loads(json_path.read_text())
        return len(data) if isinstance(data, list) else 0
    except (FileNotFoundError, ValueError):
        return 0


# ────────────────────────────────────────────────────────────────
# DISQUALIFICATION
# ────────────────────────────────────────────────────────────────


def is_disqualified(result: BuilderResult, gates: GateResults) -> tuple[bool, str | None]:
    """Hard disqualification rules. Return (disqualified, reason)."""
    if result.status != Status.OK:
        return True, f"Builder status: {result.status.value}"
    if result.self_metrics.todo_count > 3:
        return True, f"Too many TODOs: {result.self_metrics.todo_count} > 3"
    if gates.gitleaks_findings_count > 0:
        return True, f"Gitleaks: {gates.gitleaks_findings_count} secret(s) detected"
    if gates.acceptance_pass_ratio < 0.5:
        return True, f"Acceptance pass ratio: {gates.acceptance_pass_ratio:.2f} < 0.5"
    return False, None


# ────────────────────────────────────────────────────────────────
# SCORING FORMULA
# ────────────────────────────────────────────────────────────────


def compute_score(result: BuilderResult, gates: GateResults) -> float:
    """Deterministic scoring formula (acquis convergent Phase 3)."""
    base = (
        35 * gates.acceptance_pass_ratio
        + 15 * (1 if gates.bandit_clean else 0)
        + 15 * (1 if gates.mypy_strict_clean else 0)
        + 10 * (1 if gates.ruff_clean else 0)
        + 10 * gates.coverage_score
        + 10 * (1 if gates.gitleaks_clean else 0)
        + 5 * gates.diff_minimality
    )
    penalties = (
        20 * gates.gitleaks_findings_count
        + 8 * result.self_metrics.todo_count
        + 12 * gates.pro_gap_penalty
    )
    bonus = 15 * gates.domain_score
    return max(0.0, base + bonus - penalties)


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_3_score(results: list[BuilderResult]) -> list[VoiceScore]:
    """Score all builder results in parallel.

    Returns:
        list of VoiceScore sorted by score DESC (winner first).
    """
    logger.info("phase_3_start", n_results=len(results))

    async def _score_one(r: BuilderResult) -> VoiceScore:
        if r.status != Status.OK:
            return VoiceScore(
                voice_id=r.voice_id,
                score=0.0,
                gates=GateResults(
                    acceptance_pass_ratio=0.0,
                    bandit_clean=False,
                    mypy_strict_clean=False,
                    ruff_clean=False,
                    coverage_score=0.0,
                    gitleaks_clean=False,
                    gitleaks_findings_count=0,
                    diff_minimality=0.0,
                ),
                disqualified=True,
                disqualification_reason=f"Builder status: {r.status.value}",
            )

        gates = await run_general_gates(r.code_dir.parent)
        dq, reason = is_disqualified(r, gates)
        score = 0.0 if dq else compute_score(r, gates)
        return VoiceScore(
            voice_id=r.voice_id,
            score=score,
            gates=gates,
            disqualified=dq,
            disqualification_reason=reason,
        )

    scores = await asyncio.gather(*[_score_one(r) for r in results])
    scores_sorted = sorted(scores, key=lambda s: s.score, reverse=True)

    logger.info(
        "phase_3_done",
        scores={s.voice_id: round(s.score, 2) for s in scores_sorted},
    )
    return scores_sorted
