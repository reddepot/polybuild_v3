"""Core Pydantic models shared across all pipeline phases.

These are the canonical contracts used by every adapter, phase, and gate.
Any change here must be tracked via an ADR.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ────────────────────────────────────────────────────────────────
# COMMON ENUMS
# ────────────────────────────────────────────────────────────────


class Severity(StrEnum):
    """Finding severity levels."""

    P0 = "P0"  # Sécurité, crash, hallucination critique
    P1 = "P1"  # Qualité, archi, perf
    P2 = "P2"  # Style, nommage
    P3 = "P3"  # Cosmétique


class Status(StrEnum):
    """Generic status for builders, fixes, validations."""

    OK = "ok"
    TIMEOUT = "timeout"
    FAILED = "failed"
    DISQUALIFIED = "disqualified"
    ESCALATED = "escalated"


class PrivacyLevel(StrEnum):
    """Privacy/sensitivity classification for medical profile (Phase -1)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ────────────────────────────────────────────────────────────────
# SPEC
# ────────────────────────────────────────────────────────────────


class AcceptanceCriterion(BaseModel):
    """A single executable acceptance criterion."""

    id: str
    description: str
    test_command: str  # ex: "pytest tests/test_x.py::test_y"
    blocking: bool = True


class RiskProfile(BaseModel):
    """Risk profile of the task, drives Phase 1 voice selection."""

    sensitivity: PrivacyLevel = PrivacyLevel.LOW
    code_inedit_critique: bool = False
    requires_probe: bool = False
    audit_axes: list[str] = Field(default_factory=list)
    domain_gates: list[str] = Field(default_factory=list)
    excludes_openrouter: bool = False
    excludes_us_cn_models: bool = False


class Spec(BaseModel):
    """Canonical specification for a POLYBUILD run.

    Output of Phase 0 (Opus 4.7). Hashed and verified through Phase 6.
    """

    model_config = ConfigDict(frozen=False)

    run_id: str
    profile_id: str  # ex: "module_inedit_critique", "helia_algo"
    task_description: str
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion]
    interfaces: dict[str, Any] = Field(default_factory=dict)  # Pydantic schemas, DB schemas
    risk_profile: RiskProfile
    spec_hash: str = ""  # SHA-256, calculé après Phase 0c
    # Round 10.7 fix [POLYLENS v3 Qwen B-02 P2]: the previous default
    # factory used a deprecated naive UTC API. Use a timezone-aware
    # ``datetime.now(UTC)`` factory instead.
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpecAttack(BaseModel):
    """Output of Phase 0b — challenger critique without code generation."""

    challenger_model: str
    missing_invariants: list[str] = Field(default_factory=list)
    ambiguous_terms: list[str] = Field(default_factory=list)
    untestable_acceptance: list[str] = Field(default_factory=list)
    unsafe_assumptions: list[str] = Field(default_factory=list)
    rgpd_risks: list[str] = Field(default_factory=list)
    edge_cases_missed: list[str] = Field(default_factory=list)

    def has_critical_findings(self) -> bool:
        return bool(
            self.missing_invariants
            or self.untestable_acceptance
            or self.rgpd_risks
        )


# ────────────────────────────────────────────────────────────────
# PHASE 1 — VOICE SELECTION
# ────────────────────────────────────────────────────────────────


class VoiceConfig(BaseModel):
    """Configuration for a single voice in Phase 2."""

    voice_id: str  # ex: "claude-opus-4.7", "deepseek/deepseek-v4-pro"
    family: str    # ex: "anthropic", "deepseek"
    role: Literal["builder", "auditor", "fixer", "verifier", "critic", "judge"]
    timeout_sec: int = 720
    context: dict[str, Any] = Field(default_factory=dict)


# ────────────────────────────────────────────────────────────────
# PHASE 2 — BUILDER OUTPUT
# ────────────────────────────────────────────────────────────────


class SelfMetrics(BaseModel):
    """Self-reported metrics by each voice (for Phase 3 anti-gaming checks)."""

    loc: int
    complexity_cyclomatic_avg: float
    test_to_code_ratio: float
    todo_count: int
    imports_count: int
    functions_count: int


class BuilderResult(BaseModel):
    """Normalized output of a single voice in Phase 2."""

    voice_id: str
    family: str
    code_dir: Path
    tests_dir: Path
    diff_patch: Path
    self_metrics: SelfMetrics
    duration_sec: float
    status: Status
    raw_output: str = ""
    error: str | None = None


# ────────────────────────────────────────────────────────────────
# PHASE 3 — SCORING
# ────────────────────────────────────────────────────────────────


class GateResults(BaseModel):
    """Output of running general gates on a builder's worktree."""

    acceptance_pass_ratio: float
    bandit_clean: bool
    mypy_strict_clean: bool
    ruff_clean: bool
    coverage_score: float
    gitleaks_clean: bool
    gitleaks_findings_count: int
    diff_minimality: float
    pro_gap_penalty: float = 0.0
    domain_score: float = 0.0
    raw_outputs: dict[str, str] = Field(default_factory=dict)


