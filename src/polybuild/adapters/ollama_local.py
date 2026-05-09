"""Ollama local adapter.

Calls a local Ollama HTTP endpoint. Used EXCLUSIVELY for medical
paranoia HIGH profile (no external calls).

Models:
    - qwen2.5-coder:14b-int4 (~9 GB)
    - qwen2.5-coder:7b-int4  (~5 GB)

NOTE: DeepSeek V3.2 INT4 (685B → ~340 GB) excluded — physically
impossible on a low-RAM box.
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


class OllamaLocalAdapter(BuilderProtocol):
    """Adapter for Ollama running locally.

    Args:
        slug: Ollama model tag (e.g. "qwen2.5-coder:14b-int4")
        endpoint: HTTP endpoint (default from ``OLLAMA_ENDPOINT`` env var)
    """

    family = "alibaba"  # Qwen models = Alibaba

    def __init__(
        self,
        slug: str = "qwen2.5-coder:14b-int4",
        endpoint: str | None = None,
    ):
        self.slug = slug
        self.endpoint = endpoint or os.environ.get(
            "OLLAMA_ENDPOINT", "http://nas.local:11434"
        )
        # Sanitize for adapter name
        safe = slug.replace(":", "_").replace("-", "_").replace(".", "_")
        self.name = f"ollama_local_{safe}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # Local model is slow (~3 tok/s); use generous timeout
        local_timeout = max(cfg.timeout_sec, 1800)

        try:
            async with httpx.AsyncClient(timeout=local_timeout) as client:
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.slug,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {
                            "temperature": 0.4,
                            "num_predict": 4096,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("response", "")
                duration = time.monotonic() - start
                return self._parse_response(content, worktree, cfg, duration)

        except httpx.TimeoutException:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                "ollama_local_http_error",
                slug=self.slug,
                status=e.response.status_code,
            )
            return self._failed_result(cfg, worktree, duration, str(e))

    async def smoke_test(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.slug,
                        "prompt": "Reply JSON: {\"ok\": true}",
                        "format": "json",
                        "stream": False,
                    },
                )
                response.raise_for_status()
                content = response.json().get("response", "")
                return json.loads(content).get("ok") is True
        except (httpx.HTTPError, json.JSONDecodeError):
            return False

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                if response.status_code != 200:
                    return False
                tags = response.json().get("models", [])
                return any(t.get("name") == self.slug for t in tags)
        except httpx.HTTPError:
            return False

    def _setup_worktree(self, spec: Spec, cfg: VoiceConfig) -> Path:
        safe = cfg.voice_id.replace(":", "_").replace("/", "_")
        worktree = (
            Path(".polybuild")
            / "runs"
            / spec.run_id
            / "worktrees"
            / safe
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
        # Local models = profil médical HIGH = pas de fuite externe possible par construction
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
  "self_metrics": {{"loc": 0, "complexity_cyclomatic_avg": 0.0, "test_to_code_ratio": 0.0, "todo_count": 0, "imports_count": 0, "functions_count": 0}}
}}
</OUTPUT_SCHEMA>

LOCAL EXECUTION. Output ONLY valid JSON.
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

        # Round 10.8 fix [ChatGPT A-01 + Kimi A-02, 2/5 cross-voice P0]:
        # path traversal — LLM-controlled ``rel_path`` was concatenated and
        # written without bounds checks (same bug Round 10.7 fixed in
        # ``openrouter._parse_response``, never propagated here). Use the
        # shared helper which enforces resolve + is_relative_to.
        from polybuild.security.safe_write import write_files_to_worktree

        if not isinstance(data, dict):
            return self._failed_result(
                cfg, worktree, duration,
                f"Response JSON not a dict (got {type(data).__name__})",
            )
        write_files_to_worktree(
            data.get("files", {}), worktree, adapter_name="ollama_local"
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
            error=f"Ollama local timeout after {cfg.timeout_sec}s",
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
