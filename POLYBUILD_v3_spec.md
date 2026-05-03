# POLYBUILD v3 — Spécification d'architecture

> **Version** : 3.0-draft
> **Date** : 2026-05-03
> **Auteur** : reddie (médecin du travail SPSTI, dev Python solo)
> **Statut** : Acquis convergents intégrés (rounds 1-3). Failles résiduelles round 4 en attente.
> **Mantra** : *Trois voix orthogonales bâtissent. Les tests tranchent. Les snipers cognitifs polissent.*

---

## Méta — Équipe consultative ayant designé POLYBUILD

POLYBUILD v3 est lui-même le produit d'une orchestration multi-LLM appliquée à sa propre conception. Quatre rounds successifs de consultation ont permis de converger sur l'architecture présentée. **Round 4 (en cours)** intègre désormais **DeepSeek** dans l'équipe, qui passe de 5 à **6 modèles**.

| Round | Modèles consultés | Sortie |
|-------|------------------|--------|
| Round 1 (large) | Gemini 3.1 Pro, GPT-5.5, Kimi K2.6, Qwen 3.5, ChatGPT (DeepSeek implicite via reasoning) | ~70 décisions architecturales soumises ; convergence sur 30% |
| Round 2 (focus) | Gemini, GPT-5.5, Kimi, DeepSeek, ChatGPT | Convergence ~70%, 12 points résiduels |
| Round 3 (clôture) | Gemini, GPT-5.5, Kimi, Qwen, ChatGPT, DeepSeek | Convergence ~90% des décisions actées |
| Round 4 (failles résiduelles, en cours) | **GPT-5.5, DeepSeek V4-Pro, Gemini 3.1 Pro, Kimi K2.6, Grok 4.20, Claude Opus 4.7** | 5 failles résiduelles — voir §5, §13, §15, §20, §22, §23 |

**Diversité 5D de l'équipe round 4** :
- **Provider** : Anthropic (Opus), OpenAI (GPT-5.5), Google (Gemini), Moonshot (Kimi), DeepSeek (V4-Pro), xAI (Grok)
- **Architecture** : dense (Opus, GPT, Gemini), MoE (DeepSeek V4-Pro, Kimi K2.6), hybride (Grok)
- **Alignment** : RLHF Anthropic, RLHF OpenAI, Constitutional AI/Sparrow Google, post-train Moonshot, RL-pure DeepSeek, post-train xAI
- **Corpus de pré-entraînement** : majoritairement EN avec dosages variables FR/CN/multilingue
- **Role bias** : architect (Opus), pragmatic builder (GPT-5.5), long-context analyst (Gemini), contradicteur (Kimi), math reasoner (DeepSeek), skeptic (Grok)

Cette diversité 5D est exactement celle exigée par POLYBUILD pour les profils `inedit_critique` et `helia_algo` (cf. §16). Le méta-design de POLYBUILD est donc dogfooding strict de sa propre méthodologie.

---

## Table des matières

