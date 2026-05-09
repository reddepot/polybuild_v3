"""BuilderProtocol — abstract interface implemented by every model adapter.

Every model (CLI or OpenRouter or local Ollama) exposes the same async API.
This is the contract that makes Phase 2 parallel orchestration possible.

Round 5 fix [O] (Audit 2 P0): added concrete `run_raw_prompt()` method with a
default implementation. Phase 5 triade was calling
`builder.generate(prompt=..., workdir=..., timeout_s=..., role=...)` which does
not match `generate(self, spec, cfg)` — would have crashed all 7 adapters with
TypeError. The default impl synthesises a minimal Spec+VoiceConfig.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, TypeAlias

from polybuild.models import (
    AcceptanceCriterion,
    BuilderResult,
    RiskProfile,
    Spec,
    VoiceConfig,
)

VoiceRole: TypeAlias = Literal[
    "builder", "auditor", "fixer", "verifier", "critic", "judge"
]


class BuilderProtocol(ABC):
    """Abstract base class for all builders.

    Implementations:
        - ClaudeCodeAdapter (CLI)
        - CodexCLIAdapter (CLI)
        - GeminiCLIAdapter (CLI)
        - KimiCLIAdapter (CLI)
        - OpenRouterAdapter (HTTP)
        - MistralEUAdapter (HTTP, api.mistral.ai direct)
        - OllamaLocalAdapter (HTTP local)
    """

    name: str  # ex: "claude_code_opus", "openrouter_deepseek_v4_pro"
    family: str  # ex: "anthropic", "deepseek"

    @abstractmethod
    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Generate a complete code module from the spec.

        Must:
            1. Create a worktree under .polybuild/runs/{run_id}/worktrees/{voice_id}/
            2. Inject AGENTS.md + relevant memory in the prompt
            3. Respect cfg.timeout_sec (asyncio.wait_for)
            4. Return a BuilderResult with normalized fields

        Must NOT:
            - Modify the production code directly
            - Bypass the privacy gate for sensitive profiles
            - Cross-talk with other voices (no shared state)
        """

    @abstractmethod
    async def smoke_test(self) -> bool:
        """Quick sanity check that the adapter works.

        Sends a deterministic prompt and verifies the output structure.
        Used by `polybuild test-cli` (weekly cron + pre-run cache).
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the underlying CLI/API is reachable.

        Lightweight check (e.g. version query). Used before invoking generate().
        """

    async def run_raw_prompt(
        self,
        prompt: str,
        workdir: Path,
        timeout_s: int = 600,
        role: str = "auditor",
        risk_profile: RiskProfile | None = None,
    ) -> str:
        """Run an ad-hoc prompt and return the model's raw text output.

        Round 5 [O]: used by Phase 5 triade (critic, fixer, verifier) where we
        don't want a full generate() pipeline (no spec, no acceptance criteria,
        no AGENTS.md injection). Default impl wraps generate() with a minimal
        synthetic Spec+VoiceConfig.

        Round 6 fix [O2]:
          - Audit 4: default impl violated "verifier never rewrites code" —
            generate() can create a worktree. Now we set
            `context["raw_prompt_no_write"]=True` which adapters MUST honor
            to short-circuit any worktree creation for verifier/critic roles.
          - Audit 6: default impl dropped risk_profile, losing medical_high
            constraints in Phase 5 prompts. Now propagated through context.

        Round 7 fix [O3] (Gemini P0 + ChatGPT CONDITIONAL_GO):
          The previous round-6 patch was insufficient. CLI adapters wrap any
          spec.task_description in `<INSTRUCTIONS>Generate a complete Python
          module...</INSTRUCTIONS>` via `_build_prompt()`, so feeding a
          critic/verifier prompt through the default `generate()` path
          produced two contradictory directives in a single message — the
          model would hallucinate JSON `files_written` instead of confirming
          a finding.

          Contract enforced now (NOT just convention):
          ALL implementations of `_build_prompt()` MUST check
          `cfg.context.get("raw_prompt")` and return `spec.task_description`
          unchanged when True. Tests live under tests/test_raw_prompt_bypass.py
          (sprint A) — 7/7 current adapters already comply.

        Adapters SHOULD override this method for efficiency (direct chat API,
        no worktree). The default keeps the contract intact when adapters
        comply with the `_build_prompt` bypass requirement.
        """
        valid_roles: tuple[VoiceRole, ...] = (
            "builder",
            "auditor",
            "fixer",
            "verifier",
            "critic",
            "judge",
        )
        normalized_role: VoiceRole = role if role in valid_roles else "auditor"

        # Round 6 [O2]: roles that must NEVER write to the filesystem.
        no_write_roles = {"critic", "verifier", "judge", "auditor"}
        no_write = normalized_role in no_write_roles

        # Round 10.7 fix [GLM A-04 P1]: ``hash()`` salts are randomized
        # per-process (``PYTHONHASHSEED=random`` is the default), so the
        # same prompt yields different ``run_id`` values across processes
        # — breaking dedup, caching, and reproducibility. Use a stable
        # cryptographic digest. ``[:12]`` keeps the suffix short while
        # still giving 48 bits of entropy.
        import hashlib

        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        synthetic_spec = Spec(
            run_id=f"raw-{normalized_role}-{prompt_digest}",
            profile_id=f"phase5_{normalized_role}",
            task_description=prompt,
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="raw-1",
                    description=f"Produce a valid {normalized_role} response",
                    test_command="echo 'phase5_raw_prompt_no_test'",
                    blocking=False,
                ),
            ],
            risk_profile=risk_profile or RiskProfile(),
        )
        synthetic_cfg = VoiceConfig(
            voice_id=self.name,
            family=self.family,
            role=normalized_role,
            timeout_sec=timeout_s,
            context={
                "phase5_workdir": str(workdir),
                "raw_prompt": True,
                # Round 6 [O2]: adapters honoring this flag must skip worktree
                # creation and any filesystem write — return raw text only.
                "raw_prompt_no_write": no_write,
            },
        )
        result = await self.generate(synthetic_spec, synthetic_cfg)
        return result.raw_output or ""
