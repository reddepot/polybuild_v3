 ```json
{
  "honeypots": {"H1": false, "H2": false, "H3": true},
  "axes_audited": ["D_performance", "E_architecture"],
  "findings": [
    {
      "id": "D-01",
      "axis": "D_performance",
      "severity": "P0",
      "file": "src/polybuild/adapters/claude_code.py:225-245",
      "title": "Blocking sync file I/O in async adapter metrics estimation",
      "evidence": "def _estimate_metrics(self, worktree: Path) -> SelfMetrics:\n    py_files = list((worktree / \"src\").rglob(\"*.py\"))\n    loc = sum(len(f.read_text().splitlines()) for f in py_files)\n    todo_count = sum(f.read_text().count(\"TODO\") + f.read_text().count(\"FIXME\") for f in py_files)",
      "impact": "Event loop blocked during Phase 2 parallel generation; stalls other voices and degrades overall pipeline throughput.",
      "remediation": "Offload Path.read_text() and string processing to asyncio.to_thread(), or cache file contents in a single threaded pass."
    },
    {
      "id": "D-02",
      "axis": "D_performance",
      "severity": "P1",
      "file": "src/polybuild/adapters/claude_code.py:225-235",
      "title": "Redundant file reads in _estimate_metrics",
      "evidence": "loc = sum(len(f.read_text().splitlines()) for f in py_files)\ntodo_count = sum(f.read_text().count(\"TODO\") + f.read_text().count(\"FIXME\") for f in py_files)",
      "impact": "Every source file is read from disk twice; amplified across 3 parallel voices and large worktrees.",
      "remediation": "Read each file once into a local variable, then compute loc and todo_count from the cached string."
    },
    {
      "id": "D-03",
      "axis": "D_performance",
      "severity": "P1",
      "file": "src/polybuild/orchestrator/__init__.py:340-360",
      "title": "Synchronous checkpoint I/O in async orchestrator hot path",
      "evidence": "tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))\ntmp.rename(target)",
      "impact": "Blocks event loop on every phase transition; write latency grows with payload size (builder raw outputs) and stalls concurrent tasks.",
      "remediation": "Wrap save_checkpoint body in asyncio.to_thread() or adopt aiofiles for non-blocking disk writes."
    },
    {
      "id": "D-04",
      "axis": "D_performance",
      "severity": "P1",
      "file": "src/polybuild/domain_gates/validate_sqlite.py:40-90",
      "title": "Synchronous domain gates block async event loop",
      "evidence": "def validate_sqlite_db(...) -> SQLiteGateResult:\n    conn = sqlite3.connect(uri, uri=True)\n    cur = conn.execute(\"PRAGMA integrity_check\")",
      "impact": "SQLite, FTS5 and RAG gates execute blocking DB I/O inside async phase_6_validate; stalls entire event loop during validation.",
      "remediation": "Execute sync gates via asyncio.to_thread() or provide async-native DB drivers (aiosqlite, etc.)."
    },
    {
      "id": "D-05",
      "axis": "D_performance",
      "severity": "P1",
      "file": "src/polybuild/models.py:170",
      "title": "Unbounded raw_output string retention causes memory bloat",
      "evidence": "class BuilderResult(BaseModel):\n    ...\n    raw_output: str = \"\"",
      "impact": "Complete LLM JSON responses retained in memory for every voice through Phase 3-6; multi-MB strings multiplied by 3 voices pressure heap and checkpoint serialization.",
      "remediation": "Spill raw outputs to disk immediately after parsing; store only a Path reference or truncate after scoring."
    },
    {
      "id": "D-06",
      "axis": "D_performance",
      "severity": "P1",
      "file": "src/polybuild/adapters/claude_code.py:215-222",
      "title": "AGENTS.md loaded repeatedly without cross-adapter caching",
      "evidence": "def _load_agents_md(self) -> str:\n    local = Path(\"AGENTS.md\")\n    if local.exists():\n        return sanitize_prompt_context(local.read_text())",
      "impact": "Redundant disk I/O and sanitizer CPU for every generate() and run_raw_prompt() call across all 7 adapters; no memoization.",
      "remediation": "Cache sanitized AGENTS.md content via functools.lru_cache or an instance-level cache shared across calls."
    },
    {
      "id": "D-07",
      "axis": "D_performance",
      "severity": "P0",
      "file": "src/polybuild/adapters/openrouter.py:340-360",
      "title": "HTTP adapters perform synchronous filesystem writes inside async generate",
      "evidence": "for rel_path, source in files.items():\n    abs_path = worktree / rel_path\n    abs_path.parent.mkdir(parents=True, exist_ok=True)\n    abs_path.write_text(source)",
      "impact": "Event loop blocked while writing potentially many/large files to worktree inside async generate; same pattern in MistralEU and Ollama adapters.",
      "remediation": "Offload Path.write_text() and mkdir() to asyncio.to_thread() or use an async file I/O library."
    },
    {
      "id": "E-01",
      "axis": "E_architecture",
      "severity": "P0",
      "file": "src/polybuild/phases/phase_0_spec.py:90-110,150-180",
      "title": "Phase 0 directly invokes CLI and HTTP APIs, bypassing adapter layer",
      "evidence": "proc = await asyncio.create_subprocess_exec(\"claude\", \"code\", \"--model\", \"opus-4.7\", ...)\n\nasync with httpx.AsyncClient(timeout=timeout_sec) as client:\n    response = await client.post(\"https://openrouter.ai/api/v1/chat/completions\", ...)",
      "impact": "Duplicates transport logic, bypasses concurrency limiter and is_available checks, and breaks the abstraction boundary between phases and adapters.",
      "remediation": "Inject a BuilderProtocol instance into Phase 0 and call its generate() or a new spec-only method; reuse OpenRouterAdapter for HTTP."
    },
    {
      "id": "E-02",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/orchestrator/__init__.py:30-40",
      "title": "Orchestrator tightly coupled to concrete phase implementations",
      "evidence": "from polybuild.phases import phase_0_spec, phase_2_generate, phase_3_score, ...\n\nspec = await phase_0_spec(...)\nvoices = await select_voices(...)",
      "impact": "Phases cannot be swapped, mocked, or versioned without editing the orchestrator; violates dependency inversion.",
      "remediation": "Define a Phase protocol and register phases in a pipeline registry; orchestrator drives execution via generic interface."
    },
    {
      "id": "E-03",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/models.py:130",
      "title": "VoiceConfig.context untyped dict leaks adapter internals",
      "evidence": "class VoiceConfig(BaseModel):\n    ...\n    context: dict[str, Any] = Field(default_factory=dict)\n\n# usage in builder_protocol.py:\ncontext={\"raw_prompt\": True, \"raw_prompt_no_write\": no_write, \"phase5_workdir\": str(workdir)}",
      "impact": "Phases depend on magic string keys to control adapter behavior; no type safety, fragile cross-layer contract, prone to key drift.",
      "remediation": "Promote known flags to typed fields on VoiceConfig or use a discriminated union; reserve context for opaque metadata only."
    },
    {
      "id": "E-04",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/adapters/__init__.py:40-80",
      "title": "Adapter factory hardcodes voice-to-adapter mapping",
      "evidence": "def get_builder(voice_id: str) -> BuilderProtocol:\n    if voice_id.startswith(\"claude-\"):\n        return ClaudeCodeAdapter(model=model)\n    if voice_id.startswith(\"gpt-\"):\n        return CodexCLIAdapter(model=voice_id)",
      "impact": "Adding a new voice requires modifying the factory; violates Open/Closed principle and prevents runtime adapter registration or testing with mocks.",
      "remediation": "Implement a declarative registry (e.g., register_adapter decorator) or load voice-to-adapter mappings from configuration."
    },
    {
      "id": "E-05",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/adapters/builder_protocol.py:80-150",
      "title": "BuilderProtocol.run_raw_prompt default leaks filesystem concerns",
      "evidence": "async def run_raw_prompt(self, ...):\n    ...\n    result = await self.generate(synthetic_spec, synthetic_cfg)\n    return result.raw_output or \"\"",
      "impact": "Default implementation calls generate(), which may create worktrees unless adapters honor a magic context key; callers cannot rely on no-write semantics.",
      "remediation": "Make run_raw_prompt abstract with no default implementation; force each adapter to provide a prompt-only path without worktree side effects."
    },
    {
      "id": "E-06",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/models.py:330-350",
      "title": "TokenUsage model uses provider-specific flat fields",
      "evidence": "class TokenUsage(BaseModel):\n    claude_max_input: int = 0\n    claude_max_output: int = 0\n    chatgpt_pro_input: int = 0\n    chatgpt_pro_output: int = 0\n    ...",
      "impact": "Schema must change for every new provider; violates Open/Closed principle and complicates aggregation logic.",
      "remediation": "Replace flat fields with dict[str, ProviderTokenMetrics] or a list of usage records keyed by provider name."
    },
    {
      "id": "E-07",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/orchestrator/__init__.py:200-280",
      "title": "Orchestrator mixes infrastructure and business logic",
      "evidence": "def save_checkpoint(...): ...\ndef _handle_shutdown_signal(...): ...\ndef _resolve_config_root() -> Path: ...",
      "impact": "Checkpointing, signal handling, and config discovery live inside the orchestrator module; cannot be unit-tested or reused independently.",
      "remediation": "Extract CheckpointStore, SignalManager, and ConfigResolver into dedicated infrastructure modules; inject them into the orchestrator."
    },
    {
      "id": "E-08",
      "axis": "E_architecture",
      "severity": "P1",
      "file": "src/polybuild/cli.py:130-150",
      "title": "CLI directly instantiates concrete adapters, bypassing factory",
      "evidence": "adapters = [\n    ClaudeCodeAdapter(\"opus-4.7\"),\n    CodexCLIAdapter(\"gpt-5.5\"),\n    GeminiCLIAdapter(\"gemini-3.1-pro-preview\"),\n    ...\n]",
      "impact": "CLI is tightly coupled to adapter constructors and naming; factory validation, routing logic, and voice_id normalization are circumvented.",
      "remediation": "Use get_builder(voice_id) for all adapter instantiation in the test-cli command."
    }
  ]
}
```