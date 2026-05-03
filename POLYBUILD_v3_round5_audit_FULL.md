# POLYBUILD v3 — Round 5 audit request

> **À toi, modèle audité** : tu fais partie d'une équipe de 6 LLM (Claude Opus 4.7,
> GPT-5.5, Gemini 3.1 Pro, Kimi K2.6, DeepSeek V4-Pro, Grok 4.20) consultés en
> parallèle sur ce code. Tu reçois la même demande que les 5 autres. Sois honnête,
> orthogonal, pas diplomatique. Un dissensus utile vaut mieux qu'un consensus mou.

---

## Contexte

POLYBUILD v3 est un méta-orchestrateur multi-LLM conçu par un médecin du travail
SPSTI / dev Python solo (NAS Synology DS224+ 18GB RAM, MacBook M2 8GB, 3 serveurs
MCP Docker en prod 24/7). Objectif : générer du code Python de production en
combinant les forfaits CLI gratuits (Claude Max 20x, ChatGPT Pro, Gemini Pro, Kimi
Allegretto) + budget OpenRouter complémentaire (~15-20€/mois cible, hard cap 30€)
+ API Mistral EU directe pour les profils médicaux.

**Stack imposée** : Python 3.11+, asyncio, uv, ruff, mypy --strict, pytest, SQLite,
Qdrant, Pydantic strict. **Interdits** : LangChain, LlamaIndex.

**Méthodologie** : POLYBUILD a été conçu lui-même par consultation multi-LLM en
4 rounds successifs. Convergence ≥4/6 → décision actée. Dissensus → ADR.

### Ce qui a été décidé rounds 1-3 (NON-NÉGOCIABLE — ne pas re-débattre)

- Phase 0 = Opus seul ; Phase 0b = Spec Attack par DeepSeek (algo) + Grok (adhérence)
- Mémoire repo : `AGENTS.md` racine + vector summary local (sqlite-vec + Model2Vec)
- Verifier Phase 5 : Évaluateur-Optimiseur strict, JSON-only, ne réécrit jamais
- Adapter pattern Python asyncio + BuilderProtocol Pydantic
- Grounding AST post-génération obligatoire (P1 si imports hallucinés, disqualif si ≥2)
- Triade Phase 5 : Critic ≠ Fixer ≠ Verifier (familles différentes)
- 15 profils routing (module_standard, inedit_critique, helia_algo, medical_low/medium/high,
  parsing_pdf_medical, rag_ingestion, mcp_schema, oai_pmh, devops_iac, refactor, llm_judge,
  post_polylens_fix, doc_adr)
