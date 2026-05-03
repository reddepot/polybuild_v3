"""Phase -1 — Privacy Gate (round 4 finalisé).

Architecture 3 couches séquentielles (convergence 6/6 round 4):
    L1 PII directe — presidio + regex FR (NIR, email, phone, address, birth_date)
        → blocage hard, jamais de négociation
    L2 Quasi-identifiants médicaux — eds-pseudo (AP-HP, F1=0.97-0.99 sur clinique FR)
        → escalade `paranoia=high` si attestation forte présente, sinon BLOCK
    L3 Contextuel + attestation — champ `sensitivity_attestation` énuméré dans spec.yaml
        → BLOCK si "missing", PASS sinon (selon valeur)

Attestation values (ChatGPT propose énumération > booléen):
    - "missing"                    : aucune attestation, blocage par défaut
    - "synthetic"                  : données synthétiques (PASS L1+L2+L3)
    - "fully_anonymized"           : anonymisation certifiée hors POLYBUILD (PASS)
    - "abstract_schema_only"       : code/schema uniquement, pas de données réelles (PASS)
    - "health_adjacent"            : sujet médical sans patient identifiable (paranoia high)
    - "identifiable"               : données réelles → BLOCK toujours

Eds-pseudo lazy-load (Qwen): ~350MB RAM au premier chargement, libéré après run.
Kimi écartait eds-pseudo (instable hors clinique narratif). Compromis : eds-pseudo
optionnel via EDS_PSEUDO_ENABLED=1, fallback dictionnaire métier statique sinon
(NAS-safe). Avis majoritaire 5/6 conservé (eds-pseudo F1=0.97 documenté).
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal, cast

import structlog
import yaml
from pydantic import BaseModel

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# MODELS
# ────────────────────────────────────────────────────────────────


PrivacyVerdictLevel = Literal["PASS", "BLOCK", "ESCALATE_PARANOIA"]
AttestationValue = Literal[
    "missing",
    "synthetic",
    "fully_anonymized",
    "abstract_schema_only",
    "health_adjacent",
    "identifiable",
]


class PIIFinding(BaseModel):
    """A detected PII entity."""

    layer: int  # 1, 2, 3
    entity_type: str
    matched_text: str  # truncated to 30 chars for log safety
    score: float | None = None


class PrivacyVerdict(BaseModel):
    """Verdict from Phase -1 privacy gate."""

    level: PrivacyVerdictLevel
    blocked: bool
    reason: str
    findings: list[PIIFinding] = []
    attestation: AttestationValue = "missing"
    paranoia_level: Literal["low", "medium", "high"] = "low"


# ────────────────────────────────────────────────────────────────
# LAYER 1 — DIRECT PII (regex + presidio)
# ────────────────────────────────────────────────────────────────


_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "nir": re.compile(
        r"\b[12]\s?\d{2}\s?(0[1-9]|1[0-2])\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b"
    ),
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "phone_fr": re.compile(r"(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}"),
    "birth_date": re.compile(
        r"\b(?:n[ée]e?\s+le|date\s+de\s+naissance)\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        re.IGNORECASE,
    ),
    "postal_address": re.compile(
        r"\b\d{1,4}\s+(?:rue|avenue|boulevard|bd|impasse|chemin|route|place)\s+[\w\s'-]{3,}",
        re.IGNORECASE,
    ),
}


def _layer_1_regex(text: str) -> list[PIIFinding]:
    """Pure-regex PII detection (no external dep, always available)."""
    findings: list[PIIFinding] = []
    for entity_type, pattern in _PII_PATTERNS.items():
        for match in pattern.finditer(text):
            matched = match.group(0)
            findings.append(
                PIIFinding(
                    layer=1,
                    entity_type=entity_type,
                    matched_text=matched[:30] + ("…" if len(matched) > 30 else ""),
                )
            )
    return findings


def _layer_1_presidio(text: str) -> list[PIIFinding]:
    """Presidio analyzer L1 — soft import, returns [] if presidio unavailable."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
    except ImportError:
        logger.debug("presidio_unavailable_skipping_l1_nlp")
        return []

    # Round 10.7 fix [Kimi C-09 P1]: ``AnalyzerEngine()`` lazily downloads /
    # loads spaCy models the first time it runs ``.analyze()``. Re-creating
    # it on every call multiplied the cold-start cost across runs and
    # leaked memory under high concurrency. Cache at module level — the
    # engine is thread-safe for ``.analyze()`` calls.
    global _PRESIDIO_ENGINE
    if _PRESIDIO_ENGINE is None:
        try:
            _PRESIDIO_ENGINE = AnalyzerEngine()
        except Exception as e:
            logger.warning("presidio_init_failed", error=str(e))
            return []

    try:
        results = _PRESIDIO_ENGINE.analyze(
            text=text,
            language="fr",
            entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_TIME"],
        )
    except Exception as e:
        logger.warning("presidio_analyze_failed", error=str(e))
        return []

    findings: list[PIIFinding] = []
    for r in results:
        if r.score < 0.85:
            continue
        excerpt = text[r.start : r.end]
        findings.append(
            PIIFinding(
                layer=1,
                entity_type=r.entity_type,
                matched_text=excerpt[:30] + ("…" if len(excerpt) > 30 else ""),
                score=r.score,
            )
        )
    return findings


