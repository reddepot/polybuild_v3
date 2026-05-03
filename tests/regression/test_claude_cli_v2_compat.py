"""Régression Round 10.8 prod-launch — claude CLI v2 compatibility.

Lors du premier smoke run en prod (commit d68dd52), POLYBUILD a crashé
sur Phase 0 spec generation : la claude CLI installée localement (v2.x)
a refusé l'invocation legacy ``claude code --prompt X --output-format
json`` avec ``error: unknown option '--prompt'``.

claude CLI v2 (>= 2.x) :
  - plus de sous-commande ``code``
  - prompt en positionnel derrière ``-p / --print``
  - ``--output-format`` = ``text|json|stream-json`` mais ``json`` retourne
    une enveloppe (``{result, usage, ...}``) ; on utilise ``text`` pour
    récupérer le model output direct
  - plus d'``--output-dir`` (le wrapper ne crée plus de fichiers ;
    l'adapter parse le JSON émis par le modèle et écrit lui-même via
    ``polybuild.security.safe_write``).

Ce test verrouille l'invariant pour qu'une régression future soit
détectée par CI plutôt que par un crash en prod.
"""

from __future__ import annotations

from pathlib import Path

_SRC = Path("src/polybuild")


def _read(rel: str) -> str:
    return (_SRC / rel).read_text()


class TestPhase0SpecUsesClaudeV2:
    def test_phase_0_uses_print_flag(self) -> None:
        src = _read("phases/phase_0_spec.py")
        # Exact invocation: claude -p PROMPT --model M --output-format text
        assert '"claude", "-p", prompt' in src
        # Old v1 patterns are gone
        assert '"claude", "code"' not in src
        assert '"--prompt", prompt' not in src

    def test_phase_0_uses_text_format(self) -> None:
        src = _read("phases/phase_0_spec.py")
        # text mode required: json mode wraps in envelope, breaks json.loads
        assert '"--output-format", "text"' in src
        assert '"--output-format", "json"' not in src


class TestPhase7CommitUsesClaudeV2:
    def test_phase_7_uses_print_flag(self) -> None:
        src = _read("phases/phase_7_commit.py")
        assert '"claude", "-p", prompt' in src
        assert '"claude", "code"' not in src


class TestClaudeCodeAdapterUsesV2:
    def test_generate_uses_print_flag(self) -> None:
        src = _read("adapters/claude_code.py")
        assert '"-p", prompt' in src
        # The legacy ``"code"`` subcommand and ``--prompt`` value-flag are gone.
        assert '"code",\n            "--model"' not in src
        assert '"--prompt", prompt' not in src
        assert '"--output-dir"' not in src
        assert '"--output-format", "text"' in src

    def test_smoke_test_uses_print_flag(self) -> None:
        src = _read("adapters/claude_code.py")
        assert '"-p", smoke_prompt' in src
        assert '"--prompt", smoke_prompt' not in src


class TestClaudeModelIdsUseFullName:
    def test_uses_full_model_id(self) -> None:
        # Round 10.8: switched from short alias ``opus-4.7`` to canonical
        # full id ``claude-opus-4-7`` (claude CLI v2 accepts both but full
        # id is unambiguous for cache + telemetry attribution).
        src_phase0 = _read("phases/phase_0_spec.py")
        src_phase7 = _read("phases/phase_7_commit.py")
        assert "claude-opus-4-7" in src_phase0
        assert "claude-opus-4-7" in src_phase7
        assert '"opus-4.7"' not in src_phase0
        assert '"opus-4.7"' not in src_phase7


# ──────────────────────────────────────────────────────────────────────
# Codex CLI 0.128 — --output-format dropped, default text out
# ──────────────────────────────────────────────────────────────────────


class TestCodexCliV0128Compat:
    def test_no_output_format_flag(self) -> None:
        src = _read("adapters/codex_cli.py")
        # Old flag is gone (now ``--output-schema FILE`` for JSON-Schema
        # validation, or ``--json`` for JSONL events).
        assert '"--output-format", "json"' not in src

    def test_skip_git_repo_check_present(self) -> None:
        src = _read("adapters/codex_cli.py")
        # Sandboxes/worktrees often aren't git repos; ``--skip-git-repo-check``
        # avoids codex aborting on absence of .git.
        assert '"--skip-git-repo-check"' in src


# ──────────────────────────────────────────────────────────────────────
# Kimi CLI 1.41 — output-format json invalid (now text or stream-json)
# ──────────────────────────────────────────────────────────────────────


class TestKimiCli141Compat:
    def test_uses_text_output_format(self) -> None:
        src = _read("adapters/kimi_cli.py")
        # ``json`` is no longer a valid value
        assert '"--output-format", "json"' not in src
        assert '"--output-format", "text"' in src

    def test_uses_print_afk_yolo(self) -> None:
        src = _read("adapters/kimi_cli.py")
        # Headless mode requires ``--print --afk -y`` so the agent does
        # not hang waiting for human approval.
        assert '"--print"' in src
        assert '"--afk"' in src
        assert '"-y"' in src


# ──────────────────────────────────────────────────────────────────────
# Gemini CLI 0.40 — workspace trust required for headless
# ──────────────────────────────────────────────────────────────────────


class TestGeminiCli040Compat:
    def test_uses_skip_trust_yolo(self) -> None:
        src = _read("adapters/gemini_cli.py")
        # Without ``--skip-trust`` the CLI exits with code 55 in untrusted
        # workspaces. ``--yolo`` auto-approves tool calls so headless runs
        # don't hang.
        assert '"--skip-trust"' in src
        assert '"--yolo"' in src
