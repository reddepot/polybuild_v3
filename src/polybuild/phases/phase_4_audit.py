"""Phase 4 — Orthogonal POLYLENS audit.

Rule (acquis convergent):
    - Auditor model family ≠ winner family
    - For medical sensitive: pool filtered to exclude US/CN
    - Audit axes selected per profile (A_security, B_quality, ..., G_adversarial)

Quality control (anti `Auditor Laziness`):
    - If finding_count == 0 AND audit_duration < 60s → audit rejected, retry
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import httpx
import structlog

from polybuild.models import (
    AuditReport,
    BuilderResult,
    Finding,
    FindingEvidence,
    RiskProfile,
    Severity,
)
from polybuild.phases.phase_1_select import select_auditor

logger = structlog.get_logger()

# Round 10.2 fix [Gemini RX-102-02 + Qwen RX-002] caps for the audit prompt.
_MAX_FILE_BYTES = 256 * 1024
_MAX_AUDIT_BYTES = 1024 * 1024


# ────────────────────────────────────────────────────────────────
# AUDIT AXES (acquis Round 3)
# ────────────────────────────────────────────────────────────────

AUDIT_AXIS_DESCRIPTIONS = {
    "A_security": "Vulnérabilités, injections, fuites de données",
    "B_quality": "Style, lisibilité, idioms, naming",
    "C_tests": "Couverture, edge cases, mocks abusifs, integration vs mock",
    "D_perf": "Goulots d'étranglement, complexité algorithmique",
    "E_architecture": "Cohérence, séparation des préoccupations, couplage",
    "F_documentation": "Docstrings, commentaires, README, ADR",
    "G_adversarial": "Property tests, fuzzing potential, edge cases méchants",
}


# ────────────────────────────────────────────────────────────────
# AUDIT INVOCATION
# ────────────────────────────────────────────────────────────────


async def _invoke_auditor(
    auditor_voice: str,
    winner_result: BuilderResult,
    axes: list[str],
    timeout_sec: int = 300,
) -> AuditReport:
    """Send the winner's code to an auditor and parse the structured findings.

    Round 10.2 fix [Gemini RX-102-02 + Qwen RX-002] (2/3 conv, P1): the
    audit prompt previously concatenated *every* generated .py without an
    upper bound. A single large mock-data file (or an attacker that emits
    a 5 MB payload) was enough to either explode the auditor's context
    window or drive cost up. We now apply two limits:

      * per-file:   _MAX_FILE_BYTES (256 KiB) — files larger than this are
                    truncated with a sentinel.
      * cumulative: _MAX_AUDIT_BYTES (1 MiB) — once reached, remaining
                    files are listed by name only.

    These caps are deliberately generous for legitimate code (median Python
    module < 4 KiB) and tight enough to bound worst-case spend.
    """

    def _read_capped(
        py_file: Path, current_total: int
    ) -> tuple[str, int]:
        try:
            content = py_file.read_text()
        except (UnicodeDecodeError, OSError):
            return "", current_total
        if len(content.encode("utf-8")) > _MAX_FILE_BYTES:
            content = (
                content[: _MAX_FILE_BYTES // 2]
                + "\n\n# … [TRUNCATED by polybuild auditor cap] …\n"
            )
        if current_total + len(content) > _MAX_AUDIT_BYTES:
            content = (
                "# … [omitted: audit byte budget exhausted, file listed only] …\n"
            )
        return content, current_total + len(content)

    code_files: dict[str, str] = {}
    total_bytes = 0
    for py_file in winner_result.code_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        body, total_bytes = _read_capped(py_file, total_bytes)
        code_files[str(py_file.relative_to(winner_result.code_dir))] = body

    test_files: dict[str, str] = {}
    for py_file in winner_result.tests_dir.rglob("test_*.py"):
        if "__pycache__" in py_file.parts:
            continue
        body, total_bytes = _read_capped(py_file, total_bytes)
        test_files[str(py_file.relative_to(winner_result.tests_dir))] = body

    axes_section = "\n".join(
        f"  - {ax}: {AUDIT_AXIS_DESCRIPTIONS[ax]}" for ax in axes
    )

    prompt = f"""You are the AUDITOR phase of POLYBUILD v3.

Audit the code below across these axes:
{axes_section}

Output STRICT JSON ONLY:
{{
  "findings": [
    {{
      "id": "f001",
      "severity": "P0|P1|P2|P3",
      "axis": "A_security",
      "description": "concrete issue",
      "evidence": {{
        "file": "path/to/file.py",
        "line": 42,
        "snippet": "the offending code",
        "reproducer": "pytest tests/test_x.py::test_y"
      }}
    }}
  ],
  "metrics": {{
    "actionable_rate": 0.85,
    "vagueness_index": 0.12
  }}
}}

Severity guide:
  - P0: security vuln, crash, hallucinated import (blocking)
  - P1: quality, archi, perf issue (should fix)
  - P2: style, naming (auto-fixable)
  - P3: cosmetic

DO NOT propose fixes. DO NOT rewrite code. ONLY identify issues with reproducible evidence.

<CODE>
{json.dumps(code_files, indent=2, ensure_ascii=False)}
</CODE>