# ────────────────────────────────────────────────────────────────
# LAYER 2 — QUASI-IDENTIFIERS (eds-pseudo, lazy)
# ────────────────────────────────────────────────────────────────


_QUASI_LABELS_EDS: set[str] = {
    "HOPITAL",
    "VILLE",
    "ZIP",
    "DATE",
    "RARE_DISEASE",
    "MEDICAL_PROCEDURE",
    "PATIENT",
}

# Round 5 fix [C]: singleton with thread-safe init to avoid re-loading eds-pseudo
# (~350MB) on every call. Audits 1+4 flagged this as P0/P1: "libéré après run"
# was a docstring promise never honored, causing OOM risk on the 18GB NAS.
_EDS_NLP_INSTANCE: Any | None = None
_EDS_NLP_LOAD_FAILED: bool = False

# Round 10.7 fix [Kimi C-09 P1]: cached Presidio engine — see _layer_1_presidio.
_PRESIDIO_ENGINE: Any | None = None


def _get_eds_nlp() -> Any | None:
    """Lazy singleton for eds-pseudo. Returns None if unavailable.

    Round 5 (Audit 5): tries `edsnlp.load("eds")` first (canonical), falls back
    to `edsnlp.blank("eds")` + add_pipe (legacy code path).
    """
    global _EDS_NLP_INSTANCE, _EDS_NLP_LOAD_FAILED
    if _EDS_NLP_LOAD_FAILED:
        return None
    if _EDS_NLP_INSTANCE is not None:
        return _EDS_NLP_INSTANCE

    try:
        import edsnlp
    except ImportError:
        _EDS_NLP_LOAD_FAILED = True
        logger.info("eds_pseudo_unavailable_using_static_fallback")
        return None

    # Try canonical load first (Audit 5 recommendation), fall back to blank+pipe.
    try:
        nlp = edsnlp.load("eds")
        if not nlp.has_pipe("pseudonymisation"):
            nlp.add_pipe("eds.pseudonymisation")
    except Exception:
        try:
            nlp = edsnlp.blank("eds")
            nlp.add_pipe("eds.pseudonymisation")
        except Exception as e:
            _EDS_NLP_LOAD_FAILED = True
            logger.warning("eds_pseudo_load_failed", error=str(e))
            return None

    _EDS_NLP_INSTANCE = nlp
    logger.info("eds_pseudo_loaded_singleton")
    return nlp

_RARE_OCCUPATIONS_FR: set[str] = {
    "chimiste analyseur",
    "technicien cryogénie",
    "plongeur professionnel",
    "soudeur nucléaire",
    "amianteur",
    "thanatopracteur",
    "radioprotection",
    "chirurgien thoracique",
}

_RARE_PATHOLOGIES_FR: set[str] = {
    "mésothéliome",
    "silicose",
    "bérylliose",
    "saturnisme",
    "fibrose pulmonaire idiopathique",
    "sarcome de kaposi",
    "maladie de creutzfeldt",
}


def _layer_2_eds_pseudo(text: str) -> list[PIIFinding]:
    """eds-pseudo (AP-HP) lazy-load. Soft fallback to static dict if unavailable.

    Round 5 [C]: uses module-level singleton via _get_eds_nlp() — no more
    per-call re-instantiation of the 350MB pipeline.
    """
    if os.environ.get("EDS_PSEUDO_ENABLED", "0") != "1":
        return _layer_2_static_fallback(text)

    nlp = _get_eds_nlp()
    if nlp is None:
        return _layer_2_static_fallback(text)

    try:
        doc = nlp(text)
    except Exception as e:
        logger.warning("eds_pseudo_run_failed", error=str(e))
        return _layer_2_static_fallback(text)

    findings: list[PIIFinding] = []
    for ent in doc.ents:
        if ent.label_ not in _QUASI_LABELS_EDS:
            continue
        excerpt = ent.text
        findings.append(
            PIIFinding(
                layer=2,
                entity_type=ent.label_,
                matched_text=excerpt[:30] + ("…" if len(excerpt) > 30 else ""),
            )
        )
    return findings


