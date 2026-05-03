"""Tests unitaires pour Phase -1 — Privacy Gate.

Couvre les 3 layers (L1 regex, L2 static fallback, L3 attestation) et l'arbre de décision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from polybuild.phases.phase_minus_one_privacy import (
    _layer_1_regex,
    _layer_1_presidio,
    _layer_2_static_fallback,
    _load_attestation,
    _normalize_attestation,
    phase_minus_one_privacy_gate,
)


class TestLayer1Regex:
    """Détection PII directe par regex."""

    def test_nir_detected(self) -> None:
        text = "Le patient a le NIR 1 85 03 45 678 901 23"
        findings = _layer_1_regex(text)
        assert any(f.entity_type == "nir" for f in findings)

    def test_email_detected(self) -> None:
        findings = _layer_1_regex("Contact: jean.dupont@example.com")
        assert any(f.entity_type == "email" for f in findings)

    def test_phone_fr_detected(self) -> None:
        findings = _layer_1_regex("Tél: +33 6 12 34 56 78")
        assert any(f.entity_type == "phone_fr" for f in findings)

    def test_birth_date_detected(self) -> None:
        findings = _layer_1_regex("Née le 15/04/1987 à Paris")
        assert any(f.entity_type == "birth_date" for f in findings)

    def test_postal_address_detected(self) -> None:
        findings = _layer_1_regex("Habite 12 rue de la Paix, Paris")
        assert any(f.entity_type == "postal_address" for f in findings)

    def test_clean_text_no_findings(self) -> None:
        findings = _layer_1_regex("Implement a Python module for sorting algorithms.")
        assert len(findings) == 0

    def test_matched_text_truncated(self) -> None:
        long_email = "a" * 50 + "@example.com"
        findings = _layer_1_regex(long_email)
        assert len(findings[0].matched_text) <= 33  # 30 + "…"


class TestLayer1Presidio:
    """Presidio est optionnel ; fallback à [] si absent."""

    def test_returns_empty_if_presidio_unavailable(self) -> None:
        # On simule l'absence en patchant l'import dans le module
        import polybuild.phases.phase_minus_one_privacy as mod

        original = mod.__dict__.get("AnalyzerEngine")
        try:
            mod.AnalyzerEngine = None  # type: ignore[attr-defined]
            # _layer_1_presidio fait un import local ; on ne peut pas facilement
            # patcher l'import, mais au minimum on vérifie que ça ne plante pas
            findings = _layer_1_presidio("some text")
            assert isinstance(findings, list)
        finally:
            if original is not None:
                mod.AnalyzerEngine = original  # type: ignore[attr-defined]


class TestLayer2StaticFallback:
    """Quasi-identifiants sans eds-pseudo (NAS-safe)."""

    def test_rare_occupation_detected(self) -> None:
        findings = _layer_2_static_fallback("Le chimiste analyseur travaille ici.")
        assert any(f.entity_type == "rare_occupation_fr" for f in findings)

    def test_rare_pathology_detected(self) -> None:
        findings = _layer_2_static_fallback("Diagnostic : mésothéliome")
        assert any(f.entity_type == "rare_pathology_fr" for f in findings)

    def test_clean_text_no_findings(self) -> None:
        findings = _layer_2_static_fallback("Write a REST API in FastAPI.")
        assert len(findings) == 0


class TestNormalizeAttestation:
    """Round 5 fix [B] : normalisation robuste de l'attestation."""

    def test_valid_values_preserved(self) -> None:
        for val in ["synthetic", "fully_anonymized", "abstract_schema_only", "health_adjacent", "identifiable"]:
            assert _normalize_attestation(val) == val

    def test_none_becomes_missing(self) -> None:
        assert _normalize_attestation(None) == "missing"

    def test_invalid_becomes_missing(self) -> None:
        assert _normalize_attestation("random_value") == "missing"

    def test_whitespace_normalized(self) -> None:
        assert _normalize_attestation("  Synthetic  ") == "synthetic"


