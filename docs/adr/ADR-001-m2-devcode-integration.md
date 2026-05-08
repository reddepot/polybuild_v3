# ADR-001 — M2 : DEVCODE arbitration + ``--solo`` mode + POLYLENS audit hook

* **Status** : Accepted
* **Date** : 2026-05-08
* **Branch** : `feat/m2-devcode-integration`
* **Plan source** : `/tmp/m2_polybuild_plan_final.md` (synthèse `/avis --améliorations` 4 voix Codex GPT-5.5 + Kimi K2.6 + Qwen 3.6 Plus + GLM 5.1 sur draft)
* **Méthodologie** : PDCA enrichi (`feedback_no_precipitation_pdca.md`), POLYLENS anti-patterns surveillés (`feedback_polylens_method.md` v3 §4)

---

## Context

POLYBUILD v3 round 10.8 finissait avec :

* un orchestrateur monolithique `_run_polybuild_inner` de **906 LOC** (god function flagué Kimi pendant la review M2 plan),
* un scoring Phase 3 codé en dur dans `polybuild.phases.phase_3_score`, retournant un bare `list[VoiceScore]`,
* aucun mécanisme d'arbitrage cross-voix au-delà d'un `max(score)` filtré par les disqualifications grounding,
* aucune surveillance POLYLENS post-commit hors des sprints d'audit ponctuels (R6, R10, R10.8).

DEVCODE v1.0 (`~/Developer/projects/devcode/`, tag `v1.0.1`) venait de fermer en *option β reformulée* (`lessons_session_20260508_devcode_v1_closure.md`) :

* librairie noyau Python stable (1214 LOC src, 62 tests),
* implémente Schulze pondéré bayésien Glicko-2 + cosinus anti-collusion + supermajorité cross-culturelle,
* multi-domaine (IT / scientifique / médical / perso),
* statut "stable maintenance only" — pas de nouvelles features.

L'intégration POLYBUILD ↔ DEVCODE devait :

