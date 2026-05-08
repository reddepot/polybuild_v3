"""Integration tests for M2A — ScorerProtocol + DEVCODE arbitration.

Mock-only by default (no LLM calls, no real builder runs); a single
opt-in test marked ``@pytest.mark.slow`` exercises the full
``DevcodeScorer.score`` path against a real ``InMemoryReputationStore``
and the actual ``devcode_vote_v1`` math kernel — still $0 because it
runs entirely in-process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from polybuild.models import (
    BuilderResult,
    GateResults,
    RiskProfile,
    SelfMetrics,
    Spec,
    Status,
    VoiceScore,
)
from polybuild.scoring import NaiveScorer, ScoredResult, ScorerProtocol


# ────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────


def _make_spec(run_id: str = "scorer-test-1") -> Spec:
    return Spec(
        run_id=run_id,
        profile_id="module_standard_known",
        task_description="scorer integration test",
        acceptance_criteria=[],
        risk_profile=RiskProfile(),
        spec_hash="sha256:dummy",
    )


def _make_result(voice_id: str, family: str) -> BuilderResult:
    return BuilderResult(
        voice_id=voice_id,
        family=family,
        code_dir=Path("/dev/null"),
        tests_dir=Path("/dev/null"),
        diff_patch=Path("/dev/null"),
        self_metrics=SelfMetrics(
            loc=10,
            complexity_cyclomatic_avg=1.0,
            test_to_code_ratio=0.5,
            todo_count=0,
            imports_count=2,
            functions_count=1,
        ),
        duration_sec=1.0,
        status=Status.OK,
    )


def _make_voice_score(voice_id: str, score: float) -> VoiceScore:
    return VoiceScore(
        voice_id=voice_id,
        score=score,
        gates=GateResults(
            acceptance_pass_ratio=1.0,
            bandit_clean=True,
            mypy_strict_clean=True,
            ruff_clean=True,
            coverage_score=1.0,
            gitleaks_clean=True,
            gitleaks_findings_count=0,
            diff_minimality=1.0,
        ),
        disqualified=False,
    )


# ────────────────────────────────────────────────────────────────
# CONTRACT — both scorers satisfy ScorerProtocol
# ────────────────────────────────────────────────────────────────


class TestScorerProtocolContract:
    def test_naive_satisfies_protocol(self) -> None:
        scorer: ScorerProtocol = NaiveScorer()
        assert scorer.name == "naive"
        assert callable(scorer.score)

    def test_devcode_satisfies_protocol(self) -> None:
        from polybuild.scoring.devcode_scorer import DevcodeScorer

        scorer: ScorerProtocol = DevcodeScorer()
        assert scorer.name == "devcode"
        assert callable(scorer.score)


# ────────────────────────────────────────────────────────────────
# NAIVE — wraps phase_3_score, abstains on winner
# ────────────────────────────────────────────────────────────────


class TestNaiveScorer:
    @pytest.mark.asyncio
    async def test_naive_abstains_on_winner_selection(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NaiveScorer always returns ``winner_voice_id=None`` so the
        consensus pipeline applies its eligibility filter."""
        import polybuild.orchestrator as _orch

        scores = [
            _make_voice_score("claude-opus-4.7", 95.0),
            _make_voice_score("gpt-5.5", 85.0),
        ]
        monkeypatch.setattr(_orch, "phase_3_score", AsyncMock(return_value=scores))

        result = await NaiveScorer().score(
            results=[
                _make_result("claude-opus-4.7", "anthropic"),
                _make_result("gpt-5.5", "openai"),
            ],
            spec=_make_spec(),
        )

        assert result.scorer_name == "naive"
        assert result.winner_voice_id is None
        assert result.voice_scores == scores
        # Confidence is the top score normalised on /100.
        assert result.confidence == pytest.approx(0.95)


# ────────────────────────────────────────────────────────────────
# DEVCODE — Schulze pick over consensus heuristic
# ────────────────────────────────────────────────────────────────


