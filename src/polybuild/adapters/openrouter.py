"""OpenRouter HTTP adapter.

Used for the 3 irreplaceable OR models:
    - deepseek/deepseek-v4-pro (algo, audit, spec attack)
    - x-ai/grok-4.20 (verifier strict, LLM-as-judge)
    - deepseek/deepseek-v4-flash (probe 50 LOC, fallback)

Mistral EU (api.mistral.ai direct) uses a separate adapter, NOT this one,
to ensure jurisdiction is preserved.
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

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(BuilderProtocol):
    """Generic adapter for OpenRouter-hosted models."""

    def __init__(
        self,
        slug: str,
        family: str,
        api_key_env: str = "OPENROUTER_API_KEY",
    ):
        self.slug = slug  # e.g. "deepseek/deepseek-v4-pro"
        self.family = family  # e.g. "deepseek"
        self.name = f"openrouter_{slug.replace('/', '_').replace('-', '_').replace('.', '_')}"
        self.api_key = os.environ.get(api_key_env)
        if not self.api_key:
            logger.warning(
                "openrouter_no_api_key",
                env_var=api_key_env,
                slug=slug,
            )

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Call OpenRouter and parse the structured output."""
        # Refus de générer pour profils RGPD high
        if spec.risk_profile.excludes_openrouter:
            return BuilderResult(
                voice_id=cfg.voice_id,
                family=self.family,
                code_dir=Path("/dev/null"),
                tests_dir=Path("/dev/null"),
                diff_patch=Path("/dev/null"),
                self_metrics=SelfMetrics(
                    loc=0,
                    complexity_cyclomatic_avg=0.0,
                    test_to_code_ratio=0.0,
                    todo_count=0,
                    imports_count=0,
                    functions_count=0,
                ),
                duration_sec=0.0,
                status=Status.DISQUALIFIED,
                error="OpenRouter excluded by risk_profile (medical sensitive data)",
            )

        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: integrate concurrency_limiter (Faille 3)
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_sec) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://polybuild.local",
                        "X-Title": "POLYBUILD v3",
                    },
                    json={
                        "model": self.slug,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a builder voice in POLYBUILD v3. "
                                    "Output STRICT JSON only matching the schema in the prompt."
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
                # Round 10.7 fix [GLM A-05 + Qwen D-02, 2/5 conv P0]: OpenRouter
                # can return 200 with a body that omits ``choices`` (rate-limit
                # response, content-filter refusal, tool-call response with
                # ``content=None``). The previous direct subscript chain raised
                # ``KeyError``/``TypeError`` and crashed Phase 2 instead of
                # returning a graceful FAILED ``BuilderResult``.
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as e:
                    duration = time.monotonic() - start
                    logger.warning(
                        "openrouter_malformed_response",
                        slug=self.slug,
                        error=str(e),
                        body_preview=str(data)[:200],
                    )
                    return self._failed_result(
                        cfg, worktree, duration, f"Malformed OR response: {e}"
                    )
                if content is None:
                    duration = time.monotonic() - start
                    logger.warning("openrouter_null_content", slug=self.slug)
                    return self._failed_result(
                        cfg, worktree, duration, "OR returned content=null"
                    )
                duration = time.monotonic() - start
                return self._parse_response(content, worktree, cfg, duration)

        except httpx.TimeoutException:
            duration = time.monotonic() - start
            logger.warning("openrouter_timeout", slug=self.slug, timeout=cfg.timeout_sec)
            return self._timeout_result(cfg, worktree, duration)

        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            logger.error(
                "openrouter_http_error",
                slug=self.slug,
                status=e.response.status_code,
                body=e.response.text[:500],
            )
            return self._failed_result(cfg, worktree, duration, str(e))

    async def smoke_test(self) -> bool:
        """Verify OpenRouter access with the chosen model."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.slug,
                        "messages": [
                            {"role": "user", "content": "Reply with JSON: {\"ok\": true}"},
                        ],
                        "response_format": {"type": "json_object"},
                        "max_tokens": 50,
                    },
                )
                response.raise_for_status()
                data = response.json()
                # Round 10.7 fix [Codex validation PB-R107-OR-SMOKE-MALFORMED P1]:
                # apply the same malformed-response guard used in generate().
                # Previously we caught KeyError but not IndexError or TypeError,
                # and ``content=None`` reached ``json.loads(None)`` which raises.
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError):
                    return False
                if not isinstance(content, str):
                    return False
                parsed = json.loads(content)
                return isinstance(parsed, dict) and parsed.get("ok") is True
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            return False

    async def is_available(self) -> bool:
        """Check if OpenRouter API is reachable."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{OPENROUTER_BASE}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    # ────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ────────────────────────────────────────────────────────────

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

Output ONLY valid JSON matching the schema. No prose.
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
        self,
        content: str,
        worktree: Path,
        cfg: VoiceConfig,
        duration: float,
    ) -> BuilderResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return self._failed_result(cfg, worktree, duration, f"Invalid JSON: {e}")

        # Round 10.7 fix [Codex validation PB-R107-OR-PARSE-SHAPE P1]: a valid
        # JSON document might be a list, string, or null; without an
        # ``isinstance(data, dict)`` guard, ``data.get("files", {})`` raises
        # AttributeError. Same defence already applied at Phase 4 audit.
        if not isinstance(data, dict):
            return self._failed_result(
                cfg, worktree, duration, f"Response JSON not a dict (got {type(data).__name__})"
            )
        files = data.get("files", {})
        if not isinstance(files, dict):
            logger.warning(
                "openrouter_files_not_mapping",
                files_type=type(files).__name__,
            )
            files = {}
        metrics_data = data.get("self_metrics", {})
        if not isinstance(metrics_data, dict):
            metrics_data = {}

        # Write files to worktree
        # Round 10.7 fix [GLM A-01 P0]: ``rel_path`` is LLM-controlled and
        # ``Path(worktree) / rel_path`` resolves an absolute right-hand-side
        # to its absolute value (``worktree / "/etc/cron.d/x"`` →
        # ``/etc/cron.d/x``); ``..`` segments also escape the worktree.
        # Combined with prompt-injection vectors elsewhere this would let a
        # compromised builder write arbitrary host files.
        # Round 10.7 fix [GLM A-08 P1]: ``write_text`` raises ``TypeError``
        # if ``source`` is not a string (LLM may emit numbers / nested
        # objects under the file value). Skip+log non-string entries
        # rather than crashing the whole adapter response.
        worktree_resolved = worktree.resolve()
        for rel_path, source in files.items():
            if not isinstance(rel_path, str) or not isinstance(source, str):
                logger.warning(
                    "openrouter_skip_invalid_file_entry",
                    rel_path=str(rel_path)[:120],
                    rel_path_type=type(rel_path).__name__,
                    source_type=type(source).__name__,
                )
                continue
            try:
                abs_path = (worktree / rel_path).resolve()
            except (OSError, ValueError) as e:
                logger.warning(
                    "openrouter_path_resolve_failed",
                    rel_path=rel_path,
                    error=str(e),
                )
                continue
            if not abs_path.is_relative_to(worktree_resolved):
                logger.warning(
                    "openrouter_path_traversal_blocked",
                    rel_path=rel_path,
                    abs_path=str(abs_path),
                )
                continue
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(source)

        metrics_data = data.get("self_metrics", {})
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
        self,
        cfg: VoiceConfig,
        worktree: Path,
        duration: float,
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=duration,
            status=Status.TIMEOUT,
            error=f"OpenRouter timeout after {cfg.timeout_sec}s",
        )

    def _failed_result(
        self,
        cfg: VoiceConfig,
        worktree: Path,
        duration: float,
        reason: str,
    ) -> BuilderResult:
        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree,
            tests_dir=worktree,
            diff_patch=worktree / "diff.patch",
            self_metrics=SelfMetrics(
                loc=0,
                complexity_cyclomatic_avg=0.0,
                test_to_code_ratio=0.0,
                todo_count=0,
                imports_count=0,
                functions_count=0,
            ),
            duration_sec=duration,
            status=Status.FAILED,
            error=reason,
        )
