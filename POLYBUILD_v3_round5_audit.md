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
  config/
    concurrency_limits.yaml
    models.yaml
    routing.yaml
  scripts/
    deploy_staging.sh
    polybuild/
      SKILL.md
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
        phase_6_validate.py
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

**End of code.** Now answer Q1-Q7 in the format specified above.
Be brutal, specific, and honest. Thanks.