- OpenRouter interdit pour données médicales (Mistral via api.mistral.ai EU direct)
- Local NAS : Qwen 2.5 Coder 14B INT4 seul viable
- Repo dédié `polybuild-core` avec ADR
- Apprentissage supervisé, suggestions ADR après 20-30 runs
- **Claude Opus jamais via API payante** (déjà l'orchestrateur via Claude Max gratuit)

### Ce qui vient d'être livré round 4 — c'est CE CODE que tu dois auditer

5 failles résiduelles closes par convergence multi-modèles round 4. Pour chacune,
le récap de la convergence (≥4/6) et le risque résiduel sont dans le README ci-dessous.

| # | Faille | Convergence round 4 | Module livré |
|---|---|---|---|
| 1 | Privacy Gate Phase -1 | 6/6 sur 3 couches séquentielles (Presidio L1, eds-pseudo lazy L2, attestation L3) | `phase_minus_one_privacy.py` |
| 2 | Domain gates Phase 6 | 5/6 bloquants (DeepSeek nuance SQLite warn) | `domain_gates/*.py` |
| 3 | Concurrency CLI | 6/6 sémaphores asyncio + back-pressure P0/P1/P2/P3 différentielle | `concurrency/limiter.py` |
| 4 | Déploiement Option B | 6/6 worktree+RO+rollback ; dissensus seuil dégradation 0% strict (DeepSeek) vs 5% (autres) | `phase_8_prod_smoke.py` + `deploy_staging.sh` |
| 5 | Skill /polybuild + secrets | 6/6 tmux+gitleaks+chmod 600 ; fallback `tmux→screen→nohup` (Kimi+DeepSeek) | `skills/polybuild/SKILL.md` + `security/secrets_loader.py` + `.gitleaks.toml` |

**Total round 4** : 36 fichiers Python (~7500 LOC), validation syntaxique + imports cross-module 100% OK.

---

## Ce que je te demande

**Audite ce code à la lumière des décisions rounds 1-3 et des convergences round 4.**

### Questions structurées (réponds à chacune explicitement)

#### Q1 — Failles d'exécution (le code marche-t-il vraiment ?)
Repère les bugs concrets : race conditions, leaks de ressources, edge cases non gérés,
mauvaises annotations de type, dépendances manquantes, signatures async incorrectes.
Pour chaque : ligne précise, sévérité (P0/P1/P2/P3), patch proposé.

#### Q2 — Cohérence avec les décisions actées
Le code implémente-t-il fidèlement les convergences round 4 ?
Y a-t-il des dérives silencieuses par rapport aux 5 décisions tranchées ?

#### Q3 — Trous dans la spec
Quelles questions importantes le code ne traite pas alors qu'il prétend traiter ?
Exemple type : "le commentaire dit X mais le code fait Y", "ce gate prétend bloquer
mais en pratique laisse passer Z", "Phase 9 cleanup oublie le cas W".

#### Q4 — Dette architecturale émergente
Vois-tu des choix qui vont casser à l'échelle ou créer une dette technique
(couplage caché, abstractions trop tôt, abstractions trop tard, anti-patterns Python) ?

#### Q5 — Convergences round 4 que tu remettrais en cause
Les 5 décisions actées ont été prises à 4-6/6. Si tu en repérais une qui te paraît
mauvaise après lecture du code, dis-le explicitement avec contre-proposition.
**Ne te censure pas pour suivre la majorité.**

#### Q6 — Bugs "stupides" (le truc évident raté)
Dans toute revue il y a 1-2 conneries embarrassantes : import oublié, condition
inversée, off-by-one, exception jamais levée, log qui fuite un secret, Pydantic
mal configuré, etc. Liste-les.

#### Q7 — Score global et verdict GO/NO-GO sprint A
Est-ce qu'on peut passer au sprint A (tests smoke_cli minimal, fondations)
ou y a-t-il un blocker round 5 à résoudre d'abord ?
Score global : note 0-10 + verdict binaire.

---

## Format de réponse attendu

Structure-toi pour faciliter la synthèse cross-modèles :

```markdown
## Q1 — Failles d'exécution
### [P0] <titre court>
**Fichier** : path:line
**Problème** : ...
**Patch** :
```python
# code corrigé
```

### [P1] ...
...

## Q2 — Cohérence avec décisions actées
...

## Q3 — Trous dans la spec
...

## Q4 — Dette architecturale
...

## Q5 — Convergences à remettre en cause
- **Faille N — décision actée** : <ce qui est décidé>
- **Ma contre-proposition** : <pourquoi tu n'es pas d'accord>
- **Risque si je tais** : ...

## Q6 — Bugs stupides
1. file:line — description en une phrase
2. ...

## Q7 — Verdict
**Score** : N/10
**GO/NO-GO sprint A** : GO | NO-GO car <raison principale>
**Top 3 priorités avant sprint A** :
1. ...
2. ...
3. ...
```

---

## Règles de l'audit

1. **Pas de complaisance.** Le concepteur préfère une critique dure à un compliment vide.
2. **Pas de re-débat des décisions rounds 1-3.** Sauf si le code y dérive (Q2).
3. **Chiffres et lignes précises.** Pas de "il faudrait peut-être".
4. **Patches courts.** Pas de réécriture massive — montrer le delta minimal.
5. **Si tu vois un truc dont les autres modèles risquent de ne pas parler** (orthogonalité), insiste dessus.
6. **Voice notes interdites.** Markdown uniquement.

---

## Code à auditer

### Repository tree

```
polybuild_v3/
  .env.example
  .gitignore
  .gitleaks.toml
  .pre-commit-config.yaml
  AGENTS.md
  config/
    concurrency_limits.yaml
    model_dimensions.yaml
    models.yaml
    routing.yaml
    timeouts.yaml
  prompts/
    adr.md
    builder_unified.md
    critic.md
    fixer.md
    opus_spec.md
    spec_attack.md
    verifier_strict.md
  pyproject.toml
  scripts/
    deploy_staging.sh
    polybuild/
      SKILL.md
    polybuild/
      __init__.py
      _version.py
      adapters/
        __init__.py
        builder_protocol.py
        claude_code.py
        codex_cli.py
        gemini_cli.py
        kimi_cli.py
        mistral_eu.py
        ollama_local.py
        openrouter.py
    polybuild/
      cli.py
      concurrency/
        __init__.py
        limiter.py
      domain_gates/
        __init__.py
        validate_fts5.py
        validate_mcp.py
        validate_qdrant.py
        validate_rag.py
        validate_sqlite.py
    polybuild/
      models.py
      orchestrator.py
      phases/
        __init__.py
        phase_0_spec.py
        phase_1_select.py
        phase_2_generate.py
        phase_3_score.py
        phase_3b_grounding.py
        phase_4_audit.py
        phase_5_triade.py
        phase_6_validate.py
        phase_7_commit.py
        phase_8_prod_smoke.py
        phase_minus_one_privacy.py
      security/
        __init__.py
        secrets_loader.py
```

---

## Round 4 deliverables (PRIMARY AUDIT TARGET)

These are the 5 modules implementing the round 4 convergences. **Audit them first and most thoroughly.**


### `src/polybuild/phases/phase_minus_one_privacy.py` (410 lines)

```python
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
from pathlib import Path
from typing import Literal

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

    try:
        analyzer = AnalyzerEngine()
        results = analyzer.analyze(
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
    """eds-pseudo (AP-HP) lazy-load. Soft fallback to static dict if unavailable."""
    if os.environ.get("EDS_PSEUDO_ENABLED", "0") != "1":
        return _layer_2_static_fallback(text)

    try:
        import edsnlp  # type: ignore[import-not-found]
    except ImportError:
        logger.info("eds_pseudo_unavailable_using_static_fallback")
        return _layer_2_static_fallback(text)

    try:
        nlp = edsnlp.blank("eds")
        nlp.add_pipe("eds.pseudonymisation")
        doc = nlp(text)
    except Exception as e:
        logger.warning("eds_pseudo_load_failed", error=str(e))
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
) -> PrivacyVerdict:
    """Run the 3-layer privacy gate on a brief/spec text.

    Args:
        text: Full text of the brief or generated spec to inspect.
        spec_path: Path to spec.yaml (for attestation lookup).
        declared_sensitivity: Optional override (CLI flag) of the YAML attestation.

    Decision tree (round 4 convergence):
        1. L1 hit → BLOCK always (no negotiation).
        2. attestation = "identifiable" → BLOCK always.
        3. L2 hit (>=2 quasi-id):
            - attestation in strong set → ESCALATE_PARANOIA (force EU/local).
            - else: BLOCK.
        4. L2 hit (1 quasi-id) + attestation = "missing" → BLOCK.
        5. attestation = "missing" + text >300 chars → BLOCK.
        6. else → PASS.
    """
    attestation: str = (
        declared_sensitivity if declared_sensitivity else _load_attestation(spec_path)
    )

    # ── Layer 1 ──────────────────────────────────────────────────
    l1_findings = _layer_1_regex(text) + _layer_1_presidio(text)
    if l1_findings:
        types = sorted({f.entity_type for f in l1_findings})
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=f"L1 direct PII detected: {types}",
            findings=l1_findings,
            attestation=attestation,  # type: ignore[arg-type]
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
    l2_findings = _layer_2_eds_pseudo(text)

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
                attestation=attestation,  # type: ignore[arg-type]
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
            attestation=attestation,  # type: ignore[arg-type]
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
    if attestation == "missing" and len(text) > 300:
        return PrivacyVerdict(
            level="BLOCK",
            blocked=True,
            reason=(
                "attestation=missing for non-trivial brief. "
                "Add sensitivity_attestation to spec.yaml."
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
        attestation=attestation,  # type: ignore[arg-type]
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

```


### `src/polybuild/domain_gates/__init__.py` (30 lines)

```python
"""Domain-specific gates for Phase 6 (round 4 finalisé).

Each gate validates a specific domain concern (MCP, SQLite, Qdrant, FTS5, RAG).
Activated per profile via routing.yaml `domain_gates` mapping.

Convergence round 4 (5/6, DeepSeek nuance vers warn pour SQLite optionnel):
    - All gates strictly BLOCK Phase 7 commit on failure.
    - Optional warnings reserved for P2/P3 documentation findings.
    - MCP gate: spawn server in stdio/JSON-RPC mode, send initialize + tools/list,
      validate tool schemas via Pydantic, terminate cleanly.
    - SQLite gate: PRAGMA integrity_check + WAL mode + schema diff.
    - Qdrant gate: get_collection + dimension match + sample query.
    - FTS5 gate: 3 golden queries with expected hits.
    - RAG gate: chunk hash stability + Qdrant count + golden retrieval check.
"""

from polybuild.domain_gates.validate_mcp import validate_mcp_server
from polybuild.domain_gates.validate_sqlite import validate_sqlite_db
from polybuild.domain_gates.validate_qdrant import validate_qdrant_collection
from polybuild.domain_gates.validate_fts5 import validate_fts5_golden
from polybuild.domain_gates.validate_rag import validate_rag_smoke

__all__ = [
    "validate_mcp_server",
    "validate_sqlite_db",
    "validate_qdrant_collection",
    "validate_fts5_golden",
    "validate_rag_smoke",
]

```


### `src/polybuild/domain_gates/validate_mcp.py` (208 lines)

```python
"""Validate MCP server contract via JSON-RPC handshake (round 4).

Synthèse round 4:
    - Gemini : asyncio.subprocess + initialize JSON-RPC + parse stdout line.
    - Kimi : initialize + tools/list + Pydantic schema validation, ligne par ligne.
    - DeepSeek : staging port + RO volumes + golden tool call.
    - ChatGPT : start_new_session=True + os.killpg cleanup; capabilities check.
    - Grok : Docker isolation (rejeté : trop lourd pour tous les profils).

Décision : asyncio subprocess en stdio (pas Docker par défaut, simpler), avec
volumes RO via env vars. Docker reste possible via flag `--use-docker` pour
les profils production-grade (mcp_schema_change critique).
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path

import structlog
from pydantic import BaseModel, Field, ValidationError

logger = structlog.get_logger()


class MCPToolSchema(BaseModel):
    """Subset of MCP tool spec we validate (round 4 convergence)."""

    name: str = Field(min_length=1)
    description: str | None = None
    inputSchema: dict = Field(default_factory=dict)


class MCPGateResult(BaseModel):
    """Result of MCP server validation."""

    passed: bool
    n_tools: int = 0
    tool_names: list[str] = []
    errors: list[str] = []
    elapsed_s: float = 0.0


async def _send_jsonrpc(
    proc: asyncio.subprocess.Process,
    request: dict,
    timeout_s: float = 5.0,
) -> dict:
    """Send a JSON-RPC request and read the next response line."""
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("Subprocess has no stdin/stdout")

    payload = (json.dumps(request) + "\n").encode("utf-8")
    proc.stdin.write(payload)
    await proc.stdin.drain()

    line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout_s)
    if not line:
        raise RuntimeError("MCP server closed stdout unexpectedly")
    return json.loads(line.decode("utf-8"))


async def validate_mcp_server(
    server_cmd: list[str],
    cwd: str | Path,
    expected_tools: set[str] | None = None,
    timeout_s: float = 30.0,
    extra_env: dict[str, str] | None = None,
) -> MCPGateResult:
    """Spawn MCP server in stdio mode and run JSON-RPC handshake.

    Args:
        server_cmd: Command to launch the server (e.g. ["uv", "run", "python", "-m", "server"]).
        cwd: Working directory for the server.
        expected_tools: Set of tool names that must be present (subset check).
        timeout_s: Total timeout for the validation.
        extra_env: Additional environment variables (e.g. read-only mounts).

    Returns:
        MCPGateResult with pass/fail + diagnostics.
    """
    import time

    start = time.time()
    errors: list[str] = []

    env = os.environ.copy()
    env.update(
        {
            "POLYBUILD_TEST_MODE": "1",
            "MCP_TRANSPORT": "stdio",
            "SQLITE_READONLY": "1",  # Volumes prod en RO (DeepSeek + ChatGPT)
            "QDRANT_READONLY": "1",
        }
    )
    if extra_env:
        env.update(extra_env)

    try:
        proc = await asyncio.create_subprocess_exec(
            *server_cmd,
            cwd=str(cwd),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # ChatGPT: enables os.killpg cleanup
        )
    except (OSError, FileNotFoundError) as e:
        return MCPGateResult(passed=False, errors=[f"spawn_failed: {e}"])

    tool_names: list[str] = []

    try:
        # ── Step 1: initialize ──────────────────────────────────────────
        init_resp = await _send_jsonrpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "polybuild", "version": "3"},
                },
            },
            timeout_s=8.0,
        )
        if "result" not in init_resp:
            errors.append(f"initialize_no_result: {init_resp.get('error', '<missing>')}")
            return MCPGateResult(
                passed=False, errors=errors, elapsed_s=time.time() - start
            )
        if "capabilities" not in init_resp["result"]:
            errors.append("initialize_no_capabilities")

        # Send the initialized notification (no response expected)
        if proc.stdin is not None:
            proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            await proc.stdin.drain()

        # ── Step 2: tools/list ──────────────────────────────────────────
        tools_resp = await _send_jsonrpc(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout_s=8.0,
        )
        if "result" not in tools_resp:
            errors.append(f"tools_list_failed: {tools_resp.get('error', '<missing>')}")
            return MCPGateResult(
                passed=False, errors=errors, elapsed_s=time.time() - start
            )

        raw_tools = tools_resp["result"].get("tools", [])
        for raw in raw_tools:
            try:
                tool = MCPToolSchema.model_validate(raw)
                tool_names.append(tool.name)
            except ValidationError as e:
                errors.append(f"tool_schema_invalid: {raw.get('name', '?')} → {e.errors()[:1]}")

        # ── Step 3: expected tools subset check ─────────────────────────
        if expected_tools:
            missing = expected_tools - set(tool_names)
            if missing:
                errors.append(f"missing_expected_tools: {sorted(missing)}")

    except asyncio.TimeoutError:
        errors.append(f"timeout > {timeout_s}s during JSON-RPC handshake")
    except json.JSONDecodeError as e:
        errors.append(f"json_decode_error: {e}")
    except Exception as e:
        errors.append(f"unexpected: {type(e).__name__}: {e}")

    finally:
        # ChatGPT: kill the entire process group to catch grandchildren
        try:
            if proc.returncode is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    elapsed = time.time() - start
    passed = not errors
    logger.info(
        "mcp_gate_done",
        passed=passed,
        n_tools=len(tool_names),
        n_errors=len(errors),
        elapsed_s=round(elapsed, 2),
    )

    return MCPGateResult(
        passed=passed,
        n_tools=len(tool_names),
        tool_names=tool_names,
        errors=errors,
        elapsed_s=elapsed,
    )

```


### `src/polybuild/domain_gates/validate_sqlite.py` (143 lines)

```python
"""Validate SQLite database integrity (round 4 — convergence).

Checks (Kimi + DeepSeek + ChatGPT convergence):
    - PRAGMA integrity_check returns "ok"
    - PRAGMA journal_mode is "wal" (production requirement)
    - Schema diff vs reference snapshot (if provided)
    - Foreign key integrity (PRAGMA foreign_key_check empty)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class SQLiteGateResult(BaseModel):
    """Result of SQLite validation."""

    passed: bool
    integrity_ok: bool = False
    journal_mode: str = ""
    schema_diff: list[str] = []
    fk_violations: int = 0
    errors: list[str] = []


def _read_schema(conn: sqlite3.Connection) -> dict[str, str]:
    """Read all CREATE statements indexed by object name."""
    cur = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type IN ('table','index','view','trigger') "
        "AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0]: row[1] or "" for row in cur.fetchall()}


def validate_sqlite_db(
    db_path: str | Path,
    expected_journal_mode: str = "wal",
    schema_snapshot_path: str | Path | None = None,
    require_wal: bool = True,
) -> SQLiteGateResult:
    """Run integrity, journal mode, and schema diff checks on a SQLite DB.

    Args:
        db_path: Path to the SQLite file.
        expected_journal_mode: Expected journal_mode (typically "wal" for prod).
        schema_snapshot_path: Optional path to a JSON snapshot for diff.
        require_wal: If True, non-WAL journal mode triggers failure.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return SQLiteGateResult(passed=False, errors=[f"db_not_found: {db_path}"])

    errors: list[str] = []
    integrity_ok = False
    journal_mode = ""
    fk_violations = 0
    schema_diff: list[str] = []

    try:
        # Open read-only via URI
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        return SQLiteGateResult(passed=False, errors=[f"open_failed: {e}"])

    try:
        # ── PRAGMA integrity_check ──────────────────────────────────
        cur = conn.execute("PRAGMA integrity_check")
        result = cur.fetchone()
        if result and result[0] == "ok":
            integrity_ok = True
        else:
            errors.append(f"integrity_check_failed: {result}")

        # ── PRAGMA journal_mode ─────────────────────────────────────
        cur = conn.execute("PRAGMA journal_mode")
        journal_mode = (cur.fetchone() or [""])[0].lower()
        if require_wal and journal_mode != expected_journal_mode.lower():
            errors.append(
                f"journal_mode={journal_mode} (expected {expected_journal_mode})"
            )

        # ── PRAGMA foreign_key_check ────────────────────────────────
        cur = conn.execute("PRAGMA foreign_key_check")
        fk_rows = cur.fetchall()
        fk_violations = len(fk_rows)
        if fk_violations > 0:
            errors.append(f"foreign_key_violations: {fk_violations}")

        # ── Schema diff ─────────────────────────────────────────────
        if schema_snapshot_path:
            import json

            snap_path = Path(schema_snapshot_path)
            if snap_path.exists():
                expected_schema = json.loads(snap_path.read_text(encoding="utf-8"))
                actual_schema = _read_schema(conn)

                # Removed objects = potential breaking change
                removed = set(expected_schema) - set(actual_schema)
                added = set(actual_schema) - set(expected_schema)
                changed = {
                    name
                    for name in set(expected_schema) & set(actual_schema)
                    if expected_schema[name].strip() != actual_schema[name].strip()
                }
                if removed:
                    schema_diff.append(f"removed: {sorted(removed)}")
                    errors.append(f"schema_objects_removed: {sorted(removed)}")
                if changed:
                    schema_diff.append(f"changed: {sorted(changed)}")
                if added:
                    # Adding new objects is non-breaking → log only
                    schema_diff.append(f"added: {sorted(added)}")

    finally:
        conn.close()

    passed = not errors
    logger.info(
        "sqlite_gate_done",
        passed=passed,
        integrity_ok=integrity_ok,
        journal_mode=journal_mode,
        fk_violations=fk_violations,
    )

    return SQLiteGateResult(
        passed=passed,
        integrity_ok=integrity_ok,
        journal_mode=journal_mode,
        schema_diff=schema_diff,
        fk_violations=fk_violations,
        errors=errors,
    )

```


### `src/polybuild/domain_gates/validate_qdrant.py` (145 lines)

```python
"""Validate Qdrant collection (round 4 convergence).

Checks (ChatGPT + DeepSeek convergence):
    - GET /collections/{name} returns 200 + valid config
    - vector dimension matches expected
    - points_count > 0 (or matches min_points)
    - sample search query returns results
"""

from __future__ import annotations

import asyncio

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class QdrantGateResult(BaseModel):
    """Result of Qdrant collection validation."""

    passed: bool
    collection_name: str
    points_count: int = 0
    expected_dim: int = 0
    actual_dim: int = 0
    sample_query_returned: int = 0
    errors: list[str] = []


async def validate_qdrant_collection(
    qdrant_url: str,
    collection: str,
    expected_dim: int,
    min_points: int = 1,
    sample_vector: list[float] | None = None,
    timeout_s: float = 10.0,
) -> QdrantGateResult:
    """Validate a Qdrant collection over HTTP.

    Args:
        qdrant_url: e.g. "http://localhost:6333".
        collection: Collection name.
        expected_dim: Expected vector dimension (e.g. 768 for E5-base, 1024 for BGE-M3).
        min_points: Minimum required points_count.
        sample_vector: Optional vector for a search smoke test.
                       If None, generates a zero-vector of expected_dim.
        timeout_s: HTTP timeout per call.
    """
    try:
        import httpx
    except ImportError:
        return QdrantGateResult(
            passed=False,
            collection_name=collection,
            errors=["httpx_unavailable"],
        )

    errors: list[str] = []
    points_count = 0
    actual_dim = 0
    sample_returned = 0

    base = qdrant_url.rstrip("/")

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        # ── GET collection ──────────────────────────────────────────
        try:
            resp = await client.get(f"{base}/collections/{collection}")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            return QdrantGateResult(
                passed=False,
                collection_name=collection,
                errors=[f"get_collection_failed: {e}"],
            )

        result = data.get("result", {})
        config = result.get("config", {}).get("params", {}).get("vectors", {})
        # Qdrant supports named vectors and unnamed default; handle both
        if isinstance(config, dict) and "size" in config:
            actual_dim = int(config.get("size", 0))
        elif isinstance(config, dict):
            # Named vectors: take first one
            for v_cfg in config.values():
                if isinstance(v_cfg, dict) and "size" in v_cfg:
                    actual_dim = int(v_cfg["size"])
                    break

        points_count = int(result.get("points_count", 0))

        if actual_dim != expected_dim:
            errors.append(f"dim_mismatch: expected {expected_dim}, got {actual_dim}")
        if points_count < min_points:
            errors.append(f"points_count={points_count} < min_points={min_points}")

        # ── Sample search query ─────────────────────────────────────
        if not errors:
            vec = sample_vector if sample_vector else [0.0] * expected_dim
            try:
                resp = await client.post(
                    f"{base}/collections/{collection}/points/search",
                    json={"vector": vec, "limit": 3, "with_payload": False},
                )
                resp.raise_for_status()
                hits = resp.json().get("result", [])
                sample_returned = len(hits)
                if sample_returned == 0:
                    errors.append("sample_search_returned_zero_hits")
            except httpx.HTTPError as e:
                errors.append(f"sample_search_failed: {e}")

    passed = not errors
    logger.info(
        "qdrant_gate_done",
        passed=passed,
        collection=collection,
        points=points_count,
        dim=actual_dim,
    )

    return QdrantGateResult(
        passed=passed,
        collection_name=collection,
        points_count=points_count,
        expected_dim=expected_dim,
        actual_dim=actual_dim,
        sample_query_returned=sample_returned,
        errors=errors,
    )


def validate_qdrant_collection_sync(
    qdrant_url: str,
    collection: str,
    expected_dim: int,
    min_points: int = 1,
) -> QdrantGateResult:
    """Sync wrapper for non-async callers."""
    return asyncio.run(
        validate_qdrant_collection(qdrant_url, collection, expected_dim, min_points)
    )

```


### `src/polybuild/domain_gates/validate_fts5.py` (140 lines)

```python
"""Validate FTS5 full-text index via golden queries (round 4).

Convergence (Kimi + DeepSeek): 3 golden queries with expected minimum hits.
The golden set is loaded from a JSON fixture path; tolerates non-existence
in early dev (returns warn-level result) but BLOCKS in mcp_schema_change /
rag_ingestion_eval profiles where the fixture is mandatory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class FTS5GateResult(BaseModel):
    """Result of FTS5 golden query validation."""

    passed: bool
    fts_table: str
    n_queries: int = 0
    n_passed: int = 0
    failures: list[str] = []
    errors: list[str] = []


def validate_fts5_golden(
    db_path: str | Path,
    fts_table: str,
    golden_path: str | Path,
    require_golden_file: bool = True,
) -> FTS5GateResult:
    """Run a set of FTS5 golden queries and check minimum hit counts.

    Golden file format (JSON list):
        [
          {"query": "amiante", "min_hits": 5, "max_hits": 10000},
          {"query": "burnout", "min_hits": 3}
        ]

    Args:
        db_path: SQLite DB path.
        fts_table: Name of the FTS5 virtual table (e.g. "articles_fts").
        golden_path: Path to JSON golden queries.
        require_golden_file: If True, missing file → fail. If False → warn-only.
    """
    db_path = Path(db_path)
    golden_path = Path(golden_path)

    if not db_path.exists():
        return FTS5GateResult(
            passed=False, fts_table=fts_table, errors=[f"db_not_found: {db_path}"]
        )

    if not golden_path.exists():
        if require_golden_file:
            return FTS5GateResult(
                passed=False,
                fts_table=fts_table,
                errors=[f"golden_file_not_found: {golden_path}"],
            )
        logger.warning("fts5_golden_file_missing_skipping", path=str(golden_path))
        return FTS5GateResult(
            passed=True, fts_table=fts_table, errors=["golden_skipped"]
        )

    try:
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        if not isinstance(golden, list):
            return FTS5GateResult(
                passed=False,
                fts_table=fts_table,
                errors=["golden_file_not_a_list"],
            )
    except json.JSONDecodeError as e:
        return FTS5GateResult(
            passed=False, fts_table=fts_table, errors=[f"golden_parse_error: {e}"]
        )

    failures: list[str] = []
    n_passed = 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        return FTS5GateResult(
            passed=False, fts_table=fts_table, errors=[f"open_failed: {e}"]
        )

    try:
        for entry in golden:
            query = str(entry.get("query", "")).strip()
            min_hits = int(entry.get("min_hits", 1))
            max_hits = entry.get("max_hits")  # optional

            if not query:
                continue

            try:
                cur = conn.execute(
                    # noqa: S608 — fts_table is a structural identifier from config, not user input
                    f"SELECT COUNT(*) FROM {fts_table} WHERE {fts_table} MATCH ?",  # noqa: S608
                    (query,),
                )
                n_hits = int(cur.fetchone()[0])
            except sqlite3.Error as e:
                failures.append(f"query={query!r} sqlite_error={e}")
                continue

            if n_hits < min_hits:
                failures.append(f"query={query!r} hits={n_hits} < min={min_hits}")
            elif max_hits is not None and n_hits > int(max_hits):
                failures.append(f"query={query!r} hits={n_hits} > max={max_hits}")
            else:
                n_passed += 1
    finally:
        conn.close()

    passed = not failures
    logger.info(
        "fts5_gate_done",
        passed=passed,
        table=fts_table,
        n_passed=n_passed,
        n_total=len(golden),
    )

    return FTS5GateResult(
        passed=passed,
        fts_table=fts_table,
        n_queries=len(golden),
        n_passed=n_passed,
        failures=failures,
    )

```


### `src/polybuild/domain_gates/validate_rag.py` (131 lines)

```python
"""Validate RAG pipeline smoke (round 4 convergence).

Checks (Kimi + DeepSeek + ChatGPT):
    - Chunk hash stability: re-chunking the same input produces identical chunks.
    - Golden retrieval: known-relevant queries return expected docs in top-K.
    - Pipeline end-to-end: ingest → embed → query → results.

Implementation note: this gate is lightweight by default (hash-only). Full
golden retrieval requires the calling project to provide a golden fixture
JSON with {query, expected_doc_id, top_k} entries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class RAGGateResult(BaseModel):
    """Result of RAG smoke validation."""

    passed: bool
    chunk_hash_stable: bool = True
    golden_top_k_passed: int = 0
    golden_total: int = 0
    errors: list[str] = []


def _hash_chunks(chunks: list[str]) -> str:
    """Produce a stable hash of a chunk list."""
    h = hashlib.sha256()
    for chunk in chunks:
        h.update(chunk.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def validate_rag_smoke(
    chunker_fn: Callable[[str], list[str]] | None = None,
    sample_text: str = "",
    golden_retrieval_path: str | Path | None = None,
    retrieval_fn: Callable[[str, int], list[str]] | None = None,
) -> RAGGateResult:
    """Run RAG smoke checks.

    Args:
        chunker_fn: Optional chunker function `text -> list[chunks]`.
                    If provided, runs hash-stability check (call twice, hashes must match).
        sample_text: Text to feed the chunker.
        golden_retrieval_path: Optional JSON file with golden retrieval cases.
            Format: [{"query": "...", "expected_doc_id": "abc", "top_k": 5}, ...]
        retrieval_fn: Function `(query, top_k) -> list[doc_id]` for golden checks.

    Returns:
        RAGGateResult.
    """
    errors: list[str] = []
    chunk_stable = True

    # ── Chunk hash stability ─────────────────────────────────────────
    if chunker_fn is not None and sample_text:
        try:
            chunks_a = chunker_fn(sample_text)
            chunks_b = chunker_fn(sample_text)
            if _hash_chunks(chunks_a) != _hash_chunks(chunks_b):
                chunk_stable = False
                errors.append("chunker_non_deterministic: hash mismatch on identical input")
        except Exception as e:
            errors.append(f"chunker_failed: {type(e).__name__}: {e}")

    # ── Golden retrieval ─────────────────────────────────────────────
    n_passed = 0
    n_total = 0
    if golden_retrieval_path:
        path = Path(golden_retrieval_path)
        if not path.exists():
            errors.append(f"golden_retrieval_file_not_found: {path}")
        else:
            try:
                cases = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"golden_parse_error: {e}")
                cases = []

            n_total = len(cases)
            if cases and retrieval_fn is None:
                errors.append("golden_provided_but_retrieval_fn_missing")
            elif cases and retrieval_fn is not None:
                for case in cases:
                    query = str(case.get("query", ""))
                    expected = str(case.get("expected_doc_id", ""))
                    top_k = int(case.get("top_k", 5))
                    if not query or not expected:
                        continue
                    try:
                        retrieved = retrieval_fn(query, top_k)
                    except Exception as e:
                        errors.append(f"retrieval_failed: query={query!r} err={e}")
                        continue
                    if expected in retrieved:
                        n_passed += 1
                    else:
                        errors.append(
                            f"golden_miss: query={query!r} expected={expected} "
                            f"retrieved={retrieved[:5]}"
                        )

    passed = (not errors) and chunk_stable
    logger.info(
        "rag_gate_done",
        passed=passed,
        chunk_stable=chunk_stable,
        golden_passed=n_passed,
        golden_total=n_total,
    )

    return RAGGateResult(
        passed=passed,
        chunk_hash_stable=chunk_stable,
        golden_top_k_passed=n_passed,
        golden_total=n_total,
        errors=errors,
    )

```


### `src/polybuild/concurrency/__init__.py` (24 lines)

```python
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

```


### `src/polybuild/concurrency/limiter.py` (290 lines)

```python
"""CLI concurrency limiter with severity-aware back-pressure.

Round 4 convergence (6/6):
    - One asyncio.Semaphore per provider family.
    - Conservative defaults; overridable via concurrency_limits.yaml or env vars.
    - Severity-differentiated waits:
        P0 → wait up to 180s, no fallback (medical safety: would change family).
        P1 → wait up to 30s, then fallback to OpenRouter if `fallback_fn` provided.
        P2 → if locked, drop the voice immediately (binôme suffit).
        P3 → drop immediately if any contention.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

import structlog
import yaml

logger = structlog.get_logger()

T = TypeVar("T")


# ────────────────────────────────────────────────────────────────
# PRIORITY & ERRORS
# ────────────────────────────────────────────────────────────────


class Priority(str, Enum):
    """Request severity for back-pressure decisions."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ConcurrencyError(RuntimeError):
    """Raised when a request cannot be served due to throttling/saturation."""

    def __init__(self, provider: str, reason: str):
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason


# ────────────────────────────────────────────────────────────────
# THROTTLE DETECTION
# ────────────────────────────────────────────────────────────────


_THROTTLE_PATTERN = re.compile(
    r"rate.?limit|429|quota|throttl|too\s+many\s+requests|retry-after|reset\s+in",
    re.IGNORECASE,
)


def is_throttle_error(message: str) -> bool:
    """Return True if `message` looks like a rate-limit/throttle error."""
    return bool(_THROTTLE_PATTERN.search(message or ""))


# ────────────────────────────────────────────────────────────────
# DEFAULT LIMITS (Round 4 averaged convergence)
# ────────────────────────────────────────────────────────────────


_DEFAULT_LIMITS: dict[str, int] = {
    "claude": 2,      # Grok=2, Qwen=3, Kimi=2, Gemini=2, ChatGPT=1, DeepSeek=3 → median=2
    "codex": 2,       # Grok=3, Qwen=3, Kimi=2, Gemini=2, ChatGPT=1, DeepSeek=4 → median=2
    "gemini": 4,      # Grok=2, Qwen=5, Kimi=3, Gemini=4, ChatGPT=1, DeepSeek=8 → median=4
    "kimi": 1,        # Grok=3, Qwen=2, Kimi=2, Gemini=1, ChatGPT=1, DeepSeek=5 → median=1.5 → 1 conservative
    "openrouter": 3,  # ChatGPT=3, DeepSeek=irrelevant, default=3
    "mistral": 2,     # EU direct API, generous
    "ollama": 1,      # Local NAS, single-threaded inference
}


# Override boost for high-throughput profiles (HELIA_algo, code_inedit_critique)
_PROFILE_BOOST: dict[str, dict[str, int]] = {
    "helia_algo": {"codex": 2, "gemini": 2, "openrouter": 4},
    "module_inedit_critique": {"codex": 2, "gemini": 2, "openrouter": 4},
}


# ────────────────────────────────────────────────────────────────
# CLILimiter
# ────────────────────────────────────────────────────────────────


@dataclass
class _ProviderStats:
    """Lightweight runtime stats for instrumentation."""

    invocations: int = 0
    throttle_events: int = 0
    fallback_events: int = 0
    drops: int = 0
    total_wait_s: float = 0.0


@dataclass
class CLILimiter:
    """Per-provider asyncio.Semaphore concurrency limiter.

    Usage:
        limiter = CLILimiter.from_yaml(profile="helia_algo")
        result = await limiter.run(
            "claude",
            lambda: my_async_call(),
            priority=Priority.P0,
            fallback_fn=lambda: openrouter_call(),
        )
    """

    limits: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_LIMITS))
    _semaphores: dict[str, asyncio.Semaphore] = field(default_factory=dict, init=False)
    _stats: dict[str, _ProviderStats] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._rebuild_semaphores()

    def _rebuild_semaphores(self) -> None:
        self._semaphores = {k: asyncio.Semaphore(max(1, v)) for k, v in self.limits.items()}
        for k in self.limits:
            self._stats.setdefault(k, _ProviderStats())

    @classmethod
    def from_yaml(
        cls,
        path: str | Path | None = None,
        profile: str | None = None,
    ) -> CLILimiter:
        """Build from `config/concurrency_limits.yaml`. Falls back to defaults."""
        limits = dict(_DEFAULT_LIMITS)

        if path is None:
            path = Path(__file__).resolve().parents[3] / "config" / "concurrency_limits.yaml"
        path = Path(path)
        if path.exists():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                yaml_limits = data.get("limits", {})
                if isinstance(yaml_limits, dict):
                    limits.update({k: int(v) for k, v in yaml_limits.items()})
            except (yaml.YAMLError, ValueError) as e:
                logger.warning("concurrency_yaml_parse_failed", error=str(e))

        if profile and profile in _PROFILE_BOOST:
            for k, v in _PROFILE_BOOST[profile].items():
                limits[k] = max(limits.get(k, 0), v)

        return cls(limits=limits)

    # ── Acquisition logic ──────────────────────────────────────────────

    def _resolve_provider(self, name_or_voice: str) -> str:
        """Map a voice id (e.g. `claude-opus-4.7`) to a provider family key."""
        if "/" in name_or_voice:
            family = name_or_voice.split("/")[0].lower()
            mapping = {
                "deepseek": "openrouter",
                "x-ai": "openrouter",
                "qwen": "openrouter",
                "openrouter": "openrouter",
                "mistral": "mistral",
            }
            return mapping.get(family, "openrouter")
        if name_or_voice.startswith("claude"):
            return "claude"
        if name_or_voice.startswith(("gpt", "codex")):
            return "codex"
        if name_or_voice.startswith("gemini"):
            return "gemini"
        if name_or_voice.startswith("kimi"):
            return "kimi"
        if name_or_voice.startswith("qwen") and ":" in name_or_voice:
            return "ollama"
        return name_or_voice

    async def run(
        self,
        provider_or_voice: str,
        coro_factory: Callable[[], Awaitable[T]],
        priority: Priority = Priority.P1,
        fallback_fn: Callable[[], Awaitable[T]] | None = None,
    ) -> T:
        """Execute `coro_factory()` under the provider's semaphore.

        Args:
            provider_or_voice: Either a family name ("claude") or a voice id ("claude-opus-4.7").
            coro_factory: Zero-arg callable returning a fresh coroutine each call.
                          Using a factory (not a coroutine) lets us retry/fallback safely.
            priority: P0..P3 — controls wait timeout and fallback behaviour.
            fallback_fn: Optional fallback factory used for P1/P2 only.

        Raises:
            ConcurrencyError on P0 timeout, or unrecoverable throttle.
        """
        provider = self._resolve_provider(provider_or_voice)
        sem = self._semaphores.get(provider)
        if sem is None:
            # Unknown provider: run unrestricted (no limiter applied)
            logger.debug("concurrency_unknown_provider_passthrough", provider=provider)
            return await coro_factory()

        stats = self._stats.setdefault(provider, _ProviderStats())

        # Severity-aware acquisition
        wait_timeout = {
            Priority.P0: 180.0,
            Priority.P1: 30.0,
            Priority.P2: 5.0,
            Priority.P3: 0.0,
        }[priority]

        # P3: never wait
        if priority == Priority.P3 and sem.locked():
            stats.drops += 1
            raise ConcurrencyError(provider, "P3 dropped on contention")

        t0 = time.time()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=wait_timeout if wait_timeout > 0 else 0.001)
        except asyncio.TimeoutError:
            wait = time.time() - t0
            stats.total_wait_s += wait

            if priority == Priority.P0:
                # No fallback for P0 (would change model family → medical/audit safety risk)
                raise ConcurrencyError(
                    provider,
                    f"P0 timeout after {wait:.1f}s — manual intervention required",
                )
            if priority in (Priority.P1, Priority.P2) and fallback_fn is not None:
                stats.fallback_events += 1
                logger.warning(
                    "concurrency_fallback_triggered",
                    provider=provider,
                    priority=priority.value,
                    waited_s=round(wait, 1),
                )
                return await fallback_fn()
            stats.drops += 1
            raise ConcurrencyError(
                provider,
                f"{priority.value} timeout after {wait:.1f}s, no fallback configured",
            )

        wait = time.time() - t0
        stats.total_wait_s += wait
        stats.invocations += 1

        try:
            result = await coro_factory()
            return result
        except Exception as e:
            if is_throttle_error(str(e)):
                stats.throttle_events += 1
                logger.warning(
                    "concurrency_throttle_detected",
                    provider=provider,
                    error=str(e)[:200],
                )
            raise
        finally:
            sem.release()

    # ── Instrumentation ────────────────────────────────────────────────

    def stats_summary(self) -> dict[str, dict[str, Any]]:
        """Return current stats for logging/ADR generation."""
        return {
            provider: {
                "invocations": s.invocations,
                "throttle_events": s.throttle_events,
                "fallback_events": s.fallback_events,
                "drops": s.drops,
                "total_wait_s": round(s.total_wait_s, 2),
            }
            for provider, s in self._stats.items()
        }

```


### `src/polybuild/security/__init__.py` (20 lines)

```python
"""Secrets management & secret-scanning hooks (Round 4 Faille 5).

Convergence 6/6 round 4:
    - `~/.polybuild/secrets.env` (chmod 600), source via `set -a; . ; set +a`.
    - `.gitleaks.toml` minimal allowlist + custom regex rules.
    - Pre-commit hook calling gitleaks before any commit.
    - CLI tokens (claude/codex/gemini/kimi) handled by the tools natively.

The actual scanning is delegated to gitleaks; this module only provides
helpers to load secrets at runtime and validate the secrets file mode.
"""

from polybuild.security.secrets_loader import (
    SecretsError,
    ensure_secrets_file_locked,
    load_secrets,
)

__all__ = ["SecretsError", "ensure_secrets_file_locked", "load_secrets"]

```


### `src/polybuild/security/secrets_loader.py` (110 lines)

```python
"""Load secrets from ~/.polybuild/secrets.env at runtime.

Convergence round 4 (6/6):
    - File must be chmod 600 (owner read/write only).
    - Loaded into os.environ via dotenv-style parsing (no shell needed).
    - Refuses to load if mode is too permissive (group/world readable).
    - Logs which keys are loaded but never their values.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import structlog

logger = structlog.get_logger()


SECRETS_PATH = Path.home() / ".polybuild" / "secrets.env"


class SecretsError(RuntimeError):
    """Raised when secrets loading fails."""


def ensure_secrets_file_locked(path: Path | None = None) -> bool:
    """Verify the secrets file exists and has restrictive permissions (mode 0600).

    Returns True if file is properly locked. False (and logs) if file missing.
    Raises SecretsError if file exists but is too permissive.
    """
    p = path or SECRETS_PATH
    if not p.exists():
        logger.info("secrets_file_not_found", path=str(p))
        return False

    st = p.stat()
    # On macOS/Linux, check group/world bits are clear.
    bad_bits = stat.S_IRWXG | stat.S_IRWXO
    if st.st_mode & bad_bits:
        raise SecretsError(
            f"{p} has permissive mode {oct(st.st_mode & 0o777)} — "
            f"run `chmod 600 {p}` to lock it down"
        )
    return True


def load_secrets(
    path: Path | None = None,
    *,
    overwrite: bool = False,
    require_lock: bool = True,
) -> list[str]:
    """Parse ~/.polybuild/secrets.env and inject into os.environ.

    Args:
        path: Override path (default: ~/.polybuild/secrets.env).
        overwrite: If True, replaces existing env vars. Default False (env wins).
        require_lock: If True, raises if file mode is permissive.

    Returns:
        List of keys loaded (values never logged).
    """
    p = path or SECRETS_PATH
    if not p.exists():
        return []

    if require_lock:
        ensure_secrets_file_locked(p)

    loaded: list[str] = []
    for line_num, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Allow `export KEY=val` and `KEY=val`
        if line.startswith("export "):
            line = line[len("export ") :]

        if "=" not in line:
            logger.warning("secrets_line_skipped", line_num=line_num)
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        # Strip matching quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if not key:
            continue
        if not overwrite and key in os.environ:
            continue

        os.environ[key] = value
        loaded.append(key)

    if loaded:
        logger.info("secrets_loaded", n=len(loaded), keys=loaded)

    return loaded


__all__ = ["SECRETS_PATH", "SecretsError", "ensure_secrets_file_locked", "load_secrets"]

```


### `src/polybuild/phases/phase_8_prod_smoke.py` (422 lines)

```python
"""Phase 8 — Production smoke (Round 4 Faille 4 finalisé).

Convergence round 4 (6/6) sur Option B :
    1. git tag `polybuild/run-{run_id}-pre` AVANT toute modification prod.
    2. Worktree Git séparé + Docker staging avec ports décalés (+10000) et
       volumes de prod montés en `:ro`.
    3. Phase 8 smoke = 5 minutes de monitoring + N requêtes golden.
    4. Sur échec → rollback automatique via `git reset --hard <tag-pre>`.

Désaccord majeur sur le seuil de dégradation accepté :
    - DeepSeek : 0% strict (réponses bit-à-bit identiques sur RAG déterministe).
    - Grok / Qwen / Kimi / Gemini / ChatGPT : 5% latence + 0% erreur protocolaire.
Compromis retenu : 0% MCP errors + 5% latence p95 + 0% missing critical results.

Phase 9 cleanup (bonus Gemini) intégrée comme bloc `finally:` strict.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# MODELS
# ────────────────────────────────────────────────────────────────


class GoldenQuery(BaseModel):
    """A single golden query for production smoke."""

    name: str
    method: str
    params: dict = {}
    expected_status: int = 200
    expected_min_results: int | None = None  # for list-returning queries
    expected_hash: str | None = None  # bit-exact match if RAG deterministic


class SmokeQueryResult(BaseModel):
    """Outcome of a single golden query."""

    query_name: str
    passed: bool
    latency_ms: float
    error: str | None = None
    response_hash: str | None = None


class SmokeVerdict(BaseModel):
    """Final verdict from Phase 8 production smoke."""

    passed: bool
    n_queries: int
    n_passed: int
    error_rate: float  # fraction of failed queries
    latency_p95_ms: float
    error_rate_threshold: float
    latency_increase_threshold: float
    query_results: list[SmokeQueryResult]
    rollback_triggered: bool = False
    notes: list[str] = []


# ────────────────────────────────────────────────────────────────
# GIT TAG / ROLLBACK HELPERS
# ────────────────────────────────────────────────────────────────


def _git(args: list[str], cwd: Path | str = ".") -> tuple[int, str]:
    """Run a git command, return (returncode, output)."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def tag_pre_run(run_id: str, repo_dir: Path | str = ".") -> str:
    """Create a `polybuild/run-{run_id}-pre` tag at HEAD for rollback."""
    tag = f"polybuild/run-{run_id}-pre"
    rc, out = _git(["tag", "-f", tag, "HEAD"], cwd=repo_dir)
    if rc != 0:
        logger.warning("pre_tag_failed", tag=tag, output=out)
    else:
        logger.info("pre_tag_created", tag=tag)
    return tag


def rollback_to_tag(tag: str, repo_dir: Path | str = ".") -> bool:
    """Hard-reset to a tag and force the working tree back."""
    rc, out = _git(["reset", "--hard", tag], cwd=repo_dir)
    if rc != 0:
        logger.error("rollback_failed", tag=tag, output=out)
        return False
    logger.warning("rollback_completed", tag=tag)
    return True


# ────────────────────────────────────────────────────────────────
# GOLDEN QUERY EXECUTION
# ────────────────────────────────────────────────────────────────


async def _execute_golden(
    endpoint_url: str,
    query: GoldenQuery,
    timeout_s: float = 10.0,
) -> SmokeQueryResult:
    """Execute a single golden query against an HTTP/JSON-RPC endpoint."""
    try:
        import httpx
    except ImportError:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=0.0,
            error="httpx_unavailable",
        )

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": query.method,
        "params": query.params,
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(endpoint_url, json=payload)
        latency_ms = (time.time() - t0) * 1000.0
    except httpx.HTTPError as e:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=(time.time() - t0) * 1000.0,
            error=f"http_error: {e}",
        )

    if resp.status_code != query.expected_status:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=latency_ms,
            error=f"status={resp.status_code} != expected={query.expected_status}",
        )

    try:
        body = resp.json()
    except json.JSONDecodeError:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=latency_ms,
            error="invalid_json_response",
        )

    if "error" in body:
        return SmokeQueryResult(
            query_name=query.name,
            passed=False,
            latency_ms=latency_ms,
            error=f"jsonrpc_error: {body['error']}",
        )

    response_hash: str | None = None
    result = body.get("result", {})

    # Min results check (for list-returning queries)
    if query.expected_min_results is not None:
        # Try common list locations
        items = None
        if isinstance(result, list):
            items = result
        elif isinstance(result, dict):
            for key in ("items", "results", "tools", "articles", "data"):
                if isinstance(result.get(key), list):
                    items = result[key]
                    break
        if items is None or len(items) < query.expected_min_results:
            return SmokeQueryResult(
                query_name=query.name,
                passed=False,
                latency_ms=latency_ms,
                error=f"min_results not met (got {len(items) if items else 0})",
            )

    # Hash match (for fully deterministic responses)
    if query.expected_hash is not None:
        canonical = json.dumps(result, sort_keys=True, ensure_ascii=False)
        response_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if response_hash != query.expected_hash:
            return SmokeQueryResult(
                query_name=query.name,
                passed=False,
                latency_ms=latency_ms,
                response_hash=response_hash,
                error="hash_mismatch_with_baseline",
            )

    return SmokeQueryResult(
        query_name=query.name,
        passed=True,
        latency_ms=latency_ms,
        response_hash=response_hash,
    )


# ────────────────────────────────────────────────────────────────
# PHASE 8 ENTRY
# ────────────────────────────────────────────────────────────────


async def phase_8_production_smoke(
    endpoint_url: str,
    golden_queries: list[GoldenQuery],
    baseline_latency_p95_ms: float | None = None,
    error_rate_threshold: float = 0.0,  # 0% MCP errors (round 4 strict)
    latency_increase_threshold: float = 0.05,  # 5% latency degradation
    monitoring_window_s: int = 300,  # 5 minutes (round 4)
    sample_interval_s: int = 30,
    rollback_tag: str | None = None,
    repo_dir: Path | str = ".",
) -> SmokeVerdict:
    """Run production smoke test against deployed staging endpoint.

    Procedure:
        1. For `monitoring_window_s` seconds, sample golden queries every
           `sample_interval_s` seconds.
        2. Aggregate error rate and p95 latency.
        3. Compare to thresholds. If exceeded → trigger rollback (if tag provided).

    Args:
        endpoint_url: JSON-RPC endpoint of the staging MCP/server.
        golden_queries: List of golden queries to execute repeatedly.
        baseline_latency_p95_ms: If provided, latency_increase_threshold is
                                 measured against this value.
        error_rate_threshold: Maximum acceptable error rate (default 0.0 = strict).
        latency_increase_threshold: Maximum acceptable latency increase fraction.
        monitoring_window_s: Total monitoring duration (default 5 min).
        sample_interval_s: Time between full golden suite executions.
        rollback_tag: If provided and smoke fails, run `git reset --hard <tag>`.
        repo_dir: Repository directory for the rollback.
    """
    logger.info(
        "phase_8_start",
        endpoint=endpoint_url,
        n_queries=len(golden_queries),
        window_s=monitoring_window_s,
    )

    all_results: list[SmokeQueryResult] = []
    end_time = time.time() + monitoring_window_s

    while time.time() < end_time:
        round_results = await asyncio.gather(
            *(_execute_golden(endpoint_url, q) for q in golden_queries),
            return_exceptions=False,
        )
        all_results.extend(round_results)

        # Early abort if catastrophic
        recent_errors = sum(1 for r in round_results if not r.passed)
        if recent_errors == len(round_results) and recent_errors > 0:
            logger.error("phase_8_catastrophic_round_aborting_early")
            break

        await asyncio.sleep(sample_interval_s)

    n_total = len(all_results)
    n_passed = sum(1 for r in all_results if r.passed)
    error_rate = (n_total - n_passed) / n_total if n_total else 1.0
    latencies = sorted(r.latency_ms for r in all_results if r.passed)
    p95_idx = int(0.95 * len(latencies)) if latencies else 0
    latency_p95 = latencies[p95_idx] if latencies else 0.0

    notes: list[str] = []
    failed_queries: list[str] = []

    threshold_hit_error = error_rate > error_rate_threshold
    if threshold_hit_error:
        notes.append(f"error_rate {error_rate:.3f} > threshold {error_rate_threshold:.3f}")
        failed_queries = sorted({r.query_name for r in all_results if not r.passed})
        notes.append(f"failed_queries: {failed_queries[:5]}")

    threshold_hit_latency = False
    if baseline_latency_p95_ms is not None and baseline_latency_p95_ms > 0:
        increase = (latency_p95 - baseline_latency_p95_ms) / baseline_latency_p95_ms
        if increase > latency_increase_threshold:
            threshold_hit_latency = True
            notes.append(
                f"latency_p95 {latency_p95:.1f}ms vs baseline "
                f"{baseline_latency_p95_ms:.1f}ms (+{increase:.1%}) > "
                f"threshold +{latency_increase_threshold:.1%}"
            )

    passed = not (threshold_hit_error or threshold_hit_latency)
    rollback_triggered = False

    if not passed and rollback_tag:
        rollback_triggered = rollback_to_tag(rollback_tag, repo_dir)
        if rollback_triggered:
            notes.append(f"rollback_executed to {rollback_tag}")
        else:
            notes.append(f"ROLLBACK_FAILED tag={rollback_tag} — manual intervention")

    logger.info(
        "phase_8_done",
        passed=passed,
        n_total=n_total,
        n_passed=n_passed,
        error_rate=round(error_rate, 4),
        latency_p95_ms=round(latency_p95, 1),
        rollback=rollback_triggered,
    )

    return SmokeVerdict(
        passed=passed,
        n_queries=n_total,
        n_passed=n_passed,
        error_rate=error_rate,
        latency_p95_ms=latency_p95,
        error_rate_threshold=error_rate_threshold,
        latency_increase_threshold=latency_increase_threshold,
        query_results=all_results,
        rollback_triggered=rollback_triggered,
        notes=notes,
    )


# ────────────────────────────────────────────────────────────────
# PHASE 9 CLEANUP (Bonus Gemini)
# ────────────────────────────────────────────────────────────────


def phase_9_cleanup(
    run_id: str,
    staging_dir: Path | str | None = None,
    docker_containers: list[str] | None = None,
    repo_dir: Path | str = ".",
) -> dict[str, Any]:
    """Always-run cleanup. Removes staging worktree, kills containers, prunes cache.

    Should be called from a `finally:` block in the orchestrator regardless of
    run outcome (Gemini's bonus, accepted by all 6 round-4 models implicitly).
    """
    report: dict[str, Any] = {
        "containers_removed": 0,
        "worktree_removed": False,
        "uv_cache_cleaned": False,
        "errors": [],
    }

    # 1. Remove staging Docker containers
    for container in docker_containers or []:
        rc = subprocess.run(
            ["docker", "rm", "-f", container],
            capture_output=True,
            check=False,
        ).returncode
        if rc == 0:
            report["containers_removed"] += 1
        else:
            report["errors"].append(f"docker_rm_failed: {container}")

    # 2. Remove git worktree
    if staging_dir:
        staging_path = Path(staging_dir)
        if staging_path.exists():
            rc, out = _git(
                ["worktree", "remove", "-f", str(staging_path)], cwd=repo_dir
            )
            if rc == 0:
                report["worktree_removed"] = True
            else:
                # Force fallback: rm -rf the directory + worktree prune
                try:
                    shutil.rmtree(staging_path)
                    _git(["worktree", "prune"], cwd=repo_dir)
                    report["worktree_removed"] = True
                except OSError as e:
                    report["errors"].append(f"rmtree_failed: {e}")

    # 3. Clean uv cache (best-effort, non-blocking)
    try:
        rc = subprocess.run(
            ["uv", "cache", "clean"], capture_output=True, check=False
        ).returncode
        report["uv_cache_cleaned"] = rc == 0
    except FileNotFoundError:
        # uv not available — ignore
        pass

    logger.info("phase_9_cleanup_done", run_id=run_id, **report)
    return report


__all__ = [
    "GoldenQuery",
    "SmokeQueryResult",
    "SmokeVerdict",
    "phase_8_production_smoke",
    "phase_9_cleanup",
    "rollback_to_tag",
    "tag_pre_run",
]

```


### `scripts/deploy_staging.sh` (124 lines)

```bash
#!/usr/bin/env bash
# scripts/deploy_staging.sh — Round 4 Faille 4 finalisé
#
# Synthèse des 6 modèles round 4 :
#   - Worktree Git séparé (Gemini, Kimi, DeepSeek, ChatGPT)
#   - Docker staging avec ports décalés +10000 (DeepSeek, Kimi)
#   - Volumes prod montés en :ro (DeepSeek, ChatGPT, Gemini)
#   - Limites CPU/RAM hard pour ne pas pénaliser la prod (Qwen)
#   - Tag Git polybuild/run-{id}-pre AVANT toute modif (6/6)
#   - Phase 8 smoke obligatoire avant promote (6/6)
#   - Cleanup en bloc finally: (Gemini, complété par Phase 9)
#
# Usage:
#   ./deploy_staging.sh <run_id> <server_name> [<server_image>]
# Example:
#   ./deploy_staging.sh 2026-05-03_140000_a4f7 sstinfo sstinfo:latest

set -euo pipefail

RUN_ID="${1:?usage: deploy_staging.sh <run_id> <server_name> [<image>]}"
SERVER="${2:?missing server name}"
IMAGE="${3:-${SERVER}:latest}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_DIR="${REPO_ROOT}/.worktrees/staging-${RUN_ID}"
STAGING_BRANCH="polybuild/run-${RUN_ID}"
PRE_TAG="polybuild/run-${RUN_ID}-pre"
CONTAINER_NAME="polybuild-stg-${SERVER}-${RUN_ID//[^a-zA-Z0-9]/_}"

# Lecture du port prod (convention : .prod_port dans le dossier du serveur)
PROD_PORT_FILE="${REPO_ROOT}/services/${SERVER}/.prod_port"
if [[ -f "${PROD_PORT_FILE}" ]]; then
    PROD_PORT="$(cat "${PROD_PORT_FILE}")"
else
    PROD_PORT="8716"  # default SSTinfo
fi
STAGING_PORT="$(( PROD_PORT + 10000 ))"

echo "━━━ POLYBUILD deploy_staging ━━━"
echo "  run_id       : ${RUN_ID}"
echo "  server       : ${SERVER} (image=${IMAGE})"
echo "  branch       : ${STAGING_BRANCH}"
echo "  pre_tag      : ${PRE_TAG}"
echo "  staging_port : ${STAGING_PORT} (prod was ${PROD_PORT})"
echo "  worktree     : ${WORKTREE_DIR}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cleanup() {
    local rc=$?
    echo "[cleanup] rc=$rc — removing staging artefacts"
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
    if [[ -d "${WORKTREE_DIR}" ]]; then
        git -C "${REPO_ROOT}" worktree remove -f "${WORKTREE_DIR}" 2>/dev/null || rm -rf "${WORKTREE_DIR}"
        git -C "${REPO_ROOT}" worktree prune || true
    fi
    exit $rc
}
trap cleanup EXIT INT TERM

# ── 1. Pre-tag for rollback (6/6 convergence) ────────────────────────
echo "[1/5] Tagging current HEAD as rollback point..."
git -C "${REPO_ROOT}" tag -f "${PRE_TAG}" HEAD
echo "      → ${PRE_TAG}"

# ── 2. Worktree isolated ─────────────────────────────────────────────
echo "[2/5] Creating worktree..."
git -C "${REPO_ROOT}" worktree add -B "${STAGING_BRANCH}" "${WORKTREE_DIR}" HEAD

# ── 3. Docker staging with RO prod volumes + resource caps ───────────
echo "[3/5] Starting staging container..."
PROD_DATA_DIR="${REPO_ROOT}/services/${SERVER}/data"
if [[ ! -d "${PROD_DATA_DIR}" ]]; then
    echo "      WARN: ${PROD_DATA_DIR} not found, container will start without data volume"
    PROD_DATA_MOUNT=""
else
    PROD_DATA_MOUNT="-v ${PROD_DATA_DIR}:/app/data:ro"
fi

# shellcheck disable=SC2086
docker run -d \
    --name "${CONTAINER_NAME}" \
    --cpus="1" \
    --memory="1g" \
    -p "${STAGING_PORT}:${PROD_PORT}" \
    ${PROD_DATA_MOUNT} \
    -v "${WORKTREE_DIR}:/app/src:ro" \
    -e POLYBUILD_STAGING=1 \
    -e SQLITE_READONLY=1 \
    -e QDRANT_READONLY=1 \
    -e MCP_PORT="${PROD_PORT}" \
    "${IMAGE}"

# ── 4. Wait for healthy ──────────────────────────────────────────────
echo "[4/5] Waiting for staging to become healthy..."
HEALTHY=0
for i in $(seq 1 20); do
    if curl -sf "http://localhost:${STAGING_PORT}/health" >/dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    sleep 1
done
if [[ "${HEALTHY}" -eq 0 ]]; then
    echo "      ERROR: staging not healthy after 20s"
    docker logs --tail 30 "${CONTAINER_NAME}" || true
    exit 1
fi
echo "      → staging healthy at http://localhost:${STAGING_PORT}"

# ── 5. Phase 8 smoke ─────────────────────────────────────────────────
echo "[5/5] Running Phase 8 production smoke..."
if ! uv run python -m polybuild.phases.phase_8_prod_smoke \
    --endpoint "http://localhost:${STAGING_PORT}/jsonrpc" \
    --golden "${REPO_ROOT}/tests/golden/${SERVER}_smoke.json" \
    --rollback-tag "${PRE_TAG}" \
    --window-s 300; then
    echo "      ✘ Phase 8 smoke FAILED — rollback already triggered"
    exit 1
fi

echo "✔ Staging validated. Promote with:"
echo "    git checkout main && git merge --ff-only ${STAGING_BRANCH} && git tag polybuild/run-${RUN_ID}-ok"
exit 0

```


### `skills/polybuild/SKILL.md` (182 lines)

```markdown
# /polybuild — Skill Claude Code

> Lance et supervise des runs POLYBUILD v3 en arrière-plan via tmux.

**Convergence round 4 (6/6) sur tmux** comme orchestrateur background :
- Survives Claude Code disconnections and SSH drops.
- Inspectable via `tmux capture-pane`.
- Killable cleanly via `tmux kill-session`.
- Fallback `screen` puis `nohup` si tmux indisponible (Kimi + DeepSeek).

## Commandes

### `/polybuild run --spec <spec.yaml> [--profile <name>]`
Lance un run POLYBUILD en background.

```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)"
mkdir -p .polybuild/runs .polybuild/logs

