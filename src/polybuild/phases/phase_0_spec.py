"""Phase 0 — Spec generation + Spec Attack.

Decisions (acquis convergent):
    - Phase 0a: Claude Opus 4.7 ALONE generates the canonical spec
    - Phase 0b: Orthogonal challenger does "Spec Attack" (critique only, no code)
    - Phase 0c: If Spec Attack has critical findings, Opus revises the spec

Spec Attack challenger by profile:
    - algo/math/HELIA      → deepseek/deepseek-v4-pro
    - adhérence/parsing    → x-ai/grok-4.20
    - long-contexte/repo   → gemini-3.1-pro
    - médical              → no external Spec Attack, user attestation only
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import structlog

from polybuild.models import (
    AcceptanceCriterion,
    PrivacyLevel,
    RiskProfile,
    Spec,
    SpecAttack,
)

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# CHALLENGER SELECTION (Phase 0b)
# ────────────────────────────────────────────────────────────────


def pick_spec_attacker(profile_id: str, risk_profile: RiskProfile) -> str | None:
    """Return the slug of the Spec Attack challenger, or None if skipped."""
    # Medical sensitive: no external Spec Attack
    if risk_profile.sensitivity == PrivacyLevel.HIGH:
        return None

    # By profile id
    if profile_id == "helia_algo":
        return "deepseek/deepseek-v4-pro"
    if profile_id == "mcp_schema_change":
        return "x-ai/grok-4.20"
    if profile_id == "module_inedit_critique":
        return "deepseek/deepseek-v4-pro"
    if profile_id in {"oai_pmh_scraping", "parsing_pdf_medical"}:
        return "x-ai/grok-4.20"
    if profile_id == "rag_ingestion_eval":
        return "gemini-3.1-pro"

    # Default: deepseek for algo rigor
    return "deepseek/deepseek-v4-pro"


# ────────────────────────────────────────────────────────────────
# PHASE 0a — Opus generates spec
# ────────────────────────────────────────────────────────────────


async def _opus_generate_spec(
    brief: str,
    profile_id: str,
    risk_profile: RiskProfile,
    project_ctx: str,
    timeout_sec: int = 480,
) -> dict[str, Any]:
    """Call Opus 4.7 via Claude Code CLI to draft the spec.

    Returns a parsed dict matching the Spec schema (without spec_hash yet).

    Note: we invoke the ``claude`` CLI directly here rather than going through
    ``get_builder()``, because Phase 0 produces a JSON spec on stdout — there
    is no worktree, no source files to write. The dedicated subprocess path
    below is intentional. Earlier drafts created a builder/cfg pair that was
    never used; that dead code has been removed.
    """
    prompt = f"""You are the SPEC ARCHITECT phase of POLYBUILD v3.

Generate a canonical specification for the following task.
DO NOT generate code. Output JSON ONLY matching this schema:

{{
  "task_description": "<reformulation claire et complète>",
  "constraints": ["<contrainte 1>", "..."],
  "acceptance_criteria": [
    {{"id": "ac001", "description": "...", "test_command": "pytest tests/test_x.py::test_y", "blocking": true}},
    ...
  ],
  "interfaces": {{"<symbol>": "<pydantic schema or function signature>"}},
  "rationale": "<courte explication des choix d'architecture>"
}}

<PROJECT_CONTEXT>
{project_ctx}
</PROJECT_CONTEXT>

<PROFILE>
profile_id: {profile_id}
sensitivity: {risk_profile.sensitivity.value}
</PROFILE>

<BRIEF>
{brief}
</BRIEF>

Hard rules:
  - Acceptance criteria must be EXECUTABLE (pytest commands).
  - Constraints must reference AGENTS.md conventions.
  - Interfaces must use Pydantic v2 schemas.