1. [Vision & objectifs](#1-vision--objectifs)
2. [Contraintes & ressources](#2-contraintes--ressources)
3. [Inventaire des modèles](#3-inventaire-des-modèles)
4. [Architecture du pipeline](#4-architecture-du-pipeline)
5. [Phase -1 — Privacy Gate](#5-phase--1--privacy-gate) ⚠️ **Round 4**
6. [Phase 0 — Spec & Spec Attack](#6-phase-0--spec--spec-attack)
7. [Phase 1 — Sélection des voix](#7-phase-1--sélection-des-voix)
8. [Phase 2 — Génération parallèle](#8-phase-2--génération-parallèle)
9. [Phase 3 — Scoring déterministe](#9-phase-3--scoring-déterministe)
10. [Phase 3b — Grounding AST](#10-phase-3b--grounding-ast)
11. [Phase 4 — Audit POLYLENS orthogonal](#11-phase-4--audit-polylens-orthogonal)
12. [Phase 5 — Triade Critic-Fixer-Verifier](#12-phase-5--triade-critic-fixer-verifier)
13. [Phase 6 — Validation finale (gates généraux + domain)](#13-phase-6--validation-finale) ⚠️ **Round 4**
14. [Phase 7 — Commit & ADR](#14-phase-7--commit--adr)
15. [Phase 8 — Production smoke](#15-phase-8--production-smoke) ⚠️ **Round 4**
16. [Table de routage v3](#16-table-de-routage-v3)
17. [Mémoire de projet](#17-mémoire-de-projet)
18. [Apprentissage continu](#18-apprentissage-continu)
19. [Tests d'intégration CLI](#19-tests-dintégration-cli)
20. [Concurrence & rate limits](#20-concurrence--rate-limits) ⚠️ **Round 4**
21. [Déploiement production](#21-déploiement-production) ⚠️ **Round 4**
22. [Skill Claude Code `/polybuild`](#22-skill-claude-code-polybuild) ⚠️ **Round 4**
23. [Gestion des secrets](#23-gestion-des-secrets) ⚠️ **Round 4**
24. [Versioning de POLYBUILD](#24-versioning-de-polybuild)
25. [Bootstrap d'un projet vierge](#25-bootstrap-dun-projet-vierge)
26. [Anti-patterns documentés](#26-anti-patterns-documentés)
27. [Roadmap d'implémentation](#27-roadmap-dimplémentation)

---

## 1. Vision & objectifs

### 1.1 Problème adressé

La génération de code par un LLM unique présente trois failles structurelles :

1. **Echo Chamber** : un modèle valide ses propres hallucinations, surtout en boucle agentique
2. **Convergent Hallucination** : plusieurs modèles inventent la même API inexistante par contamination de corpus partagé
3. **Pro Gap** : les benchmarks publics surestiment la performance réelle de 21 à 35 points sur du code inédit (SWE-bench Verified vs SWE-bench Pro)

POLYBUILD v3 répond à ces failles par l'orchestration de 3 voix orthogonales (provider, architecture, biais d'alignement, corpus distincts) avec validation déterministe par tests réels et audit adversarial systématique.

### 1.2 Objectifs mesurables

| Objectif | Cible |
|---|---|
| Taux de findings P0 résolus avant commit | 100% |
| Taux de findings P1 résolus avant commit | ≥95% |
| Couverture pytest sur module généré | ≥80% |
| Imports hallucinés en commit final | 0 |
| Latence run standard | ≤45 min |
| Latence run HELIA critique | ≤60 min |
| Coût marginal en API payantes (forfaits exclus) | ≤2€/run standard |
| Conformité RGPD/HDS données SST réelles | 100% (zéro fuite) |

### 1.3 Non-objectifs

- Remplacer le jugement clinique du médecin du travail
- Servir d'outil collaboratif multi-utilisateurs (POLYBUILD est solo dev)
- Être agnostique au stack (Python 3.11+/asyncio/uv imposé)
- Supporter d'autres langages que Python (Rust/Go/JS hors scope v3)

---

## 2. Contraintes & ressources

### 2.1 Hardware

| Composant | Spec | Rôle dans POLYBUILD |
|---|---|---|
| NAS Synology DS224+ | Celeron J4125 (4 cœurs), **18 GB RAM**, 3.5 TB RAID1 | Production MCP servers + vector store + modèles locaux |
| MacBook Air M2 | 8 GB RAM | Dev, lancement runs POLYBUILD |
| Réseau | Tailscale + Caddy reverse proxy + domaine OVH `*.example.com` | Accès distant sécurisé |

### 2.2 Software stack imposée

- Python 3.11+ exclusivement
- `uv` pour gestion deps (jamais pip direct)
- `ruff` + `mypy --strict` + `pytest` + `pre-commit` + `bandit` + `gitleaks`
- SQLite WAL en dev / immutable en prod, FTS5 pour recherche, sqlite-vec pour embeddings
- Qdrant local (déjà déployé via MedData)
- Docker Compose pour staging/test isolés
- **Interdits** : LangChain, LlamaIndex, frameworks lourds

### 2.3 Forfaits CLI gratuits (tous payés, tous sous-utilisés)

| Forfait | CLI | Modèles accessibles | Quota typique |
|---|---|---|---|
| Claude Max 20x | `claude code` | Opus 4.7, Sonnet 4.6, Haiku 4.5 | Très large, sous-utilisé |
| ChatGPT Pro | `codex exec` | GPT-5.5, GPT-5.5-Pro, GPT-5.4, GPT-5.3-Codex | Large |
| Gemini Pro (Google One) | `gemini` | Gemini 3.1 Pro (2M ctx), Gemini 3.1 Flash | Large |
| Kimi Allegretto | `kimi` | Kimi K2.6 | À mesurer |

### 2.4 Budget API complémentaire

| Provider | Modèles utilisés | Budget mensuel cible |
|---|---|---|
| OpenRouter | DeepSeek V4-Pro, DeepSeek V4-Flash, Grok 4.20 | ~10-15€ |
| Mistral EU direct (api.mistral.ai) | Devstral 2 (profil médical uniquement) | ~5€ |
| **Total cible** | — | **~15-20€/mois**, hard cap 30€ |

### 2.5 Contraintes RGPD/HDS

- Aucune donnée nominative santé hors infrastructure locale ou endpoint EU certifié
- Pseudonymisation regex insuffisante seule (quasi-identifiants ré-identifiables)
- Phase -1 Privacy Gate bloquante obligatoire pour tout profil `medical_*`
- Modèles US (Anthropic/OpenAI/Google) et CN (Moonshot) interdits sur données sensibles haute paranoïa

---

## 3. Inventaire des modèles

### 3.1 Modèles via CLI gratuits (privilégiés)

| Modèle | CLI | Forces | Profils |
|---|---|---|---|
| `claude-opus-4.7` | `claude code` | Architecture, raisonnement nuancé, contexte massif (1M), SWE-bench V. 87.6% | Architecte Phase 0, médiateur Phase 5 |
| `claude-sonnet-4.6` | `claude code --model sonnet` | Itération rapide, généraliste équilibré, SWE 80.8% | Workhorse multi-profils |
| `claude-haiku-4.5` | `claude code --model haiku` | Vitesse, coût marginal nul | Tâches atomiques, scoring local-LLM |
| `gpt-5.5` | `codex exec -m gpt-5.5` | Exécution agentique, Terminal-Bench 82.7%, structured outputs | Bâtisseur pragmatique |
| `gpt-5.3-codex` | `codex exec -m gpt-5.3-codex` | CLI/CI/CD, scripts shell, IaC, Terraform | Profils DevOps |
| `gemini-3.1-pro` | `gemini -m gemini-3.1-pro-preview` | Contexte 2M tokens, multimodal, ingestion massive | Long-context, parsing PDF |
| `gemini-3.1-flash` | `gemini -m gemini-3.1-flash` | Vitesse, coût marginal nul | Tâches batch |
| `kimi-k2.6` | `kimi --quiet --thinking` | Swarm 100+ agents, idioms créatifs, SWE 80.2% | Variantes audacieuses, exploration |

### 3.2 Modèles OpenRouter (3 irremplaçables, 1 conditionnel)

| Modèle (slug OR) | Statut | Justification non-substitutionnelle | Profils |
|---|---|---|---|
| `deepseek/deepseek-v4-pro` | **Irremplaçable** | CoT transparent + MoE 1.6T/49B + licence MIT, seul à offrir auditabilité algorithmique de cette qualité | HELIA algo, Spec Attack algo, audit |
| `x-ai/grok-4.20` | **Irremplaçable** | Adhérence stricte aux instructions + low hallucination rate, aucun équivalent CLI | Spec Attack adhérence, LLM-as-Judge, Verifier sécurité |
| `mistral/devstral-2` | **Irremplaçable** | Endpoint EU certifié (api.mistral.ai direct, pas via OR), 123B agentic, MIT modifiée | Profil médical uniquement |
| `deepseek/deepseek-v4-flash` | **Conditionnel** | Coût marginal très bas, latence faible | Sonde 50 LOC, fallback CLI down |

### 3.3 Modèles éliminés du routing v3

Convergence 5/6 : redondance avec CLI gratuits, pas d'orthogonalité unique.

- DeepSeek V3.2 (remplaçable par Kimi K2.6 CLI)
- Grok 4.1 Fast (remplaçable par Gemini 3.1 Flash CLI)
- Qwen 3.6 Plus (remplaçable par GPT-5.5 CLI)
- GLM 5.1 (remplaçable par DeepSeek V4-Pro)
- Minimax M2.5 (remplaçable par Kimi K2.6 CLI)
- Nemotron 3 Super (pas de différentiateur clair)

### 3.4 Modèles locaux (NAS Ollama)

| Modèle | Quantization | RAM utilisée | Tok/s estimés | Usage |
|---|---|---|---|---|
| `qwen2.5-coder:14b-int4` | Q4_K_M | ~9 GB | 2-4 tok/s | Profil médical paranoia HIGH |
| `qwen2.5-coder:7b-int4` | Q4_K_M | ~5 GB | 6-10 tok/s | Fonctions atomiques médicales |
| `nomic-embed-text` ou `all-minilm-l6-v2` | FP16 | ~100 MB | 50 tok/s | Embedder vector store |

> ⚠️ **Décision actée round 3** : DeepSeek V3.2 INT4 = 685B, ~340 GB minimum, **physiquement impossible sur NAS DS224+ 18 GB**. Écarté définitivement.

> ⚠️ **Décision actée round 3** : Llama 3.3 70B INT2 trop juste sur 18 GB partagé avec MCP servers. Écarté.

---

## 4. Architecture du pipeline

### 4.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENTRY POINT (Claude Code skill)                  │
│                          /polybuild run ...                         │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  polybuild_v3.py main  │
                    │   (orchestrateur Py)   │
                    └────────────┬───────────┘
                                 │
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                         ▼
┌──────────────┐        ┌─────────────────┐       ┌──────────────────┐
│ Phase -1     │        │ Phase 0 + 0b    │       │ Phase 1          │
│ Privacy Gate │  ───►  │ Spec + Attack   │  ───► │ Sélection voix   │
└──────────────┘        └─────────────────┘       └────────┬─────────┘
                                                           │
                                                           ▼
                                                  ┌────────────────┐
                                                  │ Phase 2        │
                                                  │ 3 builders //  │
                                                  └────────┬───────┘
                                                           │
        ┌──────────────────────────────────────────────────┤
        ▼                                                  ▼
┌──────────────┐        ┌─────────────────┐       ┌──────────────────┐
│ Phase 3      │        │ Phase 3b        │       │ Phase 4          │
│ Scoring det. │  ───►  │ Grounding AST   │  ───► │ Audit POLYLENS   │
└──────────────┘        └─────────────────┘       └────────┬─────────┘
                                                           │
                                                           ▼
                                                  ┌────────────────┐
                                                  │ Phase 5        │
                                                  │ Triade fix     │
                                                  └────────┬───────┘
                                                           │
        ┌──────────────────────────────────────────────────┤
        ▼                        ▼                         ▼
┌──────────────┐        ┌─────────────────┐       ┌──────────────────┐
│ Phase 6      │        │ Phase 7         │       │ Phase 8          │
│ Validation   │  ───►  │ Commit + ADR    │  ───► │ Prod smoke       │
│ + Domain     │        │                 │       │ + Rollback auto  │
└──────────────┘        └─────────────────┘       └──────────────────┘
```

### 4.2 Principes d'orchestration

1. **Pas de cross-talk entre voix** : aucune voix Phase 2 ne sait quelles autres voix tournent
2. **Output normalisé** : chaque voix retourne un `BuilderResult` Pydantic standardisé
3. **Tests = vérité** : aucun LLM ne valide seul un finding P0/P1 sans preuve exécutable
4. **Critic ≠ Fixer ≠ Verifier** pour les findings P0 (familles strictement différentes)
5. **Checkpoints à chaque phase** pour reprise après timeout ou crash
6. **Aucun commit partiel** : run complet réussi ou run aborté avec état sauvegardé

### 4.3 Structure des artefacts par run

```
.polybuild/
├── runs/
│   └── {run_id}/
│       ├── spec.yaml              # Phase 0 output
│       ├── spec_attack.json       # Phase 0b output
│       ├── voice_selection.json   # Phase 1 output
│       ├── worktrees/             # Phase 2 — un dossier par voix
│       │   ├── opus_4.7/
│       │   ├── gpt_5.5/
│       │   └── deepseek_v4_pro/
│       ├── scores.json            # Phase 3 output
│       ├── grounding.json         # Phase 3b output
│       ├── findings.json          # Phase 4 output
│       ├── fix_results.json       # Phase 5 output
│       ├── domain_gates.json      # Phase 6 output
│       ├── commit_info.json       # Phase 7 output
│       ├── prod_smoke.json        # Phase 8 output
│       └── polybuild_run.json     # log consolidé
└── checkpoints/
    └── {run_id}_phase{N}.json     # checkpoint pour reprise
```

---

## 5. Phase -1 — Privacy Gate

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 1)**
>
> Cette phase nécessite une spécification rigoureuse :
> - Architecture multi-couches (PII directe / quasi-identifiants / contextuelle)
> - Outils Python concrets : `presidio-analyzer` + `spacy fr_core_news_lg` vs `eds-pseudo` (AP-HP, F1=0.97)
> - Mode "déclaration utilisateur" obligatoire pour `sensitivity_attestation` dans `spec.yaml`
> - Logique d'escalade : Couche 1 hard block / Couche 2 escalade niveau / Couche 3 attestation
>
> **Acquis convergent (round 3)** : 3 niveaux de paranoïa (`low` / `medium` / `high`).
> - `low` : données déjà anonymisées ou synthétiques → CLI frontier autorisés
> - `medium` : données pseudonymisées → CLI frontier OK, OpenRouter US interdit, Mistral EU OK
> - `high` : données SPSTI réelles ré-identifiables → 100% local NAS + Mistral EU validé contractuellement, **aucun CLI frontier US/CN**

**Placeholder code** :
```python
# phase_minus_one_privacy.py
# TODO: implémenter post-round 4 selon spec finalisée
async def phase_minus_one(spec_draft: dict) -> PrivacyVerdict:
    """
    Returns PrivacyVerdict with:
      - level: "low" | "medium" | "high"
      - blocked: bool (si Couche 1 match)
      - findings: list[PIIFinding]
      - requires_attestation: bool
    """
    raise NotImplementedError("Round 4 in progress")
```

---

## 6. Phase 0 — Spec & Spec Attack

### 6.1 Phase 0a — Génération spec canonique

**Architecte unique** : `claude-opus-4.7` via Claude Code CLI.

**Pourquoi exclusif** : un seul cerveau pour la spec évite les drifts définitionnels en aval. Opus 4.7 a le meilleur SWE-bench Verified (87.6%) et la meilleure tenue contextuelle pour spécifier sans hallucination.

**Inputs obligatoires** :
- Brief utilisateur (texte libre ou `.polybuild/brief.md`)
- `AGENTS.md` racine du projet
- Top-5 runs pertinents du vector store (similarité cosinus ≥ 0.72)
- `risk_profile.yaml` si fourni

**Livrables bloquants** :
- `spec.yaml` — besoin fonctionnel, contraintes, dépendances autorisées, budget tokens, profil de tâche
- `acceptance.feature` — Gherkin OU pytest scenarios exécutables (les tests sont la vérité)
- `interfaces.md` — signatures Pydantic, schemas DB attendus
- `risk_profile.yaml` — sécurité, perf, sensibilité données, taille module

**Hash de la spec** : SHA-256 calculé après Phase 0a, vérifié en Phase 6 pour détecter spec drift mid-run.

### 6.2 Phase 0b — Spec Attack

**Challenger orthogonal** : sélectionné selon le profil de tâche.

| Profil de tâche | Challenger Spec Attack |
|---|---|
| Algo/math/HELIA | `deepseek/deepseek-v4-pro` (CoT transparent, rigueur algo) |
| Adhérence stricte / regex / parsing | `x-ai/grok-4.20` (low hallucination, prompt adherence) |
| Long-contexte / repo entier | `gemini-3.1-pro` (CLI, ctx 2M) |
| Données médicales (post Phase -1) | Pas de Phase 0b externe, attestation utilisateur requise |

**Le challenger ne code jamais.** Il produit uniquement un `spec_attack.json` :

```yaml
spec_attack:
  missing_invariants: [...]      # Invariants oubliés
  ambiguous_terms: [...]         # Termes mal définis
  untestable_acceptance: [...]   # Critères non exécutables
  unsafe_assumptions: [...]      # Hypothèses dangereuses
  rgpd_risks: [...]              # Risques de fuite données
  edge_cases_missed: [...]       # Cas limites oubliés
```

### 6.3 Phase 0c — Révision

Opus 4.7 reçoit `spec.yaml` + `spec_attack.json` et produit `spec_final.yaml`. Hash recalculé. Si différence > 30%, log warning (la spec initiale était trop fragile).

### 6.4 Implémentation

```python
# phase_0_spec.py
async def phase_0_spec(brief: str, project_ctx: ProjectContext) -> Spec:
    # 0a — Draft Opus
    draft_prompt = render_template("opus_spec.md", brief=brief, ctx=project_ctx)
    draft = await claude_code_cli(draft_prompt, model="opus-4.7", timeout=480)

    # 0b — Spec Attack
    profile = detect_profile(brief, project_ctx)
    if profile.is_medical_high:
        # Pas de Spec Attack externe pour high paranoia
        attack = await user_attestation_prompt(draft)
    else:
        challenger = pick_challenger(profile)
        attack_prompt = render_template("spec_attack.md", spec=draft, profile=profile)
        attack = await call_model(challenger, attack_prompt, timeout=120)

    # 0c — Révision si findings critiques
    if attack.has_critical_findings():
        revise_prompt = render_template("spec_revise.md", spec=draft, attack=attack)
        final = await claude_code_cli(revise_prompt, model="opus-4.7", timeout=300)
    else:
        final = draft

    spec = Spec.from_yaml(final)
    spec.hash = sha256(final.encode()).hexdigest()
    write_artifact("spec.yaml", final)
    write_artifact("spec_attack.json", attack.to_json())
    return spec
```

---

## 7. Phase 1 — Sélection des voix

### 7.1 Mode hybride matrice/sonde

**Décision (acquis convergent T1)** :
- **Matrice statique par défaut** (latence ~ms, ~80% des runs)
- **Sonde 50 LOC pré-génération** uniquement pour profils `code_inédit_critique`

**Critères déclencheurs sonde** :
- `profile.id` ∈ `{HELIA_algo, code_inedit_critique, new_core_module}`
- `task.acceptance_tests_count < 3`
- `prior_runs_count == 0`
- `risk_level` ∈ `{P0, P1}`

### 7.2 Matrice de diversité multi-dimensions

```yaml
# config/model_dimensions.yaml
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

gpt-5.5:
  provider: openai
  architecture: dense
  alignment: agentic
  corpus_proxy: openai_corpus
  role_bias: pragmatic_builder

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

kimi-k2.6:
  provider: moonshot
  architecture: moe
  alignment: creative
  corpus_proxy: chinese_corpus
  role_bias: variant_explorer

deepseek-v4-pro:
  provider: deepseek
  architecture: moe
  alignment: algo_strict
  corpus_proxy: deepseek_corpus
  role_bias: math_reasoner

grok-4.20:
  provider: xai
  architecture: dense
  alignment: prompt_adherent
  corpus_proxy: xai_corpus
  role_bias: skeptic
```

**Score de diversité** : somme des dissimilarités par paire sur les 5 dimensions.

```python
def diversity_score(voices: list[str], matrix: dict) -> float:
    score = 0
    n_pairs = 0
    for a, b in combinations(voices, 2):
        for dim in ["provider", "architecture", "alignment", "corpus_proxy", "role_bias"]:
            if matrix[a][dim] != matrix[b][dim]:
                score += 1
        n_pairs += 1
    return score / n_pairs if n_pairs else 0
```

**Seuils par profil** :
| Profil | `min_diversity` |
|---|---|
| Refactor mécanique | 1.5 |
| Module standard | 2.0 |
| Code inédit critique | 2.3 |
| HELIA algo | 2.5 |

### 7.3 Sonde 50 LOC (profils critiques)

```python
async def probe_diversity(candidates: list[str], spec: Spec) -> list[str]:
    probe_prompt = extract_atomic_function(spec, max_loc=50)
    results = await asyncio.gather(*[
        quick_generate(v, probe_prompt, max_tokens=2000, timeout=60)
        for v in candidates
    ])
    # Calcul matrice dissimilarité
    div_matrix = {}
    for i, ri in enumerate(results):
        for j, rj in enumerate(results[i+1:], i+1):
            ast_d = ast_levenshtein(ri.code, rj.code)
            emb_d = cosine_distance(embed(ri.code), embed(rj.code))
            div_matrix[(i, j)] = 0.6 * ast_d + 0.4 * emb_d
    # Sélection top-3 max diversité (gloutonne)
    return greedy_max_diversity(candidates, div_matrix, k=3)
```

### 7.4 Logique de sélection finale

```python
async def select_voices(spec: Spec, profile: Profile) -> list[VoiceConfig]:
    # 1. Pool de candidats selon profil (table de routage v3, voir §16)
    candidates = ROUTING_TABLE[profile.id]

    # 2. Filtre matrice statique
    valid_triads = [
        triad for triad in combinations(candidates, 3)
        if diversity_score(triad, MATRIX) >= profile.min_diversity
    ]

    # 3. Mode sonde si déclencheurs
    if profile.requires_probe:
        return await probe_diversity(candidates, spec)
    else:
        return valid_triads[0]  # ou top-1 selon historique vector store
```

---

## 8. Phase 2 — Génération parallèle

### 8.1 Adapter pattern BuilderProtocol

```python
# adapters/builder_protocol.py
from abc import ABC, abstractmethod
from pydantic import BaseModel
from pathlib import Path

class BuilderResult(BaseModel):
    voice_id: str
    code_dir: Path
    tests_dir: Path
    diff_patch: Path
    self_metrics: dict  # LOC, complexity, todos, ...
    duration_sec: float
    status: str  # "ok" | "timeout" | "failed"
    raw_output: str

class BuilderProtocol(ABC):
    @abstractmethod
    async def generate(self, spec: Spec, voice_cfg: VoiceConfig) -> BuilderResult:
        ...

    @abstractmethod
    async def smoke_test(self) -> bool:
        ...
```

### 8.2 Adapters spécifiques

```python
# adapters/claude_code_adapter.py
class ClaudeCodeAdapter(BuilderProtocol):
    def __init__(self, model: str = "opus-4.7"):
        self.model = model

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        worktree = create_worktree(cfg.voice_id, spec.run_id)
        prompt = render_template("builder_unified.md", spec=spec, ctx=cfg.context)

        proc = await asyncio.create_subprocess_exec(
            "claude", "code",
            "--model", self.model,
            "--prompt", prompt,
            "--output-dir", str(worktree),
            "--output-format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=worktree
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cfg.timeout
            )
            return self._parse_output(stdout, worktree, cfg)
        except asyncio.TimeoutError:
            proc.kill()
            return BuilderResult(
                voice_id=cfg.voice_id,
                status="timeout",
                duration_sec=cfg.timeout,
                # ...
            )
```

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 3)** : intégration du `concurrency_limiter` avec semaphores par CLI pour éviter throttling des forfaits.

### 8.3 Orchestration parallèle

```python
async def phase_2_generate(spec: Spec, voices: list[VoiceConfig]) -> list[BuilderResult]:
    builders = {v.voice_id: get_builder(v) for v in voices}
    tasks = [
        builders[v.voice_id].generate(spec, v)
        for v in voices
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        r if isinstance(r, BuilderResult)
        else BuilderResult(status="failed", error=str(r))
        for r in results
    ]
```

### 8.4 Self-metrics imposés

Chaque voix doit produire dans son output :
```json
{
  "loc": 234,
  "complexity_cyclomatic_avg": 3.2,
  "test_to_code_ratio": 0.45,
  "todo_count": 1,
  "imports_count": 12,
  "functions_count": 8
}
```

**Disqualification automatique** si `todo_count > 3`.

---

## 9. Phase 3 — Scoring déterministe

### 9.1 Formule de score (script Python, pas LLM)

```python
def compute_score(result: BuilderResult, gates: GateResults) -> float:
    base = (
        35 * gates.acceptance_pass_ratio +
        15 * (1 if gates.bandit_clean else 0) +
        15 * (1 if gates.mypy_strict_clean else 0) +
        10 * (1 if gates.ruff_clean else 0) +
        10 * gates.coverage_score +
        10 * (1 if gates.gitleaks_clean else 0) +
        5 * gates.diff_minimality
    )

    penalties = (
        20 * gates.gitleaks_findings_count +  # secrets en dur = disqualifying
        8 * result.self_metrics.get("todo_count", 0) +
        12 * gates.pro_gap_penalty  # pénalité si patterns SWE-bench contaminés détectés
    )

    bonus = (
        15 * gates.domain_score  # invariants métier (HELIA, MCP, RAG)
    )

    return max(0, base + bonus - penalties)
```

### 9.2 Tie-break

Si écart entre top-2 < 3 points : **les deux versions passent à Phase 4**, l'audit orthogonal tranche.

### 9.3 Disqualifications automatiques (avant scoring)

- `todo_count > 3`
- `gitleaks_findings_count > 0`
- `bandit_severity_high > 0`
- `acceptance_pass_ratio < 0.5`

### 9.4 Anti-gaming

**Mutation testing rapide** (via `mutmut` en mode `--paths-to-mutate src/`) :
- Si > 30% des mutants survivent les tests → tests tautologiques détectés → `coverage_score *= 0.5`

**Détection de mocks abusifs** :
- Si ratio `unittest.mock` ou `pytest.fixture` mock > 40% des tests → `test_quality_score *= 0.6`

---

## 10. Phase 3b — Grounding AST

### 10.1 GroundingEngine 3 couches

```python
# phase_3b_grounding.py
import ast, sys, tomllib
from pathlib import Path

class GroundingEngine:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.installed_pkgs = self._load_uv_lock()
        self.stdlib = set(sys.stdlib_module_names)
        self.local_modules = self._index_local_modules()
        self.local_symbols = self._index_local_symbols()

    def _load_uv_lock(self) -> set[str]:
        with open(self.project_root / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return {dep.split(">")[0].split("=")[0].split("<")[0].strip()
                for dep in data["project"].get("dependencies", [])}

    def _index_local_modules(self) -> set[str]:
        return {p.stem for p in self.project_root.rglob("*.py")
                if not p.name.startswith("_")}

    def _index_local_symbols(self) -> set[str]:
        symbols = set()
        for py_file in self.project_root.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        symbols.add(node.name)
            except SyntaxError:
                continue
        return symbols

    def check(self, code: str, voice_id: str) -> list[GroundingFinding]:
        findings = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            findings.append(GroundingFinding(
                severity="P0",
                voice_id=voice_id,
                kind="syntax_error",
                detail=str(e)
            ))
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._is_valid_import(alias.name):
                        findings.append(GroundingFinding(
                            severity="P1",
                            voice_id=voice_id,
                            kind="hallucinated_import",
                            detail=f"Import '{alias.name}' inconnu"
                        ))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if not self._is_valid_import(node.module):
                    findings.append(GroundingFinding(
                        severity="P1",
                        voice_id=voice_id,
                        kind="hallucinated_import_from",
                        detail=f"From '{node.module}' inconnu"
                    ))
        return findings

    def _is_valid_import(self, mod: str) -> bool:
        top = mod.split(".")[0]
        return (top in self.installed_pkgs
                or top in self.stdlib
                or top in self.local_modules)
```

### 10.2 Politique de traitement

| Type | Sévérité | Action |
|---|---|---|
| Erreur de syntaxe | P0 | Disqualification voix |
| Import halluciné (≥2) | P0 | Disqualification voix |
| Import halluciné (1) | P1 | Finding pour Phase 5 |
| Symbole interne inexistant | P1 | Finding pour Phase 5 |
| Méthode inexistante sur lib externe | P2 | Détectable seulement par tests d'exécution |

**Pas de fix automatique** sur P0/P1 grounding (acquis convergent #10). Disqualification ou finding strict.

---

## 11. Phase 4 — Audit POLYLENS orthogonal

### 11.1 Sélection de l'auditeur

**Règle d'or** : l'auditeur Phase 4 n'est JAMAIS le générateur gagnant Phase 3, et appartient à une famille modèle différente.

```python
AUDITOR_POOLS = {
    "anthropic": ["deepseek-v4-pro", "gemini-3.1-pro", "gpt-5.5"],
    "openai":    ["deepseek-v4-pro", "claude-opus-4.7", "gemini-3.1-pro"],
    "google":    ["deepseek-v4-pro", "claude-opus-4.7", "gpt-5.5"],
    "deepseek":  ["claude-opus-4.7", "gpt-5.5", "gemini-3.1-pro"],
    "moonshot":  ["claude-opus-4.7", "deepseek-v4-pro", "gpt-5.5"],
    "xai":       ["claude-opus-4.7", "gemini-3.1-pro", "deepseek-v4-pro"],
}

def pick_auditor(winner: str, profile: Profile) -> str:
    winner_family = MATRIX[winner]["provider"]
    pool = AUDITOR_POOLS[winner_family]
    # Filtre selon profil (médical → pas OR US)
    if profile.is_medical_high:
        pool = [m for m in pool if not is_us_or_cn(m)]
    return pool[0]  # ou rotation selon historique
```

### 11.2 Axes d'audit (selon profil)

```python
AUDIT_AXES = {
    "A_security":      "Vulnérabilités, injections, fuites",
    "B_quality":       "Style, lisibilité, idioms",
    "C_tests":         "Coverage, edge cases, mocks abusifs",
    "D_perf":          "Goulots, complexité algorithmique",
    "E_architecture":  "Cohérence, séparation préoccupations",
    "F_documentation": "Docstrings, commentaires, README",
    "G_adversarial":   "Property tests, fuzzing potential",
}

PROFILE_AXES = {
    "module_standard":          {"B", "C", "E", "F"},
    "donnees_medicales":        {"A", "B", "C", "E", "F", "G"},
    "refactor_mecanique":       {"B", "C", "E"},
    "migration_deps":           {"E", "C"},
    "post_polylens_finding":    {"A", "C"},
    "algo_helia":               {"A", "C", "D", "G"},
}
```

### 11.3 Output structuré

```json
{
  "auditor_model_family": "deepseek",
  "audit_duration_sec": 142,
  "axes_audited": ["B", "C", "E", "F"],
  "metrics": {
    "actionable_rate": 0.85,
    "vagueness_index": 0.12,
    "finding_count": 7
  },
  "findings": [
    {
      "id": "f001",
      "severity": "P0",
      "axis": "A_security",
      "evidence": {
        "file": "src/parser.py",
        "line": 42,
        "snippet": "...",
        "reproducer": "pytest tests/test_parser.py::test_injection"
      },
      "description": "Injection SQL via paramètre non échappé"
    }
  ]
}
```

**Règle de qualité (anti `Auditor Laziness`)** :
- Si `finding_count == 0` ET `audit_duration_sec < 60` → audit rejeté, on retente avec un autre auditeur du pool

---

## 12. Phase 5 — Triade Critic-Fixer-Verifier

### 12.1 Différenciation P0 / P1 / P2-P3

**Acquis convergent (T4)** :
- **P0 (sécurité, crash, hallucination critique)** : traitement individuel, triade complète, Critic ≠ Fixer ≠ Verifier de familles strictement différentes
- **P1 (qualité, archi, perf)** : batch unifié par axe, un Critic + un Fixer pour le batch
- **P2/P3** : fix automatique local (`ruff --fix`, `mypy --hint`, no LLM)

### 12.2 Implémentation

```python
async def phase_5_dispatch(findings: list[Finding], winner: BuilderResult) -> FixReport:
    p0 = [f for f in findings if f.severity == "P0"]
    p1_by_axis = group_by_axis([f for f in findings if f.severity == "P1"])
    p2_p3 = [f for f in findings if f.severity in ("P2", "P3")]

    results = []

    # P0 : par finding, triade stricte
    for f in p0:
        result = await asyncio.wait_for(
            triade_p0(f, winner),
            timeout=480  # 8 min par P0
        )
        results.append(result)
        if result.status == "escalate":
            return FixReport(status="blocked_p0", results=results)

    # P1 : batch par axe
    for axis, batch in p1_by_axis.items():
        result = await asyncio.wait_for(
            triade_p1_batch(axis, batch, winner),
            timeout=600  # 10 min par batch axe
        )
        results.append(result)
        if result.status == "escalate":
            mark_unresolved(batch)

    # P2/P3 : fix auto local
    for f in p2_p3:
        auto_fix_local(f, winner)

    return FixReport(status="completed", results=results)


async def triade_p0(finding: Finding, winner: BuilderResult) -> FixResult:
    winner_family = MATRIX[winner.voice_id]["provider"]

    # Critic : famille ≠ winner
    critic = pick_model(family_neq=[winner_family], role="critic")
    critique = await critic.criticize(finding, winner.code_dir)

    for attempt in range(2):  # max 2 tours
        # Fixer : famille ≠ winner ET ≠ critic
        critic_family = MATRIX[critic]["provider"]
        fixer = pick_model(
            family_neq=[winner_family, critic_family],
            role="fixer"
        )
        patch = await fixer.fix(finding, critique, winner.code_dir)

        # Gate local d'abord (pytest, mypy, bandit)
        local_ok = await run_local_gates(winner.code_dir, patch)
        if not local_ok:
            critique = critique.with_failure_context(local_ok.failures)
            continue

        # Verifier : Évaluateur-Optimiseur strict, JSON-only
        # Famille ≠ critic ET ≠ fixer
        verifier_family_excl = [winner_family, critic_family, MATRIX[fixer]["provider"]]
        verifier = pick_model(
            family_neq=verifier_family_excl,
            role="verifier"
        )
        verdict = await verifier.evaluate_strict(finding, patch, critique)
        # verdict = {"pass": bool, "reason": str, "required_evidence": str}

        if verdict["pass"]:
            return FixResult(status="accepted", finding=finding, patch=patch)

        # Pas pass : on itère avec le contexte du verdict
        critique = critique.with_verifier_feedback(verdict)

    return FixResult(status="escalate", finding=finding, last_patch=patch)
```

### 12.3 Verifier strict (JSON-only)

Prompt système du Verifier :

```
Tu es un Évaluateur-Optimiseur strict. Tu reçois :
- Le finding initial
- Le patch proposé par le Fixer
- Le contexte du Critic

Tu retournes UNIQUEMENT du JSON valide, jamais de prose libre, jamais de code.
Schema:
{
  "pass": boolean,
  "reason": "string (1-3 phrases concrètes)",
  "required_evidence": "commande exécutable qui prouve le fix (ex: pytest tests/test_x.py::test_y)"
}

Tu rejettes par défaut si tu n'as pas une preuve reproductible.
Tu ne réécris JAMAIS le code. Tu n'ajoutes JAMAIS de suggestion d'amélioration.
```

---

## 13. Phase 6 — Validation finale

### 13.1 Gates généraux (toujours actifs)

```python
GENERAL_GATES = [
    "pytest -q --tb=short",
    "mypy --strict src/",
    "ruff check src/ tests/",
    "bandit -r src/ -ll",
    "gitleaks detect --no-banner",
]

async def run_general_gates(workdir: Path) -> GateResults:
    results = {}
    for gate in GENERAL_GATES:
        proc = await asyncio.create_subprocess_shell(
            gate,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        results[gate] = (proc.returncode == 0, stdout.decode(), stderr.decode())
    return GateResults(**results)
```

### 13.2 Domain gates

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 2)** : implémentation des gates spécifiques MCP/RAG/SQLite/Qdrant.
>
> **Acquis** : un test pytest qui passe ne garantit PAS qu'un serveur MCP fonctionne en prod. Il faut :
> - `validate_mcp_schema.py` : démarrage server isolé, appel `tools/list`, validation schemas Pydantic
> - `validate_sqlite_migration.py` : diff schémas avant/après, refus migrations destructives
> - `validate_fts5_golden.py` : 3 requêtes golden avec résultats attendus
> - `validate_qdrant_consistency.py` : count + sample query avec retrieval@k attendu
> - `validate_rag_smoke.py` : 5 requêtes golden, hash chunks
>
> **Question round 4** : un gate domain qui échoue bloque-t-il le commit (Phase 7) ou émet-il warning ?

**Placeholder** :
```python
# domain_gates/__init__.py
DOMAIN_GATES_BY_PROFILE = {
    "mcp_schema_change":       ["validate_mcp_schema"],
    "rag_ingestion":           ["validate_qdrant_consistency", "validate_rag_smoke"],
    "sqlite_migration":        ["validate_sqlite_migration", "validate_fts5_golden"],
    # ... à compléter
}
```

### 13.3 Critères de validation finale

```python
def validate_final(workdir: Path, profile: Profile) -> ValidationVerdict:
    general = run_general_gates(workdir)
    domain = run_domain_gates(workdir, profile)
    spec_hash_ok = verify_spec_hash(workdir)

    return ValidationVerdict(
        passed=all([general.all_pass, domain.all_pass, spec_hash_ok]),
        general=general,
        domain=domain,
        spec_drift_detected=not spec_hash_ok
    )
```

---

## 14. Phase 7 — Commit & ADR

### 14.1 Commit Git

```bash
# Tag automatique avant commit pour rollback rapide
git tag polybuild/run-{run_id}-pre HEAD

# Commit feature
git add -A
git commit -m "polybuild: {summary} [run-{run_id}]

Co-authored-by: {winner_voice}
Polybuild-run: {run_id}
Polybuild-profile: {profile_id}
"

# Tag post-commit pour reprise
git tag polybuild/run-{run_id}-commit HEAD
```

### 14.2 ADR automatique (si critères)

```python
ADR_TRIGGERS = [
    "schema_db_change",
    "new_dependency",
    "architecture_pattern_change",
    "breaking_api_change",
    "polylens_p0_resolved",
]

async def maybe_generate_adr(run: PolybuildRun) -> Optional[ADR]:
    if not any(t in run.events for t in ADR_TRIGGERS):
        return None

    prompt = render_template("adr.md", run=run)
    adr_text = await claude_code_cli(prompt, model="opus-4.7", timeout=180)
    adr_id = next_adr_id(run.project_root)
    write_adr(run.project_root, adr_id, adr_text)
    return ADR(id=adr_id, text=adr_text)
```

### 14.3 polybuild_run.json archivé

```json
{
  "run_id": "2026-05-03_run_42",
  "profile": "module_python_standard",
  "spec_hash": "abc123...",
  "voices": ["claude-opus-4.7", "gpt-5.5", "kimi-k2.6"],
  "winner": "gpt-5.5",
  "scores": {"opus": 78.2, "gpt-5.5": 84.5, "kimi": 71.0},
  "phase4_findings": {"P0": 0, "P1": 3, "P2": 5, "P3": 2},
  "phase5_iterations": {"f001": 1, "f002": 2},
  "domain_gates_passed": true,
  "duration_total_sec": 1840,
  "tokens_used": {
    "claude_max": 45000,
    "chatgpt_pro": 38000,
    "gemini_pro": 12000,
    "kimi_allegretto": 30000,
    "openrouter_deepseek": 22000,
    "openrouter_grok": 8000
  },
  "cost_eur_marginal": 1.20
}
```

---

## 15. Phase 8 — Production smoke

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 4)**
>
> **Acquis** : Phase 8 nouvelle, pas dans les rounds 1-3. Manquante.
>
> Spécifie :
> - Délai après commit (5 min ? 15 min ?)
> - Suite de requêtes golden contre serveur déployé
> - Seuil de dégradation acceptable (5% ? 10% ?)
> - Rollback automatique si dépassement → `git reset --hard polybuild/run-{run_id}-pre` puis `docker-compose restart`

**Placeholder** :
```python
# phase_8_prod_smoke.py
async def phase_8_smoke(run: PolybuildRun) -> SmokeVerdict:
    # TODO post-round 4
    raise NotImplementedError("Round 4 in progress")
```

---

## 16. Table de routage v3

### 16.1 Règles d'orthogonalité dures

- Jamais 2 voix de la même famille
- Médiateur ≠ aucune voix Phase 2
- Au moins 1 voix avec contexte ≥ 1M tokens si projet > 100 fichiers
- Pour profil médical : voir niveau de paranoïa (§5)

### 16.2 Table complète (12 profils)

| # | Profil | Voix 1 (CLI) | Voix 2 (CLI) | Voix 3 (CLI/OR) | Médiateur | Gates spécifiques | Rationale |
|---|---|---|---|---|---|---|---|
| 1 | Module Python standard (codebase connue) | `gpt-5.5` (Codex) | `gemini-3.1-pro` | `kimi-k2.6` | `claude-opus-4.7` | pytest, mypy, ruff, bandit | Builder + ctx + variant |
| 2 | Module Python code propriétaire inédit | `claude-opus-4.7` | `gpt-5.5` | `deepseek-v4-pro` (OR) | `gemini-3.1-pro` | + grounding, mutation testing | Pro Gap compensé |
| 3 | Algo/math pur (HELIA) | `gpt-5.5` | `kimi-k2.6` | `deepseek-v4-pro` (OR) | `claude-opus-4.7` | + property tests (hypothesis), invariants math | DeepSeek roi algo |
| 4 | Données médicales — paranoia LOW | `claude-sonnet-4.6` | `gemini-3.1-pro` | `gpt-5.5` | `claude-opus-4.7` | + privacy_gate, redaction report | CLI frontier OK post-anonymisation |
| 5 | Données médicales — paranoia MEDIUM | `claude-sonnet-4.6` | `gemini-3.1-pro` | `mistral/devstral-2` (Mistral EU direct, pas OR) | `claude-opus-4.7` | + DPA validé Mistral | OR US interdit |
| 6 | Données médicales — paranoia HIGH | `qwen2.5-coder:14b-int4` (NAS) | `mistral/devstral-2` (EU direct) | `qwen2.5-coder:7b-int4` (NAS) | local Qwen 14B | + privacy_gate strict, no_external | 100% local + EU |
| 7 | Parsing PDF médical | `gemini-3.1-pro` (ctx 2M) | `gpt-5.5` | `deepseek-v4-pro` (OR, post-anonymisation) | `claude-opus-4.7` | + golden PDFs, encoding tests | Multimodal + parsing |
| 8 | RAG ingestion/chunking/eval | `gemini-3.1-pro` | `gpt-5.5` | `kimi-k2.6` | `claude-opus-4.7` | + retrieval@k fixtures, chunk hash | Ctx + structure + variantes |
| 9 | MCP schema/tool change | `claude-opus-4.7` | `gpt-5.5` | `grok-4.20` (OR) | `gemini-3.1-pro` | + JSON-RPC smoke, schema validation | Adhérence schemas stricte |
| 10 | OAI-PMH scraping/API REST | `gpt-5.3-codex` | `gpt-5.5` | `kimi-k2.6` | `gemini-3.1-pro` | + retry/pagination/rate-limit tests | Codex CLI + agentic |
| 11 | DevOps/IaC/scripts shell | `gpt-5.3-codex` | `claude-sonnet-4.6` | `gemini-3.1-pro` | `claude-opus-4.7` | + shellcheck, terraform validate | Codex spécialiste CLI |
| 12 | Refactor mécanique <300 LOC | `gpt-5.5` | `gemini-3.1-pro` | (binôme suffit) | gates locaux uniquement | + diff minimality, behavior snapshot | Pas de médiateur LLM |
| 13 | LLM-as-Judge / Eval pipeline | `gemini-3.1-pro` | `claude-sonnet-4.6` | `grok-4.20` (OR) | `gpt-5.5` | + bias score, inter-annotator kappa | Verdict JSON-only |
| 14 | Post-finding POLYLENS P0/P1 | (winner ≠ générateur) | (critic) | (verifier) | local gates first | + regression test obligatoire | Anti self-fix |
| 15 | Documentation/ADR | `claude-opus-4.7` | `gemini-3.1-pro` | `kimi-k2.6` | humain rapide | + ADR schema, consistency | Claude rédaction |

### 16.3 Pool de candidats (matrice diversité Phase 1)

Chaque profil a un pool de 5-7 candidats parmi lesquels la matrice de diversité ou la sonde 50 LOC sélectionne 3.

```yaml
# config/routing_pools.yaml
profile_2_inedit_critique:
  candidates:
    - claude-opus-4.7
    - claude-sonnet-4.6
    - gpt-5.5
    - gemini-3.1-pro
    - kimi-k2.6
    - deepseek-v4-pro  # OR
  min_diversity: 2.3
  requires_probe: true
```

---

## 17. Mémoire de projet

### 17.1 `AGENTS.md` racine — structure normative

```markdown
# AGENTS.md

## 0. Scope
Projet Python 3.11+, uv, asyncio, MCP, SQLite, Qdrant. Pas de LangChain/LlamaIndex.

## 1. Non-negotiable Constraints
- Pas de données nominatives santé en prompt externe
- Pas de Node/Go en prod
- ruff + mypy --strict + pytest + pre-commit
- SQLite WAL en dev, immutable en prod

## 2. Architecture Invariants
- Schemas MCP JSON-sérialisables
- RAG outputs préservent traçabilité source
- Qdrant collections schema-versionnées

## 3. Coding Conventions
- Pydantic v2 typed contracts
- Pas de `except` bare
- Pas de network calls sans timeout
- Pas de TODO en commit

## 4. Test Requirements
- Scenarios happy / edge / failure
- Smoke tests pour chaque tool MCP
- Property tests pour parsers/chunkers

## 5. Security & Privacy
- privacy_gate avant tout appel externe
- bandit + gitleaks avant commit
- Jamais log raw health text

## 6. Known Failure Patterns
| Pattern | Example | Prevention | Source |
|---|---|---|---|

## 7. Active ADRs
| ADR | Rule | Status |
|---|---|---|

## 8. Expiring Rules (TTL)
| Rule | Added | Expires | Owner |
|---|---|---|---|
```

**Limite stricte** : 200 lignes max. Sections fixes. Frontmatter YAML pour versioning et hash SHA-256.

### 17.2 Vector summary local

**Stack** :
- Embedder : `all-MiniLM-L6-v2` (384 dim, ~80 MB RAM, CPU OK)
- Stockage : `sqlite-vec` ou Qdrant local (déjà déployé pour MedData)
- Granularité : 1 chunk par `polybuild_run.json` summary + 1 chunk par failure pattern
- Indexé : task profile, winner, loser_reason, findings P0/P1, gates failed
- Exclusion absolue : aucune donnée health brute

**Service Docker dédié** (recommandé) :
```yaml
# docker-compose.polybuild.yml
services:
  polybuild-embedder:
    image: ghcr.io/sbert/all-minilm-l6-v2:latest
    ports: ["8090:8000"]
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 200M
```

**Évite** de charger/décharger l'embedder à chaque run (RAM partagée avec MCP servers ~9 GB MedData).

### 17.3 Injection dans les CLI

```python
def build_prompt_with_memory(base: str, task: str, project_root: Path) -> str:
    agents = (project_root / "AGENTS.md").read_text()
    relevant_runs = retrieve_relevant_runs(task, k=5)

    return f"""<AGENTS_MD>
{agents}
</AGENTS_MD>

<RELEVANT_PRIOR_RUNS>
{format_runs(relevant_runs)}
</RELEVANT_PRIOR_RUNS>

<TASK>
{task}
</TASK>

{base}
"""
```

**Spécificités par CLI** :
- Claude Code : lit `AGENTS.md` automatiquement si présent à la racine
- Codex CLI : injection via `--instructions $(cat AGENTS.md)` ou prompt prefix
- Gemini CLI : injection via `--system-instruction`
- Kimi CLI : injection via `--system-prompt AGENTS.md`

### 17.4 Anti-pourriture

```python
def prune_agents_md(project_root: Path):
    rules = parse_rules(project_root / "AGENTS.md")
    for rule in rules:
        if rule.is_expired() and not rule.linked_to_active_adr():
            mark_archived(rule)
        if rule.contradicts_existing(rules):
            require_adr_resolution(rule)
```

**Règle d'or** : aucune règle ne devient permanente sans ADR ou test associé.

---

## 18. Apprentissage continu

### 18.1 Auto-ajustement supervisé (jamais auto-application)

**Acquis convergent (Q4)** : suggestions ADR uniquement après 20-30 runs, validation humaine obligatoire.

```python
# learning_engine.py
async def suggest_routing_adjustments(profile_id: str) -> Optional[ADRProposal]:
    runs = load_runs(profile_id)
    if len(runs) < 30:
        return None

    window = runs[-20:]  # fenêtre glissante
    stats = aggregate_by_voice(window)

    proposals = []
    for voice_id, s in stats.items():
        score = (
            0.30 * s.win_rate
            + 0.25 * s.acceptance_pass_rate
            - 0.25 * s.p0_p1_rate
            - 0.15 * s.grounding_failure_rate
            - 0.05 * s.timeout_rate
        )
        if score < CURRENT_WEIGHT[voice_id] - 0.15:
            proposals.append(f"Rétrograder {voice_id} : score {score:.2f}")
        elif score > CURRENT_WEIGHT[voice_id] + 0.15:
            proposals.append(f"Promouvoir {voice_id} : score {score:.2f}")

    if not proposals:
        return None

    # Test de significativité (binomial)
    if not is_significant(stats, p_threshold=0.05):
        return None

    return ADRProposal(profile_id=profile_id, proposals=proposals)
```

### 18.2 Garde-fous

- **Jamais d'auto-application** : suggestion → ADR draft → validation humaine → modification `routing.yaml`
- **Fenêtre glissante de 20 runs** : pas de pénalité historique > 20 runs
- **Rotation minimale** : chaque voix doit avoir ≥10 apparitions dans la fenêtre (anti "rich get richer")
- **Expiration des suggestions** : 60 jours, sinon re-calcul

### 18.3 Commande utilisateur

```bash
$ polybuild stats --profile module_standard --last 50
| Model              | Win Rate | Avg P0 | Latency | Recommendation |
|--------------------|----------|--------|---------|----------------|
| claude-opus-4.7    | 35%      | 0.1    | 80s     | KEEP           |
| gpt-5.5            | 42%      | 0.3    | 45s     | PROMOTE        |
| kimi-k2.6          | 23%      | 0.5    | 60s     | PROBATION      |

→ ADR draft générée: .polybuild/adr_drafts/2026-05-03-module-standard-routing.md
```

---

## 19. Tests d'intégration CLI

### 19.1 Smoke test

```python
# tests/integration/smoke_cli.py
SMOKE_PROMPT = """
Écris une fonction Python `hello_polybuild()` qui retourne 'OK'.
Inclus un test pytest. Output JSON: {"code": "...", "tests": "..."}.
"""

async def smoke_test_cli(adapter: BuilderProtocol, timeout: int = 60) -> SmokeResult:
    try:
        result = await asyncio.wait_for(
            adapter.smoke_test(SMOKE_PROMPT),
            timeout=timeout
        )
        checks = {
            "valid_json": is_valid_json(result.raw_output),
            "has_function": "def hello_polybuild" in result.code,
            "returns_ok": "'OK'" in result.code or '"OK"' in result.code,
            "has_test": "def test_" in result.tests or "pytest" in result.tests,
            "ruff_clean": await ruff_check(result.code),
            "mypy_clean": await mypy_check(result.code),
        }
        return SmokeResult(
            adapter=adapter.name,
            passed=all(checks.values()),
            details=checks,
            duration_sec=result.duration
        )
    except asyncio.TimeoutError:
        return SmokeResult(adapter=adapter.name, passed=False, reason="timeout")
```

### 19.2 Fréquence

- **Hebdomadaire** : cron sur NAS ou `systemd timer`, exécute tous les adapters
- **Pré-run** : si cache > 7 jours OU run profile critique
- **Cache 24h** pour smoke tests OK

### 19.3 Fallback automatique

```python
CLI_TO_OR_FALLBACK = {
    "claude_code_opus":     "deepseek/deepseek-v4-pro",  # ctx massif + qualité
    "claude_code_sonnet":   "deepseek/deepseek-v4-flash",
    "codex_cli":            "deepseek/deepseek-v4-pro",   # même tier qualité
    "gemini_cli":           "x-ai/grok-4.20",             # ctx long alternative
    "kimi_cli":             "deepseek/deepseek-v4-pro",
}

async def ensure_cli_available(cli_name: str) -> str:
    if await smoke_test_cached(cli_name):
        return cli_name
    fallback = CLI_TO_OR_FALLBACK[cli_name]
    log.warning(f"CLI {cli_name} dégradé, fallback {fallback}")
    notify_user(f"Fallback OR activé : {cli_name} → {fallback}")
    return f"openrouter:{fallback}"
```

---

## 20. Concurrence & rate limits

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 3)**
>
> **Acquis** : avec 3 voix Phase 2 + Phase 0b Spec Attack + Phase 5 triade, on peut avoir 5-7 invocations CLI simultanées sur les mêmes 4 forfaits. Personne n'a vérifié les limites.
>
> Spécifier :
> - Limites pratiques connues des 4 forfaits (Claude Max 20x, ChatGPT Pro, Gemini Pro, Kimi Allegretto)
> - Implémentation `concurrency_limiter.py` avec semaphores par CLI
> - Stratégie de back-pressure (attendre / fallback OR / annuler la voix) selon P0/P1/P2
> - Détection des throttles (timeout HTTP, headers `X-RateLimit-*`)

**Placeholder** :
```python
# concurrency_limiter.py
SEMAPHORES = {
    "claude_code":     asyncio.Semaphore(2),  # à confirmer round 4
    "codex_cli":       asyncio.Semaphore(3),
    "gemini_cli":      asyncio.Semaphore(3),
    "kimi_cli":        asyncio.Semaphore(2),
    "openrouter":      asyncio.Semaphore(5),
    "mistral_eu":      asyncio.Semaphore(3),
}

async def acquire_cli_slot(cli_name: str):
    sem = SEMAPHORES[cli_name]
    await sem.acquire()
    try:
        yield
    finally:
        sem.release()
```

---

## 21. Déploiement production

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 4)**
>
> **Acquis** : Le NAS DS224+ = production live (3 serveurs MCP en consultation). POLYBUILD modifie du code de ces serveurs. Aucun round n'a abordé comment éviter de casser la prod pendant un run.
>
> Tranche entre :
> - **Option A** : Feature branch Git + staging Docker dédié, merge manuel
> - **Option B** : Worktree Git séparé + Docker isolé (ports différents) + bascule Caddy
> - **Option C** : Branche `polybuild/run-{id}` + auto-merge si gates OK + Phase 8 prod smoke

**Placeholder structure cible** :
```
NAS /volume1/
├── prod/                        # serveurs MCP en prod 24/7
│   ├── meddata/
│   ├── sstinfo/
│   └── redapi/
├── staging/                     # POLYBUILD opère ici
│   ├── meddata/                 # symlink ou volume read-only depuis prod/
│   └── ...
└── polybuild/
    └── runs/{run_id}/
```

---

## 22. Skill Claude Code `/polybuild`

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 5a)**
>
> **Acquis** : skill `/polybuild` ne doit PAS bloquer Claude Code 45 min. Lancement en arrière-plan.
>
> Tranche entre :
> - `nohup uv run polybuild_v3.py ... &`
> - `systemd-run --user --scope`
> - Démon Python `polybuild-daemon` avec queue
> - `tmux new-session -d -s polybuild-{run_id}`
>
> Inclure aussi commandes : `/polybuild status <run_id>`, `/polybuild logs <run_id>`, `/polybuild abort <run_id>`

**Placeholder SKILL.md** :
```markdown
# polybuild skill

## When to use
- L'utilisateur demande "lance polybuild", "génère ce module avec polybuild", etc.

## Commands
1. `/polybuild run --task <file> --profile <name>` — lance un run en arrière-plan
2. `/polybuild status <run_id>` — affiche état du run
3. `/polybuild logs <run_id>` — affiche logs récents
4. `/polybuild abort <run_id>` — arrête un run en cours

## Implementation
TODO post-round 4
```

---

## 23. Gestion des secrets

> ⚠️ **À COMPLÉTER POST-ROUND 4 (Faille 5b)**
>
> **Acquis** : POLYBUILD manipule API keys OpenRouter, Mistral EU, et tokens des 4 CLI.
>
> Tranche entre :
> - `~/.polybuild/secrets.env` avec `chmod 600`
> - `pass` (password-store)
> - `keyring` Python
> - `1Password CLI`
>
> Inclure config `.gitleaks.toml` minimal et pré-commit hook.

**Placeholder** :
```bash
# ~/.polybuild/secrets.env (chmod 600)
OPENROUTER_API_KEY=sk-or-v1-...
MISTRAL_EU_API_KEY=...
```

```toml
# .gitleaks.toml — TODO post-round 4
```

---

## 24. Versioning de POLYBUILD

### 24.1 Repo dédié `polybuild-core`

**Acquis convergent (Q-new-2)** : repo séparé des projets utilisateur, installable via `uv tool install --editable`.

### 24.2 Structure

```
polybuild-core/
├── pyproject.toml
├── uv.lock
├── README.md
├── AGENTS.md                    # conventions du dev de POLYBUILD lui-même
├── src/polybuild/
│   ├── __init__.py
│   ├── polybuild_v3.py          # entry point CLI
│   ├── orchestrator.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── builder_protocol.py
│   │   ├── claude_code.py
│   │   ├── codex_cli.py
│   │   ├── gemini_cli.py
│   │   ├── kimi_cli.py
│   │   ├── openrouter.py
│   │   ├── mistral_eu.py
│   │   └── ollama_local.py
│   ├── phases/
│   │   ├── phase_minus_one_privacy.py    # Round 4
│   │   ├── phase_0_spec.py
│   │   ├── phase_1_select.py
│   │   ├── phase_2_generate.py
│   │   ├── phase_3_score.py
│   │   ├── phase_3b_grounding.py
│   │   ├── phase_4_audit.py
│   │   ├── phase_5_triade.py
│   │   ├── phase_6_validate.py
│   │   ├── phase_7_commit.py
│   │   └── phase_8_prod_smoke.py         # Round 4
│   ├── domain_gates/                     # Round 4
│   │   ├── validate_mcp.py
│   │   ├── validate_sqlite.py
│   │   ├── validate_qdrant.py
│   │   └── validate_rag.py
│   ├── memory/
│   │   ├── agents_md_parser.py
│   │   ├── vector_store.py
│   │   └── prune.py
│   ├── routing/
│   │   ├── matrix.py
│   │   ├── probe.py
│   │   └── selector.py
│   ├── learning/
│   │   ├── stats.py
│   │   └── adr_proposer.py
│   ├── concurrency/                      # Round 4
│   │   └── limiter.py
│   ├── security/                         # Round 4
│   │   ├── secrets.py
│   │   └── gitleaks_config.py
│   └── cli.py
├── config/
│   ├── models.yaml
│   ├── routing.yaml
│   ├── timeouts.yaml
│   ├── model_dimensions.yaml
│   └── routing_pools.yaml
├── prompts/
│   ├── opus_spec.md
│   ├── spec_attack.md
│   ├── spec_revise.md
│   ├── builder_unified.md
│   ├── critic.md
│   ├── fixer.md
│   ├── verifier_strict.md
│   └── adr.md
├── tests/
│   ├── unit/
│   ├── integration/
│   │   └── smoke_cli.py
│   └── regression/
│       ├── gold_prompts.json
│       └── test_gold_regression.py
├── docs/
│   ├── architecture.md
│   ├── adr/
│   │   ├── 0001-initial-architecture.md
│   │   ├── 0002-routing-llm-judge.md
│   │   └── ...
│   └── examples/
└── skills/
    └── polybuild/
        └── SKILL.md
```

### 24.3 ADR — règles de déclenchement

| Changement | ADR ? |
|---|---|
| Ajout/retrait de modèle dans `routing.yaml` | OUI |
| Modification seuils diversité/scoring | OUI |
| Changement prompt système (`prompts/`) | OUI si rôle change, NON si typo |
| Adapter CLI : nouvelle version | NON sauf rupture majeure |
| Privacy Gate rule | OUI |
| Domain gate change | OUI |

### 24.4 Tests de non-régression

5 gold prompts représentatifs des profils principaux :
- Profil 1 (module standard)
- Profil 3 (algo HELIA)
- Profil 5 (médical paranoia medium)
- Profil 9 (MCP schema change)
- Profil 12 (refactor mécanique)

Exécutés avant chaque commit sur `polybuild-core` (pre-commit hook).

---

## 25. Bootstrap d'un projet vierge

### 25.1 `polybuild init` interactif

```python
@app.command()
def init(project_path: Path = Path(".")):
    """Initialise POLYBUILD pour un nouveau projet."""
    typer.echo("POLYBUILD v3 — Bootstrap projet")

    # 1. Charge global_agents.md
    global_agents_path = Path.home() / ".polybuild" / "global_agents.md"
    if global_agents_path.exists():
        global_ctx = global_agents_path.read_text()
    else:
        typer.echo("⚠️  ~/.polybuild/global_agents.md non trouvé, création template")
        create_global_agents_template()
        global_ctx = global_agents_path.read_text()

    # 2. 5 questions
    answers = {
        "project_name": typer.prompt("Nom du projet"),
        "project_type": typer.prompt(
            "Type de projet",
            type=typer.Choice(["MCP", "RAG", "CLI", "scraper", "library"])
        ),
        "stack_extra": typer.prompt("Stack supplémentaire (libs principales)", default=""),
        "sensitive_data": typer.prompt(
            "Sensibilité données",
            type=typer.Choice(["none", "health-adjacent", "identifiable"])
        ),
        "validation_command": typer.prompt(
            "Commande de validation",
            default="uv run pytest -q"
        ),
    }

    # 3. Génère AGENTS.md minimal via Opus 4.7 (CLI gratuit)
    prompt = render_template("init_agents.md", global_ctx=global_ctx, answers=answers)
    agents_md = asyncio.run(claude_code_cli(prompt, model="opus-4.7", timeout=120))

    # 4. Écrit fichiers
    (project_path / "AGENTS.md").write_text(agents_md)
    (project_path / ".polybuild" / "config.yaml").parent.mkdir(parents=True, exist_ok=True)
    (project_path / ".polybuild" / "config.yaml").write_text(yaml.dump(answers))

    # 5. Init vector store local (vide)
    init_vector_store(project_path / ".polybuild" / "memory.db")

    # 6. Seed synthétique pour cold-start
    seed_synthetic_runs(project_path, project_type=answers["project_type"], n=3)

    # 7. Premier brief
    brief_path = project_path / ".polybuild" / "first_brief.md"
    brief_path.write_text(BRIEF_TEMPLATE)

    typer.echo(f"""
✅ Projet initialisé.
📝 Édite {brief_path} avec ta tâche initiale.
🚀 Lance : polybuild run --brief {brief_path} --bootstrap
""")
```

### 25.2 Mode `--bootstrap`

Premier run sur un projet vierge, gates renforcés :
- AGENTS.md statut `draft` (revue manuelle après run #3)
- Seuils Phase 3 relevés de 15%
- Pas de modification production agressive
- `domain_gates` au mode warning seulement

### 25.3 `~/.polybuild/global_agents.md` template

```markdown
# Global AGENTS — Conventions transverses reddie

## Stack universelle
- Python 3.11+, uv (jamais pip)
- ruff + mypy --strict + pytest + pre-commit
- SQLite WAL dev / immutable prod, FTS5 + sqlite-vec
- Qdrant local pour vector
- Pas de LangChain, pas de LlamaIndex

## Naming
- snake_case pour Python
- UPPER_SNAKE pour constantes
- async def pour toute I/O

## Commits
- Conventional commits
- Pas de TODO en commit final
- Pré-commit hook obligatoire

## Tests
- pytest --cov >= 80%
- happy / edge / failure scenarios obligatoires
- Property tests (hypothesis) pour parsers

## Sécurité
- Jamais de secrets en code
- gitleaks pre-commit
- bandit -ll en CI

## Documentation
- Docstrings Google style
- Type hints partout (mypy --strict)
- README.md obligatoire à la racine
```

---

## 26. Anti-patterns documentés

### 26.1 Catalogue (20 anti-patterns)

| # | Anti-pattern | Solution v3 |
|---|---|---|
| 1 | Generation Drift | Spec hashée + acceptance tests stricts |
| 2 | Test Mocking Trap | mock_policy: integration > mocks |
| 3 | Premature Abstraction | Réviser après 3 cas d'usage réels |
| 4 | Hidden Tech Debt | Refus si > 3 TODOs |
| 5 | Missing Edge Cases | Scenarios obligatoires happy/edge/failure |
| 6 | Monolithic Generation | 3 voix minimum |
| 7 | Convergent Hallucination | Grounding AST Phase 3b |
| 8 | Self-Fix Bias | Critic ≠ Fixer ≠ Verifier (familles différentes) |
| 9 | Family Echo Chamber | Matrice diversité multi-dimensions |
| 10 | Mediator Capture | Verifier strict JSON-only |
| 11 | Cheap-out Spiral | (N/A : coût neutralisé par forfaits) |
| 12 | Auditor Laziness | Métriques imposées (actionable_rate, finding_count_min) |
| 13 | Spec Drift Mid-run | Spec hashée Phase 0, vérif SHA Phase 6 |
| 14 | Context Oversharing | Context packer strict, AGENTS.md filtré |
| 15 | Spec-Capture Bias | Phase 0b Spec Attack obligatoire |
| 16 | Benchmark Cargo Cult | Mini-bench interne (gold prompts) |
| 17 | Runaway Agent Loop | Max 2 itérations Phase 5, hard timeout 45 min |
| 18 | Project Memory Rot | Append-only + TTL + ADR-linked rules |
| 19 | Evaluator-Optimizer Collusion | Preuve reproductible obligatoire pour P0/P1 |
| 20 | Diff Bloat Camouflé | Score `diff_minimality`, justification > 5 fichiers |

---

## 27. Roadmap d'implémentation

### Phase A — Fondations (8h)

1. Repo `polybuild-core` initialisé via `uv init`
2. Structure de répertoires complète
3. `BuilderProtocol` + adapters Claude Code, Codex, Gemini, Kimi
4. Smoke test minimal de chaque adapter
5. `AGENTS.md` + `pyproject.toml` POLYBUILD lui-même

### Phase B — Pipeline core (12h)

6. Phase 0 (spec + spec attack)
7. Phase 1 (matrice statique)
8. Phase 2 (orchestration parallèle)
9. Phase 3 (scoring + mutation testing rapide)
10. Phase 3b (grounding AST)
11. Phase 7 (commit + ADR auto)

### Phase C — Audit & fix (8h)

12. Phase 4 (audit POLYLENS)
13. Phase 5 (triade C/F/V)
14. Phase 6 (gates généraux)
15. Verifier strict JSON-only

### Phase D — Round 4 spec finalisée (intégration)

16. Phase -1 Privacy Gate (Faille 1)
17. Phase 6 domain gates (Faille 2)
18. Concurrency limiter (Faille 3)
19. Phase 8 prod smoke + déploiement (Faille 4)
20. Skill Claude Code + secrets (Faille 5)

### Phase E — Mémoire & apprentissage (6h)

21. Vector store local (sqlite-vec ou Qdrant)
22. Embedder service Docker
23. `polybuild stats` + suggestions ADR
24. Anti-pourriture AGENTS.md

### Phase F — Bootstrap & UX (4h)

25. `polybuild init` interactif
26. Skill Claude Code `/polybuild`
27. Documentation utilisateur + exemples
28. Tests gold prompts

### Phase G — Hardening (ongoing)

29. Monitoring (Uptime Kuma sur les CLI)
30. Backup config `~/.polybuild/`
31. Tests d'intégration hebdomadaires automatisés
32. Revue trimestrielle des anti-patterns

**Total estimé** : ~40h sur 4-6 semaines en parallèle de la pratique médicale.

---

## Annexes

### A. Glossaire

- **CoT** : Chain-of-Thought, raisonnement étape par étape exposé par le modèle
- **MoE** : Mixture-of-Experts, architecture où seuls certains paramètres sont actifs par token
- **Pro Gap** : différence de score entre SWE-bench Verified (contaminé) et SWE-bench Pro (décontaminé)
- **Grounding** : vérification post-génération que le code généré référence des entités existantes
- **Évaluateur-Optimiseur** : pattern Anthropic où un LLM critique un output sans le réécrire

### B. Références

- SWE-bench Pro : https://arxiv.org/...  (à compléter)
- Anthropic Evaluator-Optimizer pattern
- Anthropic published Claude Code documentation
- DeepSeek V4-Pro paper (raisonnement transparent MoE)

### C. Historique des décisions

| Round | Date | Décisions clés |
|---|---|---|
| Round 1 | 2026-04-30 | Identification 13 failles v2, contexte coût erroné |
| Round 2 | 2026-05-01 | Correction contexte (forfaits gratuits), 8 questions architecturales tranchées |
| Round 3 | 2026-05-02 | 4 tensions résolues + 5 questions opérationnelles |
| Round 4 | 2026-05-03 | 5 failles résiduelles à combler |

---

**Fin du document principal. Les 5 sections marquées ⚠️ Round 4 seront finalisées après réception des réponses des modèles `gpt-5.5`, `deepseek-v4-pro` et optionnellement `gemini-3.1-pro`.**