# Backend selection: tmux > screen > nohup (round 4 fallback chain)
if command -v tmux >/dev/null 2>&1; then
  tmux new-session -d -s "polybuild-${RUN_ID}" \
    "set -a; \
     [ -f \"$HOME/.polybuild/secrets.env\" ] && . \"$HOME/.polybuild/secrets.env\"; \
     set +a; \
     uv run polybuild run --spec '$1' --run-id '${RUN_ID}' \
       2>&1 | tee '.polybuild/logs/${RUN_ID}.log'"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: tmux session 'polybuild-${RUN_ID}'"
elif command -v screen >/dev/null 2>&1; then
  screen -dmS "polybuild-${RUN_ID}" \
    bash -c "set -a; [ -f \"\$HOME/.polybuild/secrets.env\" ] && . \"\$HOME/.polybuild/secrets.env\"; set +a; \
             uv run polybuild run --spec '$1' --run-id '${RUN_ID}' 2>&1 | tee '.polybuild/logs/${RUN_ID}.log'"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: screen session 'polybuild-${RUN_ID}'"
else
  # nohup last-resort fallback (no attach, no inspect)
  nohup bash -c "set -a; [ -f \"\$HOME/.polybuild/secrets.env\" ] && . \"\$HOME/.polybuild/secrets.env\"; set +a; \
                 uv run polybuild run --spec '$1' --run-id '${RUN_ID}'" \
    > ".polybuild/logs/${RUN_ID}.log" 2>&1 &
  echo "$!" > ".polybuild/runs/${RUN_ID}.pid"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: nohup PID $(cat .polybuild/runs/${RUN_ID}.pid)"
fi

echo "Run ${RUN_ID} started. Check status with /polybuild status ${RUN_ID}"
```

### `/polybuild status [<run_id>]`
État d'un run. Si run_id omis, utilise le dernier.

```bash
RUN_ID="${1:-$(cat .polybuild/last_run 2>/dev/null)}"
[ -z "${RUN_ID}" ] && { echo "No run_id and no last_run found"; exit 1; }

if command -v tmux >/dev/null 2>&1 && tmux has-session -t "polybuild-${RUN_ID}" 2>/dev/null; then
  echo "Status: RUNNING (tmux)"
elif command -v screen >/dev/null 2>&1 && screen -list | grep -q "polybuild-${RUN_ID}"; then
  echo "Status: RUNNING (screen)"
elif [ -f ".polybuild/runs/${RUN_ID}.pid" ] && kill -0 "$(cat .polybuild/runs/${RUN_ID}.pid)" 2>/dev/null; then
  echo "Status: RUNNING (nohup pid=$(cat .polybuild/runs/${RUN_ID}.pid))"
else
  echo "Status: STOPPED"
fi

# Last 20 lines of log for context
echo "─── Last log lines ───"
tail -n 20 ".polybuild/logs/${RUN_ID}.log" 2>/dev/null || echo "(no log file)"
```

### `/polybuild logs [<run_id>] [--follow]`
Affiche les logs d'un run.

```bash
RUN_ID="${1:-$(cat .polybuild/last_run 2>/dev/null)}"
LOG=".polybuild/logs/${RUN_ID}.log"
[ ! -f "${LOG}" ] && { echo "No log for ${RUN_ID}"; exit 1; }

if [ "${2:-}" = "--follow" ]; then
  tail -F "${LOG}"
else
  tail -n 200 "${LOG}"
fi
```

### `/polybuild attach <run_id>`
Attache au tmux/screen interactivement (humain uniquement).

```bash
RUN_ID="${1:?run_id required}"
if command -v tmux >/dev/null 2>&1; then
  tmux attach -t "polybuild-${RUN_ID}"
elif command -v screen >/dev/null 2>&1; then
  screen -r "polybuild-${RUN_ID}"
else
  echo "No tmux/screen — use /polybuild logs instead"
fi
```

### `/polybuild abort <run_id>`
Tue un run et nettoie ses ressources (Phase 9 cleanup).

```bash
RUN_ID="${1:?run_id required}"
echo "Aborting ${RUN_ID}..."

# Kill tmux/screen/nohup
tmux kill-session -t "polybuild-${RUN_ID}" 2>/dev/null || true
screen -X -S "polybuild-${RUN_ID}" quit 2>/dev/null || true
if [ -f ".polybuild/runs/${RUN_ID}.pid" ]; then
  kill "$(cat .polybuild/runs/${RUN_ID}.pid)" 2>/dev/null || true
fi

# Trigger Phase 9 cleanup explicitly
uv run python -c "
from polybuild.phases.phase_8_prod_smoke import phase_9_cleanup
phase_9_cleanup('${RUN_ID}')
" 2>/dev/null || true

echo "Aborted ${RUN_ID}"
```

### `/polybuild list`
Liste tous les runs récents.

```bash
mkdir -p .polybuild/logs
echo "Recent runs:"
ls -t .polybuild/logs/ 2>/dev/null | head -10 | while read -r f; do
  RUN_ID="${f%.log}"
  if tmux has-session -t "polybuild-${RUN_ID}" 2>/dev/null; then
    STATUS="RUNNING"
  else
    STATUS="DONE   "
  fi
  echo "  ${STATUS}  ${RUN_ID}"
done
```

### `/polybuild secrets-check`
Vérifie l'état du fichier de secrets.

```bash
SECRETS="$HOME/.polybuild/secrets.env"
if [ ! -f "${SECRETS}" ]; then
  echo "No secrets file at ${SECRETS}"
  echo "Create one with:"
  echo "  mkdir -p ~/.polybuild && touch ~/.polybuild/secrets.env && chmod 600 ~/.polybuild/secrets.env"
  exit 1
fi

MODE=$(stat -c '%a' "${SECRETS}" 2>/dev/null || stat -f '%A' "${SECRETS}")
if [ "${MODE}" != "600" ] && [ "${MODE}" != "0600" ]; then
  echo "WARN: ${SECRETS} mode is ${MODE} (expected 600)"
  echo "Run: chmod 600 ${SECRETS}"
  exit 1
fi
echo "OK: ${SECRETS} (mode 600)"
echo "Loaded keys (names only):"
grep -E '^[A-Z_]+=' "${SECRETS}" | sed 's/=.*//' | sed 's/^/  - /'
```

---

## Convention de fichiers

```
.polybuild/
├── last_run                  # ID du dernier run lancé
├── logs/<run_id>.log         # logs complets (Phase -1 redacted)
├── runs/<run_id>/            # artefacts de run (specs, audits, ADRs)
│   ├── status.json
│   ├── spec_final.json
│   ├── audit.json
│   └── checkpoint_phase_*.json
└── runs/<run_id>.pid         # PID (uniquement pour fallback nohup)

~/.polybuild/
├── secrets.env               # chmod 600 — clés API (jamais commité)
└── safe_terms.yaml           # whitelist termes métier (round 4 DeepSeek)
```

```


### `config/concurrency_limits.yaml` (55 lines)

```yaml
# config/concurrency_limits.yaml
# Per-provider concurrency caps (Round 4 Faille 3 finalisé).
#
# Convergence 6/6 sur le principe des sémaphores asyncio.
# Désaccord sur les valeurs absolues : médiane des 6 modèles utilisée.
#
# Comment ces limites ont été obtenues (mai 2026) :
#   - claude=2  : Claude Max 20x — quotas hebdomadaires opaques, 2 concurrent sûr
#                 (DeepSeek=3, Grok=2, Qwen=3, Kimi=2, Gemini=2, ChatGPT=1 → médiane=2)
#   - codex=2   : ChatGPT Pro — limites 5h non documentées clairement
#                 (DeepSeek=4, Grok=3, Qwen=3, Kimi=2, Gemini=2, ChatGPT=1 → médiane=2)
#   - gemini=4  : Google One Pro — 60 req/min (la plus permissive)
#                 (DeepSeek=8, Grok=2, Qwen=5, Kimi=3, Gemini=4, ChatGPT=1 → médiane=4)
#   - kimi=1    : Kimi Allegretto — non documenté, 30 concurrence max théorique mais 429 sous plafond
#                 (DeepSeek=5, Grok=3, Qwen=2, Kimi=2, Gemini=1, ChatGPT=1 → médiane=2 → 1 conservatif)
#   - openrouter=3 : payant à la requête, limite locale uniquement pour budget
#   - mistral=2 : api.mistral.ai direct, EU souveraineté, limite généreuse
#   - ollama=1  : NAS DS224+ J4125, inférence single-thread

limits:
  claude: 2
  codex: 2
  gemini: 4
  kimi: 1
  openrouter: 3
  mistral: 2
  ollama: 1

# Profils qui boostent certaines limites pour throughput accru
# (HELIA_algo et code_inedit_critique parallélisent davantage de voix)
profile_boosts:
  helia_algo:
    codex: 2
    gemini: 2
    openrouter: 4
  module_inedit_critique:
    codex: 2
    gemini: 2
    openrouter: 4

# Politique back-pressure (réf. limiter.py — informatif, hard-codé aussi)
back_pressure:
  P0:
    wait_timeout_s: 180
    fallback: false        # P0 = jamais de fallback (changerait la famille → risque audit/médical)
  P1:
    wait_timeout_s: 30
    fallback: true         # → OpenRouter équivalent si configuré
  P2:
    wait_timeout_s: 5
    fallback: true
  P3:
    wait_timeout_s: 0
    fallback: false        # P3 = drop immédiat

```


### `.gitleaks.toml` (73 lines)

```toml
# .gitleaks.toml — POLYBUILD secrets policy (Round 4 Faille 5 finalisé)
#
# Synthèse round 4 (6/6 sur le principe gitleaks + allowlist stricte) :
#   - Allowlist limitée à ~/.polybuild/secrets.env et .polybuild/runs/*.log
#   - Custom rules pour clés OpenRouter, Mistral, et patterns génériques
#   - useDefault = true → conserve toutes les détections built-in (AWS, GCP, etc.)

title = "POLYBUILD secrets policy"

[extend]
useDefault = true

[allowlist]
description = "Allow local secrets file (chmod 600) and run logs"
paths = [
    '''^\.polybuild/secrets\.env$''',
    '''^\.polybuild/runs/.*\.log$''',
    '''^\.env\.example$''',
    '''^tests/fixtures/.*''',
]

# ────────────────────────────────────────────────────────────────────
# CUSTOM RULES (round 4 union)
# ────────────────────────────────────────────────────────────────────

[[rules]]
id = "openrouter-key"
description = "OpenRouter API key (sk-or-v1- prefix)"
regex = '''sk-or-v1-[A-Za-z0-9_-]{40,}'''
tags = ["key", "openrouter"]

[[rules]]
id = "anthropic-api-key"
description = "Anthropic API key"
regex = '''sk-ant-(api03|admin01|test01)-[A-Za-z0-9_-]{80,}'''
tags = ["key", "anthropic"]

[[rules]]
id = "openai-api-key"
description = "OpenAI / Codex API key"
regex = '''sk-(?:proj-)?[A-Za-z0-9_-]{40,}'''
tags = ["key", "openai"]

[[rules]]
id = "google-api-key"
description = "Google AIza key (Gemini)"
regex = '''AIza[0-9A-Za-z_-]{35}'''
tags = ["key", "google"]

[[rules]]
id = "mistral-api-key"
description = "Mistral API key"
regex = '''(?i)mistral[_-]?api[_-]?key\s*[:=]\s*["']?[A-Za-z0-9_\-]{30,}'''
tags = ["key", "mistral"]

[[rules]]
id = "huggingface-token"
description = "Hugging Face token"
regex = '''hf_[A-Za-z0-9]{30,}'''
tags = ["token", "huggingface"]

[[rules]]
id = "polybuild-secrets-elsewhere"
description = "Any KEY=value pattern resembling a token outside the allowed file"
regex = '''(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*["']?[A-Za-z0-9_\-]{32,}'''
tags = ["generic"]
[rules.allowlist]
paths = [
    '''^\.polybuild/secrets\.env$''',
    '''^\.env\.example$''',
    '''^tests/fixtures/.*''',
]

```


### `.pre-commit-config.yaml` (25 lines)

```yaml
# .pre-commit-config.yaml
# Round 4 Faille 5 — synthèse 6/6 sur gitleaks comme outil de scan secrets

repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.28.0
    hooks:
      - id: gitleaks

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-added-large-files
        args: ['--maxkb=500']

```


### `.env.example` (23 lines)

```bash
# ~/.polybuild/secrets.env — copy this file to ~/.polybuild/secrets.env and chmod 600
#
# Setup:
#   mkdir -p ~/.polybuild
#   cp .env.example ~/.polybuild/secrets.env
#   chmod 600 ~/.polybuild/secrets.env
#   # then fill in real values

# OpenRouter (irreplaceable for DeepSeek V4-Pro, Grok 4.20, etc.)
OPENROUTER_API_KEY=sk-or-v1-CHANGE_ME

# Mistral EU direct (medical_medium / medical_high profiles)
MISTRAL_API_KEY=CHANGE_ME

# Optional: HuggingFace (for embedder model downloads)
# HF_TOKEN=hf_CHANGE_ME

# CLI tokens are managed natively by their tools — DO NOT put them here:
#   claude login
#   codex login
#   gemini login
#   kimi login

```


### `.gitignore` (45 lines)

```bash
# POLYBUILD .gitignore

# Secrets & local config
.polybuild/secrets.env
.polybuild/runs/*.log
.polybuild/runs/**/checkpoint_*.json
.polybuild/last_run
~/.polybuild/secrets.env
.env
.env.local

# Worktrees
.worktrees/
*.worktree

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Data (project-specific paths, override per project)
data/
*.sqlite
*.sqlite-shm
*.sqlite-wal
*.faiss
qdrant_storage/

```

---

## Critical dependencies (context for audit)

These files are needed to assess how round 4 modules are wired in. Audit them only if relevant to your findings on the round 4 modules.


### `src/polybuild/orchestrator.py` (379 lines)

```python
"""POLYBUILD v3 main orchestrator.

Chains all phases in sequence with checkpoint persistence.
Top-level entry point invoked by the CLI (`polybuild run ...`).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import structlog

from polybuild.models import (
    PolybuildRun,
    PrivacyLevel,
    RiskProfile,
    Severity,
    TokenUsage,
)
from polybuild.phases import (
    phase_0_spec,
    phase_2_generate,
    phase_3_score,
    phase_3b_grounding,
    phase_7_commit,
    select_voices,
)
from polybuild.phases.phase_4_audit import phase_4_audit
from polybuild.phases.phase_5_triade import phase_5_dispatch
from polybuild.phases.phase_6_validate import phase_6_validate

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# CHECKPOINT MANAGEMENT
# ────────────────────────────────────────────────────────────────


def save_checkpoint(run_id: str, phase: str, payload: dict, root: Path) -> None:
    """Atomically write a checkpoint."""
    checkpoint_dir = root / ".polybuild" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    target = checkpoint_dir / f"{run_id}_{phase}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    tmp.rename(target)


# ────────────────────────────────────────────────────────────────
# RUN ID GENERATION
# ────────────────────────────────────────────────────────────────


def generate_run_id() -> str:
    """Format: 2026-05-03_143022_a4f7."""
    import secrets
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{ts}_{suffix}"


# ────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ────────────────────────────────────────────────────────────────


async def run_polybuild(
    brief: str,
    profile_id: str,
    project_root: Path = Path("."),
    risk_profile: RiskProfile | None = None,
    project_ctx: dict | None = None,
    skip_commit: bool = False,
    skip_smoke: bool = False,
) -> PolybuildRun:
    """Execute the full POLYBUILD pipeline.

    Args:
        brief: free-text description of the task
        profile_id: routing profile (e.g. "module_inedit_critique", "helia_algo")
        project_root: Path to the user's project (where AGENTS.md lives)
        risk_profile: optional override (else inferred from profile)
        project_ctx: optional dict with `spec_yaml_path`, `declared_sensitivity`,
                     `extra_context_for_opus`, `phase_8_endpoint`, `phase_8_golden_queries`
        skip_commit: True for dry-runs (Phase 7 skipped)
        skip_smoke: True to skip Phase 8 production smoke

    Returns:
        PolybuildRun with all metadata, archived to disk.
    """
    run_id = generate_run_id()
    started_at = datetime.utcnow()
    artifacts_dir = project_root / ".polybuild" / "runs"

    if risk_profile is None:
        # Default: low sensitivity unless profile suggests otherwise
        sensitivity = (
            PrivacyLevel.HIGH if "medical_high" in profile_id
            else PrivacyLevel.MEDIUM if "medical_medium" in profile_id
            else PrivacyLevel.LOW if "medical_low" in profile_id
            else PrivacyLevel.LOW
        )
        risk_profile = RiskProfile(
            sensitivity=sensitivity,
            code_inedit_critique=("inedit_critique" in profile_id),
            requires_probe=("inedit_critique" in profile_id or "helia" in profile_id),
            excludes_openrouter=(sensitivity == PrivacyLevel.HIGH),
            excludes_us_cn_models=(sensitivity == PrivacyLevel.HIGH),
        )

    logger.info("polybuild_start", run_id=run_id, profile=profile_id)

    # ── Phase -1: privacy gate (Round 4 finalisé) ──
    from polybuild.phases.phase_minus_one_privacy import phase_minus_one_privacy_gate

    # spec.yaml lookup: convention is the brief file living next to spec.yaml,
    # or an explicit spec_yaml_path passed in via project_ctx.
    spec_yaml_path = (project_ctx or {}).get("spec_yaml_path")
    declared_sensitivity = (project_ctx or {}).get("declared_sensitivity")

    privacy_verdict = phase_minus_one_privacy_gate(
        text=brief,
        spec_path=spec_yaml_path,
        declared_sensitivity=declared_sensitivity,
    )
    save_checkpoint(
        run_id, "phase_minus_one", privacy_verdict.model_dump(mode="json"), project_root
    )

    if privacy_verdict.blocked:
        logger.error(
            "polybuild_blocked_by_privacy_gate",
            level=privacy_verdict.level,
            reason=privacy_verdict.reason,
        )
        raise RuntimeError(
            f"Phase -1 privacy gate BLOCKED: {privacy_verdict.reason}"
        )

    # If escalated, force EU/local routing for the rest of the run
    if privacy_verdict.level == "ESCALATE_PARANOIA":
        logger.warning(
            "phase_minus_one_paranoia_escalated",
            reason=privacy_verdict.reason,
        )
        risk_profile = risk_profile.model_copy(
            update={
                "excludes_openrouter": True,
                "excludes_us_cn_models": True,
                "sensitivity": PrivacyLevel.HIGH,
            }
        )

    # ── Phase 0: spec ──
    spec = await phase_0_spec(
        run_id=run_id,
        brief=brief,
        profile_id=profile_id,
        risk_profile=risk_profile,
        project_ctx=project_ctx,
        artifacts_dir=artifacts_dir,
    )
    save_checkpoint(run_id, "phase0", spec.model_dump(mode="json"), project_root)

    # ── Phase 1: voice selection ──
    voices = await select_voices(spec, config_root=Path(__file__).parent.parent.parent / "config")
    save_checkpoint(
        run_id, "phase1",
        {"voices": [v.model_dump() for v in voices]},
        project_root,
    )

    # ── Phase 2: parallel generation ──
    builder_results = await phase_2_generate(spec, voices)
    save_checkpoint(
        run_id, "phase2",
        {"results": [r.model_dump(mode="json") for r in builder_results]},
        project_root,
    )

    # ── Phase 3: scoring ──
    scores = await phase_3_score(builder_results)
    save_checkpoint(
        run_id, "phase3",
        {"scores": [s.model_dump() for s in scores]},
        project_root,
    )

    # ── Phase 3b: grounding ──
    grounding = await phase_3b_grounding(builder_results, project_root)
    save_checkpoint(
        run_id, "phase3b",
        {vid: [f.model_dump(mode="json") for f in fs] for vid, fs in grounding.items()},
        project_root,
    )

    # Determine winner (highest score, not disqualified, no critical grounding)
    eligible = [
        s for s in scores
        if not s.disqualified
        and len([f for f in grounding.get(s.voice_id, []) if f.severity == Severity.P0]) == 0
    ]
    if not eligible:
        logger.error("no_eligible_winner")
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
        )

    winner_score = eligible[0]
    winner_result = next(
        r for r in builder_results if r.voice_id == winner_score.voice_id
    )

    # ── Phase 4: audit ──
    audit = await phase_4_audit(
        winner_result,
        profile_id,
        risk_profile,
        config_root=Path(__file__).parent.parent.parent / "config",
    )
    save_checkpoint(run_id, "phase4", audit.model_dump(mode="json"), project_root)

    # ── Phase 5: triade ──
    fix_report = await phase_5_dispatch(audit, winner_result, risk_profile)
    save_checkpoint(run_id, "phase5", fix_report.model_dump(mode="json"), project_root)

    if fix_report.status == "blocked_p0":
        logger.error("polybuild_blocked_p0", run_id=run_id)
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
            audit=audit, fix_report=fix_report,
        )

    # ── Phase 6: validation ──
    validation = await phase_6_validate(spec, winner_result, artifacts_dir)
    save_checkpoint(run_id, "phase6", validation.model_dump(mode="json"), project_root)

    if not validation.passed:
        logger.error("polybuild_validation_failed", run_id=run_id, notes=validation.notes)
        return _build_aborted_run(
            run_id, profile_id, spec, builder_results, scores, started_at,
            audit=audit, fix_report=fix_report,
        )

    # Build run summary
    run = PolybuildRun(
        run_id=run_id,
        profile_id=profile_id,
        spec_hash=spec.spec_hash,
        voices_used=[v.voice_id for v in voices],
        winner_voice_id=winner_score.voice_id,
        scores={s.voice_id: s.score for s in scores},
        audit_findings_by_severity={
            sev.value: sum(1 for f in audit.findings if f.severity == sev)
            for sev in Severity
        },
        fix_iterations={
            fr.finding_ids[0] if fr.finding_ids else "auto": fr.iterations
            for fr in fix_report.results
        },
        domain_gates_passed=validation.domain_gates_passed,
        duration_total_sec=(datetime.utcnow() - started_at).total_seconds(),
        tokens=TokenUsage(),  # TODO: aggregate from adapters
        cost_eur_marginal=0.0,  # TODO: compute from usage
        final_status="committed",
        commit_sha=None,
        started_at=started_at,
        completed_at=None,
    )

    # ── Phase 7: commit ──
    if not skip_commit:
        commit_info = await phase_7_commit(run, project_root)
        run.commit_sha = commit_info.sha

    # ── Phase 8: prod smoke (Round 4 finalisé) ──
    if not skip_smoke and project_ctx and project_ctx.get("phase_8_endpoint"):
        from polybuild.phases.phase_8_prod_smoke import (
            GoldenQuery,
            phase_8_production_smoke,
            tag_pre_run,
        )

        endpoint = project_ctx["phase_8_endpoint"]
        golden_raw = project_ctx.get("phase_8_golden_queries", [])
        goldens = [GoldenQuery.model_validate(g) for g in golden_raw]

        if goldens:
            pre_tag = tag_pre_run(run_id, repo_dir=project_root)
            smoke_verdict = await phase_8_production_smoke(
                endpoint_url=endpoint,
                golden_queries=goldens,
                error_rate_threshold=float(project_ctx.get("phase_8_error_threshold", 0.0)),
                latency_increase_threshold=float(project_ctx.get("phase_8_latency_threshold", 0.05)),
                monitoring_window_s=int(project_ctx.get("phase_8_window_s", 300)),
                rollback_tag=pre_tag,
                repo_dir=project_root,
            )
            save_checkpoint(
                run_id, "phase8", smoke_verdict.model_dump(mode="json"), project_root
            )
            if not smoke_verdict.passed:
                run.final_status = "rolled_back"
                logger.error(
                    "polybuild_smoke_failed_rolled_back",
                    run_id=run_id,
                    notes=smoke_verdict.notes,
                )

    run.completed_at = datetime.utcnow()

    # ── Phase 9 cleanup (Bonus Gemini) ──
    # Always-run cleanup of staging worktrees + Docker containers + uv cache.
    try:
        from polybuild.phases.phase_8_prod_smoke import phase_9_cleanup

        staging_dir = project_root / ".worktrees" / f"staging-{run_id}"
        staging_containers = (project_ctx or {}).get("staging_containers", [])
        cleanup_report = phase_9_cleanup(
            run_id=run_id,
            staging_dir=staging_dir if staging_dir.exists() else None,
            docker_containers=staging_containers,
            repo_dir=project_root,
        )
        save_checkpoint(run_id, "phase9", cleanup_report, project_root)
    except Exception as e:
        logger.warning("phase_9_cleanup_swallowed", error=str(e))

    # Final archival
    final_path = artifacts_dir / run_id / "polybuild_run.json"
    final_path.write_text(run.model_dump_json(indent=2))

    logger.info(
        "polybuild_done",
        run_id=run_id,
        winner=run.winner_voice_id,
        duration=round(run.duration_total_sec, 1),
        committed=run.commit_sha is not None,
    )
    return run


# ────────────────────────────────────────────────────────────────
# ABORT HELPERS
# ────────────────────────────────────────────────────────────────


def _build_aborted_run(
    run_id: str,
    profile_id: str,
    spec,
    builder_results,
    scores,
    started_at,
    **kwargs,
) -> PolybuildRun:
    """Build a PolybuildRun in aborted state for early exits."""
    return PolybuildRun(
        run_id=run_id,
        profile_id=profile_id,
        spec_hash=spec.spec_hash,
        voices_used=[r.voice_id for r in builder_results],
        winner_voice_id=None,
        scores={s.voice_id: s.score for s in scores},
        audit_findings_by_severity={},
        fix_iterations={},
        domain_gates_passed=False,
        duration_total_sec=(datetime.utcnow() - started_at).total_seconds(),
        tokens=TokenUsage(),
        cost_eur_marginal=0.0,
        final_status="aborted",
        commit_sha=None,
        started_at=started_at,
        completed_at=datetime.utcnow(),
    )

```


### `src/polybuild/phases/phase_6_validate.py` (282 lines)