def _layer_2_static_fallback(text: str) -> list[PIIFinding]:
    """Pure-Python fallback when eds-pseudo unavailable (NAS-safe)."""
    text_low = text.lower()
    findings: list[PIIFinding] = []

    for occ in _RARE_OCCUPATIONS_FR:
        if occ in text_low:
            findings.append(
                PIIFinding(layer=2, entity_type="rare_occupation_fr", matched_text=occ)
            )
    for pat in _RARE_PATHOLOGIES_FR:
        if pat in text_low:
            findings.append(
                PIIFinding(layer=2, entity_type="rare_pathology_fr", matched_text=pat)
            )
    return findings


# ────────────────────────────────────────────────────────────────
# LAYER 3 — ATTESTATION (spec.yaml)
# ────────────────────────────────────────────────────────────────


_VALID_ATTESTATIONS: set[str] = {
    "missing",
    "synthetic",
    "fully_anonymized",
    "abstract_schema_only",
    "health_adjacent",
    "identifiable",
}

_STRONG_ATTESTATIONS: set[str] = {
    "synthetic",
    "fully_anonymized",
    "abstract_schema_only",
}


def _normalize_attestation(value: str | None) -> AttestationValue:
    """Round 5 fix [B]: normalize any input to a valid AttestationValue.

    Audits 1+3+5 flagged this: passing `attestation=<str>` to PrivacyVerdict
    relied on `# type: ignore` and crashed Pydantic if the YAML was malformed
    or if `declared_sensitivity` came from CLI/project_ctx unsanitised.
    """
    # Round 10.1 fix [R2]: normalize before lowercasing so fullwidth
    # variants of attestation tokens (e.g. ``ＳＹＮＴＨＥＴＩＣ``) are
    # accepted instead of being silently demoted to ``missing``.
    normalized = unicodedata.normalize("NFKC", str(value or "missing"))
    val = normalized.strip().lower()
    if val not in _VALID_ATTESTATIONS:
        logger.warning("invalid_attestation_value_normalized_to_missing", value=val)
        return "missing"
    return cast("AttestationValue", val)


def _load_attestation(spec_path: str | Path | None) -> str:
    """Load `sensitivity_attestation` from spec.yaml. Returns 'missing' on failure."""
    if not spec_path:
        return "missing"
    p = Path(spec_path)
    if not p.exists():
        return "missing"
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        logger.warning("spec_yaml_parse_failed", path=str(p))
        return "missing"

    val = str(data.get("sensitivity_attestation", "missing")).strip().lower()
    if val not in _VALID_ATTESTATIONS:
        logger.warning("invalid_attestation_value", value=val)
        return "missing"
    return val


# ────────────────────────────────────────────────────────────────
# MAIN GATE
# ────────────────────────────────────────────────────────────────


