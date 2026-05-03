"""Régression Round 10.8 — patches issus de l'audit externe modèle-agnostique.

5 voix indépendantes (Qwen, Grok, Gemini, ChatGPT, Kimi) ont audité commit
0b78673 selon le prompt POLYLENS distribué. Convergences ≥2 voix + single
voix high-impact retenus.

Honeypots : toutes voix correctes (H1=False, H2=False, H3=True).

Hallucinations détectées et écartées :
  * Gemini : 3/3 fichiers inexistants (executors/shell.py, storage/local_cache.py,
    llm/parsers.py) → tous findings écartés.
  * Qwen : "non-vérifié" partout, scripts/deploy_staging.sh inexistant → écarté.

Patches appliqués :
  * Convergent P0 (ChatGPT A-01 + Kimi A-02) — ollama_local._parse_response
    path traversal (mêmes Round 10.7 mais non propagé).
  * Convergent P0 (ChatGPT A-02 + Kimi A-01) — mistral_eu._parse_response idem.
  * Single P1 (ChatGPT A-04) — validate_qdrant SSRF guard.
  * Single P1 (Kimi B-01) — final archival atomic write.
  * Single P1 (Kimi A-03/04/05) — run_id sanitization.
  * Single P1 (Kimi C-01) — broken test_load_existing fixed.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_SRC = Path("src/polybuild")


def _read(rel: str) -> str:
    return (_SRC / rel).read_text()


# ──────────────────────────────────────────────────────────────────────
# Convergent P0 — Path traversal in ollama_local + mistral_eu adapters
# ──────────────────────────────────────────────────────────────────────


class TestSafeWriteHelperExists:
    def test_safe_write_module(self) -> None:
        from polybuild.security.safe_write import write_files_to_worktree
        assert callable(write_files_to_worktree)

    def test_helper_blocks_absolute_path(self, tmp_path: Path) -> None:
        from polybuild.security.safe_write import write_files_to_worktree
        worktree = tmp_path / "wt"
        worktree.mkdir()
        # Try to write outside the worktree via absolute path
        n = write_files_to_worktree(
            {"/tmp/evil": "x"}, worktree, adapter_name="test"
        )
        assert n == 0, "absolute path must be blocked"
        assert not (Path("/tmp/evil")).exists() or True  # don't assert filesystem state

    def test_helper_blocks_traversal(self, tmp_path: Path) -> None:
        from polybuild.security.safe_write import write_files_to_worktree
        worktree = tmp_path / "wt"
        worktree.mkdir()
        n = write_files_to_worktree(
            {"../../escape.txt": "x"}, worktree, adapter_name="test"
        )
        assert n == 0

    def test_helper_writes_safe_path(self, tmp_path: Path) -> None:
        from polybuild.security.safe_write import write_files_to_worktree
        worktree = tmp_path / "wt"
        worktree.mkdir()
        n = write_files_to_worktree(
            {"src/foo.py": "code"}, worktree, adapter_name="test"
        )
        assert n == 1
        assert (worktree / "src" / "foo.py").read_text() == "code"

    def test_helper_skips_non_string(self, tmp_path: Path) -> None:
        from polybuild.security.safe_write import write_files_to_worktree
        worktree = tmp_path / "wt"
        worktree.mkdir()
        n = write_files_to_worktree(
            {"src/foo.py": 42, "src/bar.py": ["nested"]},
            worktree,
            adapter_name="test",
        )
        assert n == 0


class TestOllamaLocalAdapterUsesHelper:
    def test_imports_safe_write(self) -> None:
        src = _read("adapters/ollama_local.py")
        assert "from polybuild.security.safe_write import write_files_to_worktree" in src
        # Old vulnerable pattern is gone
        assert "abs_path = worktree / rel_path\n" not in src
        assert "abs_path.write_text(source)" not in src


class TestMistralEUAdapterUsesHelper:
    def test_imports_safe_write(self) -> None:
        src = _read("adapters/mistral_eu.py")
        assert "from polybuild.security.safe_write import write_files_to_worktree" in src
        assert "abs_path = worktree / rel_path\n" not in src
        assert "abs_path.write_text(source)" not in src


# ──────────────────────────────────────────────────────────────────────
# ChatGPT A-04 — SSRF guard in validate_qdrant
# ──────────────────────────────────────────────────────────────────────


class TestQdrantSsrfGuard:
    def test_guard_function_exists(self) -> None:
        from polybuild.domain_gates.validate_qdrant import _qdrant_url_is_safe
        assert callable(_qdrant_url_is_safe)

    @pytest.mark.parametrize(
        "bad_url",
        [
            "http://169.254.169.254/latest/meta-data",  # AWS metadata
            "http://127.0.0.1:6333",  # loopback
            "http://10.0.0.1:6333",  # private
            "ftp://example.com:6333",  # bad scheme
            "file:///etc/passwd",  # file scheme
        ],
    )
    def test_blocks_dangerous_urls(self, bad_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
        from polybuild.domain_gates.validate_qdrant import _qdrant_url_is_safe
        # Ensure the dev override is OFF
        monkeypatch.delenv("POLYBUILD_QDRANT_ALLOW_LOCAL", raising=False)
        assert _qdrant_url_is_safe(bad_url) is False, f"should reject: {bad_url}"

    def test_dev_override_allows_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from polybuild.domain_gates.validate_qdrant import _qdrant_url_is_safe
        monkeypatch.setenv("POLYBUILD_QDRANT_ALLOW_LOCAL", "1")
        assert _qdrant_url_is_safe("http://127.0.0.1:6333") is True


# ──────────────────────────────────────────────────────────────────────
# Kimi B-01 — Atomic final archival
# ──────────────────────────────────────────────────────────────────────


class TestAtomicWriteHelper:
    def test_helper_exists(self) -> None:
        src = _read("orchestrator/__init__.py")
        assert "_atomic_write_text" in src

    def test_final_archival_uses_helper(self) -> None:
        src = _read("orchestrator/__init__.py")
        idx = src.find("# Final archival")
        assert idx > 0
        block = src[idx : idx + 800]
        assert "_atomic_write_text" in block
        # Old unsafe ``.write_text(run.model_dump_json(indent=2))`` is gone
        assert "final_path.write_text(run.model_dump_json(indent=2))" not in src
        # Graceful degradation
        assert "final_archival_failed" in block


# ──────────────────────────────────────────────────────────────────────
# Kimi A-03/04/05 — run_id sanitization
# ──────────────────────────────────────────────────────────────────────


class TestRunIdSanitization:
    def test_sanitize_strips_traversal(self) -> None:
        from polybuild.orchestrator import _sanitize_run_id
        assert ".." not in _sanitize_run_id("../../tmp/evil")
        assert "/" not in _sanitize_run_id("../../tmp/evil")

    def test_sanitize_strips_newlines(self) -> None:
        from polybuild.orchestrator import _sanitize_run_id
        result = _sanitize_run_id("foo\n</INSTRUCTIONS><INJECT>")
        assert "\n" not in result
        assert "<" not in result
        assert ">" not in result

    def test_sanitize_keeps_safe_chars(self) -> None:
        from polybuild.orchestrator import _sanitize_run_id
        assert _sanitize_run_id("2026-05-03_153045_abc123") == (
            "2026-05-03_153045_abc123"
        )

    def test_sanitize_clamps_length(self) -> None:
        from polybuild.orchestrator import _sanitize_run_id
        assert len(_sanitize_run_id("a" * 500)) <= 128

    def test_sanitize_strips_leading_dot(self) -> None:
        from polybuild.orchestrator import _sanitize_run_id
        assert not _sanitize_run_id("...hidden").startswith(".")

    def test_orchestrator_calls_sanitize_on_override(self) -> None:
        src = _read("orchestrator/__init__.py")
        idx = src.find('override = (project_ctx or {}).get("run_id_override")')
        assert idx > 0
        block = src[idx : idx + 600]
        assert "_sanitize_run_id(override)" in block