```python
"""Phase 6 — Final validation gates (general + domain-specific).

General gates: pytest, mypy --strict, ruff, bandit, gitleaks (re-run after Phase 5 fixes).

Domain gates (Round 4 finalisé) — convergence 5/6 :
    - validate_mcp: subprocess JSON-RPC stdio, initialize + tools/list + Pydantic schema
    - validate_sqlite_db: PRAGMA integrity_check + WAL mode + schema diff
    - validate_qdrant_collection: get_collection + dim match + sample query
    - validate_fts5_golden: golden queries with min_hits
    - validate_rag_smoke: chunk hash stability + golden retrieval

Decision Round 4: domain gate failure → BLOCKS commit (Phase 7). Aucun warn-only.
Convergence 5/6 (Grok, Qwen, Kimi, Gemini, ChatGPT bloquant ; DeepSeek nuance vers warn
pour SQLite optionnel mais s'aligne sur bloquant pour MCP/Qdrant/RAG).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import structlog
import yaml

from polybuild.models import (
    BuilderResult,
    Spec,
    ValidationVerdict,
)
from polybuild.phases.phase_3_score import run_general_gates

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# DOMAIN GATES MAP (Round 4 finalisé)
# ────────────────────────────────────────────────────────────────

# Default profile→gates mapping (loaded from routing.yaml at runtime if present).
DOMAIN_GATES_BY_PROFILE: dict[str, list[str]] = {
    "mcp_schema_change": ["mcp", "sqlite", "fts5"],
    "rag_ingestion_eval": ["sqlite", "fts5", "qdrant", "rag"],
    "parsing_pdf_medical": ["rag"],
    "oai_pmh_scraping": ["sqlite"],
    "module_standard_known": [],
    "module_inedit_critique": [],
    "helia_algo": [],
    "medical_low": [],
    "medical_medium": [],
    "medical_high": [],
    "devops_iac_scripts": [],
    "refactor_mecanique": [],
    "llm_as_judge": [],
    "post_polylens_fix": [],
    "documentation_adr": [],
}


def _load_domain_gates_from_routing(routing_path: Path | None = None) -> dict[str, list[str]]:
    """Override default mapping with routing.yaml if it has a `domain_gates_by_profile` key."""
    if routing_path is None:
        routing_path = Path(__file__).resolve().parents[3] / "config" / "routing.yaml"
    if not routing_path.exists():
        return DOMAIN_GATES_BY_PROFILE

    try:
        data = yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return DOMAIN_GATES_BY_PROFILE

    overrides: dict[str, list[str]] = {}
    profiles = data.get("profiles", {})
    for profile_id, profile_config in profiles.items():
        gates = profile_config.get("domain_gates")
        if isinstance(gates, list):
            overrides[profile_id] = list(gates)

    return {**DOMAIN_GATES_BY_PROFILE, **overrides}


# ────────────────────────────────────────────────────────────────
# DOMAIN GATE RUNNER (Round 4 finalisé)
# ────────────────────────────────────────────────────────────────


async def _run_single_domain_gate(
    gate_name: str,
    workdir: Path,
    gate_config: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Run a single domain gate by name. Returns (passed, errors).

    `gate_config` carries gate-specific parameters loaded from spec.yaml or routing.yaml
    (e.g. `mcp.server_cmd`, `sqlite.db_path`, `qdrant.collection`).
    """
    cfg = gate_config or {}

    if gate_name == "mcp":
        from polybuild.domain_gates.validate_mcp import validate_mcp_server

        server_cmd = cfg.get("server_cmd", ["uv", "run", "python", "-m", "server"])
        expected_tools = set(cfg.get("expected_tools", []))
        result = await validate_mcp_server(
            server_cmd=server_cmd,
            cwd=workdir,
            expected_tools=expected_tools or None,
            timeout_s=float(cfg.get("timeout_s", 30.0)),
        )
        return result.passed, result.errors

    if gate_name == "sqlite":
        from polybuild.domain_gates.validate_sqlite import validate_sqlite_db

        db_path = cfg.get("db_path")
        if not db_path:
            return False, ["sqlite_gate_no_db_path_configured"]
        result = validate_sqlite_db(
            db_path=db_path,
            schema_snapshot_path=cfg.get("schema_snapshot_path"),
            require_wal=bool(cfg.get("require_wal", True)),
        )
        return result.passed, result.errors

    if gate_name == "qdrant":
        from polybuild.domain_gates.validate_qdrant import validate_qdrant_collection

        url = cfg.get("url", "http://localhost:6333")
        collection = cfg.get("collection")
        if not collection:
            return False, ["qdrant_gate_no_collection_configured"]
        result = await validate_qdrant_collection(
            qdrant_url=url,
            collection=collection,
            expected_dim=int(cfg.get("expected_dim", 768)),
            min_points=int(cfg.get("min_points", 1)),
        )
        return result.passed, result.errors

    if gate_name == "fts5":
        from polybuild.domain_gates.validate_fts5 import validate_fts5_golden

        db_path = cfg.get("db_path")
        fts_table = cfg.get("fts_table")
        golden_path = cfg.get("golden_path")
        if not all([db_path, fts_table, golden_path]):
            return False, ["fts5_gate_missing_config"]
        result = validate_fts5_golden(
            db_path=db_path,
            fts_table=fts_table,
            golden_path=golden_path,
            require_golden_file=bool(cfg.get("require_golden_file", True)),
        )
        return result.passed, result.errors + result.failures

    if gate_name == "rag":
        # Rag gate requires runtime callables (chunker_fn, retrieval_fn) which can't be
        # serialized in YAML — calling project must inject them via gate_config["_runtime"].
        from polybuild.domain_gates.validate_rag import validate_rag_smoke

        runtime = cfg.get("_runtime", {})
        result = validate_rag_smoke(
            chunker_fn=runtime.get("chunker_fn"),
            sample_text=cfg.get("sample_text", ""),
            golden_retrieval_path=cfg.get("golden_retrieval_path"),
            retrieval_fn=runtime.get("retrieval_fn"),
        )
        return result.passed, result.errors

    return False, [f"unknown_gate: {gate_name}"]


async def run_domain_gates(
    workdir: Path,
    profile_id: str,
    gate_configs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all domain gates applicable to the profile.

    Returns a dict {gate_name: {"passed": bool, "errors": [...]}}.
    """
    mapping = _load_domain_gates_from_routing()
    gates = mapping.get(profile_id, [])
    results: dict[str, dict[str, Any]] = {}

    for gate in gates:
        cfg = (gate_configs or {}).get(gate, {})
        passed, errors = await _run_single_domain_gate(gate, workdir, cfg)
        results[gate] = {"passed": passed, "errors": errors}
        logger.info("domain_gate_result", gate=gate, passed=passed, n_errors=len(errors))

    return results


# ────────────────────────────────────────────────────────────────
# SPEC HASH VERIFICATION (anti spec drift mid-run)
# ────────────────────────────────────────────────────────────────


def verify_spec_hash(spec: Spec, run_dir: Path) -> bool:
    """Verify the spec hash hasn't changed since Phase 0c."""
    spec_file = run_dir / "spec_final.json"
    if not spec_file.exists():
        return False
    canonical = json.dumps(
        json.loads(spec_file.read_text()),
        sort_keys=True,
        ensure_ascii=False,
    )
    current_hash = hashlib.sha256(canonical.encode()).hexdigest()
    return current_hash == spec.spec_hash


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_6_validate(
    spec: Spec,
    winner: BuilderResult,
    artifacts_dir: Path = Path(".polybuild/runs"),
    domain_gate_configs: dict[str, dict[str, Any]] | None = None,
) -> ValidationVerdict:
    """Run all final validation gates.

    Round 4 decision: domain gate failure BLOCKS commit (no warn-only).
    """
    logger.info("phase_6_start", run_id=spec.run_id)

    workdir = winner.code_dir.parent

    # General gates (re-run after Phase 5 fixes)
    general = await run_general_gates(workdir)

    # Domain gates (round 4 finalisé)
    domain_results = await run_domain_gates(workdir, spec.profile_id, domain_gate_configs)
    domain_passed = all(r["passed"] for r in domain_results.values())

    # Spec hash verification (drift detection)
    run_dir = artifacts_dir / spec.run_id
    spec_ok = verify_spec_hash(spec, run_dir)

    notes: list[str] = []
    if not spec_ok:
        notes.append("Spec drift detected: hash mismatch")
    if not domain_passed:
        failed = [k for k, v in domain_results.items() if not v["passed"]]
        notes.append(f"Domain gates failed: {failed}")
        for gate, r in domain_results.items():
            if not r["passed"]:
                for err in r.get("errors", [])[:3]:
                    notes.append(f"  [{gate}] {err}")

    passed = (
        general.acceptance_pass_ratio == 1.0
        and general.bandit_clean
        and general.mypy_strict_clean
        and general.ruff_clean
        and general.gitleaks_clean
        and domain_passed
        and spec_ok
    )

    logger.info(
        "phase_6_done",
        passed=passed,
        spec_drift=not spec_ok,
        domain_passed=domain_passed,
        n_domain_gates=len(domain_results),
    )

    return ValidationVerdict(
        passed=passed,
        general_gates=general,
        domain_gates_passed=domain_passed,
        domain_gates_results={k: v["passed"] for k, v in domain_results.items()},
        spec_drift_detected=not spec_ok,
        notes=notes,
    )

```


### `src/polybuild/models.py` (359 lines)

```python
"""Core Pydantic models shared across all pipeline phases.

These are the canonical contracts used by every adapter, phase, and gate.
Any change here must be tracked via an ADR.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ────────────────────────────────────────────────────────────────
# COMMON ENUMS
# ────────────────────────────────────────────────────────────────


class Severity(str, Enum):
    """Finding severity levels."""

    P0 = "P0"  # Sécurité, crash, hallucination critique
    P1 = "P1"  # Qualité, archi, perf
    P2 = "P2"  # Style, nommage
    P3 = "P3"  # Cosmétique


class Status(str, Enum):
    """Generic status for builders, fixes, validations."""

    OK = "ok"
    TIMEOUT = "timeout"
    FAILED = "failed"
    DISQUALIFIED = "disqualified"
    ESCALATED = "escalated"


class PrivacyLevel(str, Enum):
    """Privacy/sensitivity classification for medical profile (Phase -1)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ────────────────────────────────────────────────────────────────
# SPEC
# ────────────────────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    """A single executable acceptance criterion."""

    id: str
    description: str
    test_command: str  # ex: "pytest tests/test_x.py::test_y"
    blocking: bool = True


class RiskProfile(BaseModel):
    """Risk profile of the task, drives Phase 1 voice selection."""

    sensitivity: PrivacyLevel = PrivacyLevel.LOW
    code_inedit_critique: bool = False
    requires_probe: bool = False
    audit_axes: list[str] = Field(default_factory=list)
    domain_gates: list[str] = Field(default_factory=list)
    excludes_openrouter: bool = False
    excludes_us_cn_models: bool = False


class Spec(BaseModel):
    """Canonical specification for a POLYBUILD run.

    Output of Phase 0 (Opus 4.7). Hashed and verified through Phase 6.
    """

    model_config = ConfigDict(frozen=False)

    run_id: str
    profile_id: str  # ex: "module_inedit_critique", "helia_algo"
    task_description: str
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion]
    interfaces: dict[str, Any] = Field(default_factory=dict)  # Pydantic schemas, DB schemas
    risk_profile: RiskProfile
    spec_hash: str = ""  # SHA-256, calculé après Phase 0c
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpecAttack(BaseModel):
    """Output of Phase 0b — challenger critique without code generation."""

    challenger_model: str
    missing_invariants: list[str] = Field(default_factory=list)
    ambiguous_terms: list[str] = Field(default_factory=list)
    untestable_acceptance: list[str] = Field(default_factory=list)
    unsafe_assumptions: list[str] = Field(default_factory=list)
    rgpd_risks: list[str] = Field(default_factory=list)
    edge_cases_missed: list[str] = Field(default_factory=list)

    def has_critical_findings(self) -> bool:
        return bool(
            self.missing_invariants
            or self.untestable_acceptance
            or self.rgpd_risks
        )


# ────────────────────────────────────────────────────────────────
# PHASE 1 — VOICE SELECTION
# ────────────────────────────────────────────────────────────────


class VoiceConfig(BaseModel):
    """Configuration for a single voice in Phase 2."""

    voice_id: str  # ex: "claude-opus-4.7", "deepseek/deepseek-v4-pro"
    family: str    # ex: "anthropic", "deepseek"
    role: Literal["builder", "auditor", "fixer", "verifier", "critic", "judge"]
    timeout_sec: int = 720
    context: dict[str, Any] = Field(default_factory=dict)


# ────────────────────────────────────────────────────────────────
# PHASE 2 — BUILDER OUTPUT
# ────────────────────────────────────────────────────────────────


class SelfMetrics(BaseModel):
    """Self-reported metrics by each voice (for Phase 3 anti-gaming checks)."""

    loc: int
    complexity_cyclomatic_avg: float
    test_to_code_ratio: float
    todo_count: int
    imports_count: int
    functions_count: int


class BuilderResult(BaseModel):
    """Normalized output of a single voice in Phase 2."""

    voice_id: str
    family: str
    code_dir: Path
    tests_dir: Path
    diff_patch: Path
    self_metrics: SelfMetrics
    duration_sec: float
    status: Status
    raw_output: str = ""
    error: str | None = None


# ────────────────────────────────────────────────────────────────
# PHASE 3 — SCORING
# ────────────────────────────────────────────────────────────────


class GateResults(BaseModel):
    """Output of running general gates on a builder's worktree."""

    acceptance_pass_ratio: float
    bandit_clean: bool
    mypy_strict_clean: bool
    ruff_clean: bool
    coverage_score: float
    gitleaks_clean: bool
    gitleaks_findings_count: int
    diff_minimality: float
    pro_gap_penalty: float = 0.0
    domain_score: float = 0.0
    raw_outputs: dict[str, str] = Field(default_factory=dict)


class VoiceScore(BaseModel):
    """Final score and verdict for a single voice."""

    voice_id: str
    score: float
    gates: GateResults
    disqualified: bool = False
    disqualification_reason: str | None = None


# ────────────────────────────────────────────────────────────────
# PHASE 3B — GROUNDING
# ────────────────────────────────────────────────────────────────


class GroundingFinding(BaseModel):
    """A single grounding violation detected via AST analysis."""

    severity: Severity
    voice_id: str
    kind: Literal[
        "syntax_error",
        "hallucinated_import",
        "hallucinated_import_from",
        "missing_internal_symbol",
        "unverified_external_api",
    ]
    detail: str
    file: Path | None = None
    line: int | None = None


# ────────────────────────────────────────────────────────────────
# PHASE 4 — AUDIT
# ────────────────────────────────────────────────────────────────


class FindingEvidence(BaseModel):
    """Reproducible evidence supporting a finding."""

    file: Path
    line: int | None = None
    snippet: str | None = None
    reproducer: str | None = None  # ex: "pytest tests/test_x.py::test_y"


class Finding(BaseModel):
    """A single audit finding from Phase 4 (POLYLENS)."""

    id: str
    severity: Severity
    axis: str  # ex: "A_security", "B_quality"
    description: str
    evidence: FindingEvidence | None = None
    auditor_model: str
    auditor_family: str


class AuditReport(BaseModel):
    """Output of Phase 4 — orthogonal audit."""

    auditor_model: str
    auditor_family: str
    audit_duration_sec: float
    axes_audited: list[str]
    findings: list[Finding] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


# ────────────────────────────────────────────────────────────────
# PHASE 5 — TRIADE
# ────────────────────────────────────────────────────────────────


class VerifierVerdict(BaseModel):
    """Strict JSON-only verdict from a Verifier LLM. Never rewrites code."""

    pass_: bool = Field(alias="pass")
    reason: str
    required_evidence: str = ""

    model_config = ConfigDict(populate_by_name=True)


class FixResult(BaseModel):
    """Result of a single triade execution (P0 individual or P1 batch)."""

    finding_ids: list[str]
    status: Literal["accepted", "accepted_after_retry", "escalate", "tools_failed"]
    critic_model: str
    fixer_model: str
    verifier_model: str
    iterations: int
    patch_path: Path | None = None
    verifier_verdict: VerifierVerdict | None = None


class FixReport(BaseModel):
    """Aggregated output of Phase 5."""

    status: Literal["completed", "blocked_p0", "partial"]
    results: list[FixResult]


# ────────────────────────────────────────────────────────────────
# PHASE 6 — VALIDATION
# ────────────────────────────────────────────────────────────────


class ValidationVerdict(BaseModel):
    """Final validation verdict before commit."""

    passed: bool
    general_gates: GateResults
    domain_gates_passed: bool
    domain_gates_results: dict[str, bool] = Field(default_factory=dict)
    spec_drift_detected: bool = False
    notes: list[str] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────
# PHASE 7 — COMMIT & ADR
# ────────────────────────────────────────────────────────────────


class CommitInfo(BaseModel):
    """Git commit metadata."""

    sha: str
    message: str
    tag_pre: str  # ex: "polybuild/run-{run_id}-pre"
    tag_post: str  # ex: "polybuild/run-{run_id}-commit"
    files_changed: list[Path]
    adr_id: str | None = None


# ────────────────────────────────────────────────────────────────
# RUN-LEVEL AGGREGATE
# ────────────────────────────────────────────────────────────────


class TokenUsage(BaseModel):
    """Token usage by provider."""

    claude_max_input: int = 0
    claude_max_output: int = 0
    chatgpt_pro_input: int = 0
    chatgpt_pro_output: int = 0
    gemini_pro_input: int = 0
    gemini_pro_output: int = 0
    kimi_allegretto_input: int = 0
    kimi_allegretto_output: int = 0
    openrouter_input: int = 0
    openrouter_output: int = 0
    mistral_eu_input: int = 0
    mistral_eu_output: int = 0
    ollama_local_input: int = 0
    ollama_local_output: int = 0


class PolybuildRun(BaseModel):
    """Top-level aggregate for a POLYBUILD run, archived to disk."""

    run_id: str
    profile_id: str
    spec_hash: str
    voices_used: list[str]
    winner_voice_id: str | None
    scores: dict[str, float]
    audit_findings_by_severity: dict[str, int]
    fix_iterations: dict[str, int]
    domain_gates_passed: bool
    duration_total_sec: float
    tokens: TokenUsage
    cost_eur_marginal: float = 0.0
    final_status: Literal["committed", "aborted", "rolled_back"]
    commit_sha: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

```


### `config/routing.yaml` (277 lines)

```yaml
# config/routing.yaml
# Table de routage v3 — 15 profils avec règles d'orthogonalité

# ────────────────────────────────────────────────────────────────
# RÈGLES GLOBALES
# ────────────────────────────────────────────────────────────────
global_rules:
  no_two_voices_same_provider: true
  mediator_distinct_from_phase2: true
  min_one_long_context_if_repo_files_gt: 100
  medical_high_excludes_us_cn_models: true
  irreplaceable_or_models_required:
    - profiles_using_helia_algo
    - profiles_using_llm_judge
    - profiles_using_spec_attack_algo

# ────────────────────────────────────────────────────────────────
# SEUILS DE DIVERSITÉ PAR PROFIL
# ────────────────────────────────────────────────────────────────
diversity_thresholds:
  refactor_mecanique: 1.5
  module_standard: 2.0
  inedit_critique: 2.3
  helia_algo: 2.5
  medical_high: 2.0  # priorité sécurité, diversité secondaire

# ────────────────────────────────────────────────────────────────
# PROFILS DE TÂCHES
# ────────────────────────────────────────────────────────────────

profiles:

  # ─── 1. Module Python standard sur codebase connue ───
  module_standard_known:
    description: "Refactor ou ajout fonctionnel sur codebase établie, conventions stables"
    voices_phase2:
      - gpt-5.5             # CLI Codex, builder pragmatique
      - gemini-3.1-pro      # CLI, ctx 2M
      - kimi-k2.6           # CLI, variantes créatives
    mediator: claude-opus-4.7
    pool_for_diversity:
      - claude-opus-4.7
      - claude-sonnet-4.6
      - gpt-5.5
      - gemini-3.1-pro
      - kimi-k2.6
    audit_axes: [B_quality, C_tests, E_architecture, F_documentation]
    domain_gates: []
    requires_probe: false
    min_diversity: 2.0
    timeout_phase2_min: 12

  # ─── 2. Module Python sur code propriétaire inédit ───
  module_inedit_critique:
    description: "Code propriétaire sans benchmark public, Pro Gap risqué"
    voices_phase2:
      - claude-opus-4.7     # CLI, architecture
      - gpt-5.5             # CLI, builder strict
      - deepseek/deepseek-v4-pro  # OR, raisonnement transparent
    mediator: gemini-3.1-pro
    pool_for_diversity:
      - claude-opus-4.7
      - gpt-5.5
      - gemini-3.1-pro
      - kimi-k2.6
      - deepseek/deepseek-v4-pro
    audit_axes: [A_security, B_quality, C_tests, E_architecture, F_documentation, G_adversarial]
    domain_gates: [grounding_strict, mutation_testing]
    requires_probe: true                 # sonde 50 LOC obligatoire
    min_diversity: 2.3
    timeout_phase2_min: 15

  # ─── 3. Algo / math pur (HELIA scientifique) ───
  helia_algo:
    description: "Algorithmique mathématique, propriété formelles, HELIA"
    voices_phase2:
      - gpt-5.5                            # CLI, structured outputs
      - kimi-k2.6                          # CLI, swarm créatif
      - deepseek/deepseek-v4-pro           # OR, CoT auditable
    mediator: claude-opus-4.7
    pool_for_diversity:
      - claude-opus-4.7
      - gpt-5.5
      - kimi-k2.6
      - deepseek/deepseek-v4-pro
      - gemini-3.1-pro
    audit_axes: [A_security, C_tests, D_perf, G_adversarial]
    domain_gates: [property_tests_hypothesis, numerical_invariants, seed_reproducibility]
    requires_probe: true
    min_diversity: 2.5
    spec_attacker: deepseek/deepseek-v4-pro
    timeout_phase2_min: 18

  # ─── 4. Données médicales — paranoia LOW ───
  medical_low:
    description: "Données déjà anonymisées ou synthétiques, aucun PII"
    voices_phase2:
      - claude-sonnet-4.6   # CLI, post-anonymisation
      - gemini-3.1-pro      # CLI
      - gpt-5.5             # CLI
    mediator: claude-opus-4.7
    audit_axes: [A_security, B_quality, C_tests, E_architecture]
    domain_gates: [privacy_gate_check, no_pii_leak]
    requires_probe: false
    min_diversity: 2.0
    timeout_phase2_min: 12

  # ─── 5. Données médicales — paranoia MEDIUM ───
  medical_medium:
    description: "Données pseudonymisées, ré-identification théorique possible"
    voices_phase2:
      - claude-sonnet-4.6                  # CLI Claude Max (pseudonymisé)
      - gemini-3.1-pro                     # CLI Gemini Pro (pseudonymisé)
      - mistral/devstral-2                 # API Mistral EU directe
    mediator: claude-opus-4.7
    audit_axes: [A_security, B_quality, C_tests, E_architecture, F_documentation]
    domain_gates: [privacy_gate_strict, mistral_eu_dpa_validated]
    requires_probe: false
    min_diversity: 2.0
    excludes_openrouter: true
    timeout_phase2_min: 15

  # ─── 6. Données médicales — paranoia HIGH ───
  medical_high:
    description: "Données SPSTI réelles, ré-identifiables → 100% local + EU"
    voices_phase2:
      - qwen2.5-coder:14b-int4              # NAS local Ollama
      - mistral/devstral-2                  # API Mistral EU directe
      - qwen2.5-coder:7b-int4               # NAS local Ollama
    mediator: qwen2.5-coder:14b-int4
    audit_axes: [A_security, B_quality, C_tests, E_architecture, F_documentation, G_adversarial]
    domain_gates: [privacy_gate_hard_block, no_external_calls, gitleaks_strict]
    requires_probe: false
    excludes_openrouter: true
    excludes_us_cn_models: true
    requires_user_attestation: true
    timeout_phase2_min: 30                 # local lent

  # ─── 7. Parsing PDF médical ───
  parsing_pdf_medical:
    description: "Extraction PDF médicaux, multimodal, post-anonymisation"
    voices_phase2:
      - gemini-3.1-pro                     # CLI, multimodal 2M
      - gpt-5.5                            # CLI, structured outputs
      - deepseek/deepseek-v4-pro           # OR, parsing logique zero-copy
    mediator: claude-opus-4.7
    audit_axes: [A_security, B_quality, C_tests]
    domain_gates: [golden_pdfs_test, encoding_validation, extraction_invariants]
    requires_probe: false
    min_diversity: 2.2
    privacy_gate_required: true
    timeout_phase2_min: 15

  # ─── 8. RAG ingestion / chunking / eval ───
  rag_ingestion_eval:
    description: "Pipeline RAG, embeddings, retrieval@k, evaluation"
    voices_phase2:
      - gemini-3.1-pro                     # CLI, ctx massif
      - gpt-5.5                            # CLI, structured
      - kimi-k2.6                          # CLI, variantes chunking
    mediator: claude-opus-4.7
    audit_axes: [A_security, B_quality, C_tests, D_perf]
    domain_gates: [retrieval_at_k_fixtures, chunk_hash_stability, qdrant_consistency]
    requires_probe: false
    min_diversity: 2.0
    timeout_phase2_min: 15

  # ─── 9. MCP schema / tool change ───
  mcp_schema_change:
    description: "Modification d'outils MCP, schémas JSON-RPC, signatures"
    voices_phase2:
      - claude-opus-4.7                    # CLI, contrats
      - gpt-5.5                            # CLI, JSON struct
      - x-ai/grok-4.20                     # OR, prompt adherence stricte
    mediator: gemini-3.1-pro
    audit_axes: [A_security, B_quality, C_tests, E_architecture]
    domain_gates: [mcp_jsonrpc_smoke, schema_validation_pydantic, serialization_roundtrip]
    requires_probe: false
    min_diversity: 2.2
    timeout_phase2_min: 12

  # ─── 10. OAI-PMH scraping / API REST ───
  oai_pmh_scraping:
    description: "Scrapers légaux OAI-PMH, API REST, retry, pagination, robots.txt"
    voices_phase2:
      - gpt-5.3-codex                      # CLI Codex, spécialiste
      - gpt-5.5                            # CLI, logique
      - kimi-k2.6                          # CLI, edge cases
    mediator: gemini-3.1-pro
    audit_axes: [A_security, C_tests, D_perf]
    domain_gates: [retry_pagination_tests, rate_limit_compliance, xml_namespace_handling]
    requires_probe: false
    min_diversity: 2.0
    timeout_phase2_min: 12

  # ─── 11. DevOps / IaC / scripts shell ───
  devops_iac_scripts:
    description: "Terraform, Docker Compose, scripts bash, CI/CD"
    voices_phase2:
      - gpt-5.3-codex                      # CLI Codex, spécialiste
      - claude-sonnet-4.6                  # CLI, review sécu
      - gemini-3.1-pro                     # CLI, ctx changelogs
    mediator: claude-opus-4.7
    audit_axes: [A_security, B_quality, E_architecture]
    domain_gates: [shellcheck, terraform_validate, kubeval_if_applicable]
    requires_probe: false
    min_diversity: 1.8
    timeout_phase2_min: 10

  # ─── 12. Refactor mécanique <300 LOC ───
  refactor_mecanique:
    description: "Refactor sans changement comportement, codebase connue"
    voices_phase2:
      - gpt-5.5                            # CLI, exécution rapide
      - gemini-3.1-pro                     # CLI, blast radius
    mediator: null                         # gates locaux uniquement
    audit_axes: [B_quality, C_tests, E_architecture]
    domain_gates: [behavior_snapshot, diff_minimality]
    requires_probe: false
    min_diversity: 1.5
    timeout_phase2_min: 8

  # ─── 13. LLM-as-Judge / Eval pipeline ───
  llm_as_judge:
    description: "Pipeline d'évaluation, scoring, RAG eval, bias detection"
    voices_phase2:
      - gemini-3.1-pro                     # CLI, multimodal
      - claude-sonnet-4.6                  # CLI, nuance
      - x-ai/grok-4.20                     # OR, faible hallucination
    mediator: gpt-5.5
    audit_axes: [B_quality, C_tests, F_documentation]
    domain_gates: [bias_score_check, inter_annotator_kappa, json_verdict_only]
    requires_probe: false
    min_diversity: 2.2
    timeout_phase2_min: 12

  # ─── 14. Post-finding POLYLENS P0/P1 ───
  post_polylens_fix:
    description: "Correction d'un finding P0/P1 d'un audit antérieur"
    voices_phase2:
      - gpt-5.5                            # CLI fixer (≠ winner antérieur)
      - claude-opus-4.7                    # CLI reviewer
      - dynamique                          # verifier rotatif selon axe
    mediator: claude-opus-4.7
    audit_axes: [A_security, C_tests]
    domain_gates: [regression_tests_mandatory, finding_evidence_required]
    requires_probe: false
    min_diversity: 2.0
    timeout_phase2_min: 12

  # ─── 15. Documentation / ADR ───
  documentation_adr:
    description: "Génération de documentation, ADRs, README"
    voices_phase2:
      - claude-opus-4.7                    # CLI, rédaction
      - gemini-3.1-pro                     # CLI, ctx
      - kimi-k2.6                          # CLI, contradictions
    mediator: humain                       # validation rapide humaine
    audit_axes: [F_documentation]
    domain_gates: [adr_schema_validation, consistency_check]
    requires_probe: false
    min_diversity: 1.8
    timeout_phase2_min: 8

# ────────────────────────────────────────────────────────────────
# AUDITEURS PAR FAMILLE GAGNANTE (Phase 4)
# ────────────────────────────────────────────────────────────────
auditor_pools_by_winner_family:
  anthropic: [deepseek/deepseek-v4-pro, gemini-3.1-pro, gpt-5.5, x-ai/grok-4.20]
  openai:    [deepseek/deepseek-v4-pro, claude-opus-4.7, gemini-3.1-pro, x-ai/grok-4.20]
  google:    [deepseek/deepseek-v4-pro, claude-opus-4.7, gpt-5.5, x-ai/grok-4.20]
  deepseek:  [claude-opus-4.7, gpt-5.5, gemini-3.1-pro, x-ai/grok-4.20]
  moonshot:  [claude-opus-4.7, deepseek/deepseek-v4-pro, gpt-5.5, x-ai/grok-4.20]
  xai:       [claude-opus-4.7, gemini-3.1-pro, deepseek/deepseek-v4-pro, gpt-5.5]
  mistral:   [claude-opus-4.7, gpt-5.5, gemini-3.1-pro]
  alibaba:   [claude-opus-4.7, gpt-5.5, gemini-3.1-pro, deepseek/deepseek-v4-pro]

```


### `config/models.yaml` (208 lines)

