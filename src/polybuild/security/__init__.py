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