"""

    # We use the raw subprocess invocation directly here because the spec is
    # text, not a code module on disk.
    # Round 10.1 fix [Kimi P0 #1]: the orchestrator's signal handlers cancel
    # asyncio tasks on SIGINT/SIGTERM, but without ``start_new_session=True``
    # the spawned ``claude code`` process stays in the parent's process group.
    # On macOS/Linux the orchestrator can then call ``os.killpg`` on a
    # dedicated session id to take down the child *and* its grand-children
    # (e.g. the auth helper claude-code spawns). On Windows the flag is a
    # no-op so we gate it on platform.
    # Round 10.8 prod-launch fix: claude CLI v2 (>= 2.x) replaced
    # ``claude code --prompt X --output-format Y`` with positional prompt
    # behind ``-p / --print`` (non-interactive mode); ``--output-format``
    # only works under print mode. The legacy invocation now exits with
    # ``error: unknown option '--prompt'``. Updated to the v2 surface.
    # Round 10.8 prod-launch fix: claude CLI v2 surface — ``-p PROMPT
    # --output-format text`` returns the raw model response (the JSON
    # spec the LLM emits). ``json`` output-format wraps in an envelope
    # with ``{result, usage, ...}``, which would break ``json.loads(raw)``
    # here.
    # Round 10.8 prod-launch fix: explicit ``stdin=DEVNULL`` so claude
    # CLI v2 doesn't block on inherited stdin (e.g. when polybuild was
    # launched through ``tee`` or another pipe — claude reads stdin
    # under ``-p`` until EOF and would hang indefinitely).
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--model", "claude-opus-4-7",
        "--output-format", "text",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=(sys.platform != "win32"),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_sec,
        )
    except TimeoutError as err:
        proc.kill()
        raise RuntimeError(
            f"Opus spec generation timeout after {timeout_sec}s"
        ) from err

    if proc.returncode != 0:
        raise RuntimeError(f"Opus spec generation failed: {stderr.decode()[:500]}")

    raw = stdout.decode()
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except json.JSONDecodeError as err:
        # Try to extract JSON block from response
        import re

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))  # type: ignore[no-any-return]
        raise RuntimeError(f"Opus output not valid JSON: {raw[:500]}") from err


# ────────────────────────────────────────────────────────────────
# PHASE 0b — Spec Attack
# ────────────────────────────────────────────────────────────────


async def _spec_attack(
    spec_dict: dict[str, Any],
    challenger: str,
    timeout_sec: int = 180,
) -> SpecAttack:
    """Have a challenger model critique the spec without coding."""
    prompt = f"""You are the SPEC ATTACKER phase of POLYBUILD v3.

Critique the spec below. DO NOT propose code. DO NOT rewrite the spec.
Find weaknesses ONLY. Output STRICT JSON matching:

{{
  "missing_invariants": ["..."],
  "ambiguous_terms": ["..."],
  "untestable_acceptance": ["ac001 because ..."],
  "unsafe_assumptions": ["..."],
  "rgpd_risks": ["..."],
  "edge_cases_missed": ["..."]
}}

If a list is empty, return [].

<SPEC>
{json.dumps(spec_dict, indent=2, ensure_ascii=False)}
</SPEC>
"""

    # Direct OpenRouter call (not via BuilderProtocol since we don't want a worktree)
    import os

    import httpx

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("spec_attack_no_api_key", challenger=challenger)
        return SpecAttack(challenger_model=challenger)

    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": challenger,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        # Round 10.7 fix [POLYLENS v3 Qwen B-04 P1]: same OpenRouter
        # malformed-response defence as the rest of the codebase.
        # Direct subscript chain crashes on rate-limit/refusal payloads.
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning(
                "spec_attack_malformed_or_response",
                challenger=challenger,
                error=str(exc),
            )
            return SpecAttack(challenger_model=challenger)
        if not isinstance(content, str):
            return SpecAttack(challenger_model=challenger)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("spec_attack_invalid_json", challenger=challenger)
        return SpecAttack(challenger_model=challenger)

    return SpecAttack(
        challenger_model=challenger,
        missing_invariants=data.get("missing_invariants", []),
        ambiguous_terms=data.get("ambiguous_terms", []),
        untestable_acceptance=data.get("untestable_acceptance", []),
        unsafe_assumptions=data.get("unsafe_assumptions", []),
        rgpd_risks=data.get("rgpd_risks", []),
        edge_cases_missed=data.get("edge_cases_missed", []),
    )


# ────────────────────────────────────────────────────────────────
# PHASE 0c — Revision
# ────────────────────────────────────────────────────────────────


async def _opus_revise_spec(
    spec_dict: dict[str, Any],
    attack: SpecAttack,
    timeout_sec: int = 300,
) -> dict[str, Any]:
    """If Spec Attack found critical issues, Opus revises the spec."""
    prompt = f"""You are the SPEC REVISER phase of POLYBUILD v3.

The Spec Attacker found weaknesses. Revise the spec to address ALL critical findings.
Output the COMPLETE revised spec as JSON, same schema as before.

<ORIGINAL_SPEC>
{json.dumps(spec_dict, indent=2, ensure_ascii=False)}
</ORIGINAL_SPEC>