```yaml
# config/models.yaml
# Inventaire complet des modèles utilisés par POLYBUILD v3
# Catégorie : cli_free | openrouter_required | openrouter_optional | local_ollama | mistral_eu

# ────────────────────────────────────────────────────────────────
# MODÈLES CLI GRATUITS (forfaits payés, sous-utilisés)
# ────────────────────────────────────────────────────────────────

claude-opus-4.7:
  category: cli_free
  cli: claude_code
  invocation: "claude code --model opus-4.7"
  context_window: 1000000
  forces: [architecture, raisonnement_nuancé, contexte_massif]
  swe_bench_verified: 0.876
  swe_bench_pro: 0.643
  pro_gap: -0.233
  roles: [architect, mediator, audit]

claude-sonnet-4.6:
  category: cli_free
  cli: claude_code
  invocation: "claude code --model sonnet-4.6"
  context_window: 1000000
  forces: [itération_rapide, généraliste_équilibré]
  swe_bench_verified: 0.808
  roles: [workhorse, verifier]

claude-haiku-4.5:
  category: cli_free
  cli: claude_code
  invocation: "claude code --model haiku-4.5"
  forces: [vitesse, atomique]
  roles: [scoring_helper, atomic_tasks]

gpt-5.5:
  category: cli_free
  cli: codex
  invocation: "codex exec -m gpt-5.5 -c \"model_reasoning_effort=high\""
  context_window: 1000000
  forces: [exécution_agentique, terminal, structured_outputs]
  swe_bench_verified: 0.81
  swe_bench_pro: 0.575
  terminal_bench: 0.827
  pro_gap: -0.235
  roles: [pragmatic_builder, fixer, verifier]

gpt-5.5-pro:
  category: cli_free
  cli: codex
  invocation: "codex exec -m gpt-5.5-pro -c \"model_reasoning_effort=xhigh\""
  forces: [haute_complexité, raisonnement_profond]
  roles: [architect_alternative, audit]

gpt-5.4:
  category: cli_free
  cli: codex
  invocation: "codex exec -m gpt-5.4"
  swe_bench_verified: 0.815
  swe_bench_pro: 0.577
  forces: [généraliste, computer_use]
  roles: [workhorse]

gpt-5.3-codex:
  category: cli_free
  cli: codex
  invocation: "codex exec -m gpt-5.3-codex"
  forces: [cli_specialist, ci_cd, scripts_shell, iac]
  terminal_bench: 0.773
  roles: [devops, infra]

gemini-3.1-pro:
  category: cli_free
  cli: gemini
  invocation: "gemini -m gemini-3.1-pro-preview --include-directories ."
  context_window: 2000000
  forces: [long_context, multimodal, ingestion_massive]
  swe_bench_verified: 0.806
  terminal_bench: 0.542
  roles: [long_context_integrator, multimodal]

gemini-3.1-flash:
  category: cli_free
  cli: gemini
  invocation: "gemini -m gemini-3.1-flash"
  forces: [vitesse, batch]
  roles: [batch_tasks]

kimi-k2.6:
  category: cli_free
  cli: kimi
  invocation: "kimi --quiet --thinking --plan"
  context_window: 256000
  forces: [swarm_agents, idioms_créatifs, ui_ux]
  swe_bench_verified: 0.802
  swe_bench_pro: 0.586
  pro_gap: -0.216
  roles: [variant_explorer, ui_specialist]

# ────────────────────────────────────────────────────────────────
# MODÈLES OPENROUTER IRREMPLAÇABLES
# ────────────────────────────────────────────────────────────────

deepseek/deepseek-v4-pro:
  category: openrouter_required
  endpoint: "https://openrouter.ai/api/v1/chat/completions"
  context_window: 1000000
  architecture: moe
  total_params_b: 1600
  active_params_b: 49
  license: MIT
  forces: [cot_transparent, math_reasoning, algo_strict]
  swe_bench_verified: 0.806
  swe_bench_pro: 0.554
  pro_gap: -0.252
  irreplaceable_for: [helia_algo, spec_attack_algo, audit_orthogonal]
  roles: [math_reasoner, auditor, spec_attacker]

x-ai/grok-4.20:
  category: openrouter_required
  endpoint: "https://openrouter.ai/api/v1/chat/completions"
  context_window: 2000000
  forces: [prompt_adherence_strict, low_hallucination, concision]
  swe_bench_verified: 0.78
  irreplaceable_for: [llm_as_judge, spec_attack_adherence, verifier_strict]
  roles: [skeptic, verifier_strict, judge]

# ────────────────────────────────────────────────────────────────
# MISTRAL EU DIRECT (api.mistral.ai, PAS OpenRouter)
# ────────────────────────────────────────────────────────────────

mistral/devstral-2:
  category: mistral_eu
  endpoint: "https://api.mistral.ai/v1/chat/completions"
  context_window: 256000
  total_params_b: 123
  license: "MIT modified"
  jurisdiction: EU
  forces: [agentic_coding, eu_certified]
  irreplaceable_for: [medical_paranoia_medium, medical_paranoia_high]
  roles: [medical_eu_safe]

# ────────────────────────────────────────────────────────────────
# OPENROUTER CONDITIONNEL
# ────────────────────────────────────────────────────────────────

deepseek/deepseek-v4-flash:
  category: openrouter_optional
  endpoint: "https://openrouter.ai/api/v1/chat/completions"
  context_window: 1000000
  active_params_b: 13
  forces: [cost_efficient, fast]
  roles: [probe_50_loc, fallback_cli_down]

# ────────────────────────────────────────────────────────────────
# MODÈLES LOCAUX (NAS Synology DS224+ via Ollama)
# ────────────────────────────────────────────────────────────────

qwen2.5-coder:14b-int4:
  category: local_ollama
  endpoint: "http://nas.local:11434/api/generate"
  ram_gb: 9
  estimated_tok_per_sec: 3
  forces: [local_only, multilingual, code_focused]
  roles: [medical_paranoia_high, anonymisation_contextuelle]

qwen2.5-coder:7b-int4:
  category: local_ollama
  endpoint: "http://nas.local:11434/api/generate"
  ram_gb: 5
  estimated_tok_per_sec: 8
  forces: [atomic_functions, fast_local]
  roles: [medical_atomic, fast_local]

# ────────────────────────────────────────────────────────────────
# EMBEDDER LOCAL
# ────────────────────────────────────────────────────────────────

all-MiniLM-L6-v2:
  category: local_embedder
  endpoint: "http://nas.local:8090/embed"
  dimensions: 384
  ram_mb: 100
  estimated_tok_per_sec: 50
  roles: [vector_store, similarity_search]

# ────────────────────────────────────────────────────────────────
# MODÈLES ÉLIMINÉS (documentation pour traçabilité)
# ────────────────────────────────────────────────────────────────

eliminated_models:
  - slug: "deepseek/deepseek-v3.2"
    reason: "Remplaçable par Kimi K2.6 CLI (frontend similaire)"
  - slug: "x-ai/grok-4.1-fast"
    reason: "Remplaçable par Gemini 3.1 Flash CLI"
  - slug: "qwen/qwen3.6-plus"
    reason: "Remplaçable par GPT-5.5 CLI (généraliste)"
  - slug: "zai/glm-5.1"
    reason: "Remplaçable par DeepSeek V4-Pro (long-horizon OSS)"
  - slug: "minimax/m2.5"
    reason: "Remplaçable par Kimi K2.6 CLI (asiatique créatif)"
  - slug: "nvidia/nemotron-3-super"
    reason: "Pas de différentiateur clair vs GPT-5.5 CLI"
  - slug: "deepseek/deepseek-v3.2-int4-local"
    reason: "685B = 340 GB minimum, impossible sur NAS 18 GB"
  - slug: "llama-3.3-70b-int2-local"
    reason: "Trop juste sur 18 GB partagé avec MCP servers"

```

---

## Pre-round-4 artefacts (FULL mode only — reference only)

These files were stabilized in rounds 1-3. **Do not re-audit unless round 4 code drifts from their contracts.**


### `src/polybuild/__init__.py` (21 lines)

```python
"""POLYBUILD v3 — Multi-LLM orchestrated code generation pipeline.

Architecture overview:
    1. Phase -1: Privacy gate (TODO post-round 4)
    2. Phase 0:  Spec generation (Opus 4.7)
    3. Phase 0b: Spec attack (orthogonal challenger)
    4. Phase 1:  Voice selection (matrix + optional 50 LOC probe)
    5. Phase 2:  Parallel generation (3 voices)
    6. Phase 3:  Deterministic scoring
    7. Phase 3b: AST grounding check
    8. Phase 4:  Orthogonal POLYLENS audit
    9. Phase 5:  Critic-Fixer-Verifier triade
    10. Phase 6: General + domain validation gates
    11. Phase 7: Commit + auto-ADR
    12. Phase 8: Production smoke (TODO post-round 4)
"""

from polybuild._version import __version__

__all__ = ["__version__"]

```


### `src/polybuild/_version.py` (4 lines)

```python
"""Version metadata."""

__version__ = "3.0.0-dev"

```


### `src/polybuild/cli.py` (188 lines)

```python
"""POLYBUILD v3 CLI.

Commands:
    polybuild run --brief <file> --profile <name>     Run the full pipeline
    polybuild status <run_id>                         Show status of a run
    polybuild logs <run_id>                           Show logs (last 200 lines)
    polybuild abort <run_id>                          Abort a running run
    polybuild test-cli                                Smoke test all CLI adapters
    polybuild stats --profile <name> --last <N>       Show learning stats
    polybuild init                                    Bootstrap a new project
    polybuild resume --checkpoint <run_id>            Resume from checkpoint
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from polybuild import __version__
from polybuild.orchestrator import run_polybuild

app = typer.Typer(help="POLYBUILD v3 — Multi-LLM orchestrated code generation")
console = Console()


@app.callback()
def callback() -> None:
    """POLYBUILD v3 CLI."""


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"POLYBUILD v{__version__}")


@app.command()
def run(
    brief: Path = typer.Option(..., "--brief", "-b", help="Brief file (.md)"),
    profile: str = typer.Option(
        "module_standard_known",
        "--profile",
        "-p",
        help="Routing profile id",
    ),
    project_root: Path = typer.Option(Path("."), "--project-root", "-r"),
    skip_commit: bool = typer.Option(False, "--no-commit", help="Dry run (no Git commit)"),
) -> None:
    """Run the full POLYBUILD pipeline."""
    if not brief.exists():
        console.print(f"[red]Brief file not found: {brief}[/red]")
        raise typer.Exit(1)

    brief_text = brief.read_text()

    console.print(f"[cyan]POLYBUILD v{__version__}[/cyan]")
    console.print(f"  Profile: {profile}")
    console.print(f"  Brief: {brief}")
    console.print(f"  Project: {project_root.absolute()}")
    console.print(f"  Skip commit: {skip_commit}")
    console.print()

    result = asyncio.run(
        run_polybuild(
            brief=brief_text,
            profile_id=profile,
            project_root=project_root,
            skip_commit=skip_commit,
        )
    )

    # Pretty print result
    table = Table(title=f"Run {result.run_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Status", result.final_status)
    table.add_row("Winner", result.winner_voice_id or "—")
    table.add_row("Duration", f"{result.duration_total_sec:.1f}s")
    table.add_row("Commit SHA", (result.commit_sha or "—")[:12])
    console.print(table)

    if result.final_status != "committed":
        raise typer.Exit(1)


@app.command()
def status(run_id: str) -> None:
    """Show the status of a run by id."""
    run_dir = Path(".polybuild") / "runs" / run_id
    if not run_dir.exists():
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)

    final = run_dir / "polybuild_run.json"
    if final.exists():
        data = json.loads(final.read_text())
        table = Table(title=f"Run {run_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        for key in ("final_status", "profile_id", "winner_voice_id",
                    "duration_total_sec", "commit_sha", "spec_hash"):
            table.add_row(key, str(data.get(key, "—")))
        console.print(table)
    else:
        # Look at checkpoints
        cp_dir = Path(".polybuild") / "checkpoints"
        ckpts = sorted(cp_dir.glob(f"{run_id}_*.json"))
        if ckpts:
            console.print(f"[yellow]Run in progress, last checkpoint: {ckpts[-1].name}[/yellow]")
        else:
            console.print(f"[yellow]No checkpoints found for {run_id}[/yellow]")


@app.command(name="test-cli")
def test_cli() -> None:
    """Smoke test all CLI adapters and report which are available."""
    from polybuild.adapters import (
        ClaudeCodeAdapter,
        CodexCLIAdapter,
        GeminiCLIAdapter,
        KimiCLIAdapter,
        MistralEUAdapter,
        OllamaLocalAdapter,
        OpenRouterAdapter,
    )

    adapters = [
        ClaudeCodeAdapter("opus-4.7"),
        ClaudeCodeAdapter("sonnet-4.6"),
        CodexCLIAdapter("gpt-5.5"),
        GeminiCLIAdapter("gemini-3.1-pro-preview"),
        KimiCLIAdapter("k2.6"),
        OpenRouterAdapter("deepseek/deepseek-v4-pro", "deepseek"),
        OpenRouterAdapter("x-ai/grok-4.20", "xai"),
        MistralEUAdapter("devstral-2"),
        OllamaLocalAdapter("qwen2.5-coder:14b-int4"),
    ]

    table = Table(title="CLI Adapters Status")
    table.add_column("Adapter", style="cyan")
    table.add_column("Available")
    table.add_column("Smoke Test")

    async def _check_all() -> list[tuple[str, bool, bool]]:
        results = []
        for a in adapters:
            avail = await a.is_available()
            smoke = await a.smoke_test() if avail else False
            results.append((a.name, avail, smoke))
        return results

    results = asyncio.run(_check_all())
    for name, avail, smoke in results:
        avail_str = "[green]✓[/green]" if avail else "[red]✗[/red]"
        smoke_str = "[green]✓[/green]" if smoke else "[red]✗[/red]"
        table.add_row(name, avail_str, smoke_str)
    console.print(table)


@app.command()
def stats(
    profile: str | None = typer.Option(None, "--profile", "-p"),
    last_n: int = typer.Option(20, "--last", "-n"),
) -> None:
    """Show learning stats per voice (TODO Phase E)."""
    console.print("[yellow]TODO: implement stats aggregation (Phase E)[/yellow]")


@app.command()
def init() -> None:
    """Bootstrap a new project (TODO Phase F)."""
    console.print("[yellow]TODO: implement polybuild init (Phase F)[/yellow]")


@app.command()
def resume(checkpoint: str = typer.Option(..., "--checkpoint", "-c")) -> None:
    """Resume from a checkpoint (TODO Phase G)."""
    console.print(f"[yellow]TODO: resume from {checkpoint} (Phase G)[/yellow]")


if __name__ == "__main__":
    app()

```


### `src/polybuild/adapters/__init__.py` (85 lines)

```python
"""Adapters package — exposes BuilderProtocol implementations and a factory.

Usage:
    from polybuild.adapters import get_builder
    builder = get_builder("claude-opus-4.7")
"""

from __future__ import annotations

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.adapters.claude_code import ClaudeCodeAdapter
from polybuild.adapters.codex_cli import CodexCLIAdapter
from polybuild.adapters.gemini_cli import GeminiCLIAdapter
from polybuild.adapters.kimi_cli import KimiCLIAdapter
from polybuild.adapters.mistral_eu import MistralEUAdapter
from polybuild.adapters.ollama_local import OllamaLocalAdapter
from polybuild.adapters.openrouter import OpenRouterAdapter

__all__ = [
    "BuilderProtocol",
    "ClaudeCodeAdapter",
    "CodexCLIAdapter",
    "GeminiCLIAdapter",
    "KimiCLIAdapter",
    "MistralEUAdapter",
    "OllamaLocalAdapter",
    "OpenRouterAdapter",
    "get_builder",
]


# ────────────────────────────────────────────────────────────────
# FACTORY
# ────────────────────────────────────────────────────────────────


def get_builder(voice_id: str) -> BuilderProtocol:
    """Return the right adapter for a given voice_id.

    Voice ID conventions:
        - "claude-opus-4.7", "claude-sonnet-4.6", "claude-haiku-4.5"
        - "gpt-5.5", "gpt-5.5-pro", "gpt-5.4", "gpt-5.3-codex"
        - "gemini-3.1-pro", "gemini-3.1-flash"
        - "kimi-k2.6"
        - "deepseek/deepseek-v4-pro" (OR), "deepseek/deepseek-v4-flash" (OR)
        - "x-ai/grok-4.20" (OR)
        - "mistral/devstral-2" (Mistral EU direct, NOT OR)
        - "qwen2.5-coder:14b-int4" (Ollama local)
        - "qwen2.5-coder:7b-int4" (Ollama local)
    """
    # ── Anthropic Claude Code CLI ──
    if voice_id.startswith("claude-"):
        model = voice_id.removeprefix("claude-")  # "opus-4.7"
        return ClaudeCodeAdapter(model=model)

    # ── OpenAI Codex CLI ──
    if voice_id.startswith("gpt-"):
        return CodexCLIAdapter(model=voice_id)

    # ── Google Gemini CLI ──
    if voice_id.startswith("gemini-"):
        return GeminiCLIAdapter(model=f"{voice_id}-preview" if "pro" in voice_id else voice_id)

    # ── Moonshot Kimi CLI ──
    if voice_id.startswith("kimi-"):
        model = voice_id.removeprefix("kimi-")  # "k2.6"
        return KimiCLIAdapter(model=model)

    # ── Mistral EU direct (BEFORE OpenRouter check, key on "mistral/") ──
    if voice_id.startswith("mistral/"):
        slug = voice_id.removeprefix("mistral/")  # "devstral-2"
        return MistralEUAdapter(slug=slug)

    # ── OpenRouter (DeepSeek, xAI/Grok) ──
    if voice_id.startswith("deepseek/"):
        return OpenRouterAdapter(slug=voice_id, family="deepseek")
    if voice_id.startswith("x-ai/"):
        return OpenRouterAdapter(slug=voice_id, family="xai")

    # ── Ollama local (Qwen on NAS) ──
    if voice_id.startswith("qwen") and ":" in voice_id:
        return OllamaLocalAdapter(slug=voice_id)

    raise ValueError(f"Unknown voice_id: {voice_id!r}")

```


### `src/polybuild/adapters/builder_protocol.py` (60 lines)

```python
"""BuilderProtocol — abstract interface implemented by every model adapter.

Every model (CLI or OpenRouter or local Ollama) exposes the same async API.
This is the contract that makes Phase 2 parallel orchestration possible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from polybuild.models import BuilderResult, Spec, VoiceConfig


class BuilderProtocol(ABC):
    """Abstract base class for all builders.

    Implementations:
        - ClaudeCodeAdapter (CLI)
        - CodexCLIAdapter (CLI)
        - GeminiCLIAdapter (CLI)
        - KimiCLIAdapter (CLI)
        - OpenRouterAdapter (HTTP)
        - MistralEUAdapter (HTTP, api.mistral.ai direct)
        - OllamaLocalAdapter (HTTP local NAS)
    """

    name: str  # ex: "claude_code_opus", "openrouter_deepseek_v4_pro"
    family: str  # ex: "anthropic", "deepseek"

    @abstractmethod
    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Generate a complete code module from the spec.

        Must:
            1. Create a worktree under .polybuild/runs/{run_id}/worktrees/{voice_id}/
            2. Inject AGENTS.md + relevant memory in the prompt
            3. Respect cfg.timeout_sec (asyncio.wait_for)
            4. Return a BuilderResult with normalized fields

        Must NOT:
            - Modify the production code directly
            - Bypass the privacy gate for sensitive profiles
            - Cross-talk with other voices (no shared state)
        """

    @abstractmethod
    async def smoke_test(self) -> bool:
        """Quick sanity check that the adapter works.

        Sends a deterministic prompt and verifies the output structure.
        Used by `polybuild test-cli` (weekly cron + pre-run cache).
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the underlying CLI/API is reachable.

        Lightweight check (e.g. version query). Used before invoking generate().
        """

```


### `src/polybuild/adapters/claude_code.py` (281 lines)

```python
"""Claude Code CLI adapter.

Wraps `claude code --model <model> ...` invocations through asyncio.subprocess.
Used for Opus 4.7 (architect, mediator), Sonnet 4.6 (workhorse), Haiku 4.5 (atomic).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


class ClaudeCodeAdapter(BuilderProtocol):
    """Adapter for Claude Code CLI.

    Args:
        model: Anthropic model slug (opus-4.7, sonnet-4.6, haiku-4.5)
        cli_binary: Path to `claude` binary (default: "claude")
    """

    family = "anthropic"

    def __init__(self, model: str = "opus-4.7", cli_binary: str = "claude"):
        self.model = model
        self.cli_binary = cli_binary
        self.name = f"claude_code_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Run Claude Code CLI to generate the module."""
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: integrate with concurrency_limiter (Faille 3)
        cmd = [
            self.cli_binary,
            "code",
            "--model", self.model,
            "--prompt", prompt,
            "--output-dir", str(worktree),
            "--output-format", "json",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=worktree,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cfg.timeout_sec,
            )
            duration = time.monotonic() - start

            if proc.returncode != 0:
                logger.warning(
                    "claude_code_failed",
                    model=self.model,
                    returncode=proc.returncode,
                    stderr=stderr.decode()[:500],
                )
                return BuilderResult(
                    voice_id=cfg.voice_id,
                    family=self.family,
                    code_dir=worktree,
                    tests_dir=worktree / "tests",
                    diff_patch=worktree / "diff.patch",
                    self_metrics=SelfMetrics(
                        loc=0,
                        complexity_cyclomatic_avg=0.0,
                        test_to_code_ratio=0.0,
                        todo_count=0,
                        imports_count=0,
                        functions_count=0,
                    ),
                    duration_sec=duration,
                    status=Status.FAILED,
                    raw_output=stdout.decode(),
                    error=stderr.decode()[:500],
                )

            return self._parse_output(stdout.decode(), worktree, cfg, duration)

        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            logger.warning(
                "claude_code_timeout",
                model=self.model,
                timeout=cfg.timeout_sec,
            )
            return BuilderResult(
                voice_id=cfg.voice_id,
                family=self.family,
                code_dir=worktree,
                tests_dir=worktree / "tests",
                diff_patch=worktree / "diff.patch",
                self_metrics=SelfMetrics(
                    loc=0,
                    complexity_cyclomatic_avg=0.0,
                    test_to_code_ratio=0.0,
                    todo_count=0,
                    imports_count=0,
                    functions_count=0,
                ),
                duration_sec=duration,
                status=Status.TIMEOUT,
                error=f"Timeout after {cfg.timeout_sec}s",
            )

    async def smoke_test(self) -> bool:
        """Verify the CLI works with a deterministic prompt."""
        smoke_prompt = (
            "Write a Python function `def hello_polybuild(): return 'OK'`. "
            "Output JSON only: {\"code\": \"...\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary,
                "code",
                "--model", self.model,
                "--prompt", smoke_prompt,
                "--output-format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode())
            return "hello_polybuild" in data.get("code", "")
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def is_available(self) -> bool:
        """Check if the `claude` binary is reachable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (asyncio.TimeoutError, OSError):
            return False

    # ────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ────────────────────────────────────────────────────────────

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        """Create the isolated worktree for this voice."""
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        """Build the unified builder prompt with AGENTS.md + memory injection."""
        # TODO: integrate memory.retrieve_relevant_runs() once vector store is wired
        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<TASK_PROFILE>
profile_id: {spec.profile_id}
risk_level: {spec.risk_profile.sensitivity.value}
audit_axes: {spec.risk_profile.audit_axes}
</TASK_PROFILE>

<SPEC>
{spec.task_description}

Constraints:
{chr(10).join(f'  - {c}' for c in spec.constraints)}

Acceptance Criteria:
{chr(10).join(f'  - {ac.id}: {ac.description}' for ac in spec.acceptance_criteria)}
</SPEC>

<INSTRUCTIONS>
Generate a complete Python module that satisfies ALL acceptance criteria.
Output structure:
  - src/*.py (the module code)
  - tests/test_*.py (pytest tests, including happy/edge/failure scenarios)
  - diff.patch (unified diff)
  - self_metrics.json (loc, complexity, ratios, todos)

Hard rules:
  - Type hints everywhere (mypy --strict must pass)
  - No TODO/FIXME comments in final output (max 3 allowed, 0 preferred)
  - No mock-only tests (integration > mocks)
  - Pydantic v2 for all data contracts
  - asyncio for all I/O
</INSTRUCTIONS>

Working directory: {worktree}
"""

    def _load_agents_md(self) -> str:
        """Load project AGENTS.md or fallback to global."""
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        global_agents = Path.home() / ".polybuild" / "global_agents.md"
        if global_agents.exists():
            return global_agents.read_text()
        return "# AGENTS.md\n(no project conventions defined)"

    def _parse_output(
        self,
        raw: str,
        worktree: Path,
        cfg: VoiceConfig,
        duration: float,
    ) -> BuilderResult:
        """Parse stdout JSON into a BuilderResult."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: treat as raw text
            data = {"raw": raw}

        metrics_path = worktree / "self_metrics.json"
        if metrics_path.exists():
            metrics_data = json.loads(metrics_path.read_text())
            metrics = SelfMetrics(**metrics_data)
        else:
            # Estimate metrics from worktree
            metrics = self._estimate_metrics(worktree)

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=raw,
        )

    def _estimate_metrics(self, worktree: Path) -> SelfMetrics:
        """Compute metrics from the worktree if not provided by the model."""
        py_files = list((worktree / "src").rglob("*.py"))
        test_files = list((worktree / "tests").rglob("test_*.py"))
        loc = sum(len(f.read_text().splitlines()) for f in py_files)
        test_loc = sum(len(f.read_text().splitlines()) for f in test_files)
        ratio = test_loc / loc if loc > 0 else 0.0
        todo_count = sum(
            f.read_text().count("TODO") + f.read_text().count("FIXME")
            for f in py_files
        )
        return SelfMetrics(
            loc=loc,
            complexity_cyclomatic_avg=0.0,  # TODO: integrate radon
            test_to_code_ratio=ratio,
            todo_count=todo_count,
            imports_count=0,
            functions_count=0,
        )

```


### `src/polybuild/adapters/codex_cli.py` (264 lines)

```python
"""Codex CLI adapter (ChatGPT Pro).

Wraps `codex exec -m <model> ...` invocations.
Used for GPT-5.5, GPT-5.5-Pro, GPT-5.4, GPT-5.3-Codex.

GPT-5.3-Codex is the CLI specialist (devops, IaC, scripts shell).
GPT-5.5 is the pragmatic builder (Terminal-Bench 82.7%).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


class CodexCLIAdapter(BuilderProtocol):
    """Adapter for `codex exec` CLI (ChatGPT Pro forfait).

    Args:
        model: OpenAI model slug (gpt-5.5, gpt-5.5-pro, gpt-5.4, gpt-5.3-codex)
        reasoning_effort: low | medium | high | xhigh
        cli_binary: Path to `codex` binary (default: "codex")
    """

    family = "openai"

    def __init__(
        self,
        model: str = "gpt-5.5",
        reasoning_effort: str = "high",
        cli_binary: str = "codex",
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.cli_binary = cli_binary
        self.name = f"codex_cli_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Run codex exec to generate the module."""
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: concurrency_limiter integration (Faille 3)
        cmd = [
            self.cli_binary,
            "exec",
            "-m", self.model,
            "-c", f"model_reasoning_effort={self.reasoning_effort}",
            "--output-format", "json",
            "--cd", str(worktree),
            prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=worktree,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cfg.timeout_sec,
            )
            duration = time.monotonic() - start

            if proc.returncode != 0:
                logger.warning(
                    "codex_cli_failed",
                    model=self.model,
                    returncode=proc.returncode,
                    stderr=stderr.decode()[:500],
                )
                return self._failed_result(cfg, worktree, duration, stderr.decode()[:500])

            return self._parse_output(stdout.decode(), worktree, cfg, duration)

        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

    async def smoke_test(self) -> bool:
        smoke = (
            "Write Python: def hello_polybuild(): return 'OK'. "
            "Output JSON only: {\"code\": \"<source>\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "exec", "-m", self.model,
                "--output-format", "json",
                smoke,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode())
            return "hello_polybuild" in data.get("code", "")
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (asyncio.TimeoutError, OSError):
            return False

    # ────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ────────────────────────────────────────────────────────────

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<SPEC>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</SPEC>

<INSTRUCTIONS>
Generate complete Python module + pytest tests.
Write to:
  - {worktree}/src/*.py
  - {worktree}/tests/test_*.py
Then output JSON to stdout:
{{
  "files_written": ["src/x.py", "tests/test_x.py"],
  "self_metrics": {{
    "loc": <int>,
    "complexity_cyclomatic_avg": <float>,
    "test_to_code_ratio": <float>,
    "todo_count": <int>,
    "imports_count": <int>,
    "functions_count": <int>
  }}
}}

Hard rules:
  - mypy --strict must pass
  - max 3 TODO/FIXME (0 preferred)
  - integration tests > mocks
  - asyncio for I/O, Pydantic v2 for contracts
</INSTRUCTIONS>
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_output(
        self, raw: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        metrics_data = data.get("self_metrics", {})
        if metrics_data:
            metrics = SelfMetrics(**metrics_data)
        else:
            metrics = self._estimate_metrics(worktree)

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=raw,
        )

    def _estimate_metrics(self, worktree: Path) -> SelfMetrics:
        py_files = list((worktree / "src").rglob("*.py"))
        test_files = list((worktree / "tests").rglob("test_*.py"))
        loc = sum(len(f.read_text().splitlines()) for f in py_files)
        test_loc = sum(len(f.read_text().splitlines()) for f in test_files)
        ratio = test_loc / loc if loc > 0 else 0.0
        todo_count = sum(
            f.read_text().count("TODO") + f.read_text().count("FIXME")
            for f in py_files
        )
        return SelfMetrics(
            loc=loc,
            complexity_cyclomatic_avg=0.0,
            test_to_code_ratio=ratio,
            todo_count=todo_count,
            imports_count=0,
            functions_count=0,
        )

    def _timeout_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"Codex CLI timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float, reason: str
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )

```


### `src/polybuild/adapters/gemini_cli.py` (230 lines)

```python
"""Gemini CLI adapter (Google One Pro forfait).

Wraps `gemini -m <model> ...` invocations.
Used for Gemini 3.1 Pro (ctx 2M, multimodal) and Gemini 3.1 Flash (batch).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


class GeminiCLIAdapter(BuilderProtocol):
    """Adapter for `gemini` CLI (Google One Pro forfait).

    Args:
        model: Google model slug (gemini-3.1-pro-preview, gemini-3.1-flash)
        cli_binary: Path to `gemini` binary (default: "gemini")
        include_directories: bool — passes `--include-directories .` for full repo ctx
    """

    family = "google"

    def __init__(
        self,
        model: str = "gemini-3.1-pro-preview",
        cli_binary: str = "gemini",
        include_directories: bool = True,
    ):
        self.model = model
        self.cli_binary = cli_binary
        self.include_directories = include_directories
        self.name = f"gemini_cli_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: concurrency_limiter integration (Faille 3)
        cmd = [self.cli_binary, "-m", self.model]
        if self.include_directories:
            cmd.extend(["--include-directories", str(worktree)])
        cmd.extend(["--output-format", "json", "-p", prompt])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=worktree,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cfg.timeout_sec,
            )
            duration = time.monotonic() - start

            if proc.returncode != 0:
                logger.warning(
                    "gemini_cli_failed",
                    model=self.model,
                    returncode=proc.returncode,
                    stderr=stderr.decode()[:500],
                )
                return self._failed_result(cfg, worktree, duration, stderr.decode()[:500])

            return self._parse_output(stdout.decode(), worktree, cfg, duration)

        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

    async def smoke_test(self) -> bool:
        smoke = (
            "Write Python: def hello_polybuild(): return 'OK'. "
            "Output JSON only: {\"code\": \"<source>\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "-m", self.model,
                "--output-format", "json", "-p", smoke,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode())
            return "hello_polybuild" in data.get("code", "")
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (asyncio.TimeoutError, OSError):
            return False

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<SPEC>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</SPEC>

<INSTRUCTIONS>
Generate complete Python module + pytest tests in {worktree}.
Output JSON: {{"files_written": [...], "self_metrics": {{...}}}}.
Rules: mypy --strict, ≤3 TODO, integration > mocks, asyncio + Pydantic v2.
</INSTRUCTIONS>
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_output(
        self, raw: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        metrics_data = data.get("self_metrics", {})
        metrics = (
            SelfMetrics(**metrics_data) if metrics_data else self._estimate_metrics(worktree)
        )

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=raw,
        )

    def _estimate_metrics(self, worktree: Path) -> SelfMetrics:
        py_files = list((worktree / "src").rglob("*.py"))
        test_files = list((worktree / "tests").rglob("test_*.py"))
        loc = sum(len(f.read_text().splitlines()) for f in py_files)
        test_loc = sum(len(f.read_text().splitlines()) for f in test_files)
        ratio = test_loc / loc if loc > 0 else 0.0
        todo_count = sum(
            f.read_text().count("TODO") + f.read_text().count("FIXME")
            for f in py_files
        )
        return SelfMetrics(
            loc=loc,
            complexity_cyclomatic_avg=0.0,
            test_to_code_ratio=ratio,
            todo_count=todo_count,
            imports_count=0,
            functions_count=0,
        )

    def _timeout_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"Gemini CLI timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float, reason: str
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )

```


### `src/polybuild/adapters/kimi_cli.py` (231 lines)

