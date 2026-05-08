"""Phase 3b — AST-based grounding check.

After Phase 2 generation, parse each voice's code and verify:
    1. Syntactically valid Python (else P0)
    2. Every `import X` references either:
        - stdlib module
        - declared dependency in pyproject.toml
        - local module of the project
       (else P1, hallucinated import)
    3. Every internal symbol reference exists (else P1)

Decision (acquis convergent #10): NO automatic fix on grounding findings.
    - ≥2 hallucinated imports → disqualification (Phase 3 hard rule)
    - 1 hallucinated import → P1 finding (Phase 5 will treat it)
"""

from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path

import structlog

from polybuild.models import (
    BuilderResult,
    GroundingFinding,
    Severity,
    Status,
)

# Round 10 fix [Phase 3b ast.parse timeout] (3-conv: Claude + ChatGPT + Grok
# round 9 P1): a malformed/giant Python file can stall ast.parse for tens of
# seconds, freezing the asyncio event loop. We cap each parse at 8s by
# off-loading to a worker thread.
_AST_PARSE_TIMEOUT_S = 8.0

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# GROUNDING ENGINE
# ────────────────────────────────────────────────────────────────


class GroundingEngine:
    """AST-based 3-layer grounding checker."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.installed_pkgs = self._load_installed_deps()
        self.stdlib = set(sys.stdlib_module_names)
        self.local_modules = self._index_local_modules()
        self.local_symbols = self._index_local_symbols()

    def _load_installed_deps(self) -> set[str]:
        """Parse pyproject.toml dependencies."""
        pyproject = self.project_root / "pyproject.toml"
        if not pyproject.exists():
            return set()
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef,import-not-found]

        with pyproject.open("rb") as f:
            data = tomllib.load(f)

        # Round 10.7 fix [Qwen D-03 P1]: the chained ``split`` chain misparses
        # PEP 508 specifiers that include environment markers
        # (``foo; python_version>="3.11"``), URL specifiers
        # (``foo @ https://...``), or the ``~=`` operator. Use the
        # ``packaging.requirements.Requirement`` parser which is the
        # canonical PEP 508 implementation.
        from packaging.requirements import InvalidRequirement, Requirement

        def _extract_dep_name(spec: str) -> str | None:
            try:
                return Requirement(spec).name
            except InvalidRequirement:
                # Fallback for malformed specs rather than crashing the
                # grounding phase. Use a single regex split on the union
                # of PEP 508 separators rather than chained splits.
                import re as _re

                head = _re.split(r">=|<=|==|!=|~=|>|<|\[|;|@", spec, maxsplit=1)[0]
                return head.strip() or None

        deps = set()
        for dep in data.get("project", {}).get("dependencies", []):
            name = _extract_dep_name(dep)
            if name:
                deps.add(name.replace("-", "_"))  # PEP 503 normalization
                deps.add(name)
        # Optional deps
        for group in data.get("project", {}).get("optional-dependencies", {}).values():
            for dep in group:
                name = _extract_dep_name(dep)
                if name:
                    deps.add(name.replace("-", "_"))
                    deps.add(name)
        return deps

    def _index_local_modules(self) -> set[str]:
        """All importable module/package names in the project.

        Round 10.1 fix [Kimi P0 #3]: the previous implementation only indexed
        the file *stems* (``models``, ``orchestrator``…). That caused legit
        qualified imports like ``from polybuild.models import Spec`` to be
        flagged as hallucinations because the top-level package name
        ``polybuild`` was not in the set. We now index every directory that
        contains an ``__init__.py`` AND every leaf module stem, so both
        ``models`` and ``polybuild.models`` resolve.
        """
        modules: set[str] = set()
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            if not py_file.name.startswith("_"):
                modules.add(py_file.stem)
        # Walk directories that look like Python packages.
        for init_file in self.project_root.rglob("__init__.py"):
            if "__pycache__" in init_file.parts:
                continue
            modules.add(init_file.parent.name)
        return modules

    def _index_local_symbols(self) -> set[str]:
        """All function/class names defined in the project."""
        symbols = set()
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(
                        node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                    ):
                        symbols.add(node.name)
            except (SyntaxError, UnicodeDecodeError):
                continue
        return symbols

    def _is_valid_top_module(self, mod: str) -> bool:
        """Check if module top-level name is resolvable."""
        top = mod.split(".", maxsplit=1)[0]
        return (
            top in self.installed_pkgs
            or top in self.stdlib
            or top in self.local_modules
        )

    async def check_file_async(
        self, py_file: Path, voice_id: str
    ) -> list[GroundingFinding]:
        """Async wrapper of ``check_file`` that bounds ast.parse latency.

        Round 10 fix [Phase 3b ast.parse timeout]: the synchronous variant is
        kept for tests, but the orchestrator must use this async path so the
        event loop stays responsive on adversarial inputs.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.check_file, py_file, voice_id),
                timeout=_AST_PARSE_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning(
                "phase_3b_ast_parse_timeout",
                voice_id=voice_id,
                file=str(py_file),
                limit_s=_AST_PARSE_TIMEOUT_S,
            )
            return [
                GroundingFinding(
                    severity=Severity.P0,
                    voice_id=voice_id,
                    kind="syntax_error",
                    detail=f"ast.parse timeout >{_AST_PARSE_TIMEOUT_S:.0f}s on {py_file.name}",
                    file=py_file,
                    line=None,
                )
            ]

    def check_file(self, py_file: Path, voice_id: str) -> list[GroundingFinding]:
        """Analyze a single Python file for grounding issues."""
        findings: list[GroundingFinding] = []
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except SyntaxError as e:
            findings.append(
                GroundingFinding(
                    severity=Severity.P0,
                    voice_id=voice_id,
                    kind="syntax_error",
                    detail=f"{py_file.name}:{e.lineno}: {e.msg}",
                    file=py_file,
                    line=e.lineno,
                )
            )
            return findings
        except UnicodeDecodeError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._is_valid_top_module(alias.name):
                        findings.append(
                            GroundingFinding(
                                severity=Severity.P1,
                                voice_id=voice_id,
                                kind="hallucinated_import",
                                detail=f"Import '{alias.name}' not found in deps/stdlib/local",
                                file=py_file,
                                line=node.lineno,
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and not self._is_valid_top_module(node.module):
                    findings.append(
                        GroundingFinding(
                            severity=Severity.P1,
                            voice_id=voice_id,
                            kind="hallucinated_import_from",
                            detail=f"From '{node.module}' not found",
                            file=py_file,
                            line=node.lineno,
                        )
                    )

        return findings

    def check_directory(self, code_dir: Path, voice_id: str) -> list[GroundingFinding]:
        """Analyze all .py files in a directory (sync path, used in tests)."""
        findings: list[GroundingFinding] = []
        for py_file in code_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            findings.extend(self.check_file(py_file, voice_id))
        return findings

    async def check_directory_async(
        self, code_dir: Path, voice_id: str
    ) -> list[GroundingFinding]:
        """Async path: each file parse bounded by _AST_PARSE_TIMEOUT_S.

        Round 10.1 fix [Kimi P1 #10]: previously this loop was sequential.
        With 50 files x 8s timeout = 400s worst case. We now parallelise
        through ``asyncio.gather`` capped by a small Semaphore (8) so that
        a malicious payload trying to exhaust the thread pool can't starve
        unrelated runs.
        """
        files = [
            p for p in code_dir.rglob("*.py")
            if "__pycache__" not in p.parts
        ]
        if not files:
            return []

        sem = asyncio.Semaphore(8)

        async def _bounded(p: Path) -> list[GroundingFinding]:
            async with sem:
                return await self.check_file_async(p, voice_id)

        results = await asyncio.gather(
            *(_bounded(p) for p in files), return_exceptions=False
        )
        return [f for sub in results for f in sub]


# ────────────────────────────────────────────────────────────────
# DISQUALIFICATION RULE
# ────────────────────────────────────────────────────────────────


def grounding_disqualifies(findings: list[GroundingFinding]) -> tuple[bool, str | None]:
    """Apply the ≥2 hallucinated imports disqualification rule."""
    p0 = [f for f in findings if f.severity == Severity.P0]
    if p0:
        return True, f"Grounding P0: {len(p0)} syntax error(s)"

    halluc_imports = [
        f
        for f in findings
        if f.kind in {"hallucinated_import", "hallucinated_import_from"}
    ]
    if len(halluc_imports) >= 2:
        return True, f"≥2 hallucinated imports ({len(halluc_imports)})"
    return False, None


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_3b_grounding(
    results: list[BuilderResult],
    project_root: Path = Path(),
) -> dict[str, list[GroundingFinding]]:
    """Run grounding checks on all builder results.

    Returns:
        dict mapping voice_id → list of findings.
    """
    logger.info("phase_3b_start", n_results=len(results))
    engine = GroundingEngine(project_root)

    findings_by_voice: dict[str, list[GroundingFinding]] = {}
    for r in results:
        if r.status != Status.OK:
            findings_by_voice[r.voice_id] = []
            continue
        f = await engine.check_directory_async(r.code_dir, r.voice_id)
        findings_by_voice[r.voice_id] = f
        dq, reason = grounding_disqualifies(f)
        if dq:
            logger.warning(
                "phase_3b_disqualified",
                voice_id=r.voice_id,
                reason=reason,
            )

    n_findings_total = sum(len(f) for f in findings_by_voice.values())
    logger.info("phase_3b_done", n_findings=n_findings_total)
    return findings_by_voice