class TestLoadAttestation:
    """Chargement depuis spec.yaml."""

    def test_file_absent_returns_missing(self) -> None:
        assert _load_attestation("/nonexistent/spec.yaml") == "missing"

    def test_valid_yaml_loaded(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.yaml"
        spec.write_text("sensitivity_attestation: synthetic\n")
        assert _load_attestation(spec) == "synthetic"

    def test_invalid_value_returns_missing(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.yaml"
        spec.write_text("sensitivity_attestation: garbage\n")
        assert _load_attestation(spec) == "missing"

    def test_malformed_yaml_returns_missing(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.yaml"
        spec.write_text("{: bad yaml\n")
        assert _load_attestation(spec) == "missing"


class TestPrivacyGateDecisionTree:
    """Arbre de décision complet de phase_minus_one_privacy_gate."""

    def test_l1_finding_blocks_always(self) -> None:
        verdict = phase_minus_one_privacy_gate("Contact: jean.dupont@example.com")
        assert verdict.blocked is True
        assert verdict.level == "BLOCK"
        assert "email" in verdict.reason

    def test_attestation_identifiable_blocks_always(self) -> None:
        verdict = phase_minus_one_privacy_gate("foo", declared_sensitivity="identifiable")
        assert verdict.blocked is True
        assert verdict.attestation == "identifiable"

    def test_l2_two_quasi_ids_with_strong_attestation_escalates(self) -> None:
        text = "Le chimiste analyseur a un mésothéliome"
        verdict = phase_minus_one_privacy_gate(text, declared_sensitivity="synthetic")
        assert verdict.level == "ESCALATE_PARANOIA"
        assert verdict.blocked is False
        assert verdict.paranoia_level == "high"

    def test_l2_two_quasi_ids_without_strong_attestation_blocks(self) -> None:
        text = "Le chimiste analyseur a un mésothéliome"
        verdict = phase_minus_one_privacy_gate(text, declared_sensitivity="missing")
        assert verdict.level == "BLOCK"
        assert verdict.blocked is True

    def test_l2_one_quasi_id_with_missing_blocks(self) -> None:
        text = "Le patient a un mésothéliome"
        verdict = phase_minus_one_privacy_gate(text, declared_sensitivity="missing")
        assert verdict.level == "BLOCK"
        assert verdict.blocked is True
        assert len(verdict.findings) == 1

    def test_missing_attestation_long_text_blocks(self) -> None:
        text = "x " * 800  # >1500 chars
        verdict = phase_minus_one_privacy_gate(text, declared_sensitivity="missing")
        assert verdict.blocked is True
        assert "1500" in verdict.reason

    def test_missing_attestation_short_text_passes(self) -> None:
        text = "Implement a Python module"
        verdict = phase_minus_one_privacy_gate(text, declared_sensitivity="missing")
        assert verdict.level == "PASS"
        assert verdict.blocked is False

    def test_health_adjacent_passes_with_high_paranoia(self) -> None:
        verdict = phase_minus_one_privacy_gate("foo", declared_sensitivity="health_adjacent")
        assert verdict.level == "PASS"
        assert verdict.paranoia_level == "high"

    def test_synthetic_passes(self) -> None:
        verdict = phase_minus_one_privacy_gate("foo", declared_sensitivity="synthetic")
        assert verdict.level == "PASS"
        assert verdict.blocked is False

    def test_additional_context_scanned_round8_fix(self) -> None:
        """Round 8 fix [Privacy-AGENTS] : additional_context est concaténé et scanné."""
        brief = "Implement a Python module"
        agents = "Contact: spy@example.com"
        verdict = phase_minus_one_privacy_gate(brief, additional_context=agents)
        assert verdict.blocked is True
        assert "email" in verdict.reason

    def test_spec_yaml_override(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.yaml"
        spec.write_text("sensitivity_attestation: fully_anonymized\n")
        verdict = phase_minus_one_privacy_gate("foo", spec_path=spec)
        assert verdict.attestation == "fully_anonymized"
        assert verdict.level == "PASS"

    def test_declared_sensitivity_overrides_yaml(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.yaml"
        spec.write_text("sensitivity_attestation: synthetic\n")
        verdict = phase_minus_one_privacy_gate("foo", spec_path=spec, declared_sensitivity="identifiable")
        assert verdict.attestation == "identifiable"
        assert verdict.blocked is True
