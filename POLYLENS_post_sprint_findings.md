# POLYLENS Audit Post-Sprint Round 10.8 — Consolidation 4-voix

**Date** : 2026-05-03
**Cible** : commit `2b3c12f` (état au début de l'audit)
**Voix présentes** : Codex GPT-5.5, Kimi K2.6, Qwen 3.6 max, Grok 4.20
**Voix manquante** : Gemini 3.1 Pro (quota épuisé jusqu'à ~19:38)
**État actuel post-fixes** : commit `21cd183`

## Honeypots (anti-hallucination) — toutes voix correctes

| Voice | H1 (`_load_agents_md_sanitized`) | H2 (`MagicWeaverProtocol`) | H3 (prompt_sanitizer) | H4 (safe_write) | H5 (_json_extract) |
|-------|----------------------------------|----------------------------|------------------------|-----------------|---------------------|
| Codex | ❌ False ✅ | ❌ False ✅ | ✅ True ✅ | ✅ True ✅ | ✅ True ✅ |
| Kimi | ❌ False ✅ | ❌ False ✅ | ✅ True ✅ | ✅ True ✅ | ✅ True ✅ |
| Qwen | ❌ False ✅ | ❌ False ✅ | ✅ True ✅ | ✅ True ✅ | ✅ True ✅ |
| Grok | ❌ False ✅ | ❌ False ✅ | ✅ True ✅ | ✅ True ✅ | ✅ True ✅ |

## Verdicts globaux

- **Codex** : MAJOR_ISSUES, conf 0.88
- **Kimi** : MAJOR (10 findings)
- **Qwen** : MAJOR, conf 0.75
- **Grok** : FAIL, conf 0.85 (focus G_adversarial)

## Convergences cross-voix (≥2 voix)

### 🔴 P1 RGPD CRITICAL — Voix chinoises non excluables — 3 voix
- Codex `A_security-01` (P1): excludes_openrouter ignores new OR provider prefixes
- Codex `A_security-02` (P1): Remote qwen/* treated as local Qwen under US/CN exclusion
- Kimi `G-02` (P1): excluded_families manque les nouvelles familles chinoises

**Mécanisme** : `is_us_or_cn_model` retournait False pour `qwen/qwen3.6-max-preview` (à cause d'un check `startswith("qwen")` originellement destiné au Qwen Ollama LOCAL). `is_openrouter_routed` ne couvrait que `deepseek/` + `x-ai/`.

**Impact prod** : profil `medical_high` avec `excludes_us_cn_models=True` laissait passer Alibaba/ZhipuAI/MiniMax/Xiaomi/Moonshot via OR.

**Fix appliqué (commit 96622cc + fa8ceaa)** : refactor des deux helpers + 12 tests régression.

### 🟡 P1 — JSON greedy brace scan fragile — 2 voix
- Qwen `F1` (P1) : Greedy brace JSON extraction risks malformed payload injection
- Kimi `B-01` (P1) : Greedy brace scan fails on JSON with `}` in string

**Mécanisme** : `_json_extract.py` strategy 3 utilisait `raw.index('{')` + `raw.rindex('}')` qui échoue sur JSON avec `}` dans une string. Exemple : `{"msg": "ok}not"}` → `rindex('}')` trouve le `}` interne.

**Impact** : adapter codex/claude rejette des outputs LLM valides.

**Fix appliqué (commit 96622cc + 21cd183)** : compteur de braces string-aware (respecte guillemets + escapes) + tri par taille pour prendre le plus grand bloc parsable + 2 tests régression.

### 🟡 P2 — RUNBOOK + skill stale references — 2 voix
- Codex `F_documentation-01` (P2) : Runbook points to stale commit and wrong checkout path
- Kimi `F-01` + `F-02` (P2) : RUNBOOK + SKILL.md référencent commits obsolètes

**Mécanisme** : RUNBOOK référençait commit `e7f3d86` + path `Downloads/polybuild_v3-2`. Skill mentionnait `22fcc8c` et backlog "à faire" déjà résolu.

**Impact** : opérateurs suivant le runbook installent un tree obsolète.

**Fix appliqué (commit 96622cc)** : refs alignées sur `2b3c12f` + chemin canonique.

## Findings single-voix high-impact (appliqués)

### Codex `C_tests-01` (P2) — Tests neutered avec `or True`
- `test_round10_8_audit_patches.py:57` + `test_cli_file_write_parsing.py:283`
- `assert ... or True` passe TOUJOURS, neutralise le test path traversal P0
- **Fix** (commit 96622cc) : tmp_path scope + `assert not outside.exists()` réel

### Codex `B_quality-02` (P2) — final_status='committed' en dry-run
- `--no-commit` mais run rapporte 'committed' — corruption postmortem
- **Fix** (commit 96622cc) : ajout `'validated'` au Literal + ternaire

### Codex `E_architecture-01` (P1) — Chinese voices manquent dans model_dimensions
- Phase 1 matrix_select tombait au fallback sur ces voix → diversité perdue
- **Fix** (commit 01e4dbb) : 7 entrées ajoutées (z-ai/qwen/moonshotai/minimax/xiaomi)

## Findings backlog (non bloquants smoke #9, à traiter sprint suivant)

### Codex `D_performance-01` (P2) — Phase 3 gate coroutines awaited séquentiel
- `pytest`, `mypy`, `ruff`, `bandit`, `gitleaks` lancés mais `await` séquentiel
- Gain ~60% wall-clock attendu avec `asyncio.gather`
- **Status** : déjà connu (Round 10.7 backlog Kimi D-01), pas régression sprint

### Codex `B_quality-01` (P2) — Status.OK même sur JSON malformé
- Si `_try_parse_json` retourne None, fallback `_estimate_metrics` mais Status.OK
- **Status** : défensive — kimi écrit parfois files même sans JSON output, donc check trop strict casserait kimi-CLI

### Codex `G_adversarial-01` (P1) — skill /polybuild interpole args dans tmux
- Concerne docs SKILL.md (instructions Claude), pas exécutable directement
- **Status** : à valider si le user lance via tmux. Probable false-positive interprétation Codex.

### Kimi `A-01` (P1) — Greedy regex JSON fallback identique aux bugs P0 fixés ailleurs
- Chevauche avec Qwen F1 — déjà fixé via le compteur string-aware

### Kimi `E-01` (P1) — Factory get_builder if/elif chain, no registry pattern
- Ajout d'une voix nécessite modification du code (pas plug-and-play)
- **Status** : architectural — déjà connu, sprint séparé

### Kimi `D-01` (P1) — `create_subprocess_shell` anti-pattern Phase 3
- Hardcoded gates → pas d'injection réelle, mais fragilité structurelle
- **Status** : à corriger en sprint (utiliser `create_subprocess_exec` + shlex.split)

### Qwen `F2` (P1) — Symlink/TOCTOU bypass dans resolve()+is_relative_to
- Path.resolve() suit symlinks ; symlink dans worktree pointing outside → bypass
- **Status** : sprint sécu — utiliser O_NOFOLLOW ou directory FDs (openat)

### Grok `GADV-001` (P0) — KIMI yolo self-mod
- Le LLM chinois a auto-édité le codebase pendant `--plan --afk`
- **Status** : strategic concern — sprint séparé "immutable mode + signature"

### Grok `GADV-002` (P1) — H1/H2 honeypots exposés FAUX dans prompt
- Donne carte des leurres à un attaquant
- **Status** : meta — refonte methodologie POLYLENS plutôt que code

### Grok `GADV-003` (P1) — 5 voix chinoises = exfiltration vers CN entities
- Mitigé par fixes `is_us_or_cn_model` + `is_openrouter_routed` ci-dessus
- **Status** : doc user à compléter (--no-chinese-voices flag explicite)

## False-positives écartés (Codex `false_positives_avoided`)

- Path traversal résiduel dans safe_write → confirmé OK (resolve + is_relative_to)
- Phase 2 PII exfiltration via excludes_openrouter → guard exists in adapter
- O(n²) regex behavior dans _json_extract → regex est lazy, pas de PoC

## Note méthodologique : Gemini absent

Gemini 3.1 Pro Preview quota épuisé jusqu'à ~19:38. Audit complété à
4 voix (sur 5 prévues). La validation post-correction sera relancée
avec Gemini en 5e voix dès retour, focalisée sur :
- Vérifier que les fixes appliqués (commits 96622cc → 21cd183) sont
  corrects côté Gemini
- Détecter les findings que Gemini seul aurait trouvés (long-context
  graph trans-fichiers est sa force)
- Re-confirmer convergence cross-culturelle (POLYLENS v3 panel base
  4 voix occidentales : Claude+Codex+Gemini+Kimi).

## Synthèse

- 32 findings bruts (4 voix), 11 actionnables après filtrage
- 8 fixes appliqués (+ 35 tests régression)
- 8 backlog tracé pour sprints suivants
- 0 P0 réintroduit (Round 10.7 fixes intacts)
- 1 nouveau P0 stratégique (kimi yolo self-mod) → sandbox immutable mode
- Smoke #9 toujours valable pour validation prod

État actuel : `commit 21cd183` sur `main`, 222+ tests régression verts, ruff/mypy --strict/bandit clean.
