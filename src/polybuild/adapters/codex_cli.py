"""Codex CLI adapter (ChatGPT Pro).

Wraps `codex exec -m <model> ...` invocations.
Used for GPT-5.5, GPT-5.5-Pro, GPT-5.4, GPT-5.3-Codex.

GPT-5.3-Codex is the CLI specialist (devops, IaC, scripts shell).
GPT-5.5 is the pragmatic builder (Terminal-Bench 82.7%).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import structlog

from polybuild.adapters._json_extract import _try_parse_json
from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig
from polybuild.security.safe_write import write_files_to_worktree

logger = structlog.get_logger()


class CodexCLIAdapter(BuilderProtocol):
    """Adapter for `codex exec` CLI (ChatGPT Pro forfait).

    Args:
        model: OpenAI model slug (gpt-5.5, gpt-5.5-pro, gpt-5.4, gpt-5.3-codex)
        reasoning_effort: low | medium | high | xhigh
        cli_binary: Path to `codex` binary (default: "codex")
    """

    family = "openai"

    def __init__(
        self,
        model: str = "gpt-5.5",
        reasoning_effort: str = "high",
        cli_binary: str = "codex",
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.cli_binary = cli_binary
        self.name = f"codex_cli_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Run codex exec to generate the module."""
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: concurrency_limiter integration (Faille 3)
        # Round 10.7 fix [GLM A-07 P1]: insert ``--`` end-of-options
        # separator before the prompt. Without it, a prompt that begins
        # with ``-`` (e.g. an LLM-formatted YAML doc, a list of options,
        # or a sanitization-resistant adversarial payload) would be
        # parsed as a CLI flag rather than the prompt body.
        # Round 10.8 prod-launch fix: codex CLI 0.128.0 dropped
        # ``--output-format`` (now ``--output-schema FILE`` for JSON-Schema
        # validation, or ``--json`` for JSONL event stream). Default stdout
        # is the model's text output, which is what we want — the parse
        # logic downstream handles the model's emitted JSON.
        # Round 10.8 prod-launch fix: ``--cd`` was receiving a path
        # RELATIVE to the orchestrator's cwd, but the subprocess is
        # already starting with ``cwd=worktree`` — codex would then
        # resolve the relative ``--cd`` arg against its NEW cwd,
        # producing a double-path (``cwd/worktree/cwd/worktree``) which
        # doesn't exist → ``Error: No such file or directory (os error
        # 2)``. Use the absolute path instead.
        cmd = [
            self.cli_binary,
            "exec",
            "-m", self.model,
            "-c", f"model_reasoning_effort={self.reasoning_effort}",
            "--cd", str(worktree.resolve()),
            "--skip-git-repo-check",
            "--",
            prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=worktree,
                start_new_session=(sys.platform != "win32"),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=cfg.timeout_sec,
            )
            duration = time.monotonic() - start

            if proc.returncode != 0:
                logger.warning(
                    "codex_cli_failed",
                    model=self.model,
                    returncode=proc.returncode,
                    stderr=stderr.decode()[:500],
                )
                return self._failed_result(cfg, worktree, duration, stderr.decode()[:500])

            return self._parse_output(stdout.decode(), worktree, cfg, duration)

        except TimeoutError:
            duration = time.monotonic() - start
            return self._timeout_result(cfg, worktree, duration)

    async def smoke_test(self) -> bool:
        # Round 10.8 prod-launch fix: codex CLI 0.128 surface (cf generate()).
        smoke = (
            "Write Python: def hello_polybuild(): return 'OK'. "
            "Output JSON only: {\"code\": \"<source>\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "exec", "-m", self.model,
                "--skip-git-repo-check",
                "--",
                smoke,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(sys.platform != "win32"),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            text = stdout.decode().strip()
            try:
                data = json.loads(text)
                return "hello_polybuild" in data.get("code", "")
            except json.JSONDecodeError:
                return "hello_polybuild" in text
        except (TimeoutError, OSError):
            return False

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--version",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(sys.platform != "win32"),
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (TimeoutError, OSError):
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

<SPEC>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</SPEC>

<INSTRUCTIONS>
Generate complete Python module + pytest tests.
Write to:
  - {worktree}/src/*.py
  - {worktree}/tests/test_*.py
Then output **only** valid JSON to stdout (no prose, no markdown fencing):
{{
  "files": {{
    "src/<name>.py": "<full source code>",
    "tests/test_<name>.py": "<full test source code>"
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

Hard rules:
  - mypy --strict must pass
  - max 3 TODO/FIXME (0 preferred)
  - integration tests > mocks
  - asyncio for I/O, Pydantic v2 for contracts
</INSTRUCTIONS>
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

    def _parse_output(
        self, raw: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        # Round 10.8 prod-launch follow-up: codex CLI 0.128 emits model
        # output as text on stdout. The model may wrap JSON in markdown
        # fencing or emit prose around it. We use a robust extraction chain.
        # ``_try_parse_json`` already returns ``dict | None``; ``or {}``
        # narrows to dict — no else-branch needed.
        data = _try_parse_json(raw) or {}

        files = data.get("files", {})
        if isinstance(files, dict):
            write_files_to_worktree(
                files, worktree, adapter_name="codex_cli"
            )
        metrics_data = data.get("self_metrics", {})
        if isinstance(metrics_data, dict) and metrics_data:
            try:
                metrics = SelfMetrics(**metrics_data)
            except (TypeError, ValueError):
                metrics = self._estimate_metrics(worktree)
        else:
            metrics = self._estimate_metrics(worktree)

        return BuilderResult(
            voice_id=cfg.voice_id,
            family=self.family,
            code_dir=worktree / "src",
            tests_dir=worktree / "tests",
            diff_patch=worktree / "diff.patch",
            self_metrics=metrics,
            duration_sec=duration,
            status=Status.OK,
            raw_output=raw,
        )

    def _estimate_metrics(self, worktree: Path) -> SelfMetrics:
        # Round 10.7 fix [POLYLENS v3 D-02 P1]: read each file once.
        py_files = list((worktree / "src").rglob("*.py"))
        test_files = list((worktree / "tests").rglob("test_*.py"))
        loc = 0
        todo_count = 0
        for f in py_files:
            text = f.read_text()
            loc += len(text.splitlines())
            todo_count += text.count("TODO") + text.count("FIXME")
        test_loc = sum(len(f.read_text().splitlines()) for f in test_files)
        ratio = test_loc / loc if loc > 0 else 0.0
        return SelfMetrics(
            loc=loc,
            complexity_cyclomatic_avg=0.0,
            test_to_code_ratio=ratio,
            todo_count=todo_count,
            imports_count=0,
            functions_count=0,
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
            error=f"Codex CLI timeout after {cfg.timeout_sec}s",
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