```python
"""Kimi CLI adapter (Moonshot Allegretto forfait).

Wraps `kimi --quiet --thinking --plan ...` invocations.
Used for Kimi K2.6 (swarm 100+ agents, idioms créatifs, variant exploration).

Note: family = "moonshot" (Chinese provider, low corpus_proxy overlap with US models).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


class KimiCLIAdapter(BuilderProtocol):
    """Adapter for `kimi` CLI (Moonshot Allegretto forfait)."""

    family = "moonshot"

    def __init__(
        self,
        model: str = "k2.6",
        cli_binary: str = "kimi",
        thinking: bool = True,
        plan: bool = True,
    ):
        self.model = model
        self.cli_binary = cli_binary
        self.thinking = thinking
        self.plan = plan
        self.name = f"kimi_cli_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: concurrency_limiter integration (Faille 3)
        cmd = [self.cli_binary, "--quiet"]
        if self.thinking:
            cmd.append("--thinking")
        if self.plan:
            cmd.append("--plan")
        cmd.extend(["--output-format", "json", "-p", prompt])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=worktree,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cfg.timeout_sec,
            )
            duration = time.monotonic() - start

            if proc.returncode != 0:
                logger.warning(
                    "kimi_cli_failed",
                    model=self.model,
                    returncode=proc.returncode,
                    stderr=stderr.decode()[:500],
                )
                return self._failed_result(cfg, worktree, duration, stderr.decode()[:500])

            return self._parse_output(stdout.decode(), worktree, cfg, duration)

        except asyncio.TimeoutError:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

    async def smoke_test(self) -> bool:
        smoke = (
            "Write Python: def hello_polybuild(): return 'OK'. "
            "Output JSON only: {\"code\": \"<source>\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--quiet",
                "--output-format", "json", "-p", smoke,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode())
            return "hello_polybuild" in data.get("code", "")
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (asyncio.TimeoutError, OSError):
            return False

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<SPEC>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</SPEC>

<INSTRUCTIONS>
Generate Python module + pytest tests in {worktree}.
Be CREATIVE — explore alternative idioms and edge cases that other voices may miss.
Output JSON: {{"files_written": [...], "self_metrics": {{...}}}}.
Rules: mypy --strict, ≤3 TODO, asyncio + Pydantic v2.
</INSTRUCTIONS>
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_output(
        self, raw: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        metrics_data = data.get("self_metrics", {})
        metrics = (
            SelfMetrics(**metrics_data) if metrics_data else self._estimate_metrics(worktree)
        )

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=raw,
        )

    def _estimate_metrics(self, worktree: Path) -> SelfMetrics:
        py_files = list((worktree / "src").rglob("*.py"))
        test_files = list((worktree / "tests").rglob("test_*.py"))
        loc = sum(len(f.read_text().splitlines()) for f in py_files)
        test_loc = sum(len(f.read_text().splitlines()) for f in test_files)
        ratio = test_loc / loc if loc > 0 else 0.0
        todo_count = sum(
            f.read_text().count("TODO") + f.read_text().count("FIXME")
            for f in py_files
        )
        return SelfMetrics(
            loc=loc,
            complexity_cyclomatic_avg=0.0,
            test_to_code_ratio=ratio,
            todo_count=todo_count,
            imports_count=0,
            functions_count=0,
        )

    def _timeout_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"Kimi CLI timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float, reason: str
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )

```


### `src/polybuild/adapters/openrouter.py` (311 lines)

```python
"""OpenRouter HTTP adapter.

Used for the 3 irreplaceable OR models:
    - deepseek/deepseek-v4-pro (algo, audit, spec attack)
    - x-ai/grok-4.20 (verifier strict, LLM-as-judge)
    - deepseek/deepseek-v4-flash (probe 50 LOC, fallback)

Mistral EU (api.mistral.ai direct) uses a separate adapter, NOT this one,
to ensure jurisdiction is preserved.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(BuilderProtocol):
    """Generic adapter for OpenRouter-hosted models."""

    def __init__(
        self,
        slug: str,
        family: str,
        api_key_env: str = "OPENROUTER_API_KEY",
    ):
        self.slug = slug  # e.g. "deepseek/deepseek-v4-pro"
        self.family = family  # e.g. "deepseek"
        self.name = f"openrouter_{slug.replace('/', '_').replace('-', '_').replace('.', '_')}"
        self.api_key = os.environ.get(api_key_env)
        if not self.api_key:
            logger.warning(
                "openrouter_no_api_key",
                env_var=api_key_env,
                slug=slug,
            )

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Call OpenRouter and parse the structured output."""
        # Refus de générer pour profils RGPD high
        if spec.risk_profile.excludes_openrouter:
            return BuilderResult(
                voice_id=cfg.voice_id,
                family=self.family,
                code_dir=Path("/dev/null"),
                tests_dir=Path("/dev/null"),
                diff_patch=Path("/dev/null"),
                self_metrics=SelfMetrics(
                    loc=0,
                    complexity_cyclomatic_avg=0.0,
                    test_to_code_ratio=0.0,
                    todo_count=0,
                    imports_count=0,
                    functions_count=0,
                ),
                duration_sec=0.0,
                status=Status.DISQUALIFIED,
                error="OpenRouter excluded by risk_profile (medical sensitive data)",
            )

        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: integrate concurrency_limiter (Faille 3)
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://polybuild.local",
                        "X-Title": "POLYBUILD v3",
                    },
                    json={
                        "model": self.slug,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a builder voice in POLYBUILD v3. "
                                    "Output STRICT JSON only matching the schema in the prompt."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.4,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                duration = time.monotonic() - start
                return self._parse_response(content, worktree, cfg, duration)

        except httpx.TimeoutException:
            duration = time.monotonic() - start
            logger.warning("openrouter_timeout", slug=self.slug, timeout=cfg.timeout_sec)
            return self._timeout_result(cfg, worktree, duration)

        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                "openrouter_http_error",
                slug=self.slug,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            return self._failed_result(cfg, worktree, duration, str(e))

    async def smoke_test(self) -> bool:
        """Verify OpenRouter access with the chosen model."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.slug,
                        "messages": [
                            {"role": "user", "content": "Reply with JSON: {\"ok\": true}"},
                        ],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 50,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return parsed.get("ok") is True
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            return False

    async def is_available(self) -> bool:
        """Check if OpenRouter API is reachable."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{OPENROUTER_BASE}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    # ────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ────────────────────────────────────────────────────────────

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<TASK>
{spec.task_description}

Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</TASK>

<OUTPUT_SCHEMA>
{{
  "files": {{
    "src/<name>.py": "...",
    "tests/test_<name>.py": "..."
  }},
  "self_metrics": {{
    "loc": <int>,
    "complexity_cyclomatic_avg": <float>,
    "test_to_code_ratio": <float>,
    "todo_count": <int>,
    "imports_count": <int>,
    "functions_count": <int>
  }}
}}
</OUTPUT_SCHEMA>

Output ONLY valid JSON matching the schema. No prose.
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_response(
        self,
        content: str,
        worktree: Path,
        cfg: VoiceConfig,
        duration: float,
    ) -> BuilderResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return self._failed_result(cfg, worktree, duration, f"Invalid JSON: {e}")

        # Write files to worktree
        for rel_path, source in data.get("files", {}).items():
            abs_path = worktree / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(source)

        metrics_data = data.get("self_metrics", {})
        metrics = SelfMetrics(
            loc=metrics_data.get("loc", 0),
            complexity_cyclomatic_avg=metrics_data.get("complexity_cyclomatic_avg", 0.0),
            test_to_code_ratio=metrics_data.get("test_to_code_ratio", 0.0),
            todo_count=metrics_data.get("todo_count", 0),
            imports_count=metrics_data.get("imports_count", 0),
            functions_count=metrics_data.get("functions_count", 0),
        )

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=content,
        )

    def _timeout_result(
        self,
        cfg: VoiceConfig,
        worktree: Path,
        duration: float,
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"OpenRouter timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self,
        cfg: VoiceConfig,
        worktree: Path,
        duration: float,
        reason: str,
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )

```


### `src/polybuild/adapters/mistral_eu.py` (260 lines)

```python
"""Mistral EU direct adapter (api.mistral.ai).

CRITICAL: This adapter calls api.mistral.ai DIRECTLY, bypassing OpenRouter.
Reason: OpenRouter routes through US infra, breaking EU jurisdiction.
For medical profiles (paranoia medium/high), we need EU-only routing.

Used for Devstral 2 (123B agentic, EU-certified, MIT modified).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()

MISTRAL_BASE = "https://api.mistral.ai/v1"


class MistralEUAdapter(BuilderProtocol):
    """Direct Mistral EU adapter for medical/sensitive profiles.

    Args:
        slug: Mistral model slug (e.g. "devstral-2", "codestral-25.10")
        api_key_env: env var holding the Mistral API key
    """

    family = "mistral"

    def __init__(
        self,
        slug: str = "devstral-2",
        api_key_env: str = "MISTRAL_EU_API_KEY",
    ):
        self.slug = slug
        self.name = f"mistral_eu_{slug.replace('-', '_').replace('.', '_')}"
        self.api_key = os.environ.get(api_key_env)
        if not self.api_key:
            logger.warning(
                "mistral_eu_no_api_key",
                env_var=api_key_env,
                slug=slug,
            )

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
                response = await client.post(
                    f"{MISTRAL_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.slug,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a builder voice in POLYBUILD v3. "
                                    "Output STRICT JSON matching the schema. EU-only data residency."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.4,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                duration = time.monotonic() - start
                return self._parse_response(content, worktree, cfg, duration)

        except httpx.TimeoutException:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                "mistral_eu_http_error",
                slug=self.slug,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            return self._failed_result(cfg, worktree, duration, str(e))

    async def smoke_test(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{MISTRAL_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.slug,
                        "messages": [
                            {"role": "user", "content": "Reply JSON: {\"ok\": true}"},
                        ],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 50,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content).get("ok") is True
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            return False

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{MISTRAL_BASE}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<TASK>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</TASK>

<OUTPUT_SCHEMA>
{{
  "files": {{
    "src/<name>.py": "...",
    "tests/test_<name>.py": "..."
  }},
  "self_metrics": {{
    "loc": <int>,
    "complexity_cyclomatic_avg": <float>,
    "test_to_code_ratio": <float>,
    "todo_count": <int>,
    "imports_count": <int>,
    "functions_count": <int>
  }}
}}
</OUTPUT_SCHEMA>

EU-only routing. Output ONLY valid JSON.
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_response(
        self, content: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return self._failed_result(cfg, worktree, duration, f"Invalid JSON: {e}")

        for rel_path, source in data.get("files", {}).items():
            abs_path = worktree / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(source)

        metrics_data = data.get("self_metrics", {})
        metrics = SelfMetrics(
            loc=metrics_data.get("loc", 0),
            complexity_cyclomatic_avg=metrics_data.get("complexity_cyclomatic_avg", 0.0),
            test_to_code_ratio=metrics_data.get("test_to_code_ratio", 0.0),
            todo_count=metrics_data.get("todo_count", 0),
            imports_count=metrics_data.get("imports_count", 0),
            functions_count=metrics_data.get("functions_count", 0),
        )

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=content,
        )

    def _timeout_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"Mistral EU timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float, reason: str
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )

```


### `src/polybuild/adapters/ollama_local.py` (240 lines)

```python
"""Ollama local NAS adapter.

Calls Ollama running on the Synology DS224+ NAS via HTTP.
Used EXCLUSIVELY for medical paranoia HIGH profile (no external calls).

Models:
    - qwen2.5-coder:14b-int4 (~9 GB, 2-4 tok/s on Celeron J4125)
    - qwen2.5-coder:7b-int4  (~5 GB, 6-10 tok/s)

NOTE: DeepSeek V3.2 INT4 (685B → ~340 GB) excluded — physically impossible on 18 GB NAS.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


class OllamaLocalAdapter(BuilderProtocol):
    """Adapter for Ollama running locally on the NAS.

    Args:
        slug: Ollama model tag (e.g. "qwen2.5-coder:14b-int4")
        endpoint: HTTP endpoint (default from env or http://nas.local:11434)
    """

    family = "alibaba"  # Qwen models = Alibaba

    def __init__(
        self,
        slug: str = "qwen2.5-coder:14b-int4",
        endpoint: str | None = None,
    ):
        self.slug = slug
        self.endpoint = endpoint or os.environ.get(
            "OLLAMA_ENDPOINT", "http://nas.local:11434"
        )
        # Sanitize for adapter name
        safe = slug.replace(":", "_").replace("-", "_").replace(".", "_")
        self.name = f"ollama_local_{safe}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # Local model is slow (~3 tok/s); use generous timeout
        local_timeout = max(cfg.timeout_sec, 1800)

        try:
            async with httpx.AsyncClient(timeout=local_timeout) as client:
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.slug,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {
                            "temperature": 0.4,
                            "num_predict": 4096,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("response", "")
                duration = time.monotonic() - start
                return self._parse_response(content, worktree, cfg, duration)

        except httpx.TimeoutException:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                "ollama_local_http_error",
                slug=self.slug,
                status=e.response.status_code,
            )
            return self._failed_result(cfg, worktree, duration, str(e))

    async def smoke_test(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.slug,
                        "prompt": "Reply JSON: {\"ok\": true}",
                        "format": "json",
                        "stream": False,
                    },
                )
                response.raise_for_status()
                content = response.json().get("response", "")
                return json.loads(content).get("ok") is True
        except (httpx.HTTPError, json.JSONDecodeError):
            return False

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                if response.status_code != 200:
                    return False
                tags = response.json().get("models", [])
                return any(t.get("name") == self.slug for t in tags)
        except httpx.HTTPError:
            return False

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        safe = cfg.voice_id.replace(":", "_").replace("/", "_")
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / safe
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        agents_md = self._load_agents_md()
        # Local models = profil médical HIGH = pas de fuite externe possible par construction
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<TASK>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</TASK>

<OUTPUT_SCHEMA>
{{
  "files": {{
    "src/<name>.py": "...",
    "tests/test_<name>.py": "..."
  }},
  "self_metrics": {{"loc": 0, "complexity_cyclomatic_avg": 0.0, "test_to_code_ratio": 0.0, "todo_count": 0, "imports_count": 0, "functions_count": 0}}
}}
</OUTPUT_SCHEMA>

LOCAL EXECUTION. Output ONLY valid JSON.
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_response(
        self, content: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return self._failed_result(cfg, worktree, duration, f"Invalid JSON: {e}")

        for rel_path, source in data.get("files", {}).items():
            abs_path = worktree / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(source)

        metrics_data = data.get("self_metrics", {})
        metrics = SelfMetrics(
            loc=metrics_data.get("loc", 0),
            complexity_cyclomatic_avg=metrics_data.get("complexity_cyclomatic_avg", 0.0),
            test_to_code_ratio=metrics_data.get("test_to_code_ratio", 0.0),
            todo_count=metrics_data.get("todo_count", 0),
            imports_count=metrics_data.get("imports_count", 0),
            functions_count=metrics_data.get("functions_count", 0),
        )

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=content,
        )

    def _timeout_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"Ollama local timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float, reason: str
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )

```


### `src/polybuild/phases/__init__.py` (34 lines)

```python
"""POLYBUILD v3 phases.

Ordering:
    phase_minus_one_privacy  (Round 4)
    phase_0_spec             (implemented)
    phase_1_select           (implemented)
    phase_2_generate         (implemented)
    phase_3_score            (implemented)
    phase_3b_grounding       (implemented)
    phase_4_audit            (skeleton — to be completed)
    phase_5_triade           (skeleton — to be completed)
    phase_6_validate         (Round 4 — domain gates)
    phase_7_commit           (implemented)
    phase_8_prod_smoke       (Round 4)
"""

from polybuild.phases.phase_0_spec import phase_0_spec
from polybuild.phases.phase_1_select import select_auditor, select_mediator, select_voices
from polybuild.phases.phase_2_generate import phase_2_generate
from polybuild.phases.phase_3_score import phase_3_score
from polybuild.phases.phase_3b_grounding import phase_3b_grounding
from polybuild.phases.phase_7_commit import phase_7_commit

__all__ = [
    "phase_0_spec",
    "phase_2_generate",
    "phase_3_score",
    "phase_3b_grounding",
    "phase_7_commit",
    "select_auditor",
    "select_mediator",
    "select_voices",
]

```


### `src/polybuild/phases/phase_0_spec.py` (366 lines)

```python
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
import time
from pathlib import Path

import structlog

from polybuild.adapters import get_builder
from polybuild.models import (
    AcceptanceCriterion,
    PrivacyLevel,
    RiskProfile,
    Spec,
    SpecAttack,
    VoiceConfig,
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
) -> dict:
    """Call Opus 4.7 via Claude Code CLI to draft the spec.

    Returns a parsed dict matching the Spec schema (without spec_hash yet).
    """
    builder = get_builder("claude-opus-4.7")
    cfg = VoiceConfig(
        voice_id="claude-opus-4.7",
        family="anthropic",
        role="builder",  # we reuse the CLI invocation, but role is "spec_architect"
        timeout_sec=timeout_sec,
    )

    # Build a synthetic spec-fake to feed the adapter's prompt builder.
    # We reuse the generate() infrastructure but the "task" is to produce a SPEC,
    # not a code module. The output JSON is the spec dict.
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

    # We use the raw subprocess invocation directly here because the spec is text,
    # not a code module on disk.
    proc = await asyncio.create_subprocess_exec(
        "claude", "code",
        "--model", "opus-4.7",
        "--prompt", prompt,
        "--output-format", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Opus spec generation timeout after {timeout_sec}s")

    if proc.returncode != 0:
        raise RuntimeError(f"Opus spec generation failed: {stderr.decode()[:500]}")

    raw = stdout.decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON block from response
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise RuntimeError(f"Opus output not valid JSON: {raw[:500]}")


# ────────────────────────────────────────────────────────────────
# PHASE 0b — Spec Attack
# ────────────────────────────────────────────────────────────────


async def _spec_attack(
    spec_dict: dict,
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
        content = response.json()["choices"][0]["message"]["content"]

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
    spec_dict: dict,
    attack: SpecAttack,
    timeout_sec: int = 300,
) -> dict:
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

    proc = await asyncio.create_subprocess_exec(
        "claude", "code",
        "--model", "opus-4.7",
        "--prompt", prompt,
        "--output-format", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        proc.kill()
        logger.warning("spec_revise_timeout")
        return spec_dict  # fallback to original

    raw = stdout.decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
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

    spec = Spec(
        run_id=run_id,
        profile_id=profile_id,
        task_description=final_dict.get("task_description", brief),
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

```


### `src/polybuild/phases/phase_1_select.py` (247 lines)

```python
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
    """Return True if model is hosted by US or CN provider."""
    us_providers = {"anthropic", "openai", "google", "xai"}
    cn_providers = {"moonshot", "deepseek", "alibaba"}
    if voice_id.startswith(("claude-", "gpt-", "gemini-")):
        return True
    if voice_id.startswith(("kimi-", "deepseek/", "qwen")):
        # Note: qwen runs locally on user's NAS → not hosted by Alibaba in this context
        return not voice_id.startswith("qwen")
    if voice_id.startswith("x-ai/"):
        return True
    return False


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
        providers = [dimensions.get(v, {}).get("provider") for v in triad]
        if len(set(providers)) < len(providers):
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
        return mediator
    if mediator in voices_used:
        # Fallback: pick first auditor pool member
        # (mediator clash is misconfiguration but recoverable)
        return None
    return mediator


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

```


### `src/polybuild/phases/phase_2_generate.py` (93 lines)

```python
"""Phase 2 — Parallel generation by 3 orthogonal voices.

asyncio.gather with return_exceptions=True ensures that one voice failing
doesn't crash the others. A voice that times out or fails is dropped, but
the run continues with the remaining 2 (acquis convergent).

NOTE: concurrency_limiter integration TODO post-round 4 (Faille 3) — once
known, semaphores per CLI prevent forfait throttling.
"""

from __future__ import annotations

import asyncio

import structlog

from polybuild.adapters import get_builder
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


async def phase_2_generate(
    spec: Spec,
    voices: list[VoiceConfig],
) -> list[BuilderResult]:
    """Run all builder voices in parallel.

    Args:
        spec: canonical spec from Phase 0
        voices: list of voice configs from Phase 1

    Returns:
        list of BuilderResult (one per voice, including TIMEOUT/FAILED ones)
    """
    logger.info(
        "phase_2_start",
        run_id=spec.run_id,
        voices=[v.voice_id for v in voices],
    )

    builders = [(v, get_builder(v.voice_id)) for v in voices]

    tasks = [builder.generate(spec, cfg) for cfg, builder in builders]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    normalized: list[BuilderResult] = []
    for (cfg, _), r in zip(builders, results, strict=True):
        if isinstance(r, BuilderResult):
            normalized.append(r)
        elif isinstance(r, BaseException):
            logger.error(
                "phase_2_voice_exception",
                voice_id=cfg.voice_id,
                error=str(r),
            )
            normalized.append(
                BuilderResult(
                    voice_id=cfg.voice_id,
                    family=cfg.family,
                    code_dir=spec.run_id and __import__("pathlib").Path("/dev/null"),
                    tests_dir=__import__("pathlib").Path("/dev/null"),
                    diff_patch=__import__("pathlib").Path("/dev/null"),
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
                    error=f"Exception: {r}",
                )
            )

    n_ok = sum(1 for r in normalized if r.status == Status.OK)
    if n_ok < 2:
        logger.warning(
            "phase_2_insufficient_voices",
            n_ok=n_ok,
            n_total=len(normalized),
        )

    logger.info(
        "phase_2_done",
        run_id=spec.run_id,
        n_ok=n_ok,
        n_failed=len(normalized) - n_ok,
    )
    return normalized

```


### `src/polybuild/phases/phase_3_score.py` (247 lines)

```python
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
import re
from pathlib import Path

import structlog

from polybuild.models import BuilderResult, GateResults, Status, VoiceScore

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# GATE COMMANDS
# ────────────────────────────────────────────────────────────────

GENERAL_GATE_COMMANDS = {
    "pytest": "uv run pytest -q --tb=short --json-report --json-report-file=.pytest.json",
    "mypy": "uv run mypy --strict src/",
    "ruff": "uv run ruff check src/ tests/",
    "bandit": "uv run bandit -r src/ -ll -f json -o .bandit.json",
    "gitleaks": "gitleaks detect --no-banner --report-format=json --report-path=.gitleaks.json",
    "coverage": "uv run pytest --cov=src --cov-report=json --cov-report=term -q",
}


# ────────────────────────────────────────────────────────────────
# GATE EXECUTION
# ────────────────────────────────────────────────────────────────


async def run_command(cmd: str, cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    """Run a shell command, return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"Timeout after {timeout}s"


async def run_general_gates(workdir: Path) -> GateResults:
    """Run all general gates and aggregate results."""
    raw_outputs: dict[str, str] = {}

    # Run gates in parallel where independent
    pytest_task = run_command(GENERAL_GATE_COMMANDS["pytest"], workdir, timeout=120)
    mypy_task = run_command(GENERAL_GATE_COMMANDS["mypy"], workdir, timeout=60)
    ruff_task = run_command(GENERAL_GATE_COMMANDS["ruff"], workdir, timeout=30)
    bandit_task = run_command(GENERAL_GATE_COMMANDS["bandit"], workdir, timeout=30)
    gitleaks_task = run_command(GENERAL_GATE_COMMANDS["gitleaks"], workdir, timeout=30)

    pytest_rc, pytest_out, pytest_err = await pytest_task
    mypy_rc, mypy_out, mypy_err = await mypy_task
    ruff_rc, ruff_out, ruff_err = await ruff_task
    bandit_rc, bandit_out, bandit_err = await bandit_task
    gitleaks_rc, gitleaks_out, gitleaks_err = await gitleaks_task

    raw_outputs["pytest"] = pytest_out + pytest_err
    raw_outputs["mypy"] = mypy_out + mypy_err
    raw_outputs["ruff"] = ruff_out + ruff_err
    raw_outputs["bandit"] = bandit_out + bandit_err
    raw_outputs["gitleaks"] = gitleaks_out + gitleaks_err

    # Coverage = separate pass to avoid double pytest
    cov_rc, cov_out, _ = await run_command(
        GENERAL_GATE_COMMANDS["coverage"], workdir, timeout=120
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

```


### `src/polybuild/phases/phase_3b_grounding.py` (228 lines)

```python
"""Phase 3b — AST-based grounding check.

After Phase 2 generation, parse each voice's code and verify:
    1. Syntactically valid Python (else P0)
    2. Every `import X` references either:
        - stdlib module
        - declared dependency in pyproject.toml
        - local module of the project
       (else P1, hallucinated import)
    3. Every internal symbol reference exists (else P1)

Decision (acquis convergent #10): NO automatic fix on grounding findings.
    - ≥2 hallucinated imports → disqualification (Phase 3 hard rule)
    - 1 hallucinated import → P1 finding (Phase 5 will treat it)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import structlog

from polybuild.models import (
    BuilderResult,
    GroundingFinding,
    Severity,
    Status,
)

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# GROUNDING ENGINE
# ────────────────────────────────────────────────────────────────


class GroundingEngine:
    """AST-based 3-layer grounding checker."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.installed_pkgs = self._load_installed_deps()
        self.stdlib = set(sys.stdlib_module_names)
        self.local_modules = self._index_local_modules()
        self.local_symbols = self._index_local_symbols()

    def _load_installed_deps(self) -> set[str]:
        """Parse pyproject.toml dependencies."""
        pyproject = self.project_root / "pyproject.toml"
        if not pyproject.exists():
            return set()
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)

        deps = set()
        for dep in data.get("project", {}).get("dependencies", []):
            # "pydantic>=2.5" → "pydantic"
            name = dep.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip()
            deps.add(name.replace("-", "_"))  # PEP 503 normalization
            deps.add(name)
        # Optional deps
        for group in data.get("project", {}).get("optional-dependencies", {}).values():
            for dep in group:
                name = dep.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip()
                deps.add(name.replace("-", "_"))
                deps.add(name)
        return deps

    def _index_local_modules(self) -> set[str]:
        """All Python file stems in the project (potential top-level imports)."""
        return {
            p.stem
            for p in self.project_root.rglob("*.py")
            if not p.name.startswith("_") and "__pycache__" not in p.parts
        }

    def _index_local_symbols(self) -> set[str]:
        """All function/class names defined in the project."""
        symbols = set()
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(
                        node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                    ):
                        symbols.add(node.name)
            except (SyntaxError, UnicodeDecodeError):
                continue
        return symbols

    def _is_valid_top_module(self, mod: str) -> bool:
        """Check if module top-level name is resolvable."""
        top = mod.split(".")[0]
        return (
            top in self.installed_pkgs
            or top in self.stdlib
            or top in self.local_modules
        )

    def check_file(self, py_file: Path, voice_id: str) -> list[GroundingFinding]:
        """Analyze a single Python file for grounding issues."""
        findings: list[GroundingFinding] = []
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except SyntaxError as e:
            findings.append(
                GroundingFinding(
                    severity=Severity.P0,
                    voice_id=voice_id,
                    kind="syntax_error",
                    detail=f"{py_file.name}:{e.lineno}: {e.msg}",
                    file=py_file,
                    line=e.lineno,
                )
            )
            return findings
        except UnicodeDecodeError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._is_valid_top_module(alias.name):
                        findings.append(
                            GroundingFinding(
                                severity=Severity.P1,
                                voice_id=voice_id,
                                kind="hallucinated_import",
                                detail=f"Import '{alias.name}' not found in deps/stdlib/local",
                                file=py_file,
                                line=node.lineno,
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and not self._is_valid_top_module(node.module):
                    findings.append(
                        GroundingFinding(
                            severity=Severity.P1,
                            voice_id=voice_id,
                            kind="hallucinated_import_from",
                            detail=f"From '{node.module}' not found",
                            file=py_file,
                            line=node.lineno,
                        )
                    )

        return findings

    def check_directory(self, code_dir: Path, voice_id: str) -> list[GroundingFinding]:
        """Analyze all .py files in a directory."""
        findings: list[GroundingFinding] = []
        for py_file in code_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            findings.extend(self.check_file(py_file, voice_id))
        return findings


# ────────────────────────────────────────────────────────────────
# DISQUALIFICATION RULE
# ────────────────────────────────────────────────────────────────


def grounding_disqualifies(findings: list[GroundingFinding]) -> tuple[bool, str | None]:
    """Apply the ≥2 hallucinated imports disqualification rule."""
    p0 = [f for f in findings if f.severity == Severity.P0]
    if p0:
        return True, f"Grounding P0: {len(p0)} syntax error(s)"

    halluc_imports = [
        f
        for f in findings
        if f.kind in {"hallucinated_import", "hallucinated_import_from"}
    ]
    if len(halluc_imports) >= 2:
        return True, f"≥2 hallucinated imports ({len(halluc_imports)})"
    return False, None


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_3b_grounding(
    results: list[BuilderResult],
    project_root: Path = Path("."),
) -> dict[str, list[GroundingFinding]]:
    """Run grounding checks on all builder results.

    Returns:
        dict mapping voice_id → list of findings.
    """
    logger.info("phase_3b_start", n_results=len(results))
    engine = GroundingEngine(project_root)

    findings_by_voice: dict[str, list[GroundingFinding]] = {}
    for r in results:
        if r.status != Status.OK:
            findings_by_voice[r.voice_id] = []
            continue
        f = engine.check_directory(r.code_dir, r.voice_id)
        findings_by_voice[r.voice_id] = f
        dq, reason = grounding_disqualifies(f)
        if dq:
            logger.warning(
                "phase_3b_disqualified",
                voice_id=r.voice_id,
                reason=reason,
            )

    n_findings_total = sum(len(f) for f in findings_by_voice.values())
    logger.info("phase_3b_done", n_findings=n_findings_total)
    return findings_by_voice

```


### `src/polybuild/phases/phase_4_audit.py` (287 lines)

```python
"""Phase 4 — Orthogonal POLYLENS audit.

Rule (acquis convergent):
    - Auditor model family ≠ winner family
    - For medical sensitive: pool filtered to exclude US/CN
    - Audit axes selected per profile (A_security, B_quality, ..., G_adversarial)

Quality control (anti `Auditor Laziness`):
    - If finding_count == 0 AND audit_duration < 60s → audit rejected, retry
"""

from __future__ import annotations

import asyncio
import json
import os
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
    """Send the winner's code to an auditor and parse the structured findings."""
    # Read the actual code files
    code_files = {}
    for py_file in winner_result.code_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        try:
            code_files[str(py_file.relative_to(winner_result.code_dir))] = py_file.read_text()
        except (UnicodeDecodeError, OSError):
            continue

    test_files = {}
    for py_file in winner_result.tests_dir.rglob("test_*.py"):
        if "__pycache__" in py_file.parts:
            continue
        try:
            test_files[str(py_file.relative_to(winner_result.tests_dir))] = py_file.read_text()
        except (UnicodeDecodeError, OSError):
            continue

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

    # Auditor invocation depends on the model
    # For OpenRouter models (deepseek, grok), HTTP call.
    # For Claude/GPT/Gemini CLI models, use the corresponding adapter.
    # For now, route OR models via HTTP.
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
        # Fallback: invoke via Claude Code if available
        proc = await asyncio.create_subprocess_exec(
            "claude", "code",
            "--model", auditor_voice.removeprefix("claude-"),
            "--prompt", prompt,
            "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        content = stdout.decode()

    duration = time.monotonic() - start

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("audit_invalid_json", auditor=auditor_voice)
        return AuditReport(
            auditor_model=auditor_voice,
            auditor_family=auditor_voice.split("/")[0] if "/" in auditor_voice else "unknown",
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
                    auditor_family=auditor_voice.split("/")[0] if "/" in auditor_voice else "unknown",
                )
            )
        except (KeyError, ValueError) as e:
            logger.warning("audit_finding_parse_error", error=str(e), finding=f_dict)
            continue

    return AuditReport(
        auditor_model=auditor_voice,
        auditor_family=auditor_voice.split("/")[0] if "/" in auditor_voice else "unknown",
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

```


