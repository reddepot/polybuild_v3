# POLYBUILD v3 — Production Runbook

État au commit `2b3c12f` après Round 10.8 prod-launch sprint (codex/claude file extraction + Phase 3 fix + voix chinoises + skill /polybuild + 6 bugs runtime fixés via smoke #4→#9).

## Décision : lancement progressif en 3 phases

### Préalable — Pré-flight (5 min)

Vérifier UNE SEULE FOIS avant la toute première run :

```bash
# 1. API key OpenRouter présente
grep -q "OPENROUTER_API_KEY=sk-" /Users/radu/Developer/projects/mcp_redapi/.env \
  && echo "OK OR" || echo "FAIL: configurer OPENROUTER_API_KEY"

# 2. CLIs disponibles + authentifiés
for cli in claude codex gemini kimi; do
  command -v $cli >/dev/null && echo "OK $cli" || echo "FAIL: $cli manquant"
done

# 3. Polybuild installable
cd /Users/radu/Developer/projects/polybuild_v3
uv pip install -e . 2>&1 | tail -3

# 4. Smoke import du package
uv run python -c "import polybuild; print(polybuild.__version__)"

# 5. Profils dispo
uv run python -c "import yaml; print(list(yaml.safe_load(open('config/routing.yaml'))['profiles'].keys()))"

# 6. Tests régression locaux
uv run pytest tests/regression/ -q --tb=no | tail -3
```

Si une seule étape échoue → **pas de prod**, fixer avant.

---

### Phase 1 — Smoke launch (objectif : pipeline tourne)

**Cible** : un sandbox project trivial, brief minimal, aucun commit, aucun smoke Phase 8.

```bash
# Créer un sandbox isolé
mkdir -p /tmp/polybuild_smoke && cd /tmp/polybuild_smoke
git init && touch AGENTS.md && echo "# Sandbox" > AGENTS.md

# Brief minimal
cat > brief.md <<EOF
Add a one-line module-level docstring to a new file
src/foo.py describing what foo() does. No tests required.
EOF

# Profil le plus simple, dry run
export OPENROUTER_API_KEY=$(grep ^OPENROUTER_API_KEY /Users/radu/Developer/projects/mcp_redapi/.env | cut -d= -f2)

cd /Users/radu/Developer/projects/polybuild_v3
uv run polybuild run \
  --brief /tmp/polybuild_smoke/brief.md \
  --profile helia_algo \
  --project-root /tmp/polybuild_smoke \
  --no-commit --no-smoke
```

**Critères de succès** :
- Le pipeline traverse Phase -1 → Phase 6 sans crash
- Au moins 1 voix produit du code valide
- `.polybuild/runs/<run_id>/` contient `polybuild_run.json`
- Coût observé < $1 (vérifier via OpenRouter dashboard)

**Si KO** : examiner `.polybuild/runs/<run_id>/` (logs phase par phase) et `git log --oneline -3` pour voir si c'est un bug Round 10.x non détecté.

---

### Phase 2 — Real task low-risk (objectif : sortie utilisable)

**Cible** : un repo réel à toi, tâche bornée et lisible (test ou docstring), pas encore de commit auto.

```bash
# Choisir un repo réel low-stakes (pas mcp_meddata ni mcp_redapi en prod)
# Ex : un sandbox connecteur ou un repo perso

cd ~/Developer/sandbox/<un_petit_repo>
cat > brief.md <<EOF
Add a unit test in tests/test_X.py for the function X
defined in src/X.py. Use pytest, target ~95% coverage of X.
EOF

# Run sans commit (review manuel du diff après)
uv run polybuild run \
  --brief brief.md \
  --profile module_inedit_critique \
  --project-root . \
  --no-commit --no-smoke

# Examiner le winner
ls .polybuild/runs/*/winner_voice/
# Review le diff manuellement, puis commit à la main si OK
```

**Critères de succès** :
- Le winner produit du code qui passe `pytest`/`mypy --strict` localement
- Au moins 1 finding P0 ou P1 a été détecté + corrigé par le triade
- Coût < $5

---

### Phase 3 — Full pipeline (objectif : commit + smoke)

**Cible** : tâche réelle avec valeur (bug fix, refactor borné, nouvelle feature mineure), pipeline complet.

```bash
# Brief sur une vraie issue (ex: GitHub issue #42)
cat > brief.md <<EOF
Fix the off-by-one in src/parsers/foo.py:line 142
that drops the last record on chunked input.
Add a regression test reproducing the bug from
tests/fixtures/chunked_input.json.
EOF

# Run complet
uv run polybuild run \
  --brief brief.md \
  --profile module_inedit_critique \
  --project-root . \
  # PAS --no-commit, donc commit auto + ADR
  # PAS --no-smoke, donc Phase 8 production smoke (rollback si régression)
```

**Critères de succès** :
- Phase 7 commit le winner avec ADR auto-généré
- Phase 8 smoke (5 min default) passe les seuils (0% MCP errors, +5% p95 latence max)
- Si Phase 8 KO → rollback `git reset --hard <tag-pre>` automatique

---

## ROI threshold (quand utiliser POLYBUILD vs Claude direct)

| Situation | Outil |
|-----------|-------|
| Tâche < 30 min, claire, peu d'options | Claude Code direct (gratuit côté toi) |
| Tâche ambiguë, plusieurs angles, intérêt à voir la diversité | POLYBUILD (3 voix parallèles) |
| Tâche médico-juridique avec PII potentielle | POLYBUILD (privacy gate Phase -1 obligatoire) |
| Code critique requérant audit indépendant + triade | POLYBUILD (Phase 4 + Phase 5) |
| Refactor large nécessitant un commit propre + ADR | POLYBUILD (Phase 7 auto-ADR) |

## Profils disponibles (cf `config/routing.yaml`)

À filtrer le jour J — la liste exacte vit dans le YAML.

## Garde-fous "écraser de la prod"

1. **Toujours `--project-root`** explicite (défaut `Path()` = cwd, dangereux si lancé depuis un repo sensible).
2. **Toujours `--no-smoke` pour la première run** dans un repo donné (le smoke fait `git reset --hard` sur échec → perte si seuils mal calibrés).
3. **Workspace dédié** (`.worktrees/staging-<run_id>`) pour smoke, jamais sur main directement.
4. **Lire le commit Phase 7 avant push** — POLYBUILD commit en local, le push reste manuel.

## Post-mortem première run

Après Phase 1 réussie, capturer dans `.polybuild/runs/<run_id>/POSTMORTEM.md` :
- Coût total OpenRouter (USD)
- Durée wall-clock
- Voix winner + voix dropped + raison
- Findings Phase 4 audit (count P0/P1/P2)
- Triade Phase 5 itérations
- Surprises (ce qui a marché vs ce qui a déçu)

Sert de baseline pour calibrer les profils + thresholds Phase 8.