class TestDevcodeScorer:
    @pytest.mark.asyncio
    async def test_devcode_picks_schulze_winner(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A successful DEVCODE call surfaces ``winner_voice_id``."""
        from polybuild.scoring.devcode_scorer import DevcodeScorer

        scores = [
            _make_voice_score("claude-opus-4.7", 95.0),
            _make_voice_score("gpt-5.5", 85.0),
            _make_voice_score("kimi-k2.6", 90.0),
        ]
        results = [
            _make_result("claude-opus-4.7", "anthropic"),
            _make_result("gpt-5.5", "openai"),
            _make_result("kimi-k2.6", "moonshot"),
        ]

        # Mock the math kernel: pick option 0 with 0.78 confidence.
        from devcode.aggregation import devcode_vote_v1 as _real_vote

        del _real_vote  # we mock it below

        class _FakeDecision:
            winner = 0
            confidence = 0.78
            phase_resolved = "C_supermajority"
            schulze_ranking = [0, 2, 1]
            weights_applied = {"claude-opus-4.7": 1.0}
            family_collusion_penalties: list[dict[str, Any]] = []
            arbitre_if_split = None
            requires_polylens_review = False

        monkeypatch.setattr(
            "polybuild.scoring.devcode_scorer.NaiveScorer.score",
            AsyncMock(
                return_value=ScoredResult(
                    voice_scores=scores,
                    winner_voice_id=None,
                    confidence=0.95,
                    scorer_name="naive",
                )
            ),
        )
        monkeypatch.setattr(
            "devcode.aggregation.devcode_vote_v1",
            lambda votes, ctx, store: _FakeDecision(),
        )

        scorer = DevcodeScorer()
        out = await scorer.score(results, _make_spec())

        assert out.scorer_name == "devcode"
        assert out.winner_voice_id == "claude-opus-4.7"
        assert out.confidence == pytest.approx(0.78)
        assert out.requires_polylens_review is False
        assert out.debug_data["phase_resolved"] == "C_supermajority"

    @pytest.mark.asyncio
    async def test_devcode_no_quorum_abstains(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fewer than two OK voices → DEVCODE abstains."""
        from polybuild.scoring.devcode_scorer import DevcodeScorer

        scores = [_make_voice_score("claude-opus-4.7", 95.0)]
        monkeypatch.setattr(
            "polybuild.scoring.devcode_scorer.NaiveScorer.score",
            AsyncMock(
                return_value=ScoredResult(
                    voice_scores=scores,
                    winner_voice_id=None,
                    confidence=0.95,
                    scorer_name="naive",
                )
            ),
        )

        out = await DevcodeScorer().score(
            results=[_make_result("claude-opus-4.7", "anthropic")],
            spec=_make_spec(),
        )

        assert out.scorer_name == "devcode_no_quorum"
        assert out.winner_voice_id is None
        assert out.debug_data["reason"] == "fewer_than_two_ok_voices"


# ────────────────────────────────────────────────────────────────
# ADAPTER — family mapping + ranking heuristic
# ────────────────────────────────────────────────────────────────


class TestDevcodeAdapter:
    def test_family_mapping_known(self) -> None:
        from polybuild.scoring.devcode_adapter import (
            _polybuild_family_to_devcode_str,
        )

        assert _polybuild_family_to_devcode_str("anthropic") == "anthropic"
        assert _polybuild_family_to_devcode_str("zai") == "zhipu"
        assert _polybuild_family_to_devcode_str("qwen") == "alibaba"

    def test_family_mapping_unknown_raises(self) -> None:
        from polybuild.scoring.devcode_adapter import (
            _polybuild_family_to_devcode_str,
        )

        with pytest.raises(ValueError, match="DEVCODE Family mapping missing"):
            _polybuild_family_to_devcode_str("xai")  # Grok not in DEVCODE Family enum

    def test_consensus_ranking_descending(self) -> None:
        """Every voice produces the same score-descending ranking."""
        from polybuild.scoring.devcode_adapter import (
            builder_results_to_devcode_votes,
        )

        results = [
            _make_result("claude-opus-4.7", "anthropic"),
            _make_result("gpt-5.5", "openai"),
            _make_result("kimi-k2.6", "moonshot"),
        ]
        scores = [
            _make_voice_score("claude-opus-4.7", 0.7),
            _make_voice_score("gpt-5.5", 0.9),
            _make_voice_score("kimi-k2.6", 0.5),
        ]
        votes, ctx = builder_results_to_devcode_votes(results, scores, _make_spec())

        # gpt-5.5 (0.9) > claude (0.7) > kimi (0.5)
        # Mapped: claude=0, gpt=1, kimi=2 → expected ranking [1, 0, 2]
        expected = [1, 0, 2]
        assert all(v.ranked_options == expected for v in votes)
        assert ctx.options == [0, 1, 2]
        assert ctx.priority.value == "P2"  # default RiskProfile = LOW sensitivity

    def test_no_ok_voices_raises(self) -> None:
        from polybuild.scoring.devcode_adapter import (
            builder_results_to_devcode_votes,
        )

        failed = _make_result("claude", "anthropic").model_dump()
        failed["status"] = Status.FAILED
        results = [BuilderResult(**failed)]

        with pytest.raises(ValueError, match=r"no Status\.OK BuilderResult"):
            builder_results_to_devcode_votes(results, [], _make_spec())


# ────────────────────────────────────────────────────────────────
# E2E (slow, no LLM) — full DevcodeScorer with real math kernel
# ────────────────────────────────────────────────────────────────


class TestShadowScorer:
    @pytest.mark.asyncio
    async def test_shadow_returns_naive_and_logs_devcode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ShadowScorer always returns Naive's result; logs DEVCODE divergence."""
        from polybuild.scoring.shadow_scorer import (
            ShadowDivergence,
            ShadowScorer,
            shadow_log_path,
        )

        results = [
            _make_result("claude-opus-4.7", "anthropic"),
            _make_result("gpt-5.5", "openai"),
        ]
        naive_scores = [
            _make_voice_score("claude-opus-4.7", 95.0),
            _make_voice_score("gpt-5.5", 85.0),
        ]

        # Mock the naive scorer to return canned scores.
        async def _fake_naive_score(self, _r, _s):  # type: ignore[no-untyped-def]
            return ScoredResult(
                voice_scores=naive_scores,
                winner_voice_id=None,
                confidence=0.95,
                scorer_name="naive",
            )

        monkeypatch.setattr(NaiveScorer, "score", _fake_naive_score)

        # Mock DEVCODE to claim a different winner (gpt-5.5 instead of claude).
        class _FakeDevcode:
            async def score(self, _r, _s):  # type: ignore[no-untyped-def]
                return ScoredResult(
                    voice_scores=naive_scores,
                    winner_voice_id="gpt-5.5",
                    confidence=0.62,
                    requires_polylens_review=False,
                    scorer_name="devcode",
                )

        scorer = ShadowScorer(
            devcode_factory=_FakeDevcode,
            shadow_dir=tmp_path,
        )
        out = await scorer.score(results, _make_spec())

        # Live winner = naive (abstains, pipeline picks top score = claude).
        assert out.scorer_name == "devcode_shadow"
        assert out.winner_voice_id is None  # naive abstains
        assert out.debug_data["devcode_winner_voice_id"] == "gpt-5.5"

        # Shadow log contains one ShadowDivergence record marked diverged.
        log = shadow_log_path(tmp_path).read_text()
        record = ShadowDivergence.model_validate_json(log.strip())
        assert record.naive_winner == "claude-opus-4.7"
        assert record.devcode_winner == "gpt-5.5"
        assert record.diverged is True

    @pytest.mark.asyncio
    async def test_shadow_swallows_devcode_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A DEVCODE exception MUST NOT impact the live pipeline."""
        from polybuild.scoring.shadow_scorer import ShadowScorer

        async def _fake_naive_score(self, _r, _s):  # type: ignore[no-untyped-def]
            return ScoredResult(
                voice_scores=[_make_voice_score("claude-opus-4.7", 90.0)],
                winner_voice_id=None,
                confidence=0.9,
                scorer_name="naive",
            )

        monkeypatch.setattr(NaiveScorer, "score", _fake_naive_score)

        class _BoomScorer:
            async def score(self, _r, _s):  # type: ignore[no-untyped-def]
                raise RuntimeError("devcode kaboom")

        scorer = ShadowScorer(
            devcode_factory=_BoomScorer,
            shadow_dir=tmp_path,
        )
        out = await scorer.score(
            [_make_result("claude-opus-4.7", "anthropic")], _make_spec()
        )
        # Naive result still returned; debug shows DEVCODE absent.
        assert out.confidence == 0.9
        assert out.debug_data["devcode_winner_voice_id"] is None


@pytest.mark.slow
class TestDevcodeScorerE2E:
    @pytest.mark.asyncio
    async def test_e2e_with_in_memory_store(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full ``DevcodeScorer`` path: NaiveScorer (mocked) + real
        adapter + real ``devcode_vote_v1`` over ``InMemoryReputationStore``.
        Cost: $0 (no LLM, no I/O).
        """
        from devcode.reputation import InMemoryReputationStore

        from polybuild.scoring.devcode_scorer import DevcodeScorer

        results = [
            _make_result("claude-opus-4.7", "anthropic"),
            _make_result("gpt-5.5", "openai"),
            _make_result("kimi-k2.6", "moonshot"),  # non-Western voice
        ]
        scores = [
            _make_voice_score("claude-opus-4.7", 95.0),
            _make_voice_score("gpt-5.5", 85.0),
            _make_voice_score("kimi-k2.6", 90.0),
        ]
        # NaiveScorer pre-step is mocked because we don't want the real
        # gate runner to spawn pytest/mypy on every test invocation.
        monkeypatch.setattr(
            "polybuild.scoring.devcode_scorer.NaiveScorer.score",
            AsyncMock(
                return_value=ScoredResult(
                    voice_scores=scores,
                    winner_voice_id=None,
                    confidence=0.95,
                    scorer_name="naive",
                )
            ),
        )

        out = await DevcodeScorer(store=InMemoryReputationStore()).score(
            results, _make_spec()
        )

        assert out.scorer_name == "devcode"
        assert out.winner_voice_id in {
            "claude-opus-4.7",
            "gpt-5.5",
            "kimi-k2.6",
        }
        # confidence in [0, 1]
        assert 0.0 <= out.confidence <= 1.0
        # debug data shape sanity
        assert "schulze_ranking" in out.debug_data
        assert "weights_applied" in out.debug_data