### `src/polybuild/phases/phase_5_triade.py` (532 lines)

```python
"""Phase 5 — Critic-Fixer-Verifier triade.

Severity-differentiated handling (acquis convergent T4):
    - P0: per-finding triade, Critic ≠ Fixer ≠ Verifier (3 distinct families)
    - P1: batched by axis, single Critic + Fixer per batch
    - P2/P3: local auto-fix (ruff --fix, mypy --hint), NO LLM

Verifier (Évaluateur-Optimiseur strict):
    - JSON-only output: {pass, reason, required_evidence}
    - NEVER rewrites code
    - Rejects by default if no reproducible evidence

Local gates first (PRE-LLM check):
    Before invoking the Verifier, run pytest + mypy + bandit on the patch.
    If they fail, loop back to Fixer with failure context (saves verifier tokens).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path

import structlog

from polybuild.adapters import get_builder
from polybuild.models import (
    AuditReport,
    BuilderResult,
    Finding,
    FixReport,
    FixResult,
    RiskProfile,
    Severity,
)

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# ROLE ASSIGNMENT (anti self-fix)
# ────────────────────────────────────────────────────────────────


def pick_triade(
    winner_family: str,
    auditor_family: str,
    risk_profile: RiskProfile,
) -> tuple[str, str, str]:
    """Pick (critic, fixer, verifier) where each has a different family.

    Excludes:
        - winner_family (avoids self-fix bias)
        - auditor_family (avoids audit-fix collusion for the verifier)
    """
    # Hard pool minus excluded families
    all_models = [
        ("claude-opus-4.7", "anthropic"),
        ("gpt-5.5", "openai"),
        ("gemini-3.1-pro", "google"),
        ("kimi-k2.6", "moonshot"),
        ("deepseek/deepseek-v4-pro", "deepseek"),
        ("x-ai/grok-4.20", "xai"),
        ("mistral/devstral-2", "mistral"),
    ]

    # Filter for risk profile
    if risk_profile.excludes_openrouter:
        all_models = [(m, f) for m, f in all_models if not m.startswith(("deepseek/", "x-ai/"))]
    if risk_profile.excludes_us_cn_models:
        excluded_families = {"anthropic", "openai", "google", "xai", "moonshot"}
        all_models = [(m, f) for m, f in all_models if f not in excluded_families]

    available = [(m, f) for m, f in all_models if f != winner_family]

    # Critic: any family ≠ winner
    critic_model, critic_family = available[0]

    # Fixer: ≠ winner AND ≠ critic
    fixer_candidates = [(m, f) for m, f in available if f != critic_family]
    if not fixer_candidates:
        raise RuntimeError("No fixer candidate available")
    fixer_model, fixer_family = fixer_candidates[0]

    # Verifier: ≠ winner AND ≠ critic AND ≠ fixer AND ≠ auditor (no collusion)
    verifier_candidates = [
        (m, f)
        for m, f in available
        if f not in {critic_family, fixer_family, auditor_family}
    ]
    if not verifier_candidates:
        # Relax: allow auditor family for verifier (acceptable degradation)
        verifier_candidates = [
            (m, f) for m, f in available if f not in {critic_family, fixer_family}
        ]
    verifier_model = verifier_candidates[0][0]

    return critic_model, fixer_model, verifier_model


# ────────────────────────────────────────────────────────────────
# PROMPT LOADING
# ────────────────────────────────────────────────────────────────

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ directory."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        # Soft fallback: minimal inline prompt to avoid hard crash during bootstrap.
        logger.warning("prompt_template_missing", name=name, path=str(path))
        return f"# {name}\n\n(Template missing — using minimal inline fallback.)\n\n"
    return path.read_text(encoding="utf-8")


# ────────────────────────────────────────────────────────────────
# LOCAL GATES (PRE-VERIFIER)
# ────────────────────────────────────────────────────────────────


async def _run_local_gates(code_dir: Path) -> tuple[bool, str]:
    """Run pytest + mypy + ruff on patched code BEFORE invoking Verifier.

    Returns (all_pass, failure_summary). Saves Verifier tokens by short-circuiting
    on local lint/type/test failures.
    """
    failures: list[str] = []

    for label, args in [
        ("ruff", ["uv", "run", "ruff", "check", "src/"]),
        ("mypy", ["uv", "run", "mypy", "--strict", "src/"]),
        ("pytest", ["uv", "run", "pytest", "-x", "--no-header", "-q"]),
    ]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=code_dir.parent,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            if proc.returncode != 0:
                excerpt = (stdout + stderr).decode("utf-8", errors="replace")[-800:]
                failures.append(f"[{label}] returncode={proc.returncode}\n{excerpt}")
        except asyncio.TimeoutError:
            failures.append(f"[{label}] timeout >180s")
        except FileNotFoundError:
            # Tool not available in this environment — non-blocking.
            logger.debug("local_gate_tool_missing", tool=label)

    if not failures:
        return True, ""
    return False, "\n\n".join(failures)


# ────────────────────────────────────────────────────────────────
# JSON VERDICT PARSING (Verifier output)
# ────────────────────────────────────────────────────────────────


def _parse_verifier_verdict(raw: str) -> dict:
    """Extract {pass, reason, required_evidence} from Verifier output.

    Verifier is JSON-only by spec. We still defend against fenced blocks
    or trailing prose (frequent on smaller models).
    """
    # Try fenced ```json blocks first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = fenced.group(1) if fenced else raw

    # Find first balanced { ... } block
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        return {"pass": False, "reason": "verifier_returned_no_json", "required_evidence": []}

    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return {
            "pass": False,
            "reason": f"verifier_json_decode_error: {e}",
            "required_evidence": [],
        }

    return {
        "pass": bool(verdict.get("pass", False)),
        "reason": str(verdict.get("reason", "")),
        "required_evidence": list(verdict.get("required_evidence", [])),
    }


# ────────────────────────────────────────────────────────────────
# P0 PER-FINDING TRIADE
# ────────────────────────────────────────────────────────────────


async def _invoke_role(
    role: str,
    model: str,
    prompt: str,
    code_dir: Path,
    timeout_s: int = 600,
) -> str:
    """Invoke a model in a given triade role (critic/fixer/verifier).

    Returns the raw text output. Adapter dispatch is handled by get_builder().
    """
    builder = get_builder(model)
    result = await builder.generate(
        prompt=prompt,
        workdir=code_dir.parent,
        timeout_s=timeout_s,
        role=role,
    )
    return result.raw_output if hasattr(result, "raw_output") else str(result)


async def _triade_p0(
    finding: Finding,
    winner: BuilderResult,
    risk_profile: RiskProfile,
    auditor_family: str,
    max_iterations: int = 2,
) -> FixResult:
    """Process a single P0 finding through critic→fixer→verifier round-trip.

    Loop:
        1. Critic confirms the finding is real and reproducible.
        2. Fixer produces a patch + regression test.
        3. Local gates (pytest/mypy/ruff) — short-circuit if they fail.
        4. Verifier issues a strict JSON verdict {pass, reason, evidence}.
        5. If reject and iteration < max → loop back to Fixer with verdict.
        6. If still reject after max_iterations → escalate.
    """
    critic, fixer, verifier = pick_triade(winner.family, auditor_family, risk_profile)

    logger.info(
        "p0_triade_start",
        finding_id=finding.id,
        critic=critic,
        fixer=fixer,
        verifier=verifier,
    )

    critic_template = _load_prompt("critic")
    fixer_template = _load_prompt("fixer")
    verifier_template = _load_prompt("verifier_strict")

    # ── Step 1: Critic confirms the finding ─────────────────────────────
    critic_prompt = critic_template.format(
        finding_id=finding.id,
        severity=finding.severity.value,
        axis=finding.axis,
        description=finding.description,
        evidence_path=finding.evidence.file_path if finding.evidence else "n/a",
        evidence_excerpt=(finding.evidence.excerpt if finding.evidence else "")[:2000],
    )
    try:
        critic_output = await _invoke_role("critic", critic, critic_prompt, winner.code_dir)
    except Exception as e:
        logger.error("p0_critic_failed", finding_id=finding.id, error=str(e))
        return FixResult(
            finding_ids=[finding.id],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=0,
        )

    # If critic dismisses the finding (false positive), escalate to human.
    if "FALSE_POSITIVE" in critic_output.upper():
        logger.info("p0_false_positive", finding_id=finding.id)
        return FixResult(
            finding_ids=[finding.id],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=1,
        )

    # ── Steps 2-5: Fixer ↔ Verifier loop ────────────────────────────────
    last_verdict: dict = {"pass": False, "reason": "no_attempt", "required_evidence": []}
    fixer_feedback = ""

    for iteration in range(1, max_iterations + 1):
        fixer_prompt = fixer_template.format(
            finding_id=finding.id,
            critic_analysis=critic_output[:4000],
            previous_verdict=fixer_feedback or "(first attempt)",
            evidence_path=finding.evidence.file_path if finding.evidence else "n/a",
        )
        try:
            await _invoke_role("fixer", fixer, fixer_prompt, winner.code_dir)
        except Exception as e:
            logger.error("p0_fixer_failed", finding_id=finding.id, error=str(e))
            break

        # Local gates short-circuit
        gates_ok, gates_summary = await _run_local_gates(winner.code_dir)
        if not gates_ok:
            fixer_feedback = f"Local gates failed:\n{gates_summary}\nRework the patch."
            logger.info(
                "p0_local_gates_failed",
                finding_id=finding.id,
                iteration=iteration,
            )
            continue

        # Verifier
        verifier_prompt = verifier_template.format(
            finding_id=finding.id,
            critic_analysis=critic_output[:2000],
            local_gates_status="all green",
        )
        try:
            verifier_raw = await _invoke_role(
                "verifier", verifier, verifier_prompt, winner.code_dir
            )
        except Exception as e:
            logger.error("p0_verifier_failed", finding_id=finding.id, error=str(e))
            break

        last_verdict = _parse_verifier_verdict(verifier_raw)
        if last_verdict["pass"]:
            logger.info(
                "p0_triade_accepted",
                finding_id=finding.id,
                iterations=iteration,
            )
            return FixResult(
                finding_ids=[finding.id],
                status="accepted",
                critic_model=critic,
                fixer_model=fixer,
                verifier_model=verifier,
                iterations=iteration,
            )

        fixer_feedback = (
            f"Verifier rejected: {last_verdict['reason']}. "
            f"Required evidence: {last_verdict['required_evidence']}"
        )
        logger.info(
            "p0_verifier_rejected",
            finding_id=finding.id,
            iteration=iteration,
            reason=last_verdict["reason"],
        )

    # Max iterations exhausted → escalate
    logger.warning(
        "p0_triade_escalate",
        finding_id=finding.id,
        last_reason=last_verdict.get("reason"),
    )
    return FixResult(
        finding_ids=[finding.id],
        status="escalate",
        critic_model=critic,
        fixer_model=fixer,
        verifier_model=verifier,
        iterations=max_iterations,
    )


# ────────────────────────────────────────────────────────────────
# P1 BATCH BY AXIS
# ────────────────────────────────────────────────────────────────


async def _triade_p1_batch(
    axis: str,
    findings: list[Finding],
    winner: BuilderResult,
    risk_profile: RiskProfile,
    auditor_family: str,
) -> FixResult:
    """Batch all P1 findings of the same axis into a single Fixer call.

    P1 is less critical than P0, so:
        - Single Critic confirmation pass (group review)
        - Single Fixer pass (no Verifier loop)
        - Local gates as final guard (no LLM Verifier — saves tokens)
    """
    critic, fixer, verifier = pick_triade(winner.family, auditor_family, risk_profile)

    logger.info(
        "p1_batch_start",
        axis=axis,
        n_findings=len(findings),
        fixer=fixer,
    )

    fixer_template = _load_prompt("fixer")

    # Aggregate findings into a single context block
    findings_block = "\n\n".join(
        f"- [{f.id}] {f.description}\n"
        f"  evidence: {f.evidence.file_path if f.evidence else 'n/a'}"
        for f in findings
    )

    fixer_prompt = fixer_template.format(
        finding_id=f"P1_BATCH_{axis}",
        critic_analysis=f"Batch of {len(findings)} P1 findings on axis '{axis}':\n{findings_block}",
        previous_verdict="(P1 batch — no prior attempt)",
        evidence_path="(see findings list)",
    )

    try:
        await _invoke_role("fixer", fixer, fixer_prompt, winner.code_dir)
    except Exception as e:
        logger.error("p1_fixer_failed", axis=axis, error=str(e))
        return FixResult(
            finding_ids=[f.id for f in findings],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=0,
        )

    # Local gates as final guard (no Verifier loop for P1)
    gates_ok, gates_summary = await _run_local_gates(winner.code_dir)
    if not gates_ok:
        logger.warning("p1_local_gates_failed", axis=axis, summary=gates_summary[:300])
        return FixResult(
            finding_ids=[f.id for f in findings],
            status="escalate",
            critic_model=critic,
            fixer_model=fixer,
            verifier_model=verifier,
            iterations=1,
        )

    logger.info("p1_batch_accepted", axis=axis, n_findings=len(findings))
    return FixResult(
        finding_ids=[f.id for f in findings],
        status="accepted",
        critic_model=critic,
        fixer_model=fixer,
        verifier_model=verifier,
        iterations=1,
    )


# ────────────────────────────────────────────────────────────────
# P2/P3 LOCAL AUTO-FIX
# ────────────────────────────────────────────────────────────────


async def _auto_fix_local(findings: list[Finding], winner: BuilderResult) -> FixResult:
    """Apply ruff --fix and similar non-LLM fixes."""
    # ruff --fix
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "ruff", "check", "--fix", "src/", "tests/",
        cwd=winner.code_dir.parent,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    return FixResult(
        finding_ids=[f.id for f in findings],
        status="accepted",
        critic_model="<local>",
        fixer_model="ruff",
        verifier_model="<local>",
        iterations=1,
    )


# ────────────────────────────────────────────────────────────────
# DISPATCHER
# ────────────────────────────────────────────────────────────────


async def phase_5_dispatch(
    audit: AuditReport,
    winner: BuilderResult,
    risk_profile: RiskProfile,
) -> FixReport:
    """Dispatch findings to appropriate triade strategy."""
    logger.info(
        "phase_5_start",
        winner=winner.voice_id,
        n_findings=len(audit.findings),
    )

    p0 = [f for f in audit.findings if f.severity == Severity.P0]
    p1_by_axis: dict[str, list[Finding]] = defaultdict(list)
    for f in audit.findings:
        if f.severity == Severity.P1:
            p1_by_axis[f.axis].append(f)
    p2_p3 = [f for f in audit.findings if f.severity in {Severity.P2, Severity.P3}]

    results: list[FixResult] = []

    # P0: per-finding sequential triade
    for f in p0:
        result = await _triade_p0(f, winner, risk_profile, audit.auditor_family)
        results.append(result)
        if result.status == "escalate":
            logger.warning("phase_5_p0_escalate", finding_id=f.id)
            return FixReport(status="blocked_p0", results=results)

    # P1: batched per axis
    for axis, batch in p1_by_axis.items():
        result = await _triade_p1_batch(axis, batch, winner, risk_profile, audit.auditor_family)
        results.append(result)

    # P2/P3: local auto-fix
    if p2_p3:
        result = await _auto_fix_local(p2_p3, winner)
        results.append(result)

    has_partial = any(r.status == "escalate" for r in results)
    final_status = "partial" if has_partial else "completed"

    logger.info(
        "phase_5_done",
        n_results=len(results),
        status=final_status,
    )
    return FixReport(status=final_status, results=results)

```


### `src/polybuild/phases/phase_7_commit.py` (245 lines)

```python
"""Phase 7 — Git commit + automatic ADR generation.

Strategy (acquis convergent):
    - Tag pre-commit (rollback anchor): polybuild/run-{run_id}-pre
    - Commit message includes co-author = winning voice
    - Tag post-commit: polybuild/run-{run_id}-commit
    - ADR auto-generated only when ADR_TRIGGERS match

Rollback procedure (manual or via Phase 8 prod_smoke):
    git reset --hard polybuild/run-{run_id}-pre
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import structlog

from polybuild.models import CommitInfo, PolybuildRun

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# ADR TRIGGERS (acquis Round 3)
# ────────────────────────────────────────────────────────────────

ADR_TRIGGERS = {
    "schema_db_change",
    "new_dependency",
    "architecture_pattern_change",
    "breaking_api_change",
    "polylens_p0_resolved",
    "domain_gate_change",
    "privacy_gate_rule_change",
}


# ────────────────────────────────────────────────────────────────
# GIT HELPERS
# ────────────────────────────────────────────────────────────────


async def _git(*args: str, cwd: Path = Path(".")) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode(), stderr.decode()


async def _list_changed_files(cwd: Path = Path(".")) -> list[Path]:
    """Return list of files changed (staged + unstaged)."""
    rc, stdout, _ = await _git("status", "--porcelain", cwd=cwd)
    if rc != 0:
        return []
    files: list[Path] = []
    for line in stdout.splitlines():
        # format: "XY path/to/file"
        if len(line) >= 4:
            files.append(Path(line[3:]))
    return files


# ────────────────────────────────────────────────────────────────
# ADR GENERATION
# ────────────────────────────────────────────────────────────────


async def _next_adr_id(project_root: Path) -> str:
    """Find next ADR ID (0001, 0002, ...)."""
    adr_dir = project_root / "docs" / "adr"
    if not adr_dir.exists():
        return "0001"
    existing = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
    if not existing:
        return "0001"
    last = existing[-1].name
    last_id = int(last.split("-", 1)[0])
    return f"{last_id + 1:04d}"


async def _generate_adr(
    project_root: Path,
    run: PolybuildRun,
    trigger: str,
) -> str | None:
    """Use Claude Opus 4.7 to generate ADR text."""
    prompt = f"""You are generating an Architecture Decision Record (ADR).

Trigger: {trigger}
Run summary:
{json.dumps(run.model_dump(mode='json'), indent=2, ensure_ascii=False)}

Output ONLY the ADR markdown (no prose around it), structured:
# ADR-XXXX: <Title>
## Status
Accepted / Proposed / Deprecated
## Context
<2-3 paragraphs>
## Decision
<what was decided>
## Consequences
<positive and negative>
## Alternatives considered
<list>
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "code",
            "--model", "opus-4.7",
            "--prompt", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        return stdout.decode().strip()
    except (asyncio.TimeoutError, OSError) as e:
        logger.warning("adr_generation_failed", error=str(e))
        return None


def detect_adr_triggers(run: PolybuildRun, changed_files: list[Path]) -> list[str]:
    """Heuristic detection of which ADR triggers apply to this run."""
    triggers: list[str] = []

    file_names = {f.name for f in changed_files}
    if any(f.endswith((".sql", "schema.py", "models.py")) for f in file_names):
        triggers.append("schema_db_change")

    if "pyproject.toml" in file_names:
        triggers.append("new_dependency")

    if run.audit_findings_by_severity.get("P0", 0) > 0:
        triggers.append("polylens_p0_resolved")

    return triggers


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_7_commit(
    run: PolybuildRun,
    project_root: Path = Path("."),
    skip_adr: bool = False,
) -> CommitInfo:
    """Commit changes, create rollback tags, generate ADR if applicable."""
    logger.info("phase_7_start", run_id=run.run_id)

    tag_pre = f"polybuild/run-{run.run_id}-pre"
    tag_post = f"polybuild/run-{run.run_id}-commit"

    # 1. Pre-commit tag (rollback anchor) — points to current HEAD
    rc, _, stderr = await _git("tag", tag_pre, cwd=project_root)
    if rc != 0 and "already exists" not in stderr:
        logger.warning("phase_7_pre_tag_failed", stderr=stderr)

    # 2. Stage all changes
    rc, _, stderr = await _git("add", "-A", cwd=project_root)
    if rc != 0:
        raise RuntimeError(f"git add failed: {stderr}")

    # 3. List changed files for ADR detection
    changed = await _list_changed_files(project_root)

    # 4. Build commit message
    summary = run.profile_id.replace("_", " ").title()
    winner = run.winner_voice_id or "polybuild"
    commit_msg = f"""polybuild: {summary} [run-{run.run_id}]

Profile: {run.profile_id}
Winner voice: {winner}
Findings resolved: P0={run.audit_findings_by_severity.get('P0', 0)} P1={run.audit_findings_by_severity.get('P1', 0)}

Co-authored-by: {winner} <polybuild@reddie.local>
Polybuild-run: {run.run_id}
Polybuild-spec-hash: {run.spec_hash[:12]}
"""

    rc, stdout, stderr = await _git("commit", "-m", commit_msg, cwd=project_root)
    if rc != 0:
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            logger.warning("phase_7_no_changes")
            return CommitInfo(
                sha="",
                message=commit_msg,
                tag_pre=tag_pre,
                tag_post=tag_post,
                files_changed=[],
            )
        raise RuntimeError(f"git commit failed: {stderr}")

    # 5. Get commit SHA
    _, sha_out, _ = await _git("rev-parse", "HEAD", cwd=project_root)
    commit_sha = sha_out.strip()

    # 6. Post-commit tag
    await _git("tag", tag_post, cwd=project_root)

    # 7. ADR if applicable
    adr_id: str | None = None
    if not skip_adr:
        triggers = detect_adr_triggers(run, changed)
        if triggers:
            adr_text = await _generate_adr(project_root, run, ", ".join(triggers))
            if adr_text:
                adr_id = await _next_adr_id(project_root)
                adr_dir = project_root / "docs" / "adr"
                adr_dir.mkdir(parents=True, exist_ok=True)
                adr_path = adr_dir / f"{adr_id}-polybuild-run-{run.run_id}.md"
                adr_path.write_text(adr_text)
                # Amend commit to include ADR
                await _git("add", str(adr_path), cwd=project_root)
                await _git("commit", "--amend", "--no-edit", cwd=project_root)
                _, sha_out, _ = await _git("rev-parse", "HEAD", cwd=project_root)
                commit_sha = sha_out.strip()
                # Re-tag post (move tag to amended commit)
                await _git("tag", "-f", tag_post, cwd=project_root)

    logger.info(
        "phase_7_done",
        run_id=run.run_id,
        sha=commit_sha[:12],
        adr_id=adr_id,
        files=len(changed),
    )

    return CommitInfo(
        sha=commit_sha,
        message=commit_msg,
        tag_pre=tag_pre,
        tag_post=tag_post,
        files_changed=changed,
        adr_id=adr_id,
    )

```


### `config/model_dimensions.yaml` (210 lines)

```yaml
# config/model_dimensions.yaml
# Matrice de diversité multi-dimensions pour Phase 1 (sélection des voix)
# 5 dimensions orthogonales : provider, architecture, alignment, corpus_proxy, role_bias

# ────────────────────────────────────────────────────────────────
# MODÈLES CLI GRATUITS
# ────────────────────────────────────────────────────────────────

claude-opus-4.7:
  provider: anthropic
  architecture: dense
  alignment: safety_first
  corpus_proxy: anthropic_corpus
  role_bias: architect

claude-sonnet-4.6:
  provider: anthropic
  architecture: dense
  alignment: balanced
  corpus_proxy: anthropic_corpus
  role_bias: workhorse

claude-haiku-4.5:
  provider: anthropic
  architecture: dense
  alignment: balanced
  corpus_proxy: anthropic_corpus
  role_bias: fast_atomic

gpt-5.5:
  provider: openai
  architecture: dense
  alignment: agentic
  corpus_proxy: openai_corpus
  role_bias: pragmatic_builder

gpt-5.5-pro:
  provider: openai
  architecture: dense
  alignment: agentic
  corpus_proxy: openai_corpus
  role_bias: deep_reasoner

gpt-5.4:
  provider: openai
  architecture: dense
  alignment: agentic
  corpus_proxy: openai_corpus
  role_bias: workhorse

gpt-5.3-codex:
  provider: openai
  architecture: dense
  alignment: agentic
  corpus_proxy: openai_corpus
  role_bias: cli_specialist

gemini-3.1-pro:
  provider: google
  architecture: dense
  alignment: helpful
  corpus_proxy: google_corpus
  role_bias: long_context_integrator

gemini-3.1-flash:
  provider: google
  architecture: dense
  alignment: helpful
  corpus_proxy: google_corpus
  role_bias: fast_batch

kimi-k2.6:
  provider: moonshot
  architecture: moe
  alignment: creative
  corpus_proxy: chinese_corpus
  role_bias: variant_explorer

# ────────────────────────────────────────────────────────────────
# OPENROUTER
# ────────────────────────────────────────────────────────────────

deepseek/deepseek-v4-pro:
  provider: deepseek
  architecture: moe
  alignment: algo_strict
  corpus_proxy: deepseek_corpus
  role_bias: math_reasoner

deepseek/deepseek-v4-flash:
  provider: deepseek
  architecture: moe
  alignment: algo_strict
  corpus_proxy: deepseek_corpus
  role_bias: fast_cheap

x-ai/grok-4.20:
  provider: xai
  architecture: dense
  alignment: prompt_adherent
  corpus_proxy: xai_corpus
  role_bias: skeptic

# ────────────────────────────────────────────────────────────────
# MISTRAL EU
# ────────────────────────────────────────────────────────────────

mistral/devstral-2:
  provider: mistral
  architecture: dense
  alignment: agentic
  corpus_proxy: mistral_corpus
  role_bias: agentic_eu

# ────────────────────────────────────────────────────────────────
# LOCAL
# ────────────────────────────────────────────────────────────────

qwen2.5-coder:14b-int4:
  provider: alibaba
  architecture: dense
  alignment: helpful
  corpus_proxy: alibaba_corpus
  role_bias: local_safe

qwen2.5-coder:7b-int4:
  provider: alibaba
  architecture: dense
  alignment: helpful
  corpus_proxy: alibaba_corpus
  role_bias: local_atomic

# ────────────────────────────────────────────────────────────────
# DOCUMENTATION DES DIMENSIONS
# ────────────────────────────────────────────────────────────────

dimensions_doc:
  provider:
    description: "Organisation qui entraîne et opère le modèle"
    values: [anthropic, openai, google, moonshot, deepseek, xai, mistral, alibaba]

  architecture:
    description: "Architecture neurale fondamentale"
    values: [dense, moe]
    notes: "MoE = Mixture-of-Experts, paramètres actifs partiels"

  alignment:
    description: "Bias d'alignement / RLHF dominant"
    values:
      - safety_first       # refuse beaucoup, prudent
      - balanced           # compromis utilité/sécurité
      - agentic            # exécution stricte des tâches
      - helpful            # assistance maximale
      - creative           # exploration de variantes
      - algo_strict        # rigueur mathématique
      - prompt_adherent    # respect strict des instructions

  corpus_proxy:
    description: "Provenance majoritaire estimée des données d'entraînement"
    values:
      - anthropic_corpus   # propriétaire Anthropic + web filtré
      - openai_corpus      # propriétaire OpenAI + web
      - google_corpus      # web Google + propriétaire
      - chinese_corpus     # données chinoises + occidentales (Moonshot, Alibaba)
      - deepseek_corpus    # focus algo/math + web
      - xai_corpus         # web temps réel + données X
      - mistral_corpus     # corpus européen + multilingue
      - alibaba_corpus     # corpus chinois + multilingue

  role_bias:
    description: "Force fonctionnelle dominante observée"
    values:
      - architect              # vue système, design haut niveau
      - workhorse              # généraliste équilibré
      - pragmatic_builder      # exécution efficace
      - deep_reasoner          # raisonnement long et profond
      - cli_specialist         # spécialiste terminal/CLI
      - long_context_integrator # ingestion massive
      - fast_batch             # rapidité, batch
      - fast_atomic            # rapidité tâches atomiques
      - variant_explorer       # créativité, alternatives
      - math_reasoner          # rigueur mathématique
      - skeptic                # critique, low hallucination
      - agentic_eu             # agentic + souveraineté EU
      - local_safe             # exécution locale sécurisée
      - local_atomic           # local rapide

# ────────────────────────────────────────────────────────────────
# EXEMPLES DE SCORES DE DIVERSITÉ (validation)
# ────────────────────────────────────────────────────────────────

example_diversity_scores:
  # Triade convergente (mauvaise) : 3 modèles US dense
  bad_triad_us_dense:
    voices: [claude-opus-4.7, gpt-5.5, gemini-3.1-pro]
    score: 3.33  # provider OK, mais architecture/corpus très proches
    notes: "Diversité moyenne malgré 3 providers différents (tous US dense web-trained)"

  # Triade orthogonale (bonne) : multi-architecture, multi-corpus
  good_triad_orthogonal:
    voices: [claude-opus-4.7, deepseek/deepseek-v4-pro, kimi-k2.6]
    score: 4.67  # provider, architecture, alignment, corpus, role_bias tous différents
    notes: "Diversité maximale : Anthropic dense vs DeepSeek MoE vs Moonshot MoE chinois"

  # Triade médicale paranoia HIGH (locale)
  medical_high_local:
    voices: [qwen2.5-coder:14b-int4, mistral/devstral-2, qwen2.5-coder:7b-int4]
    score: 1.67  # diversité faible mais imposée par contraintes RGPD
    notes: "Conformité prime sur diversité pour profil HIGH"

```


### `config/timeouts.yaml` (147 lines)

```yaml
# config/timeouts.yaml
# Politique de timeouts par phase et global

# ────────────────────────────────────────────────────────────────
# TIMEOUT GLOBAL PAR RUN
# ────────────────────────────────────────────────────────────────
global:
  default_seconds: 2700              # 45 min (acquis convergent Round 3)
  helia_critical_seconds: 3600       # 60 min pour profils HELIA
  quick_refactor_seconds: 1200       # 20 min pour refactor mécanique
  on_hard_timeout: checkpoint_and_abort_no_partial_commit
  on_soft_timeout: notify_user_async # à 80% du global

# ────────────────────────────────────────────────────────────────
# TIMEOUTS PAR PHASE
# ────────────────────────────────────────────────────────────────
phases:

  phase_minus_one_privacy:
    default_seconds: 60
    max_seconds: 120
    critical: true
    on_timeout: abort
    notes: "Phase courte, échec = abort run"

  phase_0_spec:
    default_seconds: 480              # 8 min
    max_seconds: 720
    critical: true
    on_timeout: checkpoint_abort
    notes: "Opus 4.7 génération spec"

  phase_0b_spec_attack:
    default_seconds: 180              # 3 min
    max_seconds: 300
    critical: false
    on_timeout: continue_with_warning
    notes: "Si timeout, continue sans Spec Attack (warning)"

  phase_1_routing:
    default_seconds: 30
    max_seconds: 120
    critical: false
    on_timeout: abort
    notes: "30s matrice statique, 120s si sonde 50 LOC"

  phase_2_generate:
    default_seconds: 720              # 12 min (3 voix parallèles)
    max_seconds: 900                  # 15 min
    critical: true
    on_timeout: drop_timed_out_voice
    notes: "Si une voix timeout, dropée mais run continue avec 2 voix"

  phase_3_score:
    default_seconds: 60
    max_seconds: 120
    critical: false
    on_timeout: abort

  phase_3b_grounding:
    default_seconds: 60
    max_seconds: 120
    critical: true
    on_timeout: abort
    notes: "Grounding AST échoué = abort"

  phase_4_audit:
    default_seconds: 300              # 5 min
    max_seconds: 480
    critical: false
    on_timeout: skip_with_warning
    notes: "Si audit timeout, commit avec warning sécurité"

  phase_5_triade:
    default_seconds: 720              # 12 min total (P0s + P1 batch)
    max_seconds: 900                  # 15 min
    critical: true
    on_timeout: checkpoint_abort
    sub_timeouts:
      p0_per_finding_seconds: 480     # 8 min par P0
      p1_batch_per_axis_seconds: 600  # 10 min par batch P1

  phase_6_validate:
    default_seconds: 180
    max_seconds: 300
    critical: false
    on_timeout: skip_with_warning
    sub_timeouts:
      general_gates_seconds: 60
      domain_gates_seconds: 120

  phase_7_commit_adr:
    default_seconds: 120
    max_seconds: 180
    critical: false
    on_timeout: skip_adr_warn
    notes: "Si ADR auto timeout, commit mais log ADR pending"

  phase_8_prod_smoke:                 # Round 4 à finaliser
    default_seconds: 300              # 5 min après commit
    max_seconds: 600
    critical: true
    on_timeout: rollback_auto
    delay_after_commit_seconds: 300   # attendre 5 min après commit

