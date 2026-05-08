# POLYBUILD v3 — Handoff document (humain ou IA)

> Document destiné à un humain qui découvre POLYBUILD pour la première fois,
> ou à une IA qui prend la suite de cette session sans contexte préalable.
> Style "expert pédagogue" : pas de jargon non expliqué, exemples concrets.

État au commit `d9aeacb` sur `main` (2026-05-03, après 11 rounds d'audit).

---

## 1. C'est quoi POLYBUILD, en une phrase

POLYBUILD est un **chef d'orchestre** qui pilote plusieurs IA en parallèle pour qu'elles écrivent du code à ta place, puis qui audite ce qu'elles ont produit, le corrige et te le commet — proprement.

Si tu connais Claude Code, Cursor ou Codex CLI : POLYBUILD lance **3 modèles différents en même temps** sur la même tâche, compare leurs sorties, désigne un gagnant, fait auditer ce gagnant par un 4e modèle indépendant, fait corriger les défauts par un trio "critic-fixer-verifier", et seulement ensuite produit un commit Git avec un ADR (Architecture Decision Record) auto-généré.

L'idée centrale : **un seul modèle peut se tromper en confiance ; trois modèles différents qui convergent sur la même réponse, c'est plus fiable**. Et un audit par un modèle de famille différente attrape les angles morts du gagnant.

---

## 2. Pourquoi ça existe

Le créateur (Radu, médecin du travail + dev) avait deux problèmes :

1. **Forfaits IA payés mais sous-utilisés** : il a Claude Pro, ChatGPT Pro, Gemini One Pro, Kimi Allegretto. Faire tourner les CLI gratuites en parallèle = même prix qu'un seul, mais 3-4× plus de diversité.
2. **Code médico-juridique** : les bugs ne sont pas une option. Il faut un workflow qui résiste à l'hallucination, au prompt injection, aux fuites de données patient.

POLYBUILD répond aux deux : **multi-LLM gratuit côté forfait + audit + triade + ADR + privacy gate + smoke prod avec rollback automatique**.

---

## 3. Le pipeline en 13 phases

Quand tu fais `polybuild run --brief brief.md --profile module_standard_known --project-root .`, voici ce qui se passe :

| Phase | Nom | Rôle | Modèle |
|-------|-----|------|--------|
| **-1** | privacy gate | Détecte les PII (noms, emails, données médicales) dans le brief — bloque si données réelles avec attestation manquante | Local : Presidio + EDS-Pseudo |
| **0** | spec generation | Lit ton brief, produit une spec structurée (tâche, critères d'acceptance, contraintes Pydantic) | Claude Opus 4.7 (architecte) |
| **0b** | spec attack | Un challenger orthogonal cherche les ambiguïtés/trous dans la spec | DeepSeek (raisonnement transparent) |
| **0c** | spec revise | Si Spec Attack a trouvé des trous critiques, Opus révise la spec | Claude Opus 4.7 |
| **1** | voice selection | Choisit 3 voix pour Phase 2 selon la "diversité matrix" (provider, architecture, alignement, corpus) | Déterministe (table routing.yaml) |
| **2** | parallel generation | 3 modèles écrivent du code en parallèle, chacun dans son worktree isolé | gpt-5.5 + kimi-k2.6 + glm-5.1 (par défaut) |
| **3** | scoring | Lance pytest/mypy/ruff/bandit/gitleaks/coverage sur chaque worktree, attribue un score | Déterministe (gates + formule) |
| **3b** | grounding check | Vérifie que les imports correspondent à de vrais modules (pas d'hallucination de package) | AST parsing |
| **4** | audit POLYLENS | 1 modèle d'une **famille différente du gagnant** fait un audit indépendant sur 7 axes (sécurité, qualité, tests, perf, archi, doc, adversarial) | Choisi par routing selon family du gagnant |
| **5** | triade critic-fixer-verifier | Pour chaque finding P0 : un critic explique, un fixer édite, un verifier valide. Iterations jusqu'à preuve | 3 modèles distincts (anti-collusion) |
| **6** | validation gates | Re-lance pytest+mypy+ruff post-fixes + domain gates (SQLite/Qdrant/MCP/FTS5/RAG selon profil) | Déterministe |
| **7** | commit + ADR | git tag pre-commit, copie les artefacts du gagnant dans le repo, git add + commit + tag post-commit + ADR auto si triggers | Claude Opus pour l'ADR |
| **8** | prod smoke | (Optionnel) Lance un smoke test 5min sur ton endpoint réel ; si SLO breach (latence, erreur) → `git reset --hard <tag-pre>` automatique | Déterministe |
| **9** | cleanup | Supprime les workdirs temporaires, vide cache uv si demandé | Déterministe |

Le tout en **5-15 minutes** selon profil et taille du brief, pour un coût de **0.30 à 15 USD** OpenRouter selon mode.

---

## 4. Ce qu'il y a dedans (architecture)

```
polybuild_v3/
├── src/polybuild/
│   ├── cli.py                    # Entrée CLI Typer (polybuild run/status/logs/test-cli)
│   ├── orchestrator/__init__.py  # Pipeline 13 phases, signal handling, checkpoints
│   ├── models.py                 # Pydantic v2 — Spec, BuilderResult, AuditReport, etc.
│   ├── adapters/                 # 7 wrappers vers les modèles
│   │   ├── claude_code.py        # CLI claude (Anthropic Pro forfait)
│   │   ├── codex_cli.py          # CLI codex (ChatGPT Pro)
│   │   ├── gemini_cli.py         # CLI gemini (Google One Pro)
│   │   ├── kimi_cli.py           # CLI kimi (Moonshot Allegretto)
│   │   ├── openrouter.py         # HTTP OpenRouter (DeepSeek, Grok, GLM, Qwen, etc.)
│   │   ├── mistral_eu.py         # HTTP Mistral EU direct (souveraineté)
│   │   ├── ollama_local.py       # Ollama sur NAS (Qwen 2.5 coder, médical HIGH paranoia)
│   │   ├── _json_extract.py      # Helper 3-stratégies pour parser JSON depuis stdout text
│   │   └── builder_protocol.py   # Contrat abstrait que tous les adapters implémentent
│   ├── phases/
│   │   ├── phase_minus_one_privacy.py  # Gate PII (Presidio + EDS-Pseudo + heuristique)
│   │   ├── phase_0_spec.py             # Spec gen + attack + revise
│   │   ├── phase_1_select.py           # Voice selection + filter_candidates (RGPD)
│   │   ├── phase_2_generate.py         # Parallel generation
│   │   ├── phase_3_score.py            # Gates + scoring formula
│   │   ├── phase_3b_grounding.py       # AST grounding check
│   │   ├── phase_4_audit.py            # POLYLENS independent audit
│   │   ├── phase_5_triade.py           # Critic-Fixer-Verifier + prompt sanitization
│   │   ├── phase_6_validate.py         # Re-run gates + domain gates
│   │   ├── phase_7_commit.py           # Git tag + commit + ADR
│   │   └── phase_8_prod_smoke.py       # Smoke + rollback + Phase 9 cleanup
│   ├── domain_gates/
│   │   ├── validate_mcp.py             # Smoke JSON-RPC d'un MCP server
│   │   ├── validate_sqlite.py          # PRAGMA integrity_check + foreign_key_check
│   │   ├── validate_qdrant.py          # Collection check + sample search + SSRF guard
│   │   ├── validate_fts5.py            # FTS5 table + sample MATCH
│   │   └── validate_rag.py             # Retrieval@k + chunk hash stability
│   ├── concurrency/limiter.py          # Semaphores P0/P1/P2/P3 + fallback + drop
│   └── security/
│       ├── prompt_sanitizer.py         # NFKC normalize, strip HTML/MD comments, fenced blocks, zero-width
│       ├── safe_write.py               # write_files_to_worktree (path traversal défense)
│       └── secrets_loader.py           # Lit ~/.polybuild/secrets.env chmod 600
├── config/
│   ├── routing.yaml                    # 16 profils + auditor_pools + global_rules
│   ├── models.yaml                     # ~25 modèles avec endpoints + rôles
│   ├── model_dimensions.yaml           # Matrice de diversité (provider × architecture × corpus × alignement × role_bias)
│   ├── concurrency_limits.yaml         # Rate limits par provider (claude 5/min, gpt 8/min, etc.)
│   └── timeouts.yaml                   # Timeouts par phase
├── prompts/
│   ├── critic.md                       # Template Phase 5 critic
│   ├── fixer.md                        # Template Phase 5 fixer
│   ├── verifier_strict.md              # Template Phase 5 verifier
│   ├── builder_unified.md              # Template Phase 2 builder
│   ├── opus_spec.md                    # Template Phase 0 Opus
│   ├── spec_attack.md                  # Template Phase 0b challenger
│   └── adr.md                          # Template Phase 7 ADR auto
├── tests/
│   ├── unit/                           # ~80 tests unitaires
│   └── regression/                     # ~150 tests régression (un fichier par round d'audit)
├── docs/
│   ├── RUNBOOK_PRODUCTION.md           # 3 phases lancement progressif
│   ├── HANDOFF.md                      # ← CE FICHIER
│   └── polylens_round_10_8_post_sprint/
│       └── *_audit.json                # 5 audits archivés (codex/gemini/grok/qwen/kimi)
└── pyproject.toml                      # Hatchling backend, packaging, ruff/mypy/bandit config
```

---

## 5. Concepts à comprendre

### 5.1. "Adapter" (couche modèle)

Chaque modèle (claude, gpt, gemini, kimi, deepseek, etc.) a sa propre façon d'être appelé : CLI, HTTP, paramètres différents. POLYBUILD masque ces différences via la **classe `BuilderProtocol`** (un contrat). Tu donnes un `voice_id` (ex: `"gpt-5.5"` ou `"qwen/qwen3.6-max-preview"`), tu reçois un `BuilderResult` standardisé.

Quand le CLI vendor change sa syntaxe (ex: claude `--prompt` → `-p` en v2), seul l'adapter change. Le reste du code n'en sait rien.

### 5.2. "Profile" (recette de tâche)

Dans `config/routing.yaml`, chaque tâche-type a son profil :
- `module_standard_known` : refactor classique
- `module_inedit_critique` : code propriétaire critique
- `helia_algo` : algorithmique mathématique
- `medical_paranoia_high` : données médicales avec HDS/RGPD strict
- `cross_cultural_diversity` : maximise diversité culturelle (1 voix US + 2 voix CN)
- ... 16 profils au total

Chaque profil dit : quelles voix Phase 2, quel mediator, quel pool de diversité, quels axes d'audit, quels domain gates.

### 5.3. "Diversity matrix"

Dans `config/model_dimensions.yaml`, chaque modèle est tagué sur 5 dimensions :
- **provider** (anthropic/openai/google/zhipu/...)
- **architecture** (dense/moe)
- **alignment** (safety_first/agentic/balanced/...)
- **corpus_proxy** (anthropic_corpus/openai_corpus/...)
- **role_bias** (architect/builder/skeptic/...)

Phase 1 calcule un **score de diversité** entre voix candidates. Plus le score est élevé, plus les voix voient le problème sous des angles différents. Anti-pattern : 3 modèles US dense web-trained → score 3.33 (faux multi-voix). Bon : 1 Anthropic dense + 1 DeepSeek MoE + 1 Moonshot MoE chinois → 4.67.

### 5.4. "Triade Phase 5"

Quand l'audit Phase 4 trouve un finding P0 (sécurité/crash), POLYBUILD ne demande pas au gagnant de se corriger lui-même (anti-pattern : self-fix bias). À la place :
- **Critic** (modèle 1) : analyse profondément le finding, propose une approche
- **Fixer** (modèle 2 ≠ critic) : édite le code in-place dans le worktree
- **Verifier** (modèle 3 ≠ fixer ≠ critic) : juge si le fix résout vraiment le bug avec une preuve reproductible

Si le verifier rejette → le fixer recommence. Max 5 itérations sinon escalade humaine. Les 3 modèles doivent être de **familles différentes** (anti-collusion).

### 5.5. "Privacy gate" Phase -1

Avant tout, POLYBUILD scanne ton brief + AGENTS.md + project_ctx pour des **PII** (Personally Identifiable Information) :
- L1 Presidio : noms, emails, téléphones, dates
- L2 EDS-Pseudo : entités médicales (hôpital, ville, ZIP, date, maladie rare, procédure médicale, patient)
- L3 heuristique : longueur du brief, attestation utilisateur, etc.

Selon le résultat → BLOCK / ESCALATE_PARANOIA / PASS. Si BLOCK, le run s'arrête avant tout appel LLM.

### 5.6. "Domain gates"

Au-delà des gates génériques (pytest/mypy/ruff), certains profils activent des **gates spécifiques au domaine** :
- `mcp_jsonrpc_smoke` : invoque un MCP server, vérifie le handshake JSON-RPC
- `qdrant_consistency` : vérifie que la collection vectorielle a la bonne dimension
- `chunk_hash_stability` : pour les pipelines RAG, vérifie que le chunking est déterministe
- `retrieval_at_k_fixtures` : vérifie qu'un set de fixtures retrouve les top-k attendus

---

## 6. Ce qui a été audité et fixé (état actuel)

POLYBUILD a subi 11 rounds d'audit progressifs. Le commit `d9aeacb` (état actuel) inclut ces durcissements :

### Sécurité
- ✅ Path traversal défense via `safe_write.write_files_to_worktree` (resolve + is_relative_to + isinstance str + skip non-mapping)
- ✅ Symlink filtering (Phase 7 + Phase 5 _tree_hash) avec `is_symlink()` AVANT `is_file()`
- ✅ Subprocess hardening : `start_new_session=True`, `stdin=DEVNULL`, env isolation, `--no-verify` git
- ✅ Prompt sanitization avec NFKC + strip HTML/MD comments + fenced blocks + zero-width chars
- ✅ Re-injection sanitization Phase 5 (evidence_path, fixer_output, verifier_reason)
- ✅ SSRF guard Phase 8 via `ipaddress.ip_address` + flags normalisés (anti decimal/hex/octal bypass)
- ✅ AGENTS.md sanitization au moment de l'injection (defense in depth)
- ✅ run_id sanitization (anti `../` traversal + anti XML breakout dans prompts)
- ✅ secrets.token_hex(8) pour run_id (collision résistante)
- ✅ Multi-block JSON rejection dans Verifier (anti prompt injection multi-output)
- ✅ Anti-tampering prompt templates (placeholder check obligatoire)

### Robustesse
- ✅ JSON extraction string-aware brace counter (anti `}` dans string)
- ✅ Atomic checkpoint writes avec EXDEV cross-device fallback
- ✅ OR API response defense (try/except KeyError|IndexError|TypeError + None guard)
- ✅ JSON not-dict guard avant `.get()`
- ✅ Cross-device shutil.copy2 + chmod fallback
- ✅ Tree-hash mutation detection Phase 5 (refuse d'avancer si fixer n'a pas mute le worktree)
- ✅ PEP 508 dep parsing via `packaging.requirements.Requirement`
- ✅ OR-bound provider detection allow-list (12 préfixes, anti drift)
- ✅ Phase 3 PYTHONPATH `.:src:<existing>` (résoud `from src.foo` ET `from foo`)
- ✅ Phase 5 fixer_template `{workdir}` placeholder
- ✅ `final_status='validated'` pour `--no-commit` (anti corruption postmortem)

### Bug fixes critiques (Round 10.8 POLYLENS-driven)
- ✅ **Phase 7 'lost deletions' patch SUPPRIMÉ** — il causait `git rm` de tout le repo à chaque commit incrémental (data-loss invisible en `--no-commit`, catastrophe en `--full`)
- ✅ Voix chinoises proper exclusion under `excludes_us_cn_models=True` (le precedent fix avait raté un OR override)

### CLI v2 vendor drift
- ✅ claude `-p PROMPT --output-format text` (v1 `--prompt` retiré)
- ✅ codex `--skip-git-repo-check` + drop `--output-format`
- ✅ kimi `--print --afk -y --output-format text` (json invalide)
- ✅ gemini `--skip-trust --yolo` (workspace trust requis)
- ✅ Paths absolus partout (`worktree.resolve()`) — anti double-path bug

### Performance
- ✅ Single-pass file reads dans `_estimate_metrics`
- ✅ Presidio AnalyzerEngine cache module-level (anti recreation per call)
- ✅ Local gates env allow-list (PATH, PYTHONPATH, SSL_CERT_*, VIRTUAL_ENV, UV_*)

### Tests
- ✅ 230+ tests régression (un fichier par round d'audit)
- ✅ Tests `or True` neutered remplacés par assertions réelles
- ✅ Honeypots H1-H5 dans tous les prompts d'audit (anti hallucination LLM)

---

## 7. Comment l'utiliser concrètement

### Cas 1 : tu veux tester sans risque (smoke)

```bash
# 1. Crée un sandbox isolé
mkdir -p /tmp/polybuild_smoke && cd /tmp/polybuild_smoke
git init -q && touch AGENTS.md
echo "# Sandbox project" > AGENTS.md
echo "Crée un module src/foo.py avec une fonction hello() retournant 'hi'.
Ajoute un test pytest dans tests/test_foo.py." > brief.md

# 2. Charge les secrets
set -a; . ~/.polybuild/secrets.env; set +a

# 3. Run en mode dry-run (--no-commit + --no-smoke)
polybuild run \
  --brief brief.md \
  --profile module_standard_known \
  --project-root . \
  --no-commit --no-smoke

# 4. Examine le résultat
ls .polybuild/runs/*/worktrees/   # tu verras 3 dossiers, un par voix
cat .polybuild/runs/*/polybuild_run.json  # winner, durée, scores
```

### Cas 2 : tu veux corriger un bug dans un repo perso

```bash
cd ~/Developer/sandbox/<repo>
echo "Fix the off-by-one error in src/parsers/foo.py:line 142" > brief.md
set -a; . ~/.polybuild/secrets.env; set +a

# Run --real : pipeline complet sauf le commit auto
polybuild run \
  --brief brief.md \
  --profile module_inedit_critique \
  --project-root . \
  --no-commit --no-smoke

# Examine le winner manuellement
WINNER=$(jq -r '.winner_voice_id' .polybuild/runs/*/polybuild_run.json)
diff -r src .polybuild/runs/*/worktrees/$WINNER/src
# Si le diff te plaît : commit manuel
git add src && git commit -m "fix: off-by-one in parsers (via POLYBUILD)"
```

### Cas 3 : full pipeline avec commit + smoke

⚠️ Pas encore validé end-to-end ; le P0 GEMINI-01 est fixé mais personne n'a fait un `--full` complet sur ce commit. Recommandation : sandbox isolé d'abord.

```bash
polybuild run \
  --brief brief.md \
  --profile module_inedit_critique \
  --project-root .
# (PAS --no-commit, PAS --no-smoke = pipeline complet)
```

---

## 8. Comment ça se branche dans ton workflow

POLYBUILD est complémentaire à Claude Code direct, pas un remplacement. Quand quoi :

| Tâche | Outil |
|-------|-------|
| Question conversationnelle | Claude Code direct |
| Bug fix < 30 min, claire | Claude Code direct (gratuit côté user) |
| Refactor mécanique avec tests existants | Claude Code direct |
| Nouvelle feature ambiguë, plusieurs angles possibles | POLYBUILD (3 voix montrent la diversité) |
| Code médico-juridique avec PII potentielle | POLYBUILD obligatoire (privacy gate Phase -1) |
| Module critique avec besoin d'audit indépendant | POLYBUILD (Phase 4 + triade Phase 5) |
| Refactor large nécessitant ADR + tag pre-commit | POLYBUILD (Phase 7 auto-ADR) |

POLYBUILD est aussi **invocable comme skill** : tu tapes `/polybuild` dans Claude Code, le skill se charge en contexte avec ses heuristiques.

---

## 9. Coûts attendus

Par run, OpenRouter side (les CLI restent dans tes forfaits Pro) :

- Phase 0 spec (claude opus) : ~$0.10-0.30
- Phase 0b spec attack (deepseek OR) : ~$0.05-0.15
- Phase 4 audit (1 voix OR) : ~$0.10-0.50
- Phase 5 triade (3 calls × N itérations) : ~$0.50-3 selon nombre de findings P0
- Phase 7 ADR (claude opus) : ~$0.10
- Phase 8 smoke (déterministe) : $0
- **Total typique** : $0.50 (smoke trivial) à $5-15 (refactor avec triade itérative).

À comparer aux $200/jour d'un dev senior si POLYBUILD t'évite 1h de réflexion = ROI immédiat dès qu'il marche.

---

## 10. Ce qui ne marche pas encore

Backlog connu, à traiter en sprints suivants :

- **D-01** : Phase 3 gates `pytest`/`mypy`/`ruff`/`bandit`/`gitleaks` lancés mais `await` séquentiel pas `gather()` parallèle (gain ~60% wall-clock attendu)
- **GEMINI-04** : suspicious directives détectées mais juste loguées, pas strippées du prompt (anti-injection)
- **GEMINI-05** : sanitization loop fixed-depth 8 iterations bypassable (anti-comments imbriquées 9+ fois)
- **GEMINI-06** : `save_checkpoint` sync I/O dans event loop async (peut bloquer sur disque saturé)
- **Architectural** : factory `get_builder` if/elif chain → registry pattern, `VoiceConfig.context` typé, infra/business separation
- **Tests gaps** : concurrent stress sur limiter, mutation testing, MCP pipe deadlock, raw_prompt_no_write contract
- **Kimi yolo immutable mode** (Grok adversarial) : sandbox readonly du core polybuild quand un agent Kimi-CLI tourne (sinon il peut auto-éditer le moteur)

Tout cela est noté dans `~/.claude/projects/-Users-radu/memory/project_polybuild_v3.md` section Backlog.

---

## 11. Comment debugger quand ça casse

### `polybuild` ne tourne pas du tout

```bash
which polybuild                     # doit retourner ~/.local/bin/polybuild
polybuild --version                  # doit afficher 3.0.0-dev
```

Si KO : `cd ~/Developer/projects/polybuild_v3 && uv tool install --force .`

### Phase 0 spec generation hang

Cause connue : claude CLI v2 lit stdin par défaut. Si `polybuild` lancé depuis un pipe (ex: `tee`), claude attend stdin EOF.

Vérification : `pgrep -af claude` pendant le hang. Si claude est CPU 0% — c'est ça. Le fix `stdin=DEVNULL` est dans `d9aeacb`. Reinstall si pas à jour.

### Phase 2 voix échouent toutes

Probables : CLI vendor surface a encore changé (drift). Lance `polybuild test-cli` pour voir lesquelles répondent. Compare la cmd construite (dans le warning log) avec la doc CLI actuelle (`<cli> --help`).

### Phase 3 score = 0 même quand le code est valide

Vérifie que le worktree a bien `src/` et `tests/`. Si oui : le `from src.foo import` échoue parce que ni `src/__init__.py` n'existe ni le PYTHONPATH ne contient `.`. Le fix `PYTHONPATH=.:src` est dans `d9aeacb`.

### Phase 7 commit rate

Cause possible : worktree git pas initialisé, ou hooks pre-commit bloquants. POLYBUILD passe `--no-verify` aux git commit, donc ce n'est pas ça. Vérifie `git config user.email` et que le repo a au moins 1 commit initial.

---

## 12. Qui maintient quoi

| Composant | Source | Mainteneur |
|-----------|--------|-----------|
| Code POLYBUILD | `~/Developer/projects/polybuild_v3/` | Radu / Claude Code (sessions) |
| GitHub repo | `github.com/reddepot/polybuild_v3` | Radu (push manuel) |
| CLI installé | `~/.local/bin/polybuild` (uv tool) | Reinstall après chaque commit |
| Skills Claude Code | `~/.claude/skills/polybuild/SKILL.md` | Radu (sync repo skills) |
| Mémoire IA | `~/.claude/projects/-Users-radu/memory/project_polybuild_v3*.md` | Claude Code auto-memory |
| OPENROUTER_API_KEY | `~/.polybuild/secrets.env` chmod 600 | Radu |
| Forfaits IA | claude/codex/gemini/kimi CLIs | Radu (auth manuelle initiale) |

---

## 13. Pour aller plus loin

- **Méthodologie POLYLENS** (audit multi-voix qui a permis de durcir POLYBUILD) : `~/.claude/projects/-Users-radu/memory/feedback_polylens_method.md`
- **Runbook prod** : `docs/RUNBOOK_PRODUCTION.md` (3 phases progressives smoke/real/full)
- **Lessons CLI vendor drift** : `~/.claude/projects/-Users-radu/memory/lessons_polybuild_prod_launch_20260503.md`
- **Audits archivés** : `docs/polylens_round_10_8_post_sprint/*.json` (5 voix : codex, gemini, grok, qwen, kimi)

---

## 14. Conclusion

POLYBUILD v3 au commit `d9aeacb` est **opérationnel pour `--no-commit`**, **prudent pour `--full`** (le P0 data-loss est fixé mais pas validé end-to-end). 230+ tests régression verts, 11 rounds d'audit progressifs, 5 voix POLYLENS post-sprint convergentes.

Si tu prends la suite : commence par `polybuild test-cli` pour vérifier que les 4 CLI vendor répondent, puis lance un smoke trivial (cas 1 ci-dessus). Si OK : tu es bon. Si KO : section 11 (debug) couvre les 3 modes d'échec connus.

Bonne suite.
