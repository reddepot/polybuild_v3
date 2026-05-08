#!/usr/bin/env bash
# Install the POLYBUILD post-commit audit hook (M2C.4).
#
# After install, every ``git commit`` in the target repository:
#   1. enqueues the new commit SHA via ``polybuild audit enqueue``,
#   2. detaches a ``polybuild audit drain`` subprocess in the background
#      (``nohup ... &``) so the commit returns immediately.
#
# Disable per-commit:           POLYBUILD_AUDIT_ENABLED=0 git commit ...
# Disable globally:              git config polybuild.audit-enabled false
# Uninstall:                     scripts/install_audit_hook.sh --uninstall
#
# The hook is **never blocking**: any error inside the hook body is
# trapped and discarded. A flaky audit MUST NOT block ``git commit``.
#
# Usage:
#   scripts/install_audit_hook.sh                       # current repo
#   scripts/install_audit_hook.sh /path/to/other/repo   # specific repo
#   scripts/install_audit_hook.sh --uninstall

set -euo pipefail

UNINSTALL=0
TARGET_REPO=""

for arg in "$@"; do
    case "$arg" in
        --uninstall) UNINSTALL=1 ;;
        --help|-h)
            sed -n '/^# /,/^$/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            if [ -z "$TARGET_REPO" ]; then
                TARGET_REPO="$arg"
            else
                echo "error: unexpected argument '$arg'" >&2
                exit 2
            fi
            ;;
    esac
done

if [ -z "$TARGET_REPO" ]; then
    TARGET_REPO="$(pwd)"
fi

if [ ! -d "$TARGET_REPO/.git" ]; then
    echo "error: $TARGET_REPO is not a git repository" >&2
    exit 1
fi

HOOK_PATH="$TARGET_REPO/.git/hooks/post-commit"
MARKER="# >>> polybuild audit hook (M2C.4) >>>"
END_MARKER="# <<< polybuild audit hook (M2C.4) <<<"

# Hook body to inject. Kept self-contained: no positional arguments,
# fully resolved environment variables, every command guarded so a
# failure never propagates back to git.
HOOK_BODY=$(cat <<'BODY'
# >>> polybuild audit hook (M2C.4) >>>
# Skip when explicitly disabled (per-commit env var or repo-local
# config). The hook MUST NOT fail the commit no matter what.
if [ "${POLYBUILD_AUDIT_ENABLED:-1}" = "0" ]; then
    :
elif [ "$(git config --get polybuild.audit-enabled 2>/dev/null || echo true)" = "false" ]; then
    :
elif ! command -v polybuild >/dev/null 2>&1; then
    :
else
    (
        sha=$(git rev-parse HEAD 2>/dev/null) || exit 0
        branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || branch=""
        repo=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

        # Enqueue synchronously (cheap: a single fcntl-locked JSONL append).
        polybuild audit enqueue --sha "$sha" --repo "$repo" --branch "$branch" \
            >/dev/null 2>&1 || true

        # Drain detached. ``nohup`` + ``&`` releases the parent (git)
        # immediately. Output is discarded — the audit notifier handles
        # P0/P1 alerts on its own.
        nohup polybuild audit drain >/dev/null 2>&1 < /dev/null &
        disown >/dev/null 2>&1 || true
    )
fi
# <<< polybuild audit hook (M2C.4) <<<
BODY
)

remove_block() {
    if [ ! -f "$HOOK_PATH" ]; then
        return 0
    fi
    python3 - "$HOOK_PATH" "$MARKER" "$END_MARKER" <<'PY'
import sys
path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, encoding="utf-8") as fh:
    src = fh.read()
out = []
in_block = False
for line in src.splitlines(keepends=True):
    if start in line:
        in_block = True
        continue
    if end in line:
        in_block = False
        continue
    if not in_block:
        out.append(line)
result = "".join(out).rstrip() + "\n" if out else ""
with open(path, "w", encoding="utf-8") as fh:
    fh.write(result)
PY
}

if [ "$UNINSTALL" = "1" ]; then
    if [ -f "$HOOK_PATH" ]; then
        remove_block
        # If the file is now empty (or contains only the shebang we
        # injected), unlink it so future installs start clean.
        if [ ! -s "$HOOK_PATH" ] || [ "$(wc -l <"$HOOK_PATH" | tr -d ' ')" -le "1" ]; then
            rm -f "$HOOK_PATH"
        fi
        echo "polybuild audit hook removed from $HOOK_PATH"
    else
        echo "no hook to remove ($HOOK_PATH not found)"
    fi
    exit 0
fi

# Install path: idempotent — strip any prior block before re-injecting.
remove_block

if [ ! -f "$HOOK_PATH" ]; then
    printf '#!/usr/bin/env bash\nset -e\n\n' >"$HOOK_PATH"
fi

printf '\n%s\n' "$HOOK_BODY" >>"$HOOK_PATH"
chmod +x "$HOOK_PATH"

echo "polybuild audit hook installed at $HOOK_PATH"
echo "  disable per-commit:  POLYBUILD_AUDIT_ENABLED=0 git commit ..."
echo "  disable repo-wide:   git config polybuild.audit-enabled false"
echo "  uninstall:           scripts/install_audit_hook.sh --uninstall"