<TESTS>
{json.dumps(test_files, indent=2, ensure_ascii=False)}
</TESTS>
"""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("audit_no_api_key", auditor=auditor_voice)
        return AuditReport(
            auditor_model=auditor_voice,
            auditor_family="unknown",
            audit_duration_sec=0.0,
            axes_audited=axes,
        )

    start = time.monotonic()

    # Round 9 fix [Kimi-audit-fallback] (Kimi P0):
    #   Previous fallback hardcoded `claude code --model {voice}` for every
    #   non-OpenRouter auditor. If the routing config promotes GPT-5.5,
    #   Gemini, or Kimi as auditor, the subprocess crashes immediately:
    #   `claude code --model gpt-5.5` is not a valid CLI invocation.
    #   Now we route via the family's adapter using run_raw_prompt(), which
    #   adapters all implement (round 6 [O] + round 7 [O3]). OpenRouter
    #   models still go through direct HTTP because the auditor uses
    #   structured JSON output mode that the adapters' generate() doesn't
    #   currently expose; that's a follow-up cleanup.
    if auditor_voice.startswith(("deepseek/", "x-ai/")):
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": auditor_voice,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
    else:
        # Family-aware adapter dispatch (round 9 fix).
        from polybuild.adapters import get_builder

        builder = get_builder(auditor_voice)
        # run_raw_prompt: adapters with [O3] honour cfg.context["raw_prompt"]
        # and bypass the generation wrapper, returning the raw model output.
        # Round 10 fix [S108]: ephemeral isolated tempdir instead of /tmp
        # (race + symlink attack vector flagged by ruff S108 / bandit B108).
        with tempfile.TemporaryDirectory(prefix="polybuild_audit_") as audit_tmp:
            content = await builder.run_raw_prompt(
                prompt=prompt,
                workdir=Path(audit_tmp),
                timeout_s=int(timeout_sec),
                role="auditor",
            )

    duration = time.monotonic() - start

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("audit_invalid_json", auditor=auditor_voice)
        return AuditReport(
            auditor_model=auditor_voice,
            auditor_family=auditor_voice.split("/", maxsplit=1)[0] if "/" in auditor_voice else "unknown",
            audit_duration_sec=duration,
            axes_audited=axes,
        )

    findings = []
    for f_dict in data.get("findings", []):
        try:
            evidence_dict = f_dict.get("evidence")
            evidence = (
                FindingEvidence(
                    file=Path(evidence_dict["file"]),
                    line=evidence_dict.get("line"),
                    snippet=evidence_dict.get("snippet"),
                    reproducer=evidence_dict.get("reproducer"),
                )
                if evidence_dict
                else None
            )
            findings.append(
                Finding(
                    id=f_dict["id"],
                    severity=Severity(f_dict["severity"]),
                    axis=f_dict["axis"],
                    description=f_dict["description"],
                    evidence=evidence,
                    auditor_model=auditor_voice,
                    auditor_family=auditor_voice.split("/", maxsplit=1)[0] if "/" in auditor_voice else "unknown",
                )
            )
        except (KeyError, ValueError) as e:
            logger.warning("audit_finding_parse_error", error=str(e), finding=f_dict)
            continue

    return AuditReport(
        auditor_model=auditor_voice,
        auditor_family=auditor_voice.split("/", maxsplit=1)[0] if "/" in auditor_voice else "unknown",
        audit_duration_sec=duration,
        axes_audited=axes,
        findings=findings,
        metrics=data.get("metrics", {}),
    )


# ────────────────────────────────────────────────────────────────
# QUALITY CHECK (anti Auditor Laziness)
# ────────────────────────────────────────────────────────────────


def is_lazy_audit(report: AuditReport) -> bool:
    """Detect lazy audits: 0 findings + < 60s duration."""
    return len(report.findings) == 0 and report.audit_duration_sec < 60


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_4_audit(
    winner: BuilderResult,
    profile_id: str,
    risk_profile: RiskProfile,
    config_root: Path = Path("config"),
    max_retries: int = 1,
) -> AuditReport:
    """Run an orthogonal audit on the winner code."""
    logger.info("phase_4_start", winner=winner.voice_id, profile=profile_id)

    import yaml
    routing = yaml.safe_load((config_root / "routing.yaml").read_text())
    profile = routing["profiles"][profile_id]
    axes = profile.get("audit_axes", ["B_quality", "C_tests", "E_architecture"])

    auditor = select_auditor(winner.voice_id, risk_profile, config_root)

    for attempt in range(max_retries + 1):
        report = await _invoke_auditor(auditor, winner, axes)
        if not is_lazy_audit(report):
            break
        logger.warning(
            "phase_4_lazy_audit_retry",
            auditor=auditor,
            attempt=attempt,
        )
        # Pick another auditor from the pool
        all_auditors = (
            routing["auditor_pools_by_winner_family"]
            .get(winner.family, [])
        )
        alternatives = [a for a in all_auditors if a != auditor]
        if not alternatives:
            break
        auditor = alternatives[0]

    logger.info(
        "phase_4_done",
        winner=winner.voice_id,
        auditor=report.auditor_model,
        n_findings=len(report.findings),
        by_severity={
            sev.value: sum(1 for f in report.findings if f.severity == sev)
            for sev in Severity
        },
    )
    return report
