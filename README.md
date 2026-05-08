# POLYBUILD v3

> Méta-orchestrateur multi-LLM pour génération de code en production.
> Spec-first, adversarial review, grounding AST, déploiement contrôlé.

**Version :** 3.0.0-dev — POLYLENS round 10 (2026-05-03)
**Status :** Spec + squelette complets, 286 tests pytest, gates SAST verts (ruff/mypy strict/bandit/pip-audit). Sprints A/E/F restants pour exécutabilité prod.

## Quality gates (POLYLENS round 10, 2026-05-03)

| Gate | Status | Détails |
|---|---|---|
| ruff (E/F/W/I/N/UP/B/S/C4/DTZ/T20/RET/SIM/PTH/PL/RUF) | ✅ 0 errors | src/ + tests/ |
| mypy strict | ✅ 0 errors | 36 source files, 100% typed |
| bandit Medium+High | ✅ 0 issues | 8 Low (skips justifiés) |
| pip-audit | ✅ 0 CVE | deps minimum + dev |
| detect-secrets | ✅ clean | aucun secret commit |
| pytest | ✅ 380 passed, 9 xfail (R6 résiduel) | coverage ~57% |
| AST sanity | ✅ all 36 files parse | py3.11+ |

Voir [`POLYLENS_round10_PREMORTEM.md`](POLYLENS_round10_PREMORTEM.md) pour les 10 risques résiduels identifiés et la dette technique exposée (R6 = 18 tests xfail volontaires).

## Audit cross-LLM 10 rounds — historique

| Round | Verdict | Bugs | Patches |
|---|---|---|---|
| 5-9 | NO_GO → 4×GO + 2×CONDITIONAL_GO | 26 → 0 nouveaux | 50 patches A-Z |
| 10 (POLYLENS multi-axes 7) | GO conditionnel | 3 P0 + 7 P1 nouveaux trouvés (asyncio import manquant, 0 tests, mypy strict 52 erreurs, etc.) | 100% appliqués |
| 10 audit ortho GLM 4.6 + MiniMax M2 | CONDITIONAL_GO | 5 P0/P1 résiduels documentés | tous appliqués Round 10.1 |
| **10.1 audit cross-LLM (Grok+Qwen+Gemini+DeepSeek+ChatGPT+Kimi)** | GO conditionnel | 4 P0 + 5 P1 convergents | **9/9 patchés** ; 20 tests régression ; cf. `POLYLENS_round10_PREMORTEM.md` |
| **10.2 audit cross-LLM round 2 (Gemini+Grok+Qwen+Kimi)** | GO conditionnel | 4 P0 + 6 P1 nouveaux ; 8/9 patches 10.1 SOLID | **10/10 patchés** ; 17 tests régression ; 2 findings hallucinés rejetés |
| **10.2.1 (ChatGPT + Kimi convergent)** | GO conditionnel | adapter `_load_agents_md` bypass R1/R2 (P0 conv 2/4) | **patché** sur 7 adapters ; 14 tests régression ; honeypot adversarial 4/4 ✓ |
| **10.3 (Gemini+Grok+Qwen+DeepSeek+ChatGPT+Kimi)** | NO_GO → GO conditionnel | 4 P0 sécu Phase 4 (5/5 conv) + 8 P0/P1 archi/sécu | **16 patches** ; 17 tests régression ; 4 honeypots adversariaux ✓ ; 4 hallucinations rejetées |
| **10.4 + 10.5 (idem 5 voix focus Phase 4/7/5)** | NO_GO Phase 7 + NO_GO Phase 5 | 4 P0 Phase 7 (index dirty, prefix src/, tag collision, ADR rc) + 1 P0 absolu Phase 5 (fixer mutation 3/5 conv) | **15 patches** Phase 7/4 + **1 patch P0 absolu** Phase 5 ; 16 tests régression |

---

## Méta : équipe de conception (round 4)

POLYBUILD lui-même a été conçu par consultation multi-LLM en 4 rounds. Le round 4 a réuni 6 modèles (diversité 5D : provider, architecture, alignment, corpus, role bias) :

| Modèle | Rôle | Provider |
|---|---|---|
| Claude Opus 4.7 | Orchestrateur, spec writer | Anthropic (chat gratuit) |
| GPT-5.5 | Challenger principal | OpenAI |
| Gemini 3.1 Pro | Vue système | Google |
| Kimi K2.6 | MoE alternative | Moonshot |
| DeepSeek V4-Pro | Algo / spec attack | DeepSeek (OR) |
| Grok 4.20 | Adhérence spec, concision | xAI (OR) |

