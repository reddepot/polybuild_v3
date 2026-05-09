"""Voice rotation — round-robin 1 Western + 1 Chinese (M2C.0).

POLYLENS anti-pattern #20 (panel monoculture) requires every audit run
to combine at least one Western voice and one Chinese voice. The
rotation module persists a small JSON state file (``voice_rotation_state.
json``) so successive audit drains pick a different pairing each time
and avoid the "Codex+GLM is always the W+CN couple" failure mode
(anti-pattern #16: voice imbalance bias).

State file shape (atomic write via tmp + rename):

    {
      "schema_version": 1,
      "western_index": 2,
      "chinese_index": 1,
      "last_picked_at": "2026-05-08T18:30:00Z"
    }

The pool is **hard-coded** here per anti-pattern #23 (no user-configurable
voice substitution). Adding a voice means editing the constants below
and bumping ``schema_version`` so existing state files do not silently
desync.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polybuild.audit._atomic_io import atomic_write_text
from polybuild.audit.queue import QueueLock, audit_dir, lock_path

# ────────────────────────────────────────────────────────────────
# Voice pool (anti-pattern #23: immutable, no user override)
# ────────────────────────────────────────────────────────────────
#
# POLYLENS-WONTFIX rationale: a POLYLENS run on M2 (z-ai/glm-4.6, axis
# E_architecture, P1) suggested moving these pools to a configuration
# file with runtime validation and schema versioning. We REJECT this
# recommendation because POLYLENS v3 anti-pattern #23 ("voice
# substitution outside pool") explicitly forbids user-configurable
# voice pools — the whole point of the immutable panel is that an
# operator cannot accidentally (or deliberately) downgrade audit
# diversity by editing a YAML. Pool changes are a code-level decision,
# tracked in version control, peer-reviewed via POLYLENS itself, and
# never an environment knob. See ``feedback_polylens_method.md`` §4
# anti-pattern #23 for the broader reasoning.

# Western pool — the 4-voice base panel from POLYLENS v3 ('panel base
# 4 voix occidentales IMMUABLE'). Codex GPT-5.5 + Kimi K2.6 are most
# productive on adversarial / PoC; Gemini for cross-tests; Claude is
# excluded from the audit hook because it IS the orchestrator (would
# self-audit, breaks the orthogonality assumption).
WESTERN_VOICES: tuple[str, ...] = (
    "codex-gpt-5.5",
    "gemini-3.1-pro",
    "kimi-k2.6",
)

# Chinese pool — the 5 voices added per axis in POLYLENS v3.
# The hook picks one round-robin to keep the cost bounded
# (~$0.05-0.40 / 1M tokens) while satisfying anti-pattern #20.
CHINESE_VOICES: tuple[str, ...] = (
    "z-ai/glm-5.1",
    "qwen/qwen3.6-max-preview",
    "minimax/m2.7",
    "xiaomi/mimo-v2.5-pro",
    "qwen/qwen3-coder-plus",
)


def state_path(override: Path | None = None) -> Path:
    return audit_dir(override) / "voice_rotation_state.json"


class RotationState(BaseModel):
    """Persistent state for the round-robin voice picker."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    western_index: int = 0
    chinese_index: int = 0
    last_picked_at: datetime | None = None
    pool_western: tuple[str, ...] = Field(default=WESTERN_VOICES)
    pool_chinese: tuple[str, ...] = Field(default=CHINESE_VOICES)


@dataclass(frozen=True)
class VoicePair:
    """A single Western + Chinese pairing for one audit run."""

    western: str
    chinese: str

    def as_list(self) -> list[str]:
        return [self.western, self.chinese]


def _load_state(path: Path) -> RotationState:
    """Read the rotation state file, falling back to defaults."""
    if not path.exists():
        return RotationState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = RotationState.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        # Corrupted state — defensively reset rather than crash. The
        # next pick will simply be the head of each pool.
        return RotationState()

    # If the on-disk pools no longer match the code's pools (a voice
    # was added or removed), reset the indices so we don't pick out of
    # bounds. Keeping ``last_picked_at`` is fine — it is informational.
    if (
        state.pool_western != WESTERN_VOICES
        or state.pool_chinese != CHINESE_VOICES
    ):
        return RotationState(
            western_index=0,
            chinese_index=0,
            last_picked_at=state.last_picked_at,
        )
    return state


def _save_state(path: Path, state: RotationState) -> None:
    """Atomic write via the shared :mod:`polybuild.audit._atomic_io` helper."""
    atomic_write_text(path, state.model_dump_json(indent=2))


def pick_voice_pair(state_dir: Path | None = None) -> VoicePair:
    """Pick one Western + one Chinese voice and advance the rotation state.

    The function is **idempotent under failure**: if ``_save_state``
    raises (full disk, permission error), the picked pair is still
    returned but the rotation does not advance. The next call will
    pick the same pair — accepted, the user retries the audit and
    eventually we either advance or surface the disk error elsewhere.

    Concurrent calls are serialised via the audit lock.
    """
    spath = state_path(state_dir)
    with QueueLock(lock_path(state_dir)):
        state = _load_state(spath)
        # Defensive bounds — should never trigger thanks to the pool
        # version reset above, but guards against a hand-edited state.
        wi = state.western_index % len(WESTERN_VOICES)
        ci = state.chinese_index % len(CHINESE_VOICES)
        pair = VoicePair(
            western=WESTERN_VOICES[wi],
            chinese=CHINESE_VOICES[ci],
        )
        next_state = state.model_copy(
            update={
                "western_index": (wi + 1) % len(WESTERN_VOICES),
                "chinese_index": (ci + 1) % len(CHINESE_VOICES),
                "last_picked_at": datetime.now(UTC),
            }
        )
        _save_state(spath, next_state)
    return pair


def reset_rotation(state_dir: Path | None = None) -> None:
    """Reset the rotation state to the head of each pool.

    Useful for tests and for the ``polybuild audit configure --rotation
    reset`` CLI verb (M2C.1).
    """
    spath = state_path(state_dir)
    with QueueLock(lock_path(state_dir)):
        _save_state(spath, RotationState())


__all__ = [
    "CHINESE_VOICES",
    "WESTERN_VOICES",
    "RotationState",
    "VoicePair",
    "pick_voice_pair",
    "reset_rotation",
    "state_path",
]
