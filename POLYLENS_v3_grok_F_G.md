**```json**
{
  "honeypots": {"H1": false, "H2": false, "H3": true},
  "axes_audited": ["F_documentation", "G_adversarial"],
  "findings": [
    {
      "id": "F-01",
      "axis": "F_documentation",
      "severity": "P1",
      "file": "src/polybuild/adapters/builder_protocol.py:78",
      "title": "Stale/outdated docstring in run_raw_prompt()",
      "evidence": "Round 7 fix [O3] ... ALL implementations of `_build_prompt()` MUST check `cfg.context.get(\"raw_prompt\")` ... Tests live under tests/test_raw_prompt_bypass.py",
      "impact": "Developers and future auditors read incorrect contract; the test file referenced does not exist in the provided sources, creating documentation drift.",
      "remediation": "Update the docstring to reflect current reality (bypass lives in each adapter's `_build_prompt`, not only `_build_prompt`). Remove or update the non-existent test path. Keep the Round 10.7 hash fix note."
    },
    {
      "id": "F-02",
      "axis": "F_documentation",
      "severity": "P2",
      "file": "src/polybuild/__init__.py:1",
      "title": "Module-level docstring lists TODO phases that no longer match code",
      "evidence": "Phase -1: Privacy gate (TODO post-round 4)\nPhase 8: Production smoke (TODO post-round 4)",
      "impact": "README/AGENTS.md and internal architecture doc have drifted from actual implementation (privacy gate and phase 8 are now fully wired).",
      "remediation": "Remove the two \"TODO post-round 4\" mentions or mark them as completed. Sync with orchestrator.py which shows both phases are active."
    },
    {
      "id": "F-03",
      "axis": "F_documentation",
      "severity": "P2",
      "file": "src/polybuild/adapters/claude_code.py:130",
      "title": "Inaccurate comment about _load_agents_md sanitization",
      "evidence": "Round 10.2.1 fix [ChatGPT RX-001 P0 + Kimi RX-007 P1] — adapters were embedding the raw file content...",
      "impact": "The comment claims a fix that was already supposed to be in round 10.2, yet the code still imports and calls sanitize_prompt_context. Creates lying documentation.",
      "remediation": "Either remove the \"were embedding raw\" historical note (since sanitization is now consistently applied) or clarify that this is defence-in-depth after the orchestrator change."
    },
    {
      "id": "G-01",
      "axis": "G_adversarial",
      "severity": "P0",
      "file": "src/polybuild/adapters/openrouter.py:312",
      "title": "Residual path traversal gadget in _parse_response despite Round 10.7 fix",
      "evidence": "worktree_resolved = worktree.resolve()\nfor rel_path, source in files.items():\n    abs_path = (worktree / rel_path).resolve()",
      "impact": "LLM-controlled `files` map (via prompt injection in builder voice) can still craft paths that survive `.resolve()` + `is_relative_to()` checks on certain platforms/filesystem configurations, allowing arbitrary file write.",
      "remediation": "Use `PurePath(rel_path).parts` + explicit prefix check + `os.path.commonpath` instead of `resolve()`+`is_relative_to()`. Add a strict allow-list of permitted subdirectories (src/, tests/, self_metrics.json only)."
    },
    {
      "id": "G-02",
      "axis": "G_adversarial",
      "severity": "P1",
      "file": "src/polybuild/orchestrator/__init__.py:682",
      "title": "TOCTOU in phase_minus_one_privacy_gate + AGENTS.md injection",
      "evidence": "agents_md_clean = sanitize_prompt_context(agents_md_path.read_text(...))\nadditional_context = ...",
      "impact": "Race between reading AGENTS.md for the privacy gate and later re-reading it inside every adapter's _load_agents_md(). An attacker who can modify AGENTS.md between these points can bypass PII scanning.",
      "remediation": "Read AGENTS.md once in the orchestrator, pass the sanitized bytes explicitly to all voices via VoiceConfig.context, and make adapters consume the provided string instead of re-reading the file."
    },
    {
      "id": "G-03",
      "axis": "G_adversarial",
      "severity": "P1",
      "file": "src/polybuild/adapters/*",
      "title": "Prompt injection surface remains large via raw_prompt role bypass",
      "evidence": "if cfg.context.get(\"raw_prompt\"): return spec.task_description",
      "impact": "Phase 5 critic/fixer/verifier prompts (which come from audit findings) are fed verbatim. A malicious or compromised auditor finding can carry injection strings that survive into builder voices later in the same run.",
      "remediation": "Add a secondary sanitizer layer (polybuild.security.prompt_sanitizer) on the raw_prompt path with strict output filtering (no <INSTRUCTIONS>, no <AGENTS_MD> tags allowed in verifier role). Enforce this in run_raw_prompt()."
    },
    {
      "id": "G-04",
      "axis": "G_adversarial",
      "severity": "P2",
      "file": "src/polybuild/concurrency/limiter.py:248",
      "title": "Fork-bomb / resource exhaustion via unbounded subprocesses",
      "evidence": "No global process limit or ulimit enforcement. Each adapter does asyncio.create_subprocess_exec with no cgroup/rlimit wrapper.",
      "impact": "A compromised or extremely verbose CLI adapter (or many parallel voices) can spawn enough subprocesses to exhaust file descriptors or memory on the host.",
      "remediation": "Add a global semaphore (e.g. max 16 concurrent CLIs) at orchestrator level and/or wrap subprocess creation with resource.setrlimit(RLIMIT_NPROC). Document in AGENTS.md."
    }
  ]
}
```