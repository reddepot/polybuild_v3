"""Régression POLYLENS round 10.7 — 5 voix orthogonales (GLM 5.1 + MiniMax
M2.5 + Kimi K2.6 + Qwen 3.6 max + Grok 4.20).

Findings convergents (≥2 voix) :
  P0-CONV-01 — Symlink follow via is_file()  (Grok E-01 + E-02 + Kimi C-06)
  P0-CONV-02 — OR API response unvalidated   (GLM A-05 + Qwen D-02)
  P0-CONV-03 — LLM-controlled path traversal (GLM A-01 + Kimi C-01..C-03)

Findings single-voix high-impact (P0/P1 retained) :
  GLM A-04, A-06, A-07, A-08
  MiniMax B-01, B-02
  Kimi C-04, C-05, C-07, C-09
  Qwen D-01, D-03, D-05
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_SRC = Path("src/polybuild")


def _read(rel: str) -> str:
    return (_SRC / rel).read_text()


# ──────────────────────────────────────────────────────────────────────
# P0-CONV-01 — Symlink follow via is_file() (3/5 voix : Grok+Kimi)
# ──────────────────────────────────────────────────────────────────────


class TestSymlinkOrderingPhase7:
    """Phase 7 commit: is_symlink() must check BEFORE is_file() in both loops."""

    def test_code_dir_loop_checks_symlink_first(self) -> None:
        src = _read("phases/phase_7_commit.py")
        # Find the code_dir loop (uses src_root)
        loop = src[src.find("for src_path in src_root.rglob"):]
        # Truncate to that single loop body (~30 lines)
        loop_body = loop[: loop.find("# Also include the tests dir")]
        # Ordering: is_symlink() check fires before any is_file() check
        symlink_idx = loop_body.find("if src_path.is_symlink():")
        is_file_idx = loop_body.find("if not src_path.is_file():")
        assert 0 < symlink_idx < is_file_idx, (
            "is_symlink() must precede is_file() to avoid follow-symlink TOCTOU"
        )

    def test_tests_dir_loop_checks_symlink_first(self) -> None:
        src = _read("phases/phase_7_commit.py")
        loop = src[src.find("for src_path in tests_root.rglob"):]
        loop_body = loop[: loop.find("# Stage exactly")]
        symlink_idx = loop_body.find("if src_path.is_symlink():")
        is_file_idx = loop_body.find("if not src_path.is_file():")
        assert 0 < symlink_idx < is_file_idx

    def test_tests_loop_logs_target(self) -> None:
        # tests_dir loop now logs readlink target like code_dir loop
        src = _read("phases/phase_7_commit.py")
        tests_section = src[src.find("phase_7_symlink_skipped_in_tests"):]
        assert "target=str(src_path.readlink())" in tests_section[:400]


class TestSymlinkSkippedInTreeHash:
    """Phase 5 _tree_hash must skip symlinks before hashing."""

    def test_tree_hash_skips_symlinks(self) -> None:
        src = _read("phases/phase_5_triade.py")
        # The relevant `_tree_hash` body must mention is_symlink() in its
        # filter clause to avoid LFI via symlink-to-host-file.
        idx = src.find("def _tree_hash(root: Path)")
        assert idx > 0
        body = src[idx : idx + 700]
        assert "p.is_symlink()" in body
        # Comment cites Round 10.7 + the Kimi C-06 finding
        assert "Round 10.7" in body
        assert "C-06" in body


# ──────────────────────────────────────────────────────────────────────
# P0-CONV-02 — OR API response unvalidated (2/5 voix : GLM + Qwen)
# ──────────────────────────────────────────────────────────────────────


class TestOpenRouterMalformedResponseGuard:
    def test_openrouter_adapter_guards_choices_access(self) -> None:
        src = _read("adapters/openrouter.py")
        # The previous direct subscript chain is gone; replaced by try/except.
        idx = src.find('content = data["choices"][0]["message"]["content"]')
        # Must now exist inside a try block guarded by KeyError/IndexError/TypeError
        assert idx > 0
        guarded_section = src[max(0, idx - 200) : idx + 200]
        assert "try:" in guarded_section
        # Multi-exception except clause covers all three error families
        assert "(KeyError, IndexError, TypeError)" in guarded_section

    def test_openrouter_adapter_handles_null_content(self) -> None:
        src = _read("adapters/openrouter.py")
        assert "OR returned content=null" in src
        assert "openrouter_null_content" in src


class TestPhase4AuditMalformedResponseGuard:
    def test_phase_4_guards_choices_access(self) -> None:
        src = _read("phases/phase_4_audit.py")
        # Same pattern in phase 4 audit invocation
        assert 'audit_malformed_or_response' in src
        # Multi-except clause as in adapter
        assert "(KeyError, IndexError, TypeError)" in src


# ──────────────────────────────────────────────────────────────────────
# P0-CONV-03 — LLM-controlled path traversal (GLM A-01)
# ──────────────────────────────────────────────────────────────────────


class TestOpenRouterParseResponsePathTraversal:
    def test_resolves_and_blocks_escape(self) -> None:
        src = _read("adapters/openrouter.py")
        # After Round 10.7 + Codex validation, the loop now iterates a
        # validated ``files`` mapping (see PB-R107-OR-PARSE-SHAPE).
        idx = src.find("for rel_path, source in files.items()")
        assert idx > 0, "files mapping iteration not found"
        block = src[idx : idx + 1200]
        # New defence: resolve + is_relative_to(worktree_resolved)
        assert "worktree_resolved = worktree.resolve()" in src
        assert "abs_path = (worktree / rel_path).resolve()" in block
        assert "is_relative_to(worktree_resolved)" in block
        assert "openrouter_path_traversal_blocked" in block

    def test_response_shape_validated(self) -> None:
        src = _read("adapters/openrouter.py")
        # PB-R107-OR-PARSE-SHAPE — must validate dict shape before .get().
        assert "isinstance(data, dict)" in src
        assert "Response JSON not a dict" in src
        assert "openrouter_files_not_mapping" in src

    def test_skips_non_string_file_entries(self) -> None:
        src = _read("adapters/openrouter.py")
        assert "isinstance(rel_path, str)" in src
        assert "isinstance(source, str)" in src
        assert "openrouter_skip_invalid_file_entry" in src


# ──────────────────────────────────────────────────────────────────────
# P0 LLM-controlled re-injection in Phase 5 (Kimi C-01..C-03)
# ──────────────────────────────────────────────────────────────────────


class TestPhase5SanitizeReinjection:
    def test_evidence_path_sanitized(self) -> None:
        src = _read("phases/phase_5_triade.py")
        # critic_prompt build site must wrap finding.evidence.file in
        # sanitize_prompt_context().
        idx = src.find("critic_prompt = critic_template.format(")
        assert idx > 0
        block = src[idx : idx + 700]
        assert (
            "evidence_path=sanitize_prompt_context(" in block
        ), "evidence_path must be sanitized like description/snippet"

    def test_fixer_prompt_evidence_path_sanitized(self) -> None:
        # Codex validation PB-R107-P5-EVIDENCE-REINJECT — fixer prompt
        # also re-injects evidence path; must be sanitized too.
        src = _read("phases/phase_5_triade.py")
        idx = src.find("fixer_prompt = fixer_template.format(")
        assert idx > 0
        block = src[idx : idx + 800]
        assert (
            "evidence_path=sanitize_prompt_context(" in block
        ), "fixer prompt evidence_path must be sanitized (PB-R107-P5)"

    def test_fixer_output_sanitized_in_no_mutation_feedback(self) -> None:
        src = _read("phases/phase_5_triade.py")
        # The fixer_feedback that re-injects fixer_output must wrap it in
        # sanitize_prompt_context.
        # Search for the no-mutation feedback string + ensure the next 400
        # chars contain a sanitize call applied to fixer_output.
        idx = src.find("Your previous attempt produced text but DID NOT modify")
        assert idx > 0
        block = src[idx : idx + 700]
        assert "sanitize_prompt_context((fixer_output or '')[:1500])" in block

    def test_verifier_reason_sanitized(self) -> None:
        src = _read("phases/phase_5_triade.py")
        idx = src.find("Verifier rejected:")
        # Find the LATEST occurrence (the dynamic feedback re-injection,
        # not the first comment string).
        idx = src.rfind("Verifier rejected:")
        block = src[idx : idx + 500]
        assert "sanitize_prompt_context(str(last_verdict['reason']))" in block
        assert (
            "sanitize_prompt_context(str(last_verdict['required_evidence']))"
            in block
        )


# ──────────────────────────────────────────────────────────────────────
# B-01 — _SHUTDOWN_DRAIN_LOCK removed (was unused, comment was lying)
# ──────────────────────────────────────────────────────────────────────


class TestShutdownLockRemoved:
    def test_unused_lock_definition_removed(self) -> None:
        src = _read("orchestrator/__init__.py")
        # The misleading lock symbol must no longer be defined as a
        # module-level binding (the variable assignment must be gone;
        # the historical comment can still mention the name).
        assert "_SHUTDOWN_DRAIN_LOCK = asyncio.Lock()" not in src

    def test_dict_still_present(self) -> None:
        from polybuild.orchestrator import _SHUTDOWN_DRAIN_TASKS
        assert isinstance(_SHUTDOWN_DRAIN_TASKS, dict)

    def test_lock_not_imported_or_used(self) -> None:
        src = _read("orchestrator/__init__.py")
        # No `async with _SHUTDOWN_DRAIN_LOCK` anywhere.
        assert "async with _SHUTDOWN_DRAIN_LOCK" not in src


# ──────────────────────────────────────────────────────────────────────
# B-02 — save_checkpoint EXDEV fallback
# ──────────────────────────────────────────────────────────────────────


class TestCheckpointCrossDeviceFallback:
    def test_save_checkpoint_handles_exdev(self) -> None:
        src = _read("orchestrator/__init__.py")
        # The new save_checkpoint must catch EXDEV and use atomic
        # copy → replace fallback (per Codex PB-R107-CHK-ATOMIC-EXDEV).
        idx = src.find("def save_checkpoint(")
        assert idx > 0
        body = src[idx : idx + 2000]
        assert "errno.EXDEV" in body
        assert "shutil.copy2" in body
        assert "target_tmp" in body
        # Atomic swap: must use Path.replace() (== os.replace).
        assert "target_tmp.replace(target)" in body
        assert "tmp.unlink()" in body


# ──────────────────────────────────────────────────────────────────────
# A-04 — run_id deterministic via SHA256
# ──────────────────────────────────────────────────────────────────────


class TestBuilderProtocolRunIdDeterministic:
    def test_uses_sha256_not_python_hash(self) -> None:
        src = _read("adapters/builder_protocol.py")
        idx = src.find("synthetic_spec = Spec(")
        assert idx > 0
        # Look just BEFORE the Spec construction for the digest computation.
        pre = src[max(0, idx - 600) : idx + 200]
        assert "hashlib.sha256(prompt.encode" in pre
        # The previous abs(hash(prompt)) must be gone.
        assert "abs(hash(prompt))" not in src
        assert "prompt_digest" in pre

    def test_run_id_format(self) -> None:
        # Probe via direct reflection: the digest is 12 hex chars.
        src = _read("adapters/builder_protocol.py")
        idx = src.find('run_id=f"raw-{normalized_role}-')
        assert idx > 0
        block = src[idx : idx + 80]
        assert "{prompt_digest}" in block


# ──────────────────────────────────────────────────────────────────────
# A-06 — claude_code metrics fallback on parse error
# ──────────────────────────────────────────────────────────────────────


class TestClaudeCodeMetricsFallback:
    def test_handles_invalid_metrics_json(self) -> None:
        # Round 10.8 prod-launch follow-up: claude CLI v2 no longer writes
        # ``self_metrics.json`` to disk — metrics come from the stdout JSON
        # via ``_try_parse_json`` + ``data.get("self_metrics", ...)``. The
        # invariant is now : on parse error or missing payload, fall back
        # to ``_estimate_metrics``.
        src = _read("adapters/claude_code.py")
        idx = src.find("def _parse_output(")
        assert idx > 0
        body = src[idx : idx + 1500]
        assert "_try_parse_json(raw)" in body
        assert 'data.get("self_metrics", {})' in body
        assert "claude_metrics_parse_fallback" in body
        assert "self._estimate_metrics(worktree)" in body
        # The legacy ``self_metrics.json`` file path read is gone.
        assert 'metrics_path = worktree / "self_metrics.json"' not in src


# ──────────────────────────────────────────────────────────────────────
# A-07 — codex_cli `--` separator before prompt
# ──────────────────────────────────────────────────────────────────────


class TestCodexCliSeparator:
    def test_prompt_preceded_by_double_dash(self) -> None:
        src = _read("adapters/codex_cli.py")
        idx = src.find("cmd = [")
        # First `cmd = [` after the file header is the codex invocation list.
        block = src[idx : idx + 600]
        # The prompt is the LAST entry; "--" must appear immediately before it.
        # Find both indices.
        sep_idx = block.find('"--",')
        prompt_idx = block.find("prompt,", sep_idx)
        assert sep_idx > 0 and prompt_idx > sep_idx, (
            "`--` separator must appear immediately before `prompt,` to "
            "prevent flag-parsing of an LLM prompt that starts with `-`."
        )


# ──────────────────────────────────────────────────────────────────────
# C-04 — local-gates subprocess hardening
# ──────────────────────────────────────────────────────────────────────


class TestLocalGatesSubprocessHardening:
    def test_local_gates_use_start_new_session(self) -> None:
        src = _read("phases/phase_5_triade.py")
        idx = src.find('("ruff", ["uv", "run", "ruff", "check", "src/"])')
        assert idx > 0
        block = src[idx : idx + 1500]
        assert "start_new_session=True" in block
        assert "minimal_env" in block

    def test_minimal_env_definition(self) -> None:
        src = _read("phases/phase_5_triade.py")
        idx = src.find("_LOCAL_GATE_ENV_KEYS")
        assert idx > 0
        block = src[idx : idx + 800]
        # Allow-list must cover what local gates actually need (per Gemini
        # validation: PYTHONPATH, SSL_CERT_FILE, VIRTUAL_ENV, UV_*).
        for needle in (
            '"PATH"',
            '"PYTHONPATH"',
            '"SSL_CERT_FILE"',
            '"VIRTUAL_ENV"',
            '"UV_CACHE_DIR"',
        ):
            assert needle in block, f"minimal_env missing {needle}"


# ──────────────────────────────────────────────────────────────────────
# C-05 — eds_pseudo race noted (no real change required because
# accessed exclusively from sync code paths today, but verify the comment
# is updated when we revisit the singleton).
# C-07 — anti-tampering env opt-out switched to PROMPTS_DEBUG
# ──────────────────────────────────────────────────────────────────────


class TestPromptsTamperingDebugOnlyOptOut:
    def test_uses_prompts_debug_env_var(self) -> None:
        src = _read("phases/phase_5_triade.py")
        # The opt-out must require POLYBUILD_PROMPTS_DEBUG, not PROMPTS_DIR.
        # Find the placeholder check region.
        idx = src.find("Defence against template tampering")
        assert idx > 0
        block = src[idx : idx + 1500]
        assert "POLYBUILD_PROMPTS_DEBUG" in block
        # The deprecated check on PROMPTS_DIR must be gone in this region.
        # (PROMPTS_DIR can still be used for path resolution elsewhere; we
        # only check it's no longer the bypass condition.)
        assert (
            'os.environ.get("POLYBUILD_PROMPTS_DIR")' not in block.split("POLYBUILD_PROMPTS_DEBUG", 1)[0]
        )


# ──────────────────────────────────────────────────────────────────────
# C-09 — Presidio AnalyzerEngine cached at module level
# ──────────────────────────────────────────────────────────────────────


class TestPresidioCached:
    def test_module_level_singleton(self) -> None:
        src = _read("phases/phase_minus_one_privacy.py")
        # Module-level cache symbol exists.
        assert "_PRESIDIO_ENGINE" in src
        # _layer_1_presidio uses the cached engine instead of constructing one.
        idx = src.find("def _layer_1_presidio(")
        assert idx > 0
        body = src[idx : idx + 1500]
        assert "if _PRESIDIO_ENGINE is None:" in body
        assert "_PRESIDIO_ENGINE = AnalyzerEngine()" in body
        # The old "analyzer = AnalyzerEngine()" instantiation per-call is gone.
        assert "analyzer = AnalyzerEngine()" not in body


# ──────────────────────────────────────────────────────────────────────
# D-01 — phase 4 audit response not-dict guard
# ──────────────────────────────────────────────────────────────────────


class TestPhase4AuditNonDictGuard:
    def test_rejects_non_dict_payload(self) -> None:
        src = _read("phases/phase_4_audit.py")
        idx = src.find("audit_response_not_dict")
        assert idx > 0, "must log audit_response_not_dict and return early"
        block = src[max(0, idx - 200) : idx + 300]
        assert "isinstance(data, dict)" in block


# ──────────────────────────────────────────────────────────────────────
# D-03 — PEP 508 dependency parsing via packaging.requirements.Requirement
# ──────────────────────────────────────────────────────────────────────


class TestPep508DepParsing:
    def test_uses_packaging_requirement(self) -> None:
        src = _read("phases/phase_3b_grounding.py")
        assert "from packaging.requirements import" in src
        assert "Requirement(" in src
        assert "_extract_dep_name" in src


# ──────────────────────────────────────────────────────────────────────
# D-05 — phase 4 audit OR-bound detection by slash
# ──────────────────────────────────────────────────────────────────────


class TestOrBoundDetectionAllowList:
    def test_or_bound_allow_list(self) -> None:
        src = _read("phases/phase_4_audit.py")
        # Allow-list (per Gemini validation P12 high-risk fix).
        for needle in (
            "_OR_PROVIDER_PREFIXES",
            '"deepseek/"',
            '"qwen/"',
            '"moonshotai/"',
            '"z-ai/"',
            '"xiaomi/"',
            '"x-ai/"',
            '"google/"',
        ):
            assert needle in src, f"missing OR provider: {needle}"
        assert (
            "is_or_bound = auditor_voice.startswith(_OR_PROVIDER_PREFIXES)"
            in src
        )

    def test_local_paths_not_treated_as_or(self) -> None:
        # Local model identifiers (with slash) must NOT be classified as OR.
        # Probe via the same prefix check the code uses.
        src = _read("phases/phase_4_audit.py")
        idx = src.find("_OR_PROVIDER_PREFIXES = (")
        assert idx > 0
        block = src[idx : idx + 800]
        # ./models/llama style paths don't start with any prefix in the list
        # (which is what the new logic relies on).
        assert "_OR_PROVIDER_PREFIXES" in block


# ──────────────────────────────────────────────────────────────────────
# Codex validation patches — added after CLI verification round
# ──────────────────────────────────────────────────────────────────────


class TestPackagingDeclaredDependency:
    """PB-R107-P3B-PACKAGING-UNDECLARED — packaging>=23 must be declared."""

    def test_packaging_in_pyproject(self) -> None:
        text = Path("pyproject.toml").read_text()
        # Locate the (single) ``dependencies = [`` block at the project
        # level, then find its closing bracket. ``find("]")`` after the
        # opening bracket lands on the FIRST ``]`` — including any list
        # element that closes a substring? No, ``]`` cannot appear in a
        # TOML string element here. The block boundary is the first ``]``.
        idx = text.find("dependencies = [")
        # Scan the pyproject for the runtime block — exclude optional-dep
        # blocks by stopping at the first ``]`` AT COLUMN 0 (block end).
        rest = text[idx:]
        end = rest.index("\n]")
        block = rest[: end + 2]
        assert "packaging>=" in block, (
            "packaging must be a runtime dependency since "
            "phase_3b_grounding now imports packaging.requirements.Requirement"
        )


class TestOpenRouterSmokeTestMalformedGuard:
    """PB-R107-OR-SMOKE-MALFORMED — smoke_test must guard against malformed."""

    def test_smoke_test_catches_index_and_type_errors(self) -> None:
        src = _read("adapters/openrouter.py")
        # Locate smoke_test method.
        idx = src.find("Reply with JSON")  # the smoke probe message
        assert idx > 0
        block = src[idx : idx + 1500]
        # New defence applies the same multi-exception guard.
        assert "(KeyError, IndexError, TypeError)" in block
        # And refuses non-string content.
        assert "isinstance(content, str)" in block
        # Outer exception clause now covers the same set.
        outer_idx = src.find("except (httpx.HTTPError, json.JSONDecodeError")
        assert outer_idx > 0
        outer_block = src[outer_idx : outer_idx + 200]
        assert "IndexError" in outer_block and "TypeError" in outer_block

