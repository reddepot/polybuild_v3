"""Kimi CLI adapter (Moonshot Allegretto forfait).

Wraps `kimi --quiet --thinking --plan ...` invocations.
Used for Kimi K2.6 (swarm 100+ agents, idioms créatifs, variant exploration).

Note: family = "moonshot" (Chinese provider, low corpus_proxy overlap with US models).
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


class KimiCLIAdapter(BuilderProtocol):
    """Adapter for `kimi` CLI (Moonshot Allegretto forfait)."""

    family = "moonshot"

    def __init__(
        self,
        model: str = "k2.6",
        cli_binary: str = "kimi",
        thinking: bool = True,
        plan: bool = True,
    ):
        self.model = model
        self.cli_binary = cli_binary
        self.thinking = thinking
        self.plan = plan
        self.name = f"kimi_cli_{model.replace('-', '_').replace('.', '_')}"

    async def generate(self, spec: Spec, cfg: VoiceConfig) -> BuilderResult:
        start = time.monotonic()
        worktree = self._setup_worktree(spec, cfg)
        prompt = self._build_prompt(spec, cfg, worktree)

        # TODO post-round 4: concurrency_limiter integration (Faille 3)
        cmd = [self.cli_binary, "--quiet"]
        if self.thinking:
            cmd.append("--thinking")
        if self.plan:
            cmd.append("--plan")
        cmd.extend(["--output-format", "json", "-p", prompt])

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
                    "kimi_cli_failed",
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
        smoke = (
            "Write Python: def hello_polybuild(): return 'OK'. "
            "Output JSON only: {\"code\": \"<source>\"}."
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--quiet",
                "--output-format", "json", "-p", smoke,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(sys.platform != "win32"),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode())
            return "hello_polybuild" in data.get("code", "")
        except (TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def is_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli_binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=(sys.platform != "win32"),
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return proc.returncode == 0
        except (TimeoutError, OSError):
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

<SPEC>
{spec.task_description}
Constraints: {spec.constraints}
Acceptance: {[ac.description for ac in spec.acceptance_criteria]}
</SPEC>

<INSTRUCTIONS>
Generate Python module + pytest tests in {worktree}.
Be CREATIVE — explore alternative idioms and edge cases that other voices may miss.
Output JSON: {{"files_written": [...], "self_metrics": {{...}}}}.
Rules: mypy --strict, ≤3 TODO, asyncio + Pydantic v2.
</INSTRUCTIONS>
"""

    def _load_agents_md(self) -> str:
        local = Path("AGENTS.md")
        if local.exists():
            return local.read_text()
        return "# AGENTS.md\n(none)"

    def _parse_output(
        self, raw: str, worktree: Path, cfg: VoiceConfig, duration: float
    ) -> BuilderResult:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        metrics_data = data.get("self_metrics", {})
        metrics = (
            SelfMetrics(**metrics_data) if metrics_data else self._estimate_metrics(worktree)
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
            raw_output=raw,
        )

    def _estimate_metrics(self, worktree: Path) -> SelfMetrics:
        py_files = list((worktree / "src").rglob("*.py"))
        test_files = list((worktree / "tests").rglob("test_*.py"))
        loc = sum(len(f.read_text().splitlines()) for f in py_files)
        test_loc = sum(len(f.read_text().splitlines()) for f in test_files)
        ratio = test_loc / loc if loc > 0 else 0.0
        todo_count = sum(
            f.read_text().count("TODO") + f.read_text().count("FIXME")
            for f in py_files
        )
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
            error=f"Kimi CLI timeout after {cfg.timeout_sec}s",
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