def phase_minus_one_privacy_gate(
    text: str,
    spec_path: str | Path | None = None,
    declared_sensitivity: str | None = None,
    additional_context: str | None = None,
) -> PrivacyVerdict:
    """Run the 3-layer privacy gate on a brief/spec text.

    Args:
        text: Full text of the brief or generated spec to inspect.
        spec_path: Path to spec.yaml (for attestation lookup).
        declared_sensitivity: Optional override (CLI flag) of the YAML attestation.
        additional_context: Round 8 fix [Privacy-AGENTS] (4/6 audits convergence
            — Grok, Qwen, ChatGPT, Kimi P0). The brief alone is NOT the full
            attack surface. Adapters inject AGENTS.md, project_ctx, and prior
            checkpoint content into the LLM prompt AFTER this gate runs.
            Pass them here so they go through the same L1/L2/L3 layers.
            Concatenated to `text` before scanning. Caller responsibility:
            pass everything that will end up in any LLM prompt.

    Decision tree (round 4 convergence + round 5/8 patches):
        1. L1 hit → BLOCK always (no negotiation).
        2. attestation = "identifiable" → BLOCK always.
        3. L2 hit (>=2 quasi-id):
            - attestation in strong set → ESCALATE_PARANOIA (force EU/local).
            - else: BLOCK.
        4. L2 hit (1 quasi-id) + attestation = "missing" → BLOCK.
        5. attestation = "missing" + text >1500 chars → BLOCK.
            (Round 5 fix [U]: was 300 chars, too strict — 4 sentences blocked.
             Raised to 1500 chars (~3-4 paragraphs) to avoid UX paper cuts on
             normal briefs while still catching long sensitive narratives.)
        6. else → PASS.
    """
    # Round 8 fix [Privacy-AGENTS]: scan the FULL prompt context, not just
    # the brief. AGENTS.md and project_ctx are the most common bypass vectors
    # because they are loaded by adapters AFTER the gate runs.
    # Round 10.1 fix [R2 — Unicode confusables / homoglyphs] (5/6 conv:
    # Grok, Qwen, Gemini, DeepSeek, Kimi): the regexes match ASCII digit/
    # letter ranges only. A NIR encoded with mathematical bold digits
    # (U+1D7CE-D7) or an email with fullwidth ``＠`` (U+FF20) bypassed the
    # gate. NFKC normalization collapses those variants to their canonical
    # ASCII equivalents before any regex runs.
    text = unicodedata.normalize("NFKC", text)
    if additional_context:
        additional_context = unicodedata.normalize("NFKC", additional_context)
        # Use a sentinel to keep the layers' regexes from matching across the
        # boundary (e.g. a phone number cut between brief and AGENTS.md).
        full_text = text + "\n<--POLYBUILD-PRIVACY-BOUNDARY-->\n" + additional_context
    else:
        full_text = text

    # Round 5 fix [B]: normalize attestation to AttestationValue (Pydantic-safe)
    attestation: AttestationValue = _normalize_attestation(
        declared_sensitivity if declared_sensitivity else _load_attestation(spec_path)
    )

    # ── Layer 1 ──────────────────────────────────────────────────
    l1_findings = _layer_1_regex(full_text) + _layer_1_presidio(full_text)
    if l1_findings:
        types = sorted({f.entity_type for f in l1_findings})
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=f"L1 direct PII detected: {types}",
            findings=l1_findings,
            attestation=attestation,
            paranoia_level="high",
        )

    # ── Hard rule ─────────────────────────────────────────────────
    if attestation == "identifiable":
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason="attestation=identifiable → real data not allowed",
            attestation="identifiable",
            paranoia_level="high",
        )

    # ── Layer 2 ──────────────────────────────────────────────────
    l2_findings = _layer_2_eds_pseudo(full_text)

    if len(l2_findings) >= 2:
        if attestation in _STRONG_ATTESTATIONS:
            return PrivacyVerdict(
                level="ESCALATE_PARANOIA",
                blocked=False,
                reason=(
                    f"L2 quasi-identifiers ({len(l2_findings)}) "
                    f"with attestation={attestation} → forcing EU/local routing"
                ),
                findings=l2_findings,
                attestation=attestation,
                paranoia_level="high",
            )
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=(
                f"L2 quasi-identifiers ({len(l2_findings)}) without strong attestation. "
                "Set sensitivity_attestation to synthetic, fully_anonymized, "
                "or abstract_schema_only in spec.yaml."
            ),
            findings=l2_findings,
            attestation=attestation,
            paranoia_level="high",
        )

    if len(l2_findings) == 1 and attestation == "missing":
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason="1 quasi-identifier + missing attestation → specify explicitly",
            findings=l2_findings,
            attestation="missing",
            paranoia_level="medium",
        )

    # ── Layer 3 ──────────────────────────────────────────────────
    if attestation == "missing" and len(full_text) > 1500:
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=(
                "attestation=missing for long brief (>1500 chars). "
                "Add sensitivity_attestation to spec.yaml "
                "(e.g. 'abstract_schema_only' for code-only briefs)."
            ),
            findings=l2_findings,
            attestation="missing",
            paranoia_level="medium",
        )

    paranoia: Literal["low", "medium", "high"] = (
        "high" if attestation == "health_adjacent" else "low"
    )
    return PrivacyVerdict(
        level="PASS",
        blocked=False,
        reason=f"All 3 layers cleared (attestation={attestation})",
        findings=l2_findings,
        attestation=attestation,
        paranoia_level=paranoia,
    )


# Backward-compat alias
phase_minus_one = phase_minus_one_privacy_gate


__all__ = [
    "AttestationValue",
    "PIIFinding",
    "PrivacyVerdict",
    "PrivacyVerdictLevel",
    "phase_minus_one",
    "phase_minus_one_privacy_gate",
]
