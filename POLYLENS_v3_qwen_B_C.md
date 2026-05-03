```json
{
  "honeypots": {
    "H1": false,
    "H2": false,
    "H3": true
  },
  "axes_audited": [
    "B_quality",
    "C_tests"
  ],
  "findings": [
    {
      "id": "B-01",
      "axis": "B_quality",
      "severity": "P2",
      "file:line(s)": "src/polybuild/adapters/claude_code.py:208-211",
      "title": "Double docstring dead expression in _load_agents_md",
      "evidence": "    def _load_agents_md(self) -> str:\n        \"\"\"Load AGENTS.md sanitized through sanitize_prompt_context...\"\"\"\n        from polybuild.security.prompt_sanitizer import sanitize_prompt_context\n        \"\"\"Load project AGENTS.md or fallback to global.\"\"\"",
      "impact": "Second docstring is a no-op string expression; confuses linters/doc generators and indicates copy-paste residue.",
      "remediation": "Remove the second docstring. Merge any relevant context into the primary docstring if needed."
    },
    {
      "id": "B-02",
      "axis": "B_quality",
      "severity": "P2",
      "file:line(s)": "src/polybuild/models.py:138",
      "title": "Deprecated datetime.utcnow usage in Spec model",
      "evidence": "    created_at: datetime = Field(default_factory=datetime.utcnow)",
      "impact": "datetime.utcnow() is deprecated in Python 3.12+ and returns naive datetimes, risking timezone bugs in distributed or cross-region runs.",
      "remediation": "Replace with default_factory=lambda: datetime.now(UTC) and import UTC from datetime."
    },
    {
      "id": "B-03",
      "axis": "B_quality",
      "severity": "P1",
      "file:line(s)": "src/polybuild/adapters/codex_cli.py:168-170",
      "title": "Python list repr injected into LLM prompt",
      "evidence": "Constraints: {spec.constraints}\nAcceptance: {[ac.description for ac in spec.acceptance_criteria]}",
      "impact": "Injects raw Python list representation into the prompt, wasting tokens and potentially confusing instruction-following models.",
      "remediation": "Format as clean newline-separated text: chr(10).join(f'  - {c}' for c in spec.constraints) and similar for acceptance criteria."
    },
    {
      "id": "B-04",
      "axis": "B_quality",
      "severity": "P1",
      "file:line(s)": "src/polybuild/phases/phase_0_spec.py:285",
      "title": "Missing guard on OpenRouter response subscript chain",
      "evidence": "        content = response.json()[\"choices\"][0][\"message\"][\"content\"]",
      "impact": "Direct subscript chain crashes with KeyError/TypeError on rate-limit, content-filter, or tool-call responses, aborting Phase 0b.",
      "remediation": "Add .get() chain or try/except guard matching the malformed-response pattern already applied in openrouter.py (Round 10.7)."
    },
    {
      "id": "B-05",
      "axis": "B_quality",
      "severity": "P1",
      "file:line(s)": "src/polybuild/phases/phase_0_spec.py:248",
      "title": "Greedy regex for JSON extraction is fragile",
      "evidence": "        match = re.search(r\"\\{.*\\}\", raw, re.DOTALL)",
      "impact": "Greedy .* captures trailing text or multiple JSON blocks, causing json.loads to fail or parse the wrong payload on verbose CLI output.",
      "remediation": "Use non-greedy r\"\\{.*?\\}\" or a brace-balancing extractor. Prefer strict --output-format json parsing and drop regex fallback."
    },
    {
      "id": "B-06",
      "axis": "B_quality",
      "severity": "P1",
      "file:line(s)": "src/polybuild/domain_gates/validate_sqlite.py:89-93",
      "title": "Fragile raw string comparison for SQLite schema diff",
      "evidence": "    changed = {\n        name for name in set(expected_schema) & set(actual_schema)\n        if expected_schema[name].strip() != actual_schema[name].strip()\n    }",
      "impact": "Raw DDL string comparison triggers false positives on whitespace, quoting, or SQLite version differences, blocking Phase 7 incorrectly.",
      "remediation": "Normalize SQL strings (collapse whitespace, lowercase keywords) or use a lightweight SQL parser for structural comparison."
    },
    {
      "id": "B-07",
      "axis": "B_quality",
      "severity": "P2",
      "file:line(s)": "src/polybuild/concurrency/limiter.py:288",
      "title": "Implicit _inflight decrement masks acquisition state",
      "evidence": "            self._inflight[provider] = max(0, self._inflight.get(provider, 1) - 1)",
      "impact": "If semaphore acquisition fails, _inflight was never incremented, but finally decrements from default 1. Obscures true concurrency state.",
      "remediation": "Track acquisition with a boolean flag (acquired = False) before try, set True after acquire, and only decrement in finally if acquired."
    },
    {
      "id": "B-08",
      "axis": "B_quality",
      "severity": "P2",
      "file:line(s)": "src/polybuild/domain_gates/validate_rag.py:78",
      "title": "Runtime assert used for type narrowing in production",
      "evidence": "        assert chunker_fn is not None  # narrowed by check above",
      "impact": "assert is stripped when Python runs with -O, potentially causing TypeError in optimized production deployments.",
      "remediation": "Replace with explicit guard: if chunker_fn is None: raise RuntimeError(...) or rely on static type narrowing without runtime assert."
    },
    {
      "id": "C-01",
      "axis": "C_tests",
      "severity": "P1",
      "file:line(s)": "src/polybuild/concurrency/limiter.py:run()",
      "title": "Missing concurrent stress tests for P0-P3 routing",
      "evidence": "Complex priority routing, semaphore acquisition, _inflight tracking, and fallback logic under async contention.",
      "impact": "Untested race conditions between P3 drop checks, semaphore timeouts, and fallback execution can cause deadlocks or silent drops.",
      "remediation": "Add pytest-asyncio stress tests using AsyncMock to simulate saturated semaphores, verifying P0 waits, P1 fallbacks, and P3 drops concurrently."
    },
    {
      "id": "C-02",
      "axis": "C_tests",
      "severity": "P1",
      "file:line(s)": "src/polybuild/phases/phase_0_spec.py",
      "title": "No mutation/edge tests for Phase 0 JSON extraction",
      "evidence": "Regex JSON fallback and direct OpenRouter response parsing without malformed-payload guards.",
      "impact": "LLM non-determinism or API error shapes will crash Phase 0; mutation testing would easily kill the extraction logic.",
      "remediation": "Add property-based tests (Hypothesis) feeding truncated, multi-JSON, and error-shaped payloads to verify graceful degradation."
    },
    {
      "id": "C-03",
      "axis": "C_tests",
      "severity": "P1",
      "file:line(s)": "src/polybuild/domain_gates/validate_mcp.py",
      "title": "Missing pipe-deadlock & interleaved-log tests for MCP gate",
      "evidence": "Async stderr draining, JSON-RPC ID matching, and non-JSON stdout tolerance logic.",
      "impact": "Missing tests for interleaved logs, partial JSON reads, and broken pipes leave the gate vulnerable to hanging on verbose MCP servers.",
      "remediation": "Create a mock MCP subprocess emitting mixed logs/JSON, delaying responses, and closing pipes early; assert gate handles all without deadlock."
    },
    {
      "id": "C-04",
      "axis": "C_tests",
      "severity": "P1",
      "file:line(s)": "src/polybuild/adapters/builder_protocol.py + adapters",
      "title": "Untested raw_prompt_no_write contract across adapters",
      "evidence": "cfg.context.get(\"raw_prompt\") bypasses worktree creation; contract relies on adapter compliance.",
      "impact": "If an adapter ignores raw_prompt_no_write, Phase 5 triade could corrupt the filesystem; current tests only check happy path.",
      "remediation": "Add parametrized integration tests across all 7 adapters asserting run_raw_prompt creates zero files/directories and returns raw text only."
    },
    {
      "id": "C-05",
      "axis": "C_tests",
      "severity": "P2",
      "file:line(s)": "src/polybuild/domain_gates/validate_fts5.py",
      "title": "Missing error-path tests for FTS5 table interpolation",
      "evidence": "f\"SELECT COUNT(*) FROM {fts_table} WHERE {fts_table} MATCH ?\"",
      "impact": "Untested invalid table names or SQL syntax errors in config cause unhandled sqlite3.OperationalError, crashing Phase 6.",
      "remediation": "Add tests for missing tables, invalid identifiers, and FTS5 syntax errors; verify gate returns passed=False with structured error."
    }
  ]
}
```