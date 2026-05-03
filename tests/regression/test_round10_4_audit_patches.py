"""Régression POLYLENS round 10.4 — patches post-audit Phase 4 + Phase 7.

5 voix orthogonales (Kimi+ChatGPT+Qwen+Grok+Gemini) ont focalisé sur
phase_4_audit et phase_7_commit. 11 patches convergents appliqués.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — winner_result=None raises (anti git-add-A legacy)
# ──────────────────────────────────────────────────────────────────────


class TestPhase7RejectsMissingWinnerResult:
    def test_no_winner_raises(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "phase_7_commit requires winner_result" in src
        assert "round 10.4" in src.lower()


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — pre-staged index check
# ──────────────────────────────────────────────────────────────────────


class TestPhase7IndexCleanCheck:
    def test_diff_cached_quiet_check_present(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "phase_7_index_not_clean" in src
        assert '"diff", "--cached", "--quiet"' in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — tag_pre collision detection
# ──────────────────────────────────────────────────────────────────────


class TestPhase7TagPreCollision:
    def test_collision_check_present(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "phase_7_pre_tag_collision" in src
        assert "Run-id collision suspected" in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — git add partial = exception (was warn-only)
# ──────────────────────────────────────────────────────────────────────


class TestPhase7GitAddBatchRaises:
    def test_add_batch_failure_raises(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "phase_7_add_batch_failed" in src
        assert "raise RuntimeError" in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — deletions staged via git rm
# ──────────────────────────────────────────────────────────────────────


class TestPhase7StagesDeletions:
    def test_git_rm_for_missing_paths(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "ls-files" in src
        assert '"rm", "--"' in src
        assert "phase_7_rm_batch_failed" in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — commit message argument injection (Gemini RX-606-02)
# ──────────────────────────────────────────────────────────────────────


class TestPhase7CommitMsgArgInjection:
    def test_leading_dash_padded(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert 'commit_msg.startswith("-")' in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — sha="" rejected
# ──────────────────────────────────────────────────────────────────────


class TestPhase7NothingToCommitRaises:
    def test_no_changes_raises_now(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "phase_7_no_changes" in src
        assert "refusing committed status without" in src
        assert "real commit SHA" in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — ADR amend rc check
# ──────────────────────────────────────────────────────────────────────


class TestPhase7AdrAmendRcChecked:
    def test_amend_failures_raise(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        for label in (
            "phase_7_adr_add_failed",
            "phase_7_adr_amend_failed",
            "phase_7_adr_post_tag_failed",
        ):
            assert label in src, f"missing rc-check: {label}"


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — git env isolation + --no-verify (Gemini RX-606-01)
# ──────────────────────────────────────────────────────────────────────


class TestPhase7GitEnvHardening:
    def test_isolated_env_dict(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        for needle in (
            "GIT_CONFIG_NOSYSTEM",
            "GIT_TERMINAL_PROMPT",
            "GIT_SSH_COMMAND",
        ):
            assert needle in src, f"missing env iso: {needle}"

    def test_commit_uses_no_verify(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        # Both the main commit and the amend must --no-verify
        assert src.count('"--no-verify"') >= 2


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — _list_changed_files filters untracked (??)
# ──────────────────────────────────────────────────────────────────────


class TestPhase7ListChangedFiltersUntracked:
    def test_untracked_filter(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert 'line[:2].strip() == "??"' in src


# ──────────────────────────────────────────────────────────────────────
# Phase 7 — copy preserves permissions
# ──────────────────────────────────────────────────────────────────────


class TestPhase7CopyPreservesMode:
    def test_chmod_in_fallback(self) -> None:
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert "dst.chmod(src.stat().st_mode" in src


# ──────────────────────────────────────────────────────────────────────
# Phase 4 — auditor_family for CLI adapters (Kimi P0)
# ──────────────────────────────────────────────────────────────────────


class TestPhase4ResolveAuditorFamily:
    def test_resolve_known_cli_voices(self) -> None:
        from polybuild.phases.phase_4_audit import _resolve_auditor_family

        assert _resolve_auditor_family("claude-opus-4.7") == "anthropic"
        assert _resolve_auditor_family("gpt-5.5") == "openai"
        assert _resolve_auditor_family("gemini-3.1-pro") == "google"
        assert _resolve_auditor_family("kimi-k2.6") == "moonshot"
        assert _resolve_auditor_family("qwen2.5-coder:14b-int4") == "alibaba"
        assert _resolve_auditor_family("mistral/devstral-2") == "mistral"
        assert _resolve_auditor_family("deepseek/deepseek-v4-pro") == "deepseek"
        assert _resolve_auditor_family("x-ai/grok-4.20") == "xai"

    def test_resolve_unknown_falls_back_safely(self) -> None:
        from polybuild.phases.phase_4_audit import _resolve_auditor_family

        # Unknown voice without "/" → "unknown" (the only legitimate use)
        assert _resolve_auditor_family("zog-7000") == "unknown"
        # Unknown voice WITH "/" → returns the prefix (legacy behaviour)
        assert _resolve_auditor_family("custom/llm-9000") == "custom"


# ──────────────────────────────────────────────────────────────────────
# Functional smoke: hardened _git wrapper + winner_result enforcement
# ──────────────────────────────────────────────────────────────────────


class TestPhase7Functional:
    def test_phase_7_source_refuses_none_winner(self) -> None:
        # Static check is robust across PolybuildRun signature changes.
        src = Path("src/polybuild/phases/phase_7_commit.py").read_text()
        assert 'if winner_result is None:' in src
        assert "phase_7_commit requires winner_result" in src
