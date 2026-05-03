# /polybuild — Skill Claude Code

> Lance et supervise des runs POLYBUILD v3 en arrière-plan via tmux.

**Convergence round 4 (6/6) sur tmux** comme orchestrateur background :
- Survives Claude Code disconnections and SSH drops.
- Inspectable via `tmux capture-pane`.
- Killable cleanly via `tmux kill-session`.
- Fallback `screen` puis `nohup` si tmux indisponible (Kimi + DeepSeek).

## Commandes

### `/polybuild run --spec <spec.yaml> [--profile <name>] [--no-smoke]`
Lance un run POLYBUILD en background.

```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)"
mkdir -p .polybuild/runs .polybuild/logs

# Round 6 fix [M2] (Audit 4): the previous shell took $1 as the spec path,
# but `/polybuild run --spec spec.yaml` passes `--spec` as $1. Parse the
# real flags so the skill matches its documented usage.
SPEC=""
EXTRA_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --spec|--brief|-b)
      SPEC="$2"; shift 2 ;;
    --profile|-p|--profile=*)
      EXTRA_ARGS+=("$1"); [ "$1" = "--profile" -o "$1" = "-p" ] && { EXTRA_ARGS+=("$2"); shift 2; } || shift ;;
    *)
      EXTRA_ARGS+=("$1"); shift ;;
  esac
done

if [ -z "${SPEC}" ]; then
  echo "Usage: /polybuild run --spec <spec.yaml> [--profile <name>] [--no-smoke]"
  exit 2
fi

EXTRA="${EXTRA_ARGS[*]}"

# Backend selection: tmux > screen > nohup (round 4 fallback chain)
if command -v tmux >/dev/null 2>&1; then
  tmux new-session -d -s "polybuild-${RUN_ID}" \
    "set -a; \
     [ -f \"$HOME/.polybuild/secrets.env\" ] && . \"$HOME/.polybuild/secrets.env\"; \
     set +a; \
     uv run polybuild run --spec '${SPEC}' --run-id '${RUN_ID}' ${EXTRA} \
       2>&1 | tee '.polybuild/logs/${RUN_ID}.log'"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: tmux session 'polybuild-${RUN_ID}'"
elif command -v screen >/dev/null 2>&1; then
  screen -dmS "polybuild-${RUN_ID}" \
    bash -c "set -a; [ -f \"\$HOME/.polybuild/secrets.env\" ] && . \"\$HOME/.polybuild/secrets.env\"; set +a; \
             uv run polybuild run --spec '${SPEC}' --run-id '${RUN_ID}' ${EXTRA} 2>&1 | tee '.polybuild/logs/${RUN_ID}.log'"
  echo "${RUN_ID}" > .polybuild/last_run
  echo "Backend: screen session 'polybuild-${RUN_ID}'"
else
  # nohup last-resort fallback (no attach, no inspect)
  nohup bash -c "set -a; [ -f \"\$HOME/.polybuild/secrets.env\" ] && . \"\$HOME/.polybuild/secrets.env\"; set +a; \
                 uv run polybuild run --spec '${SPEC}' --run-id '${RUN_ID}' ${EXTRA}" \
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
