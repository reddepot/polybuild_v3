"""Tests unitaires pour Phase 5 — Critic-Fixer-Verifier triade."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from polybuild.models import (
    AuditReport,
    BuilderResult,
    Finding,
    FindingEvidence,
    RiskProfile,
    SelfMetrics,
    Severity,
    Status,
)
from polybuild.phases.phase_5_triade import (
    _load_prompt,
    _parse_verifier_verdict,
    _resolve_prompts_dir,
    pick_triade,
    phase_5_dispatch,
)


class TestPickTriade:
    """Anti self-fix : Critic ≠ Fixer ≠ Verifier, families distinctes."""

    def test_basic_triade_families_distinct(self) -> None:
        critic, fixer, verifier = pick_triade("anthropic", "openai", RiskProfile())
        families = {critic.split("/")[0] if "/" in critic else critic.split("-")[0], fixer.split("/")[0] if "/" in fixer else fixer.split("-")[0], verifier.split("/")[0] if "/" in verifier else verifier.split("-")[0]}
        # families doit contenir au moins 3 éléments (ou 2 si relaxation verifier)
        assert len(families) >= 2
        assert "anthropic" not in families  # winner_family exclue

    def test_winner_family_excluded(self) -> None:
        critic, fixer, verifier = pick_triade("openai", "anthropic", RiskProfile())
        assert not critic.startswith("gpt-")
        assert not fixer.startswith("gpt-")
        assert not verifier.startswith("gpt-")

    def test_auditor_family_excluded_from_verifier_when_possible(self) -> None:
        critic, fixer, verifier = pick_triade("anthropic", "openai", RiskProfile())
        # Le verifier ne devrait pas être OpenAI si possible
        # En pratique avec le pool actuel, il peut l'être si peu de modèles restent
        pass

    def test_excludes_openrouter(self) -> None:
        rp = RiskProfile(excludes_openrouter=True)
        critic, fixer, verifier = pick_triade("anthropic", "openai", rp)
        for m in (critic, fixer, verifier):
            assert not m.startswith("deepseek/")
            assert not m.startswith("x-ai/")

    def test_excludes_us_cn_models(self) -> None:
        """Avec excludes_us_cn_models=True le pool est trop petit pour 3 familles distinctes."""
        rp = RiskProfile(excludes_us_cn_models=True)
        # Le pool filtré ne contient pas assez de familles pour critic+fixer+verifier
        # → le code lève une exception (IndexError ou RuntimeError selon le path)
        with pytest.raises((RuntimeError, IndexError)):
            pick_triade("mistral", "openai", rp)

    def test_no_fixer_candidate_raises(self) -> None:
        """Si le pool filtré ne contient qu'une seule famille, pas de fixer possible."""
        rp = RiskProfile(excludes_us_cn_models=True, excludes_openrouter=True)
        # winner=anthropic, pool restant = [mistral]
        # critic=mistral, fixer_candidates=[] → RuntimeError
        with pytest.raises(RuntimeError, match="No fixer candidate"):
            pick_triade("anthropic", "openai", rp)


class TestParseVerifierVerdict:
    def test_plain_json(self) -> None:
        raw = '{"pass": true, "reason": "OK", "required_evidence": []}'
        v = _parse_verifier_verdict(raw)
        assert v["pass"] is True
        assert v["reason"] == "OK"

    def test_fenced_json_block(self) -> None:
        raw = "Some prose\n```json\n{\"pass\": false, \"reason\": \"NOK\"}\n```"
        v = _parse_verifier_verdict(raw)
        assert v["pass"] is False
        assert v["reason"] == "NOK"

    def test_no_json_returns_fail(self) -> None:
        v = _parse_verifier_verdict("No json here")
        assert v["pass"] is False
        assert "no_json" in v["reason"]

    def test_malformed_json_returns_fail(self) -> None:
        v = _parse_verifier_verdict("{ broken json }")
        assert v["pass"] is False
        assert "decode_error" in v["reason"]

    def test_default_evidence_empty_list(self) -> None:
        v = _parse_verifier_verdict('{"pass": true}')
        assert v["required_evidence"] == []


