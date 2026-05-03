"""Phase 1 — Voice selection (matrix-first + optional 50 LOC probe).

Decision (round 3 convergent): hybrid mode.
    - Static matrix by default (~ms latency, ~80% of runs)
    - 50 LOC probe ONLY for profiles flagged `requires_probe: true`

Diversity dimensions (model_dimensions.yaml):
    - provider, architecture, alignment, corpus_proxy, role_bias

The selected triade must respect:
    - global rule: no two voices same provider
    - profile rule: min_diversity threshold
    - profile constraints: excludes_openrouter, excludes_us_cn_models
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from polybuild.models import RiskProfile, Spec, VoiceConfig

# ────────────────────────────────────────────────────────────────
# CONFIG LOADING
# ────────────────────────────────────────────────────────────────


def load_config(config_root: Path = Path("config")) -> dict[str, Any]:
    """Load all routing-related YAML configs."""
    return {
        "models": yaml.safe_load((config_root / "models.yaml").read_text()),
        "routing": yaml.safe_load((config_root / "routing.yaml").read_text()),
        "dimensions": yaml.safe_load((config_root / "model_dimensions.yaml").read_text()),
        "timeouts": yaml.safe_load((config_root / "timeouts.yaml").read_text()),
    }


# ────────────────────────────────────────────────────────────────
# DIVERSITY SCORING
# ────────────────────────────────────────────────────────────────

DIMENSIONS = ["provider", "architecture", "alignment", "corpus_proxy", "role_bias"]


def diversity_score(voices: list[str], dimensions: dict[str, dict[str, str]]) -> float:
    """Average pairwise dissimilarity across all 5 dimensions.

    Score range: 0 (identical) to 5 (fully orthogonal).
    """
    if len(voices) < 2:
        return 0.0
    total = 0
    n_pairs = 0
    for a, b in combinations(voices, 2):
        if a not in dimensions or b not in dimensions:
            continue
        for dim in DIMENSIONS:
            if dimensions[a].get(dim) != dimensions[b].get(dim):
                total += 1
        n_pairs += 1
    return total / n_pairs if n_pairs else 0.0


# ────────────────────────────────────────────────────────────────
# CONSTRAINT FILTERS
# ────────────────────────────────────────────────────────────────


def is_us_or_cn_model(voice_id: str) -> bool:
    """Return True if model is hosted by US or CN provider.

    Provider mapping (kept here as a comment for traceability):
        US: anthropic, openai, google, xai
        CN: moonshot, deepseek, alibaba
        Local (excluded): ollama, qwen-on-NAS, mistral_eu (EU-based)
    """
    if voice_id.startswith(("claude-", "gpt-", "gemini-")):
        return True
    if voice_id.startswith(("kimi-", "deepseek/", "qwen")):
        # qwen runs locally on user's NAS → not hosted by Alibaba in this context
        return not voice_id.startswith("qwen")
    return voice_id.startswith("x-ai/")


def is_openrouter_routed(voice_id: str) -> bool:
    """Check if a voice goes through OpenRouter (excluded for medical sensitive)."""
    return voice_id.startswith(("deepseek/", "x-ai/"))


def filter_candidates(
    candidates: list[str],
    risk_profile: RiskProfile,
) -> list[str]:
    """Apply hard constraints from risk_profile."""
    filtered = candidates
    if risk_profile.excludes_openrouter:
        filtered = [v for v in filtered if not is_openrouter_routed(v)]
    if risk_profile.excludes_us_cn_models:
        filtered = [
            v for v in filtered
            if not is_us_or_cn_model(v) or v.startswith("qwen")  # local Qwen OK
        ]
    return filtered


# ────────────────────────────────────────────────────────────────
# MATRIX SELECTION (default path)
# ────────────────────────────────────────────────────────────────


def matrix_select(
    candidates: list[str],
    min_diversity: float,
    dimensions: dict[str, dict[str, str]],
    fixed_voices: list[str] | None = None,
) -> list[str] | None:
    """Find a triad respecting all constraints, or None if impossible.

    Args:
        candidates: pool of allowed voices
        min_diversity: threshold (e.g. 2.3 for inedit_critique)
        dimensions: matrix from model_dimensions.yaml
        fixed_voices: voices that MUST be in the triad (e.g. profile-mandated)
    """
    fixed = fixed_voices or []
    pool = [v for v in candidates if v not in fixed]

    # Need 3 voices total
    needed = 3 - len(fixed)
    if needed < 0:
        return None
    if needed == 0:
        return fixed if diversity_score(fixed, dimensions) >= min_diversity else None

    valid_triads = []
    for combo in combinations(pool, needed):
        triad = list(fixed) + list(combo)
        # Hard rule: no two voices same provider
        # Round 9 fix [Kimi-medical-providers] (Kimi P0): exception for
        # local-only profiles (medical_high) where RGPD constraints force
        # all voices to ollama-hosted models. The model_dimensions.yaml
        # explicitly documents medical_high_local with 2 qwen voices —
        # diversity sacrifices accepted for GDPR compliance. We detect
        # this case by checking if all voices' role_bias starts with
        # "local_" (only true for ollama-served models).
        providers = [dimensions.get(v, {}).get("provider") for v in triad]
        if len(set(providers)) < len(providers):
            role_biases = [
                str(dimensions.get(v, {}).get("role_bias", "")) for v in triad
            ]
            # EU-compliant triad: all voices must be either local (ollama)
            # or hosted in EU (api.mistral.ai direct, not OpenRouter).
            eu_compliant = all(
                rb.startswith("local_") or rb.endswith("_eu")
                for rb in role_biases
            )
            if not eu_compliant:
                continue
            # EU-compliant triad: provider duplication permitted. Still
            # require at least 2 distinct providers (e.g. 2x ollama + 1x mistral_eu).
            if len(set(providers)) < 2:
                continue
        score = diversity_score(triad, dimensions)
        if score >= min_diversity:
            valid_triads.append((score, triad))

    if not valid_triads:
        return None

    # Highest diversity score first
    valid_triads.sort(reverse=True)
    return valid_triads[0][1]


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def select_voices(
    spec: Spec,
    config_root: Path = Path("config"),
) -> list[VoiceConfig]:
    """Select 3 voices for Phase 2 generation.

    Returns:
        list of VoiceConfig (length 2-3 depending on profile, e.g. refactor=2)
    """
    cfg = load_config(config_root)
    profile = cfg["routing"]["profiles"].get(spec.profile_id)
    if profile is None:
        raise ValueError(f"Unknown profile: {spec.profile_id}")

    min_div = profile.get("min_diversity", 2.0)
    pool = profile.get("pool_for_diversity") or profile["voices_phase2"]
    pool = filter_candidates(pool, spec.risk_profile)

    # Profile-mandated voices (not flexible)
    fixed = profile.get("fixed_voices", [])

    if profile.get("requires_probe"):
        # TODO: implement 50 LOC probe (Phase B step)
        # For now, fall back to matrix
        triad = matrix_select(pool, min_div, cfg["dimensions"], fixed_voices=fixed)
    else:
        triad = matrix_select(pool, min_div, cfg["dimensions"], fixed_voices=fixed)

    if triad is None:
        raise RuntimeError(
            f"No valid triad found for profile {spec.profile_id} "
            f"(min_diversity={min_div}, pool={pool})"
        )

    # Resolve timeouts
    phase2_timeout_sec = (
        cfg["timeouts"]["phases"]["phase_2_generate"]["default_seconds"]
    )

    return [
        VoiceConfig(
            voice_id=v,
            family=cfg["dimensions"].get(v, {}).get("provider", "unknown"),
            role="builder",
            timeout_sec=phase2_timeout_sec,
        )
        for v in triad
    ]


def select_mediator(
    profile_id: str,
    voices_used: list[str],
    config_root: Path = Path("config"),
) -> str | None:
    """Select the mediator (≠ all Phase 2 voices)."""
    cfg = load_config(config_root)
    profile = cfg["routing"]["profiles"].get(profile_id)
    if profile is None:
        return None
    mediator = profile.get("mediator")
    if mediator is None or mediator == "humain":
        return None if mediator is None else str(mediator)
    if mediator in voices_used:
        # Fallback: pick first auditor pool member
        # (mediator clash is misconfiguration but recoverable)
        return None
    return str(mediator)


def select_auditor(
    winner_voice_id: str,
    risk_profile: RiskProfile,
    config_root: Path = Path("config"),
) -> str:
    """Phase 4 auditor: family ≠ winner, optionally not US/CN."""
    cfg = load_config(config_root)
    winner_family = cfg["dimensions"].get(winner_voice_id, {}).get("provider")
    if winner_family is None:
        raise ValueError(f"Unknown winner voice: {winner_voice_id}")

    pool = cfg["routing"]["auditor_pools_by_winner_family"].get(winner_family, [])
    pool = filter_candidates(pool, risk_profile)

    if not pool:
        raise RuntimeError(f"No auditor available for family {winner_family}")
    return pool[0]