class VoiceScore(BaseModel):
    """Final score and verdict for a single voice.

    POLYLENS run #4 P1 (Grok 4.3): ``is_solo_stub`` flags entries
    synthesised by ``SoloPipeline`` when Phase 3 is skipped — the
    score is not the result of a real comparison, it's a placeholder
    so ``PolybuildRun`` aggregation and downstream metrics keep
    working. Dashboards and ``--scorer=devcode`` calibration MUST
    filter out stub entries when computing averages, or they end up
    treating a single-voice solo run as a perfect 1.0-score run.
    """

    voice_id: str
    score: float
    gates: GateResults
    disqualified: bool = False
    disqualification_reason: str | None = None
    is_solo_stub: bool = False


# ────────────────────────────────────────────────────────────────
# PHASE 3B — GROUNDING
# ────────────────────────────────────────────────────────────────


class GroundingFinding(BaseModel):
    """A single grounding violation detected via AST analysis."""

    severity: Severity
    voice_id: str
    kind: Literal[
        "syntax_error",
        "hallucinated_import",
        "hallucinated_import_from",
        "missing_internal_symbol",
        "unverified_external_api",
    ]
    detail: str
    file: Path | None = None
    line: int | None = None


# ────────────────────────────────────────────────────────────────
# PHASE 4 — AUDIT
# ────────────────────────────────────────────────────────────────


class FindingEvidence(BaseModel):
    """Reproducible evidence supporting a finding."""

    file: Path
    line: int | None = None
    snippet: str | None = None
    reproducer: str | None = None  # ex: "pytest tests/test_x.py::test_y"


class Finding(BaseModel):
    """A single audit finding from Phase 4 (POLYLENS)."""

    id: str
    severity: Severity
    axis: str  # ex: "A_security", "B_quality"
    description: str
    evidence: FindingEvidence | None = None
    auditor_model: str
    auditor_family: str


class AuditReport(BaseModel):
    """Output of Phase 4 — orthogonal audit."""

    auditor_model: str
    auditor_family: str
    audit_duration_sec: float
    axes_audited: list[str]
    findings: list[Finding] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


# ────────────────────────────────────────────────────────────────
# PHASE 5 — TRIADE
# ────────────────────────────────────────────────────────────────


class VerifierVerdict(BaseModel):
    """Strict JSON-only verdict from a Verifier LLM. Never rewrites code."""

    pass_: bool = Field(alias="pass")
    reason: str
    required_evidence: str = ""

    model_config = ConfigDict(populate_by_name=True)


class FixResult(BaseModel):
    """Result of a single triade execution (P0 individual or P1 batch)."""

    finding_ids: list[str]
    status: Literal["accepted", "accepted_after_retry", "escalate", "tools_failed"]
    critic_model: str
    fixer_model: str
    verifier_model: str
    iterations: int
    patch_path: Path | None = None
    verifier_verdict: VerifierVerdict | None = None


class FixReport(BaseModel):
    """Aggregated output of Phase 5."""

    status: Literal["completed", "blocked_p0", "partial"]
    results: list[FixResult]


# ────────────────────────────────────────────────────────────────
# PHASE 6 — VALIDATION
# ────────────────────────────────────────────────────────────────


class ValidationVerdict(BaseModel):
    """Final validation verdict before commit."""

    passed: bool
    general_gates: GateResults
    domain_gates_passed: bool
    domain_gates_results: dict[str, bool] = Field(default_factory=dict)
    spec_drift_detected: bool = False
    notes: list[str] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────
# PHASE 7 — COMMIT & ADR
# ────────────────────────────────────────────────────────────────


class CommitInfo(BaseModel):
    """Git commit metadata."""

    sha: str
    message: str
    tag_pre: str  # ex: "polybuild/run-{run_id}-pre"
    tag_post: str  # ex: "polybuild/run-{run_id}-commit"
    files_changed: list[Path]
    adr_id: str | None = None


# ────────────────────────────────────────────────────────────────
# RUN-LEVEL AGGREGATE
# ────────────────────────────────────────────────────────────────


class TokenUsage(BaseModel):
    """Token usage by provider."""

    claude_max_input: int = 0
    claude_max_output: int = 0
    chatgpt_pro_input: int = 0
    chatgpt_pro_output: int = 0
    gemini_pro_input: int = 0
    gemini_pro_output: int = 0
    kimi_allegretto_input: int = 0
    kimi_allegretto_output: int = 0
    openrouter_input: int = 0
    openrouter_output: int = 0
    mistral_eu_input: int = 0
    mistral_eu_output: int = 0
    ollama_local_input: int = 0
    ollama_local_output: int = 0


class PolybuildRun(BaseModel):
    """Top-level aggregate for a POLYBUILD run, archived to disk."""

    run_id: str
    profile_id: str
    spec_hash: str
    voices_used: list[str]
    winner_voice_id: str | None
    scores: dict[str, float]
    audit_findings_by_severity: dict[str, int]
    fix_iterations: dict[str, int]
    domain_gates_passed: bool
    duration_total_sec: float
    tokens: TokenUsage
    cost_eur_marginal: float = 0.0
    # Round 10.8 POLYLENS [Codex B_quality-02 P2]: ``validated`` for
    # dry-runs (--no-commit) where Phase 7 is bypassed but the pipeline
    # ran successfully through Phase 6. Distinguishes from ``committed``
    # (Phase 7 wrote the commit) and ``aborted`` (something failed).
    final_status: Literal["committed", "validated", "aborted", "rolled_back"]
    commit_sha: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