<ATTACK_FINDINGS>
{json.dumps(attack.model_dump(), indent=2, ensure_ascii=False)}
</ATTACK_FINDINGS>
"""

    # Round 10.8 prod-launch fix: claude CLI v2 (>= 2.x) replaced
    # ``claude code --prompt X --output-format Y`` with positional prompt
    # behind ``-p / --print`` (non-interactive mode); ``--output-format``
    # only works under print mode. The legacy invocation now exits with
    # ``error: unknown option '--prompt'``. Updated to the v2 surface.
    # Round 10.8 prod-launch fix: claude CLI v2 surface — ``-p PROMPT
    # --output-format text`` returns the raw model response (the JSON
    # spec the LLM emits). ``json`` output-format wraps in an envelope
    # with ``{result, usage, ...}``, which would break ``json.loads(raw)``
    # here.
    # Round 10.8 prod-launch fix: explicit ``stdin=DEVNULL`` so claude
    # CLI v2 doesn't block on inherited stdin (e.g. when polybuild was
    # launched through ``tee`` or another pipe — claude reads stdin
    # under ``-p`` until EOF and would hang indefinitely).
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--model", "claude-opus-4-7",
        "--output-format", "text",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=(sys.platform != "win32"),
    )
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_sec,
        )
    except TimeoutError:
        proc.kill()
        logger.warning("spec_revise_timeout")
        return spec_dict  # fallback to original

    raw = stdout.decode()
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        # Round 10.7 fix [POLYLENS v3 Qwen B-05 P1]: greedy ``\{.*\}`` over
        # ``re.DOTALL`` matches across multiple JSON blocks and trailing
        # text. Switch to non-greedy (``\{.*?\}``) and prefer the LAST
        # balanced object — Opus revisions tend to put their final answer
        # last after reasoning prose.
        import re

        # Find ALL non-greedy candidates, return the largest valid one.
        candidates = re.findall(r"\{[\s\S]*?\}", raw)
        for candidate in reversed(candidates):
            try:
                return json.loads(candidate)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                continue
        return spec_dict


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_0_spec(
    run_id: str,
    brief: str,
    profile_id: str,
    risk_profile: RiskProfile,
    project_ctx: str = "",
    artifacts_dir: Path = Path(".polybuild/runs"),
) -> Spec:
    """Run Phases 0a, 0b, 0c and produce a final hashed Spec."""
    logger.info("phase_0_start", run_id=run_id, profile=profile_id)
    start = time.monotonic()

    # 0a — draft
    draft_dict = await _opus_generate_spec(brief, profile_id, risk_profile, project_ctx)

    # 0b — Spec Attack (skipped if medical HIGH)
    challenger = pick_spec_attacker(profile_id, risk_profile)
    if challenger is None:
        logger.info("phase_0b_skipped", reason="medical_high_or_none")
        attack = SpecAttack(challenger_model="<skipped>")
    else:
        try:
            attack = await _spec_attack(draft_dict, challenger)
        except Exception as e:
            logger.warning("phase_0b_failed", error=str(e))
            attack = SpecAttack(challenger_model=challenger)

    # 0c — Revision if critical
    if attack.has_critical_findings():
        logger.info("phase_0c_revise", n_critical=len(attack.missing_invariants))
        final_dict = await _opus_revise_spec(draft_dict, attack)
    else:
        final_dict = draft_dict

    # Persist artifacts
    run_dir = artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "spec_draft.json").write_text(
        json.dumps(draft_dict, indent=2, ensure_ascii=False)
    )
    (run_dir / "spec_attack.json").write_text(
        json.dumps(attack.model_dump(), indent=2, ensure_ascii=False)
    )
    (run_dir / "spec_final.json").write_text(
        json.dumps(final_dict, indent=2, ensure_ascii=False)
    )

    # Hash + Pydantic conversion
    canonical = json.dumps(final_dict, sort_keys=True, ensure_ascii=False)
    spec_hash = hashlib.sha256(canonical.encode()).hexdigest()

    # Round 10.2 fix [Kimi adversarial — poisoned spec.task_description]:
    # Phase 0 receives the user's raw brief via Opus and may interpolate
    # parts of it into ``task_description``. Without sanitization, an
    # injection in the brief survives all the way to Phase 2 builders'
    # ``_build_prompt`` (each adapter concatenates it into the LLM input).
    # We sanitize once here so every downstream consumer benefits.
    from polybuild.security.prompt_sanitizer import sanitize_prompt_context

    raw_task = final_dict.get("task_description", brief)
    cleaned_task = sanitize_prompt_context(str(raw_task))

    spec = Spec(
        run_id=run_id,
        profile_id=profile_id,
        task_description=cleaned_task,
        constraints=final_dict.get("constraints", []),
        acceptance_criteria=[
            AcceptanceCriterion(**ac) for ac in final_dict.get("acceptance_criteria", [])
        ],
        interfaces=final_dict.get("interfaces", {}),
        risk_profile=risk_profile,
        spec_hash=spec_hash,
    )

    duration = time.monotonic() - start
    logger.info(
        "phase_0_done",
        run_id=run_id,
        spec_hash=spec_hash[:12],
        n_acceptance=len(spec.acceptance_criteria),
        duration_sec=round(duration, 1),
    )
    return spec