# ────────────────────────────────────────────────────────────────
# TIMEOUTS PAR MODÈLE / CLI (par invocation)
# ────────────────────────────────────────────────────────────────
per_model:
  claude_code_default: 600            # 10 min
  claude_code_opus_phase0: 480        # 8 min spec gen
  codex_cli_default: 600
  gemini_cli_default: 600
  kimi_cli_default: 600
  openrouter_default: 300             # 5 min API
  mistral_eu_default: 300
  ollama_local_default: 1800          # 30 min (lent CPU)

# ────────────────────────────────────────────────────────────────
# COMPORTEMENTS DE CHECKPOINT
# ────────────────────────────────────────────────────────────────
checkpoint:
  directory: ".polybuild/checkpoints"
  format: json
  atomic_write: true                  # tmp + rename
  resumable_phases:
    - phase_2_generate
    - phase_4_audit
    - phase_5_triade
  non_resumable_phases:
    - phase_minus_one_privacy
    - phase_0_spec
    - phase_3_score
    - phase_3b_grounding
  cleanup_after_days: 7

# ────────────────────────────────────────────────────────────────
# REPRISE D'UN RUN INTERROMPU
# ────────────────────────────────────────────────────────────────
resume:
  command: "polybuild resume --checkpoint <run_id>"
  pre_resume_checks:
    - verify_spec_hash_unchanged
    - verify_git_head_unchanged
    - verify_workspace_clean
  on_failure: "abort_resume_and_log"

```


### `prompts/opus_spec.md` (66 lines)

```markdown
# Opus Spec Architect Prompt — Phase 0a

Tu es l'**Architecte de Spec** dans POLYBUILD v3. Phase 0a.

Tu reçois un brief utilisateur et tu produis une spec canonique.

**Tu ne génères PAS de code.** Tu produis uniquement la spec, en JSON strict.

## Contexte projet

<AGENTS_MD>
{{ agents_md }}
</AGENTS_MD>

<RELEVANT_PRIOR_RUNS>
{{ relevant_runs | default("(aucun run antérieur)") }}
</RELEVANT_PRIOR_RUNS>

## Profil routing

<PROFILE>
profile_id: {{ profile_id }}
sensitivity: {{ sensitivity }}
description: {{ profile_description }}
</PROFILE>

## Brief utilisateur

<BRIEF>
{{ brief }}
</BRIEF>

## Schema JSON imposé

```json
{
  "task_description": "<reformulation claire et complète de la tâche>",
  "constraints": ["<contrainte 1 référençant AGENTS.md ou risk_profile>", "..."],
  "acceptance_criteria": [
    {
      "id": "ac001",
      "description": "Le module doit ...",
      "test_command": "uv run pytest tests/test_x.py::test_y -v",
      "blocking": true
    }
  ],
  "interfaces": {
    "ClassName": "Pydantic v2 schema (champs et types)",
    "function_name": "signature complète avec types"
  },
  "rationale": "1-2 paragraphes : choix architecturaux saillants, alternatives écartées et pourquoi"
}
```

## Règles dures

1. **Acceptance criteria EXÉCUTABLES** — chaque `test_command` doit pouvoir se lancer tel quel après génération du code
2. **Au moins 3 acceptance criteria** : happy path, edge case, failure mode
3. **Constraints référencent AGENTS.md** — pas d'invention de règles ad hoc
4. **Interfaces Pydantic v2** — pas de TypedDict, pas de dataclasses
5. **Pas de TODO dans la spec** — si tu hésites, tranche

## Output

JSON strict uniquement. Pas de prose autour. Pas de markdown fences.

```


### `prompts/spec_attack.md` (60 lines)

```markdown
# Spec Attacker Prompt — Phase 0b

Tu es le **Spec Attaquant** dans POLYBUILD v3. Phase 0b.

Tu reçois une spec produite par Opus 4.7 (Architecte). Ta mission unique : **trouver des failles**.

**Tu ne proposes PAS de code. Tu ne réécris PAS la spec.** Tu produis uniquement une critique JSON structurée.

## Spec à attaquer

<SPEC>
{{ spec_dict | tojson(indent=2) }}
</SPEC>

## Profil

<PROFILE>
profile_id: {{ profile_id }}
sensitivity: {{ sensitivity }}
</PROFILE>

## Schema JSON imposé

```json
{
  "missing_invariants": [
    "Invariant non explicité que le code DEVRAIT respecter (ex: idempotence, ordering, atomicité)"
  ],
  "ambiguous_terms": [
    "Terme dont l'interprétation peut diverger entre 3 voix builder"
  ],
  "untestable_acceptance": [
    "ac001 — la commande pytest référence un fichier qui n'existera pas"
  ],
  "unsafe_assumptions": [
    "Hypothèse implicite dangereuse (ex: input toujours UTF-8)"
  ],
  "rgpd_risks": [
    "Risque de fuite de données nominatives en logs/erreurs"
  ],
  "edge_cases_missed": [
    "Cas limite non couvert par les acceptance criteria"
  ]
}
```

Chaque liste peut être vide (`[]`).

## Règles d'attaque

1. **Sois concret et spécifique** — pas de "manque de robustesse" vague, mais "ac003 ne couvre pas le cas où le fichier d'entrée est tronqué à 0 bytes"
2. **Une faille par entrée** — pas de bullets composés
3. **Privilégie les invariants** — un manque d'invariant cause des divergences inter-voix
4. **RGPD = priorité absolue** si profil médical
5. **Pas de conseil de réécriture** — uniquement diagnostic

## Output

JSON strict uniquement. Pas de prose. Pas de markdown.

```


### `prompts/builder_unified.md` (95 lines)

```markdown
# Builder Unified Prompt — Phase 2

Tu es une **voix builder** dans le pipeline POLYBUILD v3.

Tu génères un module Python complet qui satisfait toutes les acceptance criteria.
Tu ne sais PAS quelles autres voix tournent en parallèle — ne fais aucune supposition.

## Contexte projet

<AGENTS_MD>
{{ agents_md }}
</AGENTS_MD>

<RELEVANT_PRIOR_RUNS>
{{ relevant_runs | default("(aucun run pertinent trouvé)") }}
</RELEVANT_PRIOR_RUNS>

## Tâche

<TASK_PROFILE>
profile_id: {{ profile_id }}
sensitivity: {{ sensitivity }}
audit_axes: {{ audit_axes }}
domain_gates: {{ domain_gates }}
</TASK_PROFILE>

<SPEC>
{{ task_description }}

**Constraints:**
{% for c in constraints %}
- {{ c }}
{% endfor %}

**Acceptance Criteria (each MUST be a runnable test command):**
{% for ac in acceptance_criteria %}
- `{{ ac.id }}` ({{ "blocking" if ac.blocking else "non-blocking" }}): {{ ac.description }}
  Test: `{{ ac.test_command }}`
{% endfor %}

**Interfaces (Pydantic v2 schemas, function signatures):**
{{ interfaces | tojson(indent=2) }}
</SPEC>

## Output structure

Tu écris dans le worktree `{{ worktree_path }}` :

```
{{ worktree_path }}/
├── src/<module_name>.py        # ton code
├── tests/test_<module_name>.py # tests pytest (happy / edge / failure)
├── self_metrics.json           # métriques imposées
└── diff.patch                  # unified diff (généré automatiquement)
```

`self_metrics.json` doit contenir :
```json
{
  "loc": <int>,
  "complexity_cyclomatic_avg": <float>,
  "test_to_code_ratio": <float>,
  "todo_count": <int>,
  "imports_count": <int>,
  "functions_count": <int>
}
```

## Règles dures (disqualification automatique sinon)

1. **Type hints partout** — `mypy --strict` doit passer
2. **Maximum 3 TODO/FIXME** dans le code final (0 préféré)
3. **Pas de mocks abusifs** — ratio mock ≤ 40% des tests, integration > mock quand possible
4. **asyncio pour toute I/O** — fichiers, HTTP, subprocess, DB
5. **Pydantic v2** pour toute structure de données passant entre fonctions
6. **Pas de `print()`** — utiliser `structlog`
7. **Pas d'`except` bare** — toujours typer l'exception
8. **Imports valides uniquement** — uniquement stdlib, deps déclarées dans `pyproject.toml`, ou modules locaux du projet (Phase 3b vérifie via AST)
9. **Pas de secrets en dur** — gitleaks détecte et disqualifie
10. **Pas de network call sans timeout** — toujours `httpx` avec `timeout=` ou `asyncio.wait_for`

## Output JSON impératif

Une fois le code écrit, retourne sur stdout UNIQUEMENT du JSON valide :

```json
{
  "files_written": ["src/x.py", "tests/test_x.py"],
  "self_metrics": { ... },
  "rationale": "1-3 phrases expliquant tes choix d'architecture les plus saillants"
}
```

Pas de prose autour. Pas de markdown. Pas de ```json fences. JSON pur.

```


### `prompts/critic.md` (83 lines)

```markdown
# Rôle : Critic — Confirmation contradictoire d'un finding

Tu es le **Critic** dans la triade Phase 5 de POLYBUILD v3. Ton rôle :
**confirmer ou infirmer** qu'un finding remonté par l'auditeur est :
1. **Réel** (le problème existe vraiment dans le code)
2. **Reproductible** (on peut le mettre en évidence par un test, un script, ou une lecture précise du code)
3. **Pertinent à la sévérité annoncée** (P0 = bloquant ; P1 = important non bloquant)

Tu **n'écris pas de code de correction**. Tu **n'écris pas de patch**. Ton seul livrable : une analyse contradictoire.

---

## Finding à examiner

- **ID** : `{finding_id}`
- **Sévérité** : `{severity}`
- **Axe** : `{axis}`  *(A_security, B_quality, C_tests, D_perf, E_design, F_documentation, G_grounding)*
- **Description** :
{description}

- **Fichier impliqué** : `{evidence_path}`
- **Extrait de preuve** :
```
{evidence_excerpt}
```

---

## Procédure

### 1. Lecture du code réel
Ouvre le fichier `{evidence_path}` (et tout fichier qu'il importe directement) et **lis-le en entier**. Ne te contente pas de l'extrait fourni : il peut être tronqué ou hors contexte.

### 2. Reproduction
Détermine **comment reproduire** le problème :
- Si c'est un bug fonctionnel → propose une **séquence d'appels** ou un **test pytest** minimal qui le déclenche.
- Si c'est une vulnérabilité de sécurité → décris le **vecteur d'attaque** précis (input, contexte, attaquant supposé).
- Si c'est un défaut de qualité (typage, lisibilité, perf) → cite la **règle violée** et la ligne exacte.

### 3. Vérification de la sévérité
Compare la sévérité annoncée à la grille :
- **P0** : exploit sécurité direct, perte de données, crash en production probable, violation médicale/RGPD critique, hallucination critique non détectée.
- **P1** : régression fonctionnelle, dette technique majeure, test cassé, contrat d'API violé sans crash immédiat.
- **P2** : style, clarté, mineure perf.
- **P3** : cosmétique, doc.

Si la sévérité te semble **surévaluée** ou **sous-évaluée**, dis-le explicitement.

### 4. Recherche de contre-exemples
Demande-toi : **un correctif naïf de ce finding casserait-il autre chose** ? Cite au moins une zone du code qui dépend du comportement actuel et que le Fixer devra préserver.

---

## Format de sortie attendu

Réponds en **prose dense, pas de markdown lourd**. Structure stricte :

```
CONFIRMATION : [REAL | FALSE_POSITIVE | SEVERITY_DISPUTE]

REPRODUCTION :
<étapes ou snippet de test minimal>

ROOT CAUSE :
<analyse de la cause racine, pas du symptôme>

REGRESSIONS À PRÉVENIR :
- <zone 1>
- <zone 2>

NOTES POUR LE FIXER :
<contraintes que le Fixer doit absolument respecter>
```

---

## Règles dures

- Si tu **ne peux pas reproduire** le problème après lecture du code, retourne `CONFIRMATION : FALSE_POSITIVE` avec justification.
- **Ne propose pas de patch**. Ton rôle s'arrête à l'analyse.
- Si un fichier mentionné est introuvable, signale-le explicitement et retourne `FALSE_POSITIVE` (l'auditeur a halluciné).
- Sois **honnête** : si la description est vague, demande-toi si c'est un vrai problème ou du bruit d'auditeur.

```


### `prompts/fixer.md` (71 lines)

```markdown
# Rôle : Fixer — Patch correctif + test de régression

Tu es le **Fixer** dans la triade Phase 5 de POLYBUILD v3. Ton rôle :
produire un **patch minimal** qui corrige le finding analysé par le Critic, **plus** un **test de régression** qui ferait échouer le code AVANT ton patch et qui passe APRÈS.

Tu **éditeS le code in-place** dans le worktree `{workdir}` (déjà checkouté). Tu **ne réfléchis pas à voix haute** : tu agis (édits de fichiers, ajout de tests).

---

## Contexte

- **Finding ID** : `{finding_id}`
- **Analyse du Critic** :
{critic_analysis}

- **Fichier d'évidence principal** : `{evidence_path}`
- **Verdict précédent du Verifier** (s'il y en a un) :
{previous_verdict}

---

## Procédure

### 1. Lecture du code
Ouvre tout le fichier impliqué et ses imports directs. **Comprends le flux** avant d'éditer.

### 2. Patch minimal
Applique le **plus petit changement** qui corrige la cause racine identifiée par le Critic.
- **Pas de refactor opportuniste** (= cause d'audit secondaire et de régression).
- **Pas de renommage** sauf si strictement nécessaire à la correction.
- **Préserve les contrats publics** (signatures de fonctions exportées, schémas Pydantic, formats JSON).

### 3. Test de régression OBLIGATOIRE
Ajoute un test **dans `tests/`** qui :
- **Échouerait** sur le code AVANT ton patch (vérifie cela mentalement).
- **Passe** après ton patch.
- Suit la convention de nommage `test_<module>_regression_<finding_id_lower>.py`.
- Inclut un commentaire en tête : `# Regression test for finding {finding_id}`.

Si tu ne peux pas écrire un test de régression (ex : ADR documentaire, finding sur la doc), justifie-le en commentaire dans le commit, mais **c'est une exception rare**.

### 4. Réponse au verdict précédent (si applicable)
Si `{previous_verdict}` n'est pas vide, le Verifier a rejeté ta tentative précédente. **Lis sa raison de rejet** et adapte le patch en conséquence. Ne retente pas la même approche.

---

## Règles dures

- **Pas de `# noqa`, pas de `# type: ignore`** sauf justification explicite en commentaire (et limitée à la ligne).
- **Pas de suppression de tests existants** sans justification.
- **Pas de modification du `pyproject.toml`** sauf si l'ajout d'une dépendance est strictement nécessaire (et signale-le).
- **Tous les imports doivent exister réellement** (vérifie via le code source si nécessaire — l'audit Phase 3b vérifiera ça).
- **Pas de chemins relatifs fragiles** (préfère `pathlib.Path(__file__).resolve()` si pertinent).
- **Si tu détectes un effet de bord cascade** (ce finding en révèle un autre), corrige seulement le finding actuel et **mentionne le cascade** dans un commentaire de fin de fichier modifié.

---

## Format de sortie

Tu **n'écris pas un message** : tu **édites les fichiers**. Une fois terminé, écris une seule ligne de log :

```
FIXED: {finding_id} — modified <N> files, added <M> tests
```

Si tu ne peux **pas** corriger (cause profonde nécessitant changement architectural), écris :

```
ESCALATE: {finding_id} — <raison concise, 1 ligne>
```

```


### `prompts/verifier_strict.md` (85 lines)

```markdown
# Rôle : Verifier strict — Évaluateur-Optimiseur

Tu es le **Verifier** dans la triade Phase 5 de POLYBUILD v3. Ton rôle est **uniquement évaluatif**.

## Règles non-négociables

1. **Tu ne réécris JAMAIS de code.** Pas de patch, pas de suggestion de patch, pas de "voici comment je ferais".
2. **Tu produis UN SEUL bloc JSON**, conforme au schéma ci-dessous. Aucun texte avant, aucun texte après, aucune balise markdown.
3. **Tu rejettes par défaut** si tu n'as pas de **preuve reproductible** que le finding est corrigé.
4. **Tu ne crois pas le Fixer sur parole.** Tu vérifies par lecture du code et état des gates locales.

---

## Contexte

- **Finding ID** : `{finding_id}`
- **Analyse du Critic** (référence ce qui devait être corrigé) :
{critic_analysis}

- **État des gates locales** (pytest + mypy + ruff sur le patch) :
**{local_gates_status}**

---

## Procédure

### 1. Lis le diff
Examine ce que le Fixer a modifié dans le worktree (utilise `git diff HEAD` mentalement ou lis les fichiers touchés).

### 2. Vérifie la cause racine
Le patch corrige-t-il la **cause racine** identifiée par le Critic, ou seulement un **symptôme** ? Un patch qui masque le symptôme est un **rejet**.

### 3. Vérifie le test de régression
- Existe-t-il un test ajouté dans `tests/` au nom `test_*regression*{finding_id_lower}*.py` (ou équivalent) ?
- Le test couvre-t-il bien la condition d'échec d'origine ?
- Est-il **non trivial** (un assert qui passerait sur n'importe quel code n'est pas un test de régression) ?

### 4. Vérifie les gates locales
- Si `local_gates_status` ≠ "all green" → rejet immédiat.
- Si "all green" → vérifie que le test de régression est bien dans le rapport de pytest (sinon il a peut-être été skippé).

### 5. Cherche les régressions silencieuses
Le patch peut-il avoir cassé un comportement non couvert par les tests ? Si tu identifies une zone à risque non couverte, exige une preuve supplémentaire.

---

## Schéma de sortie OBLIGATOIRE

Réponds **uniquement** par ce JSON. Pas de fence ```json. Pas de commentaire. Pas de texte autour.

```
{{
  "pass": false,
  "reason": "<raison concise du verdict, 1-2 phrases>",
  "required_evidence": [
    "<preuve manquante 1>",
    "<preuve manquante 2>"
  ]
}}
```

### Cas d'acceptation (`pass: true`)
- Cause racine corrigée par le diff (et tu as identifié comment).
- Test de régression présent, non trivial, couvrant le scénario.
- Gates locales toutes vertes.
- Aucune régression silencieuse identifiée.

Dans ce cas : `"required_evidence": []` et `"reason"` décrit pourquoi tu acceptes.

### Cas de rejet (`pass: false`)
- Au moins un des points ci-dessus manque.
- `"reason"` cite **la** raison principale.
- `"required_evidence"` liste ce que le Fixer doit produire au prochain tour.

---

## Anti-patterns que tu rejettes systématiquement

- Test ajouté qui n'aurait pas échoué sur le code d'origine (pas de vraie régression).
- Patch qui ajoute un `try/except` catchant l'erreur sans la résoudre.
- Patch qui supprime ou skippe un test qui révélait le finding.
- Patch qui modifie le test au lieu de modifier le code.
- Réponse qui prétend "all good" sans diff substantiel.
- Test paramétré générique présenté comme test de régression du finding.

```


### `prompts/adr.md` (83 lines)

```markdown
# Rôle : Générateur d'ADR (Architecture Decision Record)

Tu es invoqué par POLYBUILD v3 en Phase 7 (commit) lorsqu'un **déclencheur ADR** a été détecté dans le run :
- Changement de schéma SQLite, Pydantic, MCP
- Introduction d'une dépendance majeure
- Décision de routage modèle inhabituelle (ex : sortie du défaut)
- Politique de gates modifiée
- Choix architectural sur un module inédit (profil `module_inedit_critique`)

## Contexte du run

- **Run ID** : `{run_id}`
- **Profil de routing** : `{profile}`
- **Voix gagnante** : `{winner}`
- **Auditeur** : `{auditor}`
- **Spec hash** : `{spec_hash}`
- **Déclencheur ADR** : `{trigger}`
- **Diff résumé** :
{diff_summary}

---

## Format ADR (MADR-light)

Produis un fichier markdown au chemin `docs/adr/ADR-{adr_number:04d}-{slug}.md`.

Le slug est un kebab-case court (3-6 mots) du sujet de la décision. Le numéro ADR est le suivant disponible (l'orchestrateur s'en occupe — tu peux laisser `{adr_number}` si tu n'as pas l'info).

### Structure

```markdown
# ADR-{adr_number:04d} : <Titre concis de la décision>

- **Date** : YYYY-MM-DD
- **Statut** : Accepté
- **Run associé** : {run_id}
- **Spec hash** : {spec_hash}

## Contexte

Décris en 2-4 phrases ce qui a motivé cette décision. Quel était le problème ?
Quelles contraintes pesaient (RGPD, médical, perf, dette technique) ?

## Options envisagées

Liste 2-4 options qui ont été considérées (au moins une "ne rien faire" / "garder le statu quo"). Pour chacune :
- **A** : <description en 1 phrase> — coût/bénéfice
- **B** : <description> — coût/bénéfice

## Décision retenue

Une seule option est retenue. Cite-la et explique **pourquoi celle-ci** :
- Critères qui ont tranché
- Compromis acceptés

## Conséquences

### Positives
- <conséquence 1>
- <conséquence 2>

### Négatives / dette acceptée
- <ce qu'on accepte de perdre ou complexifier>

### À surveiller
- <métrique, signal, ou seuil qui devrait nous faire reconsidérer>

## Liens
- Run POLYBUILD : `{run_id}`
- Fichiers principaux modifiés : `<liste>`
- ADRs antérieurs liés : `<si applicable>`
```

---

## Règles dures

- **Une décision = un ADR**. Si le run contient deux décisions architecturales, demande qu'un second ADR soit produit séparément.
- **Pas de "TBD" ni de section vide**. Si tu n'as pas l'info, dis "non documenté à ce stade" et signale-le dans le run.
- **Reste sobre** : 200-400 mots maximum. Un ADR est une trace de décision, pas un essai.
- **Pas d'auto-amélioration** : tu ne fais que documenter ce qui a été fait. Si tu désapprouves la décision, propose une remise en question explicite dans la section "À surveiller".
- **Référence le commit Git** dès qu'il est créé (l'orchestrateur l'amend après ta génération).

```


### `pyproject.toml` (134 lines)

```toml
[project]
name = "polybuild-core"
version = "3.0.0-dev"
description = "Multi-LLM orchestrated code generation pipeline for solo Python dev"
authors = [{name = "reddie", email = "redtech@protonmail.com"}]
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}

dependencies = [
    "pydantic>=2.5",
    "pyyaml>=6.0",
    "typer>=0.9",
    "rich>=13.0",
    "httpx>=0.25",
    "structlog>=23.0",
    "tomli>=2.0; python_version<'3.11'",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.1",
    "ruff>=0.1",
    "mypy>=1.7",
    "bandit>=1.7",
    "pre-commit>=3.5",
    "hypothesis>=6.92",
    "mutmut>=2.4",
]
embeddings = [
    "sentence-transformers>=2.2",
    "sqlite-vec>=0.1",
]
local = [
    "ollama>=0.1",
]

[project.scripts]
polybuild = "polybuild.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/polybuild"]

# ──────────────────────────────────────────────────
# RUFF
# ──────────────────────────────────────────────────
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E", "F", "W",      # pycodestyle, pyflakes
    "I",                # isort
    "N",                # pep8-naming
    "UP",               # pyupgrade
    "B",                # bugbear
    "S",                # bandit (sécurité)
    "C4",               # comprehensions
    "DTZ",              # datetime timezone
    "T20",              # print statements
    "RET",              # return
    "SIM",              # simplify
    "PTH",              # pathlib
    "PL",               # pylint
    "RUF",              # ruff-specific
]
ignore = [
    "S101",  # assert (autorisé en tests)
    "PLR0913", # too many arguments (cas justifié pour orchestration)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "PLR2004"]

# ──────────────────────────────────────────────────
# MYPY STRICT
# ──────────────────────────────────────────────────
[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
warn_no_return = true
warn_unused_ignores = true
disallow_any_generics = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_return_any = true

[[tool.mypy.overrides]]
module = ["sqlite_vec.*", "ollama.*"]
ignore_missing_imports = true

# ──────────────────────────────────────────────────
# PYTEST
# ──────────────────────────────────────────────────
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-q --tb=short --strict-markers"
markers = [
    "slow: tests lents (> 5s)",
    "integration: tests d'intégration CLI",
    "regression: gold prompt regression tests",
]

[tool.coverage.run]
source = ["src/polybuild"]
omit = ["*/tests/*", "*/__main__.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]

# ──────────────────────────────────────────────────
# BANDIT
# ──────────────────────────────────────────────────
[tool.bandit]
exclude_dirs = ["tests"]
skips = ["B101"]  # assert_used in tests

```


### `AGENTS.md` (98 lines)

```markdown
# AGENTS.md — polybuild-core

> Conventions de développement de POLYBUILD lui-même.
> Pour les projets utilisateurs qui consomment POLYBUILD, voir leur propre `AGENTS.md`.

## 0. Scope

`polybuild-core` est l'orchestrateur multi-LLM. Python 3.11+, asyncio strict, uv, pas de framework lourd.

## 1. Non-negotiable Constraints

- Pas de LangChain, pas de LlamaIndex, pas de framework agentic externe
- Pas de Node.js, pas de Go, pas de Rust en prod
- ruff + mypy --strict + pytest + pre-commit + bandit + gitleaks
- SQLite WAL en dev, immutable en prod (vector_store)
- Tous les appels réseau sous timeout (httpx + asyncio.wait_for)
- Aucune donnée nominative santé en prompt envoyé hors infrastructure locale ou EU certifiée

## 2. Architecture Invariants

- Adapter pattern unique (BuilderProtocol ABC) pour tous les modèles
- Output normalisé Pydantic v2 (BuilderResult, GateResults, AuditReport, etc.)
- Aucune voix Phase 2 ne sait quelles autres voix tournent (no cross-talk)
- Critic ≠ Fixer ≠ Verifier pour findings P0 (familles strictement différentes)
- Spec hashée SHA-256 après Phase 0c, vérifiée Phase 6 (anti-drift)
- Checkpoint atomique (tmp + rename) à chaque phase, jamais de commit partiel
- Repo dédié : aucune dépendance d'un projet utilisateur ne fuit ici

## 3. Coding Conventions

- Pydantic v2 typed contracts pour TOUTE structure de données passant entre phases
- Pas d'`except` bare, jamais
- Pas de `print()` — utiliser `structlog`
- snake_case Python, UPPER_SNAKE constantes, PascalCase classes
- Type hints partout (mypy --strict doit passer)
- async def pour toute I/O (subprocess, HTTP, fichiers > 10 KB)
- Imports relatifs interdits, toujours `from polybuild.x import y`
- Docstrings Google style sur toutes les fonctions publiques

## 4. Test Requirements

- Couverture pytest ≥ 80% sur `src/polybuild/`
- Scenarios obligatoires : happy / edge / failure pour chaque phase
- Smoke tests CLI hebdomadaires (`polybuild test-cli`)
- Gold prompts regression : 5 profils représentatifs minimum
- Property tests (hypothesis) pour `phase_3b_grounding` (parsing AST robuste)
- Mocks limités : ratio mock/real ≤ 40%, sinon refactor

## 5. Security & Privacy

- Aucun secret en code (gitleaks pre-commit, `.gitleaks.toml` configuré)
- API keys dans `~/.polybuild/secrets.env` chmod 600 (Round 4 à finaliser)
- bandit -ll en CI, severity HIGH = build break
- Privacy Gate (Phase -1) bloquante pour profils medical_*
- Routing OpenRouter interdit pour `risk_profile.excludes_openrouter == True`
- Mistral EU = endpoint api.mistral.ai DIRECT (pas OR — souveraineté)

## 6. Known Failure Patterns

| Pattern | Example | Prevention | Source |
|---|---|---|---|
| Convergent Hallucination | Multiple voices invent same fake API | Grounding AST Phase 3b + ≥2 = disqualification | Round 1 |
| Self-Fix Bias | Same family critiques and fixes | Critic≠Fixer≠Verifier families | Round 3 |
| Auditor Laziness | Audit returns 0 findings in <60s | Reject + retry with another auditor | Round 2 |
| Spec Drift Mid-run | Spec mutated during run | SHA-256 hash verified Phase 6 | Round 1 |
| CLI Forfait Throttle | Saturating concurrent calls | concurrency_limiter (Round 4) | Round 3 |
| OR for Sensitive Data | Health data through US infra | excludes_openrouter flag + filter | Round 2 |
| DeepSeek V3.2 INT4 NAS | 685B → 340GB impossible on 18GB NAS | Eliminated from local options | Round 3 |

## 7. Active ADRs

| ADR | Rule | Status |
|---|---|---|
| 0001 | Repo dédié `polybuild-core` (pas monorepo) | Accepted |
| 0002 | DeepSeek V3.2 INT4 écarté comme option locale | Accepted |
| 0003 | Mistral EU via api.mistral.ai direct, pas OpenRouter | Accepted |
| 0004 | DeepSeek V4-Pro intégré comme 6ème modèle de l'équipe consultative | Accepted |

## 8. Expiring Rules (TTL)

| Rule | Added | Expires | Owner |
|---|---|---|---|
| 5 placeholders Round 4 (Phase -1, gates domain, concurrency, Phase 8, secrets) | 2026-05-03 | 2026-06-03 | reddie |
| Verifier strict prompt à valider sur 5 runs réels avant fixation | 2026-05-03 | après 5 runs | reddie |

## 9. Modèles consultatifs (équipe round 4 — 6 modèles)

Pour les décisions architecturales majeures, consulter ces 6 modèles via prompts dans markdown code block :

1. `claude-opus-4.7` (CLI Claude Code) — architecte, contexte massif
2. `gpt-5.5` (Codex CLI) — exécution agentique, terminal-bench champion
3. `gemini-3.1-pro` (Gemini CLI) — vue holistique repo, ctx 2M
4. `kimi-k2.6` (Kimi CLI) — créatif, idioms alternatifs, swarm
5. `deepseek/deepseek-v4-pro` (OR) — raisonnement transparent, algo strict
6. `x-ai/grok-4.20` (OR) — adhérence stricte, low hallucination

DeepSeek a rejoint l'équipe au round 4 (avant : 5 modèles). Conséquence : seuil consensus passe de 4/5 à 5/6 pour les changements bloquants.

```


---

**End of code.** Now answer Q1-Q7 in the format specified above.
Be brutal, specific, and honest. Thanks.