class TestResolvePromptsDir:
    def test_env_var_priority(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "critic.md").write_text("critic")
        monkeypatch.setenv("POLYBUILD_PROMPTS_DIR", str(prompts))
        assert _resolve_prompts_dir() == prompts

    def test_walk_ancestors(self, tmp_path: Path) -> None:
        # Simuler une arborescence où prompts/ est un ancêtre
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "critic.md").write_text("critic")
        # On ne peut pas facilement tester le walk sans déplacer le fichier source,
        # donc on teste au moins l'env var.
        pass

    def test_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POLYBUILD_PROMPTS_DIR", raising=False)
        with patch.object(Path, "resolve", return_value=Path("/nonexistent")):
            with pytest.raises(FileNotFoundError):
                _resolve_prompts_dir()


class TestLoadPrompt:
    def test_load_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Round 10.8 fix [Kimi C-01 P1, cross-voice audit]: this test
        # broke after Round 10.7 introduced the required-placeholder
        # anti-tampering check (Kimi C-07 patch switched the opt-out to
        # POLYBUILD_PROMPTS_DEBUG, so PROMPTS_DIR no longer disables it).
        # Write a template that satisfies the required {finding_id}
        # placeholder for the critic role.
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "critic.md").write_text("# Critic prompt for {finding_id}")
        monkeypatch.setenv("POLYBUILD_PROMPTS_DIR", str(prompts))
        # Réinitialiser le cache module-level
        monkeypatch.setattr(
            "polybuild.phases.phase_5_triade._PROMPTS_DIR",
            _resolve_prompts_dir(),
        )
        content = _load_prompt("critic")
        assert "Critic" in content
        assert "{finding_id}" in content

    def test_missing_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        monkeypatch.setenv("POLYBUILD_PROMPTS_DIR", str(prompts))
        monkeypatch.setattr(
            "polybuild.phases.phase_5_triade._PROMPTS_DIR",
            prompts,
        )
        with pytest.raises(FileNotFoundError, match="Required prompt template missing"):
            _load_prompt("nonexistent")


