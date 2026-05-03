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
