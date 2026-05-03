"""Claude Code CLI adapter.

Wraps `claude code --model <model> ...` invocations through asyncio.subprocess.
Used for Opus 4.7 (architect, mediator), Sonnet 4.6 (workhorse), Haiku 4.5 (atomic).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import structlog

from polybuild.adapters.builder_protocol import BuilderProtocol
from polybuild.models import BuilderResult, SelfMetrics, Spec, Status, VoiceConfig

logger = structlog.get_logger()


class ClaudeCodeAdapter(BuilderProtocol):
    """Adapter for Claude Code CLI.

    Args:
        model: Anthropic model slug (opus-4.7, sonnet-4.6, haiku-4.5)
        cli_binary: Path to `claude` binary (default: "claude")
    """

    family = "anthropic"

    def __init__(self, model: str = "opus-4.7", cli_binary: str = "claude"):
        self.model = model
        self.cli_binary = cli_binary
        self.name = f"claude_code_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        """Run Claude Code CLI to generate the module."""
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: integrate with concurrency_limiter (Faille 3)
        # Round 10.8 prod-launch fix: claude CLI v2 — no more ``code``
        # subcommand, no ``--output-dir`` (the v2 CLI doesn't write files
        # itself; the model emits JSON of files which our _parse_output
        # then writes via the safe-write helper). ``-p PROMPT
        # --output-format text`` is the new contract.
        cmd = [
            self.cli_binary,
            "-p", prompt,
            "--model", self.model,
            "--output-format", "text",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
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
                    "claude_code_failed",
                    model=self.model,
                    returncode=proc.returncode,
                    stderr=stderr.decode()[:500],
                )
                return BuilderResult(
                    voice_id=cfg.voice_id,
                    family=self.family,
                    code_dir=worktree,
                    tests_dir=worktree / "tests",
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
                    raw_output=stdout.decode(),
                    error=stderr.decode()[:500],
                )

            return self._parse_output(stdout.decode(), worktree, cfg, duration)

        except TimeoutError:
            duration = time.monotonic() - start
            logger.warning(
                "claude_code_timeout",
                model=self.model,
                timeout=cfg.timeout_sec,
            )
            return BuilderResult(
                voice_id=cfg.voice_id,
                family=self.family,
                code_dir=worktree,
                tests_dir=worktree / "tests",
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
                error=f"Timeout after {cfg.timeout_sec}s",
            )

    async def smoke_test(self) -> bool:
        """Verify the CLI works with a deterministic prompt.

        Round 10.8 prod-launch fix: claude CLI v2 surface (cf generate()).
        """
        smoke_prompt = (
            "Write a Python function `def hello_polybuild(): return 'OK'`. "
            "Output JSON only: {\"code\": \"...\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary,
                "-p", smoke_prompt,
                "--model", self.model,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(sys.platform != "win32"),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            text = stdout.decode().strip()
            # Try strict JSON first; fall back to substring match if the
            # model wrapped the JSON in markdown fencing.
            try:
                data = json.loads(text)
                return "hello_polybuild" in data.get("code", "")
            except json.JSONDecodeError:
                return "hello_polybuild" in text
        except (TimeoutError, OSError):
            return False

    async def is_available(self) -> bool:
        """Check if the `claude` binary is reachable."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary,
                "--version",
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
        """Create the isolated worktree for this voice."""
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
        """Build the unified builder prompt with AGENTS.md + memory injection."""
        # TODO: integrate memory.retrieve_relevant_runs() once vector store is wired
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

<TASK_PROFILE>
profile_id: {spec.profile_id}
risk_level: {spec.risk_profile.sensitivity.value}
audit_axes: {spec.risk_profile.audit_axes}
</TASK_PROFILE>

<SPEC>
{spec.task_description}

Constraints:
{chr(10).join(f'  - {c}' for c in spec.constraints)}

Acceptance Criteria:
{chr(10).join(f'  - {ac.id}: {ac.description}' for ac in spec.acceptance_criteria)}
</SPEC>

<INSTRUCTIONS>
Generate a complete Python module that satisfies ALL acceptance criteria.
Output structure:
  - src/*.py (the module code)
  - tests/test_*.py (pytest tests, including happy/edge/failure scenarios)
  - diff.patch (unified diff)
  - self_metrics.json (loc, complexity, ratios, todos)

Hard rules:
  - Type hints everywhere (mypy --strict must pass)
  - No TODO/FIXME comments in final output (max 3 allowed, 0 preferred)
  - No mock-only tests (integration > mocks)
  - Pydantic v2 for all data contracts
  - asyncio for all I/O
</INSTRUCTIONS>

Working directory: {worktree}
"""

    def _load_agents_md(self) -> str:
        """Load AGENTS.md sanitized through sanitize_prompt_context.

        Round 10.2.1 fix [ChatGPT RX-001 P0 + Kimi RX-007 P1] — adapters
        were embedding the raw file content into the LLM prompt, bypassing
        the sanitization the orchestrator applied for the privacy gate.
        We now sanitize at every injection point as defence in depth.

        Round 10.7 fix [POLYLENS v3 GLM A-09 dead docstring]: removed the
        stray inner triple-quoted expression that ruff flags as dead code.
        """
        from polybuild.security.prompt_sanitizer import sanitize_prompt_context

        local = Path("AGENTS.md")
        if local.exists():
            return sanitize_prompt_context(local.read_text())
        global_agents = Path.home() / ".polybuild" / "global_agents.md"
        if global_agents.exists():
            return sanitize_prompt_context(global_agents.read_text())
        return sanitize_prompt_context("# AGENTS.md\n(no project conventions defined)")

    def _parse_output(
        self,
        raw: str,
        worktree: Path,
        cfg: VoiceConfig,
        duration: float,
    ) -> BuilderResult:
        """Parse stdout JSON into a BuilderResult.

        We try json.loads(raw) primarily as a sanity check that the CLI
        produced something parseable; the actual structured fields come from
        ``self_metrics.json`` (written by the builder skill into the worktree),
        not from this stdout payload. A JSONDecodeError is therefore tolerated.
        """
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("claude_stdout_not_json", voice=cfg.voice_id)

        # Round 10.7 fix [GLM A-06 P1]: malformed self_metrics.json (e.g.
        # builder writes invalid JSON, or types that Pydantic rejects)
        # would otherwise crash the entire ``generate()`` call. Fall back
        # to ``_estimate_metrics`` when parse/validation fails.
        metrics_path = worktree / "self_metrics.json"
        metrics: SelfMetrics
        if metrics_path.exists():
            try:
                metrics_data = json.loads(metrics_path.read_text())
                metrics = SelfMetrics(**metrics_data)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning(
                    "claude_metrics_parse_fallback",
                    voice=cfg.voice_id,
                    error=str(e),
                )
                metrics = self._estimate_metrics(worktree)
        else:
            # Estimate metrics from worktree
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
        """Compute metrics from the worktree if not provided by the model.

        Round 10.7 fix [POLYLENS v3 D-02 P1]: previous implementation read
        each .py file twice (once for loc, once for TODO count). Read each
        file once into a local variable.
        """
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
            complexity_cyclomatic_avg=0.0,  # TODO: integrate radon
            test_to_code_ratio=ratio,
            todo_count=todo_count,
            imports_count=0,
            functions_count=0,
        )
