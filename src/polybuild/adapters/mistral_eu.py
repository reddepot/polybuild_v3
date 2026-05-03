"""Mistral EU direct adapter (api.mistral.ai).

CRITICAL: This adapter calls api.mistral.ai DIRECTLY, bypassing OpenRouter.
Reason: OpenRouter routes through US infra, breaking EU jurisdiction.
For medical profiles (paranoia medium/high), we need EU-only routing.

Used for Devstral 2 (123B agentic, EU-certified, MIT modified).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()

MISTRAL_BASE = "https://api.mistral.ai/v1"


class MistralEUAdapter(BuilderProtocol):
    """Direct Mistral EU adapter for medical/sensitive profiles.

    Args:
        slug: Mistral model slug (e.g. "devstral-2", "codestral-25.10")
        api_key_env: env var holding the Mistral API key
    """

    family = "mistral"

    def __init__(
        self,
        slug: str = "devstral-2",
        api_key_env: str = "MISTRAL_EU_API_KEY",
    ):
        self.slug = slug
        self.name = f"mistral_eu_{slug.replace('-', '_').replace('.', '_')}"
        self.api_key = os.environ.get(api_key_env)
        if not self.api_key:
            logger.warning(
                "mistral_eu_no_api_key",
                env_var=api_key_env,
                slug=slug,
            )

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
                response = await client.post(
                    f"{MISTRAL_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.slug,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a builder voice in POLYBUILD v3. "
                                    "Output STRICT JSON matching the schema. EU-only data residency."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.4,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                duration = time.monotonic() - start
                return self._parse_response(content, worktree, cfg, duration)

        except httpx.TimeoutException:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                "mistral_eu_http_error",
                slug=self.slug,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            return self._failed_result(cfg, worktree, duration, str(e))

    async def smoke_test(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{MISTRAL_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.slug,
                        "messages": [
                            {"role": "user", "content": "Reply JSON: {\"ok\": true}"},
                        ],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 50,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content).get("ok") is True
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            return False

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{MISTRAL_BASE}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / cfg.voice_id.replace("/", "_")
        )
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / "src").mkdir(exist_ok=True)
        (worktree / "tests").mkdir(exist_ok=True)
        return worktree

    def _build_prompt(self, spec: Spec, cfg: VoiceConfig, worktree: Path) -> str:
        # Round 7 fix [O3] (Gemini P0 + ChatGPT CONDITIONAL_GO):
        # When called from Phase 5 triade via run_raw_prompt(), the synthetic
        # Spec.task_description IS the actual prompt (critic/fixer/verifier
        # template). Wrapping it in <AGENTS_MD>/<TASK_PROFILE>/<INSTRUCTIONS>
        # would inject a contradictory "Generate a complete Python module"
        # directive — making the model hallucinate file creation in a JSON
        # response. We bypass the wrapper entirely.
        if cfg.context.get("raw_prompt"):
            return spec.task_description

        agents_md = self._load_agents_md()
        return f"""<AGENTS_MD>
{agents_md}
</AGENTS_MD>

<TASK>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</TASK>

<OUTPUT_SCHEMA>
{{
  "files": {{
    "src/<name>.py": "...",
    "tests/test_<name>.py": "..."
  }},
  "self_metrics": {{
    "loc": <int>,
    "complexity_cyclomatic_avg": <float>,
    "test_to_code_ratio": <float>,
    "todo_count": <int>,
    "imports_count": <int>,
    "functions_count": <int>
  }}
}}
</OUTPUT_SCHEMA>

EU-only routing. Output ONLY valid JSON.
"""

    def _load_agents_md(self) -> str:
        """Load AGENTS.md sanitized through sanitize_prompt_context.

        Round 10.2.1 fix [ChatGPT RX-001 P0 + Kimi RX-007 P1] — adapters
        were embedding the raw file content into the LLM prompt, bypassing
        the sanitization the orchestrator applied for the privacy gate.
        We now sanitize at every injection point as defence in depth.
        """
        from polybuild.security.prompt_sanitizer import sanitize_prompt_context
        local = Path("AGENTS.md")
        if local.exists():
            return sanitize_prompt_context(local.read_text())
        return sanitize_prompt_context("# AGENTS.md\n(none)")

    def _parse_response(
        self, content: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return self._failed_result(cfg, worktree, duration, f"Invalid JSON: {e}")

        # Round 10.8 fix [ChatGPT A-02 + Kimi A-01, 2/5 cross-voice P0]:
        # same path traversal as the ollama_local + openrouter adapters.
        # Use shared helper for consistency.
        from polybuild.security.safe_write import write_files_to_worktree

        if not isinstance(data, dict):
            return self._failed_result(
                cfg, worktree, duration,
                f"Response JSON not a dict (got {type(data).__name__})",
            )
        write_files_to_worktree(
            data.get("files", {}), worktree, adapter_name="mistral_eu"
        )
        metrics_data = data.get("self_metrics", {})
        if not isinstance(metrics_data, dict):
            metrics_data = {}
        metrics = SelfMetrics(
            loc=metrics_data.get("loc", 0),
            complexity_cyclomatic_avg=metrics_data.get("complexity_cyclomatic_avg", 0.0),
            test_to_code_ratio=metrics_data.get("test_to_code_ratio", 0.0),
            todo_count=metrics_data.get("todo_count", 0),
            imports_count=metrics_data.get("imports_count", 0),
            functions_count=metrics_data.get("functions_count", 0),
        )

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=content,
        )

    def _timeout_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"Mistral EU timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self, cfg: VoiceConfig, worktree: Path, duration: float, reason: str
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0, complexity_cyclomatic_avg=0.0, test_to_code_ratio=0.0,
                todo_count=0, imports_count=0, functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )
