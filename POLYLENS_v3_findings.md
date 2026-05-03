# POLYLENS v3 — Multi-Axes Audit Results

**Date:** 2026-05-03
**Scope:** Axes B/C/D/E/F/G (axe A_security exhaustively covered by Round 10 — 7 sub-rounds)
**Voices:**

| Voice | Model | Axes | Findings |
|-------|-------|------|----------|
| Qwen 3.6 max | qwen/qwen3.6-max-preview | B_quality + C_tests | 13 (8B + 5C) |
| Kimi K2.6 | moonshotai/kimi-k2.6 | D_performance + E_architecture | 15 (7D + 8E) |
| Grok 4.20 | x-ai/grok-4.20 | F_documentation + G_adversarial | 7 (3F + 4G) |

**Total: 35 findings (4 P0, 24 P1, 7 P2)**

## Honeypots — All voices honest

| Voice | H1 (`_load_agents_md_sanitized`) | H2 (`MagicWeaverProtocol`) | H3 (`prompt_sanitizer`) |
|-------|----------------------------------|----------------------------|-------------------------|
| Qwen | ❌ False (correct) | ❌ False (correct) | ✅ True (correct) |
| Kimi | ❌ False (correct) | ❌ False (correct) | ✅ True (correct) |
| Grok | ❌ False (correct) | ❌ False (correct) | ✅ True (correct) |

## Patches Applied (POLYLENS v3 round)

### Quick wins (P1/P2 cosmetic, easy fixes)

| ID | Voice | File | Patch |
|----|-------|------|-------|
| Qwen B-01 | Qwen | claude_code.py:241 | Removed dead inner docstring |
| Qwen B-02 | Qwen | models.py:90 | datetime.utcnow → datetime.now(UTC) |
| Qwen B-04 | Qwen | phase_0_spec.py:221 | OR malformed-response guard (try/except + isinstance) |
| Qwen B-05 | Qwen | phase_0_spec.py:285-293 | Greedy `\{.*\}` → non-greedy + LAST-balanced |
| Kimi D-02 | Kimi | claude_code.py:302 + codex_cli.py:238 | _estimate_metrics single-pass file reads |
| Grok F-02 | Grok | __init__.py:1 | Removed "TODO post-round 4" lies for Phase -1 + Phase 8 |

### Backlog — needs ADR + dedicated sprint

These findings are valid but require architectural decisions:

| ID | Voice | Severity | File | Title |
|----|-------|----------|------|-------|
| Kimi D-01 | Kimi | P0 | claude_code._estimate_metrics | Sync I/O blocking event loop |
| Kimi D-07 | Kimi | P0 | adapters/openrouter.py | Sync write_text in async generate |
| Kimi D-04 | Kimi | P1 | domain_gates/validate_sqlite.py | Sync DB ops in async gate |
| Kimi D-03 | Kimi | P1 | orchestrator save_checkpoint | Sync json.dumps + write |
| Kimi D-05 | Kimi | P1 | models.py BuilderResult.raw_output | Unbounded string retention |
| Kimi D-06 | Kimi | P1 | adapters _load_agents_md | No cross-call cache |
| Kimi E-01 | Kimi | P0 | phase_0_spec | Direct CLI/HTTP bypassing adapter |
| Kimi E-02 | Kimi | P1 | orchestrator | Tight coupling to phases |
| Kimi E-03 | Kimi | P1 | models VoiceConfig.context | Untyped magic dict |
| Kimi E-04 | Kimi | P1 | adapters/__init__ get_builder | Hardcoded factory |
| Kimi E-05 | Kimi | P1 | builder_protocol run_raw_prompt | Default impl leaks fs |
| Kimi E-06 | Kimi | P1 | models TokenUsage | Provider-specific flat fields |
| Kimi E-07 | Kimi | P1 | orchestrator | Mixed infra + business logic |
| Kimi E-08 | Kimi | P1 | cli.py | Direct adapter instantiation |
| Grok G-01 | Grok | P0 | adapters/openrouter.py:312 | Path traversal residual (speculative) |
| Grok G-02 | Grok | P1 | phase_minus_one_privacy + adapters | TOCTOU AGENTS.md |
| Grok G-03 | Grok | P1 | adapters/* | raw_prompt prompt-injection surface |
| Grok G-04 | Grok | P2 | concurrency/limiter | Fork-bomb / no rlimit |
| Qwen B-03 | Qwen | P1 | codex_cli.py:168 | Python list repr injected |
| Qwen B-06 | Qwen | P1 | validate_sqlite.py:89 | Raw schema string compare |
| Qwen B-07 | Qwen | P2 | concurrency/limiter.py:288 | _inflight decrement masks state |
| Qwen B-08 | Qwen | P2 | validate_rag.py:78 | assert in production |
| Qwen C-01 to C-05 | Qwen | P1 | various | Missing concurrent / mutation / pipe / contract / FTS5-error tests |
| Grok F-01 | Grok | P1 | builder_protocol.py:78 | Stale docstring (false positive — line was about is_available) |
| Grok F-03 | Grok | P2 | claude_code.py:130 | Inaccurate comment (false positive — line was about smoke_test) |

These findings are recorded for future sprints. The biggest theme is **async hygiene** — many sync I/O paths in async functions that should use `asyncio.to_thread`. This is a coherent refactor that should be tackled as a single ADR-led sprint rather than piecemeal.

## Tests Added

`tests/regression/test_polylens_v3_patches.py` — 8 regression tests covering all 6 applied patches.

## Final Gates Status

- ruff check src/ — **clean**
- mypy --strict src/ — **clean** (38 source files)
- pytest tests/regression/ — **all passing** (152 tests visible across rounds)
- bandit -r src/ -ll — **9 Low only, no Medium/High**
- pip-audit — 4 transitive CVEs noted (lxml, pillow, pytest, python-multipart) — not in direct deps

---

Round 10.7 + POLYLENS v3 brings POLYBUILD v3 to a hardened state. The remaining backlog items are architectural improvements that warrant their own dedicated cycle.
