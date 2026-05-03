"""Régression POLYLENS v3 — multi-axes audit (B/C/D/E/F/G).

Voices :
  - Qwen 3.6 max  → axes B_quality + C_tests
  - Kimi K2.6     → axes D_performance + E_architecture
  - Grok 4.20     → axes F_documentation + G_adversarial
(Axe A_security exhaustively covered by Round 10 — 7 sub-rounds.)

Patches retained (P0/P1 only, easy wins) :
  Qwen B-02 — datetime.utcnow → datetime.now(UTC) in Spec.created_at
  Qwen B-04 — phase_0_spec spec_attack OR-response malformed guard
  Qwen B-05 — phase_0_spec greedy regex → non-greedy + LAST-balanced
  Qwen B-01 — claude_code._load_agents_md dead inner docstring removed
  Kimi D-02 — _estimate_metrics single-pass file reads (claude+codex)
  Grok F-02 — package __init__ docstring TODOs removed
"""

from __future__ import annotations

from pathlib import Path

import pytest


_SRC = Path("src/polybuild")


def _read(rel: str) -> str:
    return (_SRC / rel).read_text()


# ──────────────────────────────────────────────────────────────────────
# B-02 — datetime.now(UTC) instead of datetime.utcnow
# ──────────────────────────────────────────────────────────────────────


class TestSpecCreatedAtTimezoneAware:
    def test_spec_uses_now_utc_factory(self) -> None:
        src = _read("models.py")
        # Function call ``datetime.utcnow()`` must be gone (the comment
        # may still mention it as historical context).
        assert "datetime.utcnow()" not in src, (
            "datetime.utcnow() is deprecated in 3.12+; use datetime.now(UTC)"
        )
        assert "datetime.now(UTC)" in src
        # Lock the exact factory invocation in Spec.created_at.
        assert "default_factory=lambda: datetime.now(UTC)" in src

    def test_spec_imports_utc(self) -> None:
        src = _read("models.py")
        assert "from datetime import UTC, datetime" in src


# ──────────────────────────────────────────────────────────────────────
# B-04 — phase_0_spec OR malformed-response guard
# ──────────────────────────────────────────────────────────────────────


class TestPhase0SpecOrMalformedGuard:
    def test_spec_attack_handles_malformed(self) -> None:
        src = _read("phases/phase_0_spec.py")
        idx = src.find("spec_attack_malformed_or_response")
        assert idx > 0
        block = src[max(0, idx - 200) : idx + 400]
        assert "(KeyError, IndexError, TypeError)" in block
        # Direct chain assignment must be gone in the spec_attack function.
        # (Other call sites like _opus_revise_spec parse stdout directly.)
        assert (
            'content = response.json()["choices"][0]["message"]["content"]'
            not in src.split("def _opus_revise_spec")[0]
        )


# ──────────────────────────────────────────────────────────────────────
# B-05 — Non-greedy regex + LAST-balanced JSON in spec revision
# ──────────────────────────────────────────────────────────────────────


class TestPhase0SpecNonGreedyJsonExtraction:
    def test_revision_uses_non_greedy_pattern(self) -> None:
        src = _read("phases/phase_0_spec.py")
        # Greedy `\{.*\}` over re.DOTALL → replaced by `\{[\s\S]*?\}`
        # combined with reverse iteration over candidates.
        assert 're.findall(r"\\{[\\s\\S]*?\\}"' in src
        assert "for candidate in reversed(candidates):" in src
        # The previous greedy match is gone in this function.
        assert "match = re.search(r" not in src.split(
            "_opus_revise_spec"
        )[1]


# ──────────────────────────────────────────────────────────────────────
# B-01 — claude_code._load_agents_md dead docstring removed
# ──────────────────────────────────────────────────────────────────────


class TestClaudeCodeLoadAgentsDeadDocstring:
    def test_no_dead_inner_docstring(self) -> None:
        src = _read("adapters/claude_code.py")
        idx = src.find("def _load_agents_md(self) -> str:")
        end = src.find("def _parse_output", idx)
        body = src[idx:end]
        # The dead inner docstring was: """Load project AGENTS.md or fallback to global."""
        assert (
            '"""Load project AGENTS.md or fallback to global."""'
            not in body
        ), "dead inner docstring must be removed"


# ──────────────────────────────────────────────────────────────────────
# D-02 — _estimate_metrics single-pass file reads
# ──────────────────────────────────────────────────────────────────────


class TestEstimateMetricsSinglePass:
    @pytest.mark.parametrize(
        "rel",
        [
            "adapters/claude_code.py",
            "adapters/codex_cli.py",
        ],
    )
    def test_no_double_read(self, rel: str) -> None:
        src = _read(rel)
        idx = src.find("def _estimate_metrics(self, worktree: Path) -> SelfMetrics:")
        assert idx > 0
        end = idx + 800
        body = src[idx:end]
        # The previous double-read pattern with TODO/FIXME counted via
        # f.read_text() (twice over a generator) is gone.
        assert "f.read_text().count(\"TODO\") + f.read_text().count" not in body
        # Single-pass loop now uses ``text = f.read_text()`` once.
        assert "text = f.read_text()" in body


# ──────────────────────────────────────────────────────────────────────
# F-02 — Module __init__.py docstring no longer claims TODOs
# ──────────────────────────────────────────────────────────────────────


class TestPackageDocstringNoTodos:
    def test_init_docstring_no_post_round_4_todo(self) -> None:
        src = _read("__init__.py")
        # The two "TODO post-round 4" mentions for Phase -1 and Phase 8
        # have been removed (both phases are now active).
        assert "TODO post-round 4" not in src