1. permettre à POLYBUILD d'appeler le math kernel DEVCODE comme scorer alternatif au choix de l'utilisateur, sans toucher au repo DEVCODE (Killing criterion **K1** : `src/devcode/*` intouché),
2. ouvrir un mode `--solo` short-circuit (1 voix, skip Phase 2/3/5) pour les cas où l'arbitrage multi-voix est un coût pur,
3. attacher un audit POLYLENS asynchrone non-bloquant à chaque commit pour rattraper les angles morts entre sprints (anti-pattern POLYLENS #20 monoculture combattu par rotation 1W+1CN obligatoire).

Le plan a été stress-testé en `/avis --challenge` (3 voix, triple convergence sur le risque *yak shaving*) puis durci en `/avis --améliorations` (4 voix, convergence ★★★★ sur 8 modifications structurelles, dont la refacto Strategy Pattern obligatoire avant intégration et le hook async-only post-commit).

## Decision

### M2B — Strategy Pattern + ``--solo``

* `polybuild.orchestrator.pipeline_strategy` introduit le contrat `PipelineStrategy` (typing.Protocol) + `StrategyOutcome` (frozen dataclass).
* `polybuild.orchestrator.consensus_pipeline.ConsensusPipeline` extrait la séquence Phase 1 → Phase 5 + winner determination de `_run_polybuild_inner` (comportement byte-identical pour la voie `NaiveScorer`).
* `polybuild.orchestrator.solo_pipeline.SoloPipeline` court-circuite Phase 2 (parallel generate), Phase 3 (scoring) et Phase 5 (triade fix) avec une voix unique configurable (`SoloPipeline(voice_id=…, family=…)`). Phase 4 audit reste activé (safety check). Une finding P0 abort le run avec hint pour relancer en consensus.
* `run_polybuild(strategy=…)` accepte le nouveau kwarg, défaut `ConsensusPipeline()`. Phase −1 / 0 / 6 / 7 / 8 / 9 cleanup tournent toujours, indépendamment de la stratégie.
* CLI : `--solo` flag plumb le `SoloPipeline()` ; le banner echo la stratégie active.

### M2A — DEVCODE comme scorer alternatif

* `polybuild.scoring.protocol` introduit `ScorerProtocol` + `ScoredResult` (Pydantic frozen unifiant `list[VoiceScore]` et la `Decision` DEVCODE).
* `polybuild.scoring.devcode_adapter.builder_results_to_devcode_votes(results, voice_scores, spec)` est la fonction pure de mapping `BuilderResult` → `Vote`. Heuristique de ranking *consensus* (toutes les voix produisent le même score-descending, car POLYBUILD n'a pas d'évaluation cross-voix). Family map exhaustif (anthropic / openai / google / mistral / moonshot / deepseek / minimax / xiaomi / zhipu / alibaba) — `xai` non mappé (DEVCODE n'a pas d'enum, raise volontaire).
* `polybuild.scoring.naive_scorer.NaiveScorer` wrap `phase_3_score` via lazy `_orch.phase_3_score` (compat `mock.patch` des tests existants). Abstient sur winner (`winner_voice_id=None` → pipeline applique le filtre d'éligibilité canonique).
* `polybuild.scoring.devcode_scorer.DevcodeScorer` layer sur NaiveScorer + appelle `devcode.aggregation.devcode_vote_v1`. `winner_voice_id` = traduction option Schulze → `voice_id` POLYBUILD ; `confidence` et `requires_polylens_review` propagés depuis `Decision`. Pluggable `ReputationStore` (default `InMemoryReputationStore`).
* `ConsensusPipeline.__init__(scorer: ScorerProtocol | None = None)` — défaut `NaiveScorer()`. La winner-decision a deux paths : `winner_voice_id` non-None → honor (sauf si grounding-disqualified) ; None → eligibility filter canonique.
* CLI : `--scorer={naive,devcode}` flag, défaut `naive`. Lazy import devcode si `--scorer=devcode` ; absence de l'extra produit `typer.BadParameter` clair.
* `pyproject.toml` : extra `[devcode]` avec `devcode @ file:///Users/radu/Developer/projects/devcode` (PEP 508 direct ref + `tool.hatch.metadata.allow-direct-references = true`).

### M2C — POLYLENS audit hook asynchrone

* `polybuild.audit.queue` : `AuditQueueEntry` (Pydantic frozen, `extra="forbid"` — anti-pattern #15) + JSONL append/read/drain + `QueueLock` (fcntl.flock, optional `timeout_s`).
* `polybuild.audit.backlog` : `BacklogFinding` (closed schema) + `compute_fingerprint` (SHA-256 sur `commit_sha + file + line + axis + normalized_message`). Dedup 7-day rolling window dans `append_findings`.
* `polybuild.audit.rotation` : pool **immuable** (anti-pattern #23) Western (codex / gemini / kimi CLI) × Chinese (z-ai/glm / qwen / minimax / xiaomi / qwen-coder via OpenRouter). `pick_voice_pair()` round-robin avance les indices, persistance JSON atomique via mkstemp + rename + fsync.
* `polybuild.audit.runner.audit_commit(entry, voice_caller=…)` : pick W+CN, extract `git show` (≤200 lignes), prompt POLYLENS A+C+G axes, parallel `asyncio.gather(return_exceptions=True)`, parse JSON-Lines tolérant. Voice timeout 30s + silent fallback. DI testable.
* `polybuild.audit.notifier` : P0/P1 → banner macOS (`osascript`) + fallback stderr + persist backlog ; P2/P3 → backlog only. `build_digest(since=...)` markdown summary par sévérité.
* `polybuild.audit.cli` : sub-app `polybuild audit {drain,status,digest,dry-run,configure rotation,enqueue}`. Non-bloquant (drain détaché via nohup dans le hook).
* `scripts/install_audit_hook.sh` : installe un block idempotent dans `<repo>/.git/hooks/post-commit`. Disable matrix : `POLYBUILD_AUDIT_ENABLED=0`, `git config polybuild.audit-enabled false`, `--uninstall`. Hook **never blocking** par construction (chaque step `|| true`).

## Consequences

### Acquis

* `run_polybuild()` 100% backward-compatible : tous les tests R5..R10.8 (576 passed, 6 skipped, 10 xfailed) restent verts sans modification de leur code.
* Performance K2 (test suite slowdown) ✅ **PASS** : full suite ~21 s (pas de régression vs baseline).
* Performance K5 (devcode_vote_v1 latency) ✅ **PASS** : médiane 0.11 ms / max 3.46 ms sur N=5 voix × 10 runs (600× sous le seuil 2000 ms).
* Killing criteria **K1** (DEVCODE intouché ✅), **K8** (≤3 fichiers DEVCODE modifiés : 0 ✅), **K9** (hook ne bloque pas commit ✅) tous respectés.
* K7 LOC budget (800 LOC) **dépassé** (~1900 LOC src) — explicitement accepté par le user au turn-around : préoccupation perf > LOC count, code dense en docstrings + Round X/Y fix history préservés.
* DEVCODE reste librairie noyau stable (1214 LOC, v1.0.1) — pas de couplage en arrière.

### Trade-offs

* Le mapping `BuilderResult` → `Vote` utilise une *heuristique consensus* (toutes les voix votent le même ranking score-descending) car POLYBUILD n'a pas d'évaluation cross-voix. La valeur ajoutée DEVCODE sous cette heuristique se réduit à : pénalité collusion familiale + Glicko-2 reputation + supermajorité cross-culturelle. Schulze lui-même est dégénéré. Suffisant pour le ROI dev solo (ship the math) ; insuffisant pour un benchmark calibré (Phase 2/3 DEVCODE explicitement abandonnées au closure v1.0).
* Le hook audit consomme un budget cible $0.30 / commit (2 voix × $0.15 OpenRouter / 200 lignes diff max). Sur un workflow de commits fréquents (~10/jour) → $3/jour, $90/mois. Acceptable pour Radu solo dev ; à monitorer.
* Lazy attribute lookup `import polybuild.orchestrator as _orch` dans `consensus_pipeline.run` est un workaround volontaire pour préserver les `mock.patch("polybuild.orchestrator.<phase>", ...)` des tests existants. Coût lisibilité minime (pattern documenté en module docstring) ; alternative aurait été modifier ~30 patches dans 4 fichiers de tests, refusé par règle plan #6 (tests existants intouchés).

### Risques résiduels

* **Voice imbalance bias** (anti-pattern #16) : la rotation round-robin garantit la diversité W et CN indépendamment, mais sur 3 W × 5 CN = 15 paires, certaines apparaissent 1× toutes les 15 audits. Acceptable pour un dev solo ; à revoir si un finding pattern systématique apparaît dans le digest.
* **K3 (--solo overhead) et K6 (--solo failure rate)** non mesurés : aucun run réel `--solo` lancé contre des LLM live pendant M2. À mesurer empiriquement post-merge sur 5-10 invocations.
* **K4 (audit P2 noise)** : pas de baseline empirique. La dedup 7-day window devrait suffire ; à monitorer via `polybuild audit digest --since=week` après 1 semaine de hook activé.
* **Hook audit côté Windows / Linux non testé** : seul macOS testé (osascript path + fallback stderr). Le code de fallback est robuste mais aucun smoke test sur autre OS.

## PDCA Act — capitalisation

Lessons durables identifiées pendant M2 (à propager via `/capitalize` vers les autres projets) :

1. **Strategy Pattern + lazy module attribute lookup** pour préserver `mock.patch` lors de l'extraction d'une god function — pattern réutilisable pour HELIA, MedData orchestrators, RedAPI gateway.
2. **Pydantic frozen dataclasses + `extra="forbid"`** sur tous les schemas JSONL persistés — anti-pattern #15 _other inflation prévenu structurellement.
3. **PEP 508 file:// direct refs + `tool.hatch.metadata.allow-direct-references=true`** comme pattern d'install pour sibling project pas encore sur PyPI (DEVCODE → polybuild). Documenté pour réutilisation.
4. **`uv cache clean` deadlock sous `uv run pytest`** — fix défensif `timeout=10s` + skip-inside-uv-run dans `phase_9_cleanup`. À propager si le pattern se retrouve dans MedData / SSTinfo.

## Liens

* Plan détaillé : `/tmp/m2_polybuild_plan_final.md`
* Prompt session parallèle : `/tmp/m2_parallel_session_prompt.md`
* Handoff inter-session : `docs/session_handoff.json`
* DEVCODE methodology : `~/Developer/projects/devcode/docs/DEVCODE_METHODOLOGY.md`
* Memory entries : `lessons_session_20260508_devcode_v1_closure.md` + (à créer) `lessons_session_20260508_polybuild_m2.md`
* PDCA méthode référence : `~/.claude/projects/-Users-radu/memory/feedback_pdca_method.md`