Méthodologie : convergence ≥4/6 → décision actée. Dissensus → ADR.

---

## Round 4 — convergences actées

### Faille 1 — Privacy Gate (Phase -1)

3 couches séquentielles (6/6 d'accord) :
- **L1** Presidio + regex FR (NIR, email, phone, address, birth_date) → BLOCK hard.
- **L2** eds-pseudo (AP-HP, F1=0.97) lazy-load + fallback dictionnaire métier statique.
- **L3** `sensitivity_attestation` énumération dans `spec.yaml` (proposition ChatGPT retenue).

Logique : ≥2 quasi-id + attestation forte → ESCALATE_PARANOIA (force EU/local). Sinon BLOCK.

### Faille 2 — Domain gates Phase 6

Strictement **bloquants** Phase 7 (5/6, DeepSeek nuance pour SQLite). Mapping profil → gates :

| Profil | Gates obligatoires |
|---|---|
| `mcp_schema_change` | mcp + sqlite + fts5 |
| `rag_ingestion_eval` | sqlite + fts5 + qdrant + rag |
| `parsing_pdf_medical` | rag |
| `oai_pmh_scraping` | sqlite |

Implémentation :
- **MCP** : subprocess JSON-RPC stdio, `initialize` + `tools/list` + Pydantic schema validation. `start_new_session=True` + `os.killpg` cleanup (ChatGPT).
- **SQLite** : PRAGMA `integrity_check` + `journal_mode=wal` + `foreign_key_check` + schema diff vs snapshot.
- **Qdrant** : `get_collection` + dim match + sample search.
- **FTS5** : golden queries JSON avec `min_hits` / `max_hits`.
- **RAG** : chunk hash stability + golden retrieval top-K.

### Faille 3 — Concurrency limiter

Sémaphores asyncio par provider (6/6). Limites médianes round 4 :

```yaml
claude: 2
codex: 2
gemini: 4
kimi: 1
openrouter: 3
mistral: 2
ollama: 1
```

Boost profil `helia_algo` / `module_inedit_critique` : codex=2, gemini=2, openrouter=4.

Back-pressure différentielle :
- **P0** → wait 180s, **no fallback** (médical safety, ne change pas la famille).
- **P1** → wait 30s puis fallback OR si fourni.
- **P2** → wait 5s puis fallback ou drop.
- **P3** → drop immédiat sur contention.

Détection throttle : regex `rate.?limit|429|quota|throttl|retry-after`.

### Faille 4 — Déploiement (Option B)

Worktree Git séparé (6/6) + Docker staging avec ports décalés (+10000) + volumes prod RO (`:ro`) + caps `--cpus=1 --memory=1g`. Tag pre-run `polybuild/run-{id}-pre` AVANT modif. Phase 8 production smoke 5 min, échantillonnage golden queries toutes les 30s. Seuils : **0% MCP errors + 5% latence p95** (compromis DeepSeek strict vs autres). Sur échec → `git reset --hard <tag-pre>` automatique.

**Phase 9 cleanup** (bonus Gemini, accepté implicitement par tous) en bloc `finally:` strict : kill containers, remove worktree, `uv cache clean`.

### Faille 5 — Skill `/polybuild` + secrets

`tmux` par défaut (6/6), fallback chain `tmux → screen → nohup` (Kimi + DeepSeek). Sous-commandes : `run`, `status`, `logs --follow`, `attach`, `abort`, `list`, `secrets-check`. Secrets dans `~/.polybuild/secrets.env` chmod 600 (vérifié au chargement), parsing dotenv-style sans shell. `.gitleaks.toml` avec allowlist stricte + custom rules (openrouter, anthropic, openai, google AIza, mistral, huggingface). Pre-commit hook gitleaks v8.28.0 + ruff v0.7.4.

---

## Architecture — flux end-to-end

```
brief
  │
  ▼
Phase -1  Privacy Gate  ─────  BLOCK / ESCALATE_PARANOIA / PASS
  │                                          │
  │                                  (force EU/local routing)
  ▼
Phase 0   Spec (Opus seul) + Phase 0b Spec Attack (DeepSeek + Grok)
  │
  ▼
Phase 1   Voice selection (15 profils, diversité 5D)
  │
  ▼
Phase 2   Generate (concurrency limiter, severity-aware)
  │
  ▼
Phase 3   Score → Phase 3b Grounding AST (≥2 imports faux = disqualif)
  │
  ▼
Phase 4   Audit (Critic ≠ Fixer ≠ Verifier, familles différentes)
  │
  ▼
Phase 5   Triade LLM (P0 per-finding, P1 batch, P2/P3 auto local)
  │
  ▼
Phase 6   General gates + Domain gates (BLOCKING per profile)
  │
  ▼
Phase 7   Commit + ADR (MADR-light)
  │
  ▼
Phase 8   Production smoke (5 min, golden queries, rollback auto)
  │
  └──── finally ────► Phase 9 Cleanup (worktree + docker + uv cache)
```

---

## Modes d'exécution : `--solo` vs consensus (M2B)

Le segment **Phase 1 → Phase 5** ci-dessus est sélectionnable via une
**Strategy**. Phase -1, 0, 6, 7, 8 et le cleanup tournent toujours,
indépendamment du mode choisi.

| Mode | Flag CLI | Phase 1 | Phase 2 | Phase 3 | Phase 3b | Phase 4 | Phase 5 |
|---|---|---|---|---|---|---|---|
| **Consensus** *(défaut)* | *(aucun)* | sélection multi-voix | génération **parallèle** N voix | scoring + classement | grounding AST | audit orthogonal | triade Critic/Fixer/Verifier |
| **Solo** | `--solo` | voix unique configurée (Claude par défaut) | **1 voix**, pas de concurrency limiter | *skipped* — winner par construction, score stub | *skipped* | audit orthogonal *(conservé pour la sécurité)* | *skipped* — pas de boucle fix |

### Quand utiliser `--solo`

- **Cosmetic refactors / docs** où l'arbitrage multi-voix est un coût pur.
- **Fast-feedback dev loops** : pas de boucle Phase 5, retour quasi instantané.
- **Cost-sensitive runs** : 1 appel LLM au lieu de 3-5.

### Quand garder le défaut consensus

- **Module inédit critique** : le grounding AST + le scoring inter-voix sont la première barrière à la dette.
- **Code médico-juridique opposable** : la triade Phase 5 est conçue pour ces cas.
- **Tout sujet où une P0 est plausible** : `--solo` abort sur P0 audit (pas de fix loop), consensus la corrige automatiquement.

### Comportement P0 en `--solo`

Si Phase 4 surface une finding P0, le run **abort** avec la raison `solo_phase_4_p0_no_triade` et un hint pour relancer en mode consensus. La voix unique a produit du code que personne n'a corrigé — re-run sans `--solo` pour engager le triade Phase 5.

### API Python

```python
from polybuild.orchestrator import run_polybuild, SoloPipeline, ConsensusPipeline

# Défaut équivalent : strategy=ConsensusPipeline()
await run_polybuild(brief="…", profile_id="…")

# Solo avec Claude Opus 4.7 (défaut) :
await run_polybuild(brief="…", profile_id="…", strategy=SoloPipeline())

# Solo avec une autre voix (e.g. GPT-5.5) :
await run_polybuild(
    brief="…",
    profile_id="…",
    strategy=SoloPipeline(voice_id="gpt-5.5", family="openai"),
)
```

---

## Stack technique imposée

- Python 3.11+, asyncio, uv, ruff, mypy `--strict`, pytest, bandit, gitleaks
- SQLite + sqlite-vec + Model2Vec (potion-base-8M, 30MB, CPU-viable)
- Qdrant pour RAG (Docker NAS)
- Pydantic strict pour modèles
- **Interdits** : LangChain, LlamaIndex

---

## CLI gratuites mobilisées

| CLI | Forfait | Modèles |
|---|---|---|
| Claude Code | Max 20x | Opus 4.7, Sonnet 4.6, Haiku 4.5 |
| Codex CLI | ChatGPT Pro | GPT-5.5, GPT-5.5-Pro, GPT-5.3-Codex |
| Gemini CLI | Pro | Gemini 3.1 Pro, Flash |
| Kimi CLI | Allegretto | K2.6 |

OpenRouter complémentaire : **DeepSeek V4-Pro, Grok 4.20, Qwen** (irreplaçables, ~15-20€/mois). API Mistral EU directe pour profils `medical_high`. Ollama NAS (Qwen 2.5 Coder 14B INT4) pour `medical_high` paranoïa.

**Claude Opus jamais via API payante** : déjà l'orchestrateur via Claude Max.

---

## Repo final (36 .py + 6 YAML + 2 TOML + 1 .sh + 1 SKILL.md)

```
polybuild_v3/
├── POLYBUILD_v3_spec.md           # spec 27 sections + méta équipe round 4
├── README.md                       # ← ce fichier
├── pyproject.toml                  # uv/ruff/mypy strict/pytest/bandit
├── .gitignore                      # secrets, worktrees, caches
├── .gitleaks.toml                  # allowlist + custom rules round 4
├── .pre-commit-config.yaml         # gitleaks + ruff + standards
├── .env.example                    # template secrets.env
├── AGENTS.md                       # mémoire racine du repo
├── config/
│   ├── models.yaml                 # 17 modèles déclarés
│   ├── routing.yaml                # 15 profils + auditor pools
│   ├── model_dimensions.yaml       # matrice 5D
│   ├── timeouts.yaml               # politique timeouts par phase
│   └── concurrency_limits.yaml     # round 4 — limites par provider
├── prompts/
│   ├── opus_spec.md
│   ├── spec_attack.md
│   ├── builder_unified.md
│   ├── critic.md                   # phase 5
│   ├── fixer.md                    # phase 5
│   ├── verifier_strict.md          # phase 5 (JSON-only)
│   └── adr.md                      # phase 7
├── scripts/
│   └── deploy_staging.sh           # round 4 — worktree + Docker RO + smoke + rollback
├── skills/polybuild/
│   └── SKILL.md                    # round 4 — tmux/screen/nohup chain
└── src/polybuild/
    ├── __init__.py + _version.py (3.0.0-dev)
    ├── orchestrator.py             # intègre Phase -1, Phase 8, Phase 9
    ├── cli.py                      # Typer (run, status, test-cli, stats, init, resume)
    ├── models.py                   # Pydantic centraux
    ├── adapters/                   # 7 adapters + factory + protocol
    ├── phases/
    │   ├── phase_minus_one_privacy.py    # Faille 1
    │   ├── phase_0_spec.py
    │   ├── phase_1_select.py
    │   ├── phase_2_generate.py
    │   ├── phase_3_score.py
    │   ├── phase_3b_grounding.py
    │   ├── phase_4_audit.py
    │   ├── phase_5_triade.py             # LLM round-trips
    │   ├── phase_6_validate.py           # Faille 2
    │   ├── phase_7_commit.py
    │   └── phase_8_prod_smoke.py         # Faille 4 + Phase 9 cleanup
    ├── domain_gates/                     # Faille 2
    │   ├── validate_mcp.py
    │   ├── validate_sqlite.py
    │   ├── validate_qdrant.py
    │   ├── validate_fts5.py
    │   └── validate_rag.py
    ├── concurrency/                      # Faille 3
    │   └── limiter.py
    └── security/                         # Faille 5
        └── secrets_loader.py
```

---

## Quickstart (à compléter — sprints A/E/F)

```bash
# 1. Installation
uv sync
chmod 600 ~/.polybuild/secrets.env  # après l'avoir créé depuis .env.example

# 2. Lancer un run
/polybuild run --spec my_brief.yaml --profile module_standard_known

# 3. Suivre
/polybuild status
/polybuild logs --follow

# 4. Inspection
/polybuild attach 20260503-141500
```

---

## Risques résiduels round 4 (à valider empiriquement)

1. Limites concurrency = hypothèses conservatrices, à mesurer sur forfaits réels.
2. eds-pseudo entraîné sur AP-HP, peut manquer du jargon SST très spécifique.
3. Phase 8 smoke peut laisser passer une dégradation lente non triviale.
4. tmux absent sur macOS sans Homebrew → fallback `screen` puis `nohup` en place.
5. Quota hebdomadaire Claude Max opaque — instrumentation côté run requise.

---

## Next steps

- **Phase A fondations** (~8h) : tests smoke_cli minimal, AGENTS.md du polybuild-core.
- **Phase E mémoire & apprentissage** (~6h) : vector_store sqlite-vec, embedder service.
- **Phase F bootstrap & UX** (~4h) : `polybuild init` interactif, gold prompts regression.
- **Tests pack** : smoke_cli pour les 7 adapters, integration end-to-end.
- **Domain gates** : `mutation_testing` (module_inedit_critique), `property_tests_hypothesis` + `numerical_invariants` (helia_algo).
- **Consultation CIL/DPO** sur Phase -1 Privacy Gate (recommandé — LLMs pas compétents juridiquement).
- **Premier run end-to-end** sur brief réel.