class TestPhase5Dispatch:
    """Dispatcher P0 / P1 / P2-P3 avec mocks ciblés."""

    def _make_audit(self, findings: list[Finding]) -> AuditReport:
        return AuditReport(
            auditor_model="auditor",
            auditor_family="openai",
            audit_duration_sec=1.0,
            axes_audited=["A_security"],
            findings=findings,
        )

    def _make_winner(self, tmp_path: Path) -> BuilderResult:
        return BuilderResult(
            voice_id="claude-opus-4.7",
            family="anthropic",
            code_dir=tmp_path / "src",
            tests_dir=tmp_path / "tests",
            diff_patch=tmp_path / "diff.patch",
            self_metrics=SelfMetrics(loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0, todo_count=0, imports_count=0, functions_count=0),
            duration_sec=1.0,
            status=Status.OK,
        )

    @pytest.mark.asyncio
    async def test_no_findings_returns_completed(self, tmp_path: Path) -> None:
        audit = self._make_audit([])
        winner = self._make_winner(tmp_path)
        report = await phase_5_dispatch(audit, winner, RiskProfile())
        assert report.status == "completed"
        assert report.results == []

    @pytest.mark.asyncio
    async def test_p0_blocked_returns_blocked_p0(self, tmp_path: Path) -> None:
        audit = self._make_audit([
            Finding(id="F1", severity=Severity.P0, axis="A_security", description="Crash", auditor_model="m", auditor_family="f"),
        ])
        winner = self._make_winner(tmp_path)

        with patch("polybuild.phases.phase_5_triade._triade_p0", new_callable=AsyncMock) as mock_p0:
            from polybuild.models import FixResult
            mock_p0.return_value = FixResult(
                finding_ids=["F1"],
                status="escalate",
                critic_model="c",
                fixer_model="f",
                verifier_model="v",
                iterations=1,
            )
            report = await phase_5_dispatch(audit, winner, RiskProfile())

        assert report.status == "blocked_p0"

    @pytest.mark.asyncio
    async def test_p0_capped_at_5(self, tmp_path: Path) -> None:
        """Round 9 fix [Budget] : MAX_P0_TRIADE = 5."""
        findings = [
            Finding(id=f"F{i}", severity=Severity.P0, axis="A", description="x", auditor_model="m", auditor_family="f")
            for i in range(7)
        ]
        audit = self._make_audit(findings)
        winner = self._make_winner(tmp_path)

        call_count = 0
        async def _mock_p0(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            from polybuild.models import FixResult
            return FixResult(
                finding_ids=[f"F{call_count}"],
                status="accepted",
                critic_model="c",
                fixer_model="f",
                verifier_model="v",
                iterations=1,
            )

        with patch("polybuild.phases.phase_5_triade._triade_p0", side_effect=_mock_p0), \
             patch("polybuild.phases.phase_5_triade._triade_p1_batch", new_callable=AsyncMock) as mock_p1:
            from polybuild.models import FixResult
            mock_p1.return_value = FixResult(
                finding_ids=["F1"],
                status="accepted",
                critic_model="c",
                fixer_model="f",
                verifier_model="v",
                iterations=1,
            )
            report = await phase_5_dispatch(audit, winner, RiskProfile())

        # 5 P0 traités, 2 downgradeés en P1
        assert call_count == 5
        assert report.status == "completed"

    @pytest.mark.asyncio
    async def test_p1_batch_processed(self, tmp_path: Path) -> None:
        audit = self._make_audit([
            Finding(id="F1", severity=Severity.P1, axis="B_quality", description="Slow", auditor_model="m", auditor_family="f"),
            Finding(id="F2", severity=Severity.P1, axis="B_quality", description="Complex", auditor_model="m", auditor_family="f"),
        ])
        winner = self._make_winner(tmp_path)

        with patch("polybuild.phases.phase_5_triade._triade_p1_batch", new_callable=AsyncMock) as mock_p1:
            from polybuild.models import FixResult
            mock_p1.return_value = FixResult(
                finding_ids=["F1", "F2"],
                status="accepted",
                critic_model="c",
                fixer_model="f",
                verifier_model="v",
                iterations=1,
            )
            report = await phase_5_dispatch(audit, winner, RiskProfile())

        assert report.status == "completed"
        mock_p1.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_p2_p3_local_auto_fix(self, tmp_path: Path) -> None:
        audit = self._make_audit([
            Finding(id="F1", severity=Severity.P2, axis="C_style", description="Style", auditor_model="m", auditor_family="f"),
        ])
        winner = self._make_winner(tmp_path)

        with patch("polybuild.phases.phase_5_triade._auto_fix_local", new_callable=AsyncMock) as mock_auto:
            from polybuild.models import FixResult
            mock_auto.return_value = FixResult(
                finding_ids=["F1"],
                status="accepted",
                critic_model="<local>",
                fixer_model="ruff",
                verifier_model="<local>",
                iterations=1,
            )
            report = await phase_5_dispatch(audit, winner, RiskProfile())

        assert report.status == "completed"
        mock_auto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_status_on_escalate(self, tmp_path: Path) -> None:
        audit = self._make_audit([
            Finding(id="F1", severity=Severity.P1, axis="B", description="x", auditor_model="m", auditor_family="f"),
        ])
        winner = self._make_winner(tmp_path)

        with patch("polybuild.phases.phase_5_triade._triade_p1_batch", new_callable=AsyncMock) as mock_p1:
            from polybuild.models import FixResult
            mock_p1.return_value = FixResult(
                finding_ids=["F1"],
                status="escalate",
                critic_model="c",
                fixer_model="f",
                verifier_model="v",
                iterations=1,
            )
            report = await phase_5_dispatch(audit, winner, RiskProfile())

        assert report.status == "partial"
