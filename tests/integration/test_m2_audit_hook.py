"""Integration tests for M2C — async POLYLENS audit hook.

Covers:
  * queue / backlog persistence (append + read + drain + dedup),
  * voice rotation (W + CN pair invariant, round-robin),
  * runner with mocked voice callers (silent fallback, parsing,
    fingerprint dedup),
  * the W + CN invariant (anti-pattern #20 monoculture).

All tests are mock-only — no LLM calls, no network, no subprocess.
The runner's ``voice_caller`` parameter is the test-only DI hook.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from polybuild.audit import (
    AuditQueueEntry,
    BacklogFinding,
    VoicePair,
    append_findings,
    append_queue_entry,
    audit_commit,
    compute_fingerprint,
    drain_queue,
    pick_voice_pair,
    read_backlog,
    read_queue,
    reset_rotation,
)
from polybuild.audit.rotation import CHINESE_VOICES, WESTERN_VOICES


# ────────────────────────────────────────────────────────────────
# QUEUE — append / read / drain
# ────────────────────────────────────────────────────────────────


class TestQueue:
    def test_append_and_read_roundtrip(self, tmp_path: Path) -> None:
        entry = AuditQueueEntry(
            commit_sha="abc1234",
            repo_path=tmp_path,
            branch="main",
        )
        append_queue_entry(entry, queue_dir=tmp_path)

        loaded = read_queue(queue_dir=tmp_path)
        assert len(loaded) == 1
        assert loaded[0].commit_sha == "abc1234"
        assert loaded[0].branch == "main"

    def test_drain_clears_queue(self, tmp_path: Path) -> None:
        for sha in ("aaaaaaa", "bbbbbbb", "ccccccc"):
            append_queue_entry(
                AuditQueueEntry(commit_sha=sha, repo_path=tmp_path),
                queue_dir=tmp_path,
            )
        drained = list(drain_queue(queue_dir=tmp_path))
        assert [e.commit_sha for e in drained] == ["aaaaaaa", "bbbbbbb", "ccccccc"]
        # Queue is empty after a successful drain.
        assert read_queue(queue_dir=tmp_path) == []

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        # Manually inject a bad line alongside a valid one.
        entry = AuditQueueEntry(commit_sha="ddddddd", repo_path=tmp_path)
        append_queue_entry(entry, queue_dir=tmp_path)
        from polybuild.audit.queue import queue_path

        qpath = queue_path(tmp_path)
        with qpath.open("a", encoding="utf-8") as f:
            f.write("garbage not json\n")
            f.write("{}{}\n")

        loaded = read_queue(queue_dir=tmp_path)
        assert len(loaded) == 1
        assert loaded[0].commit_sha == "ddddddd"

    def test_empty_queue_returns_empty_list(self, tmp_path: Path) -> None:
        assert read_queue(queue_dir=tmp_path) == []
        assert list(drain_queue(queue_dir=tmp_path)) == []


# ────────────────────────────────────────────────────────────────
# BACKLOG — fingerprint + dedup
# ────────────────────────────────────────────────────────────────


class TestBacklog:
    def test_fingerprint_is_deterministic(self) -> None:
        fp1 = compute_fingerprint("abc", "src/foo.py", 42, "A_security", "SQL injection")
        fp2 = compute_fingerprint("abc", "src/foo.py", 42, "A_security", "SQL injection")
        assert fp1 == fp2

    def test_fingerprint_normalises_message(self) -> None:
        fp1 = compute_fingerprint("abc", "f", 1, "A_security", "SQL injection")
        fp2 = compute_fingerprint("abc", "f", 1, "A_security", "  SQL  Injection  ")
        # Whitespace + case differences are normalised away.
        assert fp1 == fp2

    def test_fingerprint_distinguishes_axis(self) -> None:
        fp_a = compute_fingerprint("abc", "f", 1, "A_security", "issue")
        fp_g = compute_fingerprint("abc", "f", 1, "G_adversarial", "issue")
        assert fp_a != fp_g

    def test_dedup_within_window(self, tmp_path: Path) -> None:
        f = BacklogFinding(
            fingerprint="fp1" + "0" * 13,
            commit_sha="abc",
            file="src/foo.py",
            line=10,
            axis="A_security",
            severity="P0",
            message="x",
            voice="codex-gpt-5.5",
        )
        w1, d1 = append_findings([f, f, f], backlog_dir=tmp_path)
        assert (w1, d1) == (1, 2)

        # Adding the same fingerprint again later is still deduped.
        w2, d2 = append_findings([f], backlog_dir=tmp_path)
        assert (w2, d2) == (0, 1)

        loaded = read_backlog(backlog_dir=tmp_path)
        assert len(loaded) == 1

    def test_severity_filter(self, tmp_path: Path) -> None:
        for i, sev in enumerate(["P0", "P1", "P2"]):
            append_findings(
                [
                    BacklogFinding(
                        fingerprint=f"fp{i:030d}",
                        commit_sha="abc",
                        file="f",
                        axis="A_security",
                        severity=sev,  # type: ignore[arg-type]
                        message=f"msg-{i}",
                        voice="v",
                    )
                ],
                backlog_dir=tmp_path,
            )
        p0 = read_backlog(backlog_dir=tmp_path, severity="P0")
        assert len(p0) == 1
        assert p0[0].severity == "P0"


# ────────────────────────────────────────────────────────────────
# ROTATION — round-robin W + CN, anti-pattern #20
# ────────────────────────────────────────────────────────────────


class TestRotation:
    def test_pair_is_western_plus_chinese(self, tmp_path: Path) -> None:
        pair = pick_voice_pair(state_dir=tmp_path)
        assert isinstance(pair, VoicePair)
        assert pair.western in WESTERN_VOICES
        assert pair.chinese in CHINESE_VOICES

    def test_advances_on_each_pick(self, tmp_path: Path) -> None:
        seen: list[tuple[str, str]] = []
        for _ in range(6):
            p = pick_voice_pair(state_dir=tmp_path)
            seen.append((p.western, p.chinese))
        # 3 Western × 5 Chinese = 15 unique pairs over a full cycle; 6
        # consecutive picks must produce at least 4 different Western
        # voices' visits (cycle length 3).
        westerns = {pair[0] for pair in seen}
        assert westerns == set(WESTERN_VOICES)

    def test_reset_rotation(self, tmp_path: Path) -> None:
        # Advance a few times, then reset, then verify we are back at
        # the head of each pool.
        for _ in range(3):
            pick_voice_pair(state_dir=tmp_path)
        reset_rotation(state_dir=tmp_path)
        pair = pick_voice_pair(state_dir=tmp_path)
        assert pair.western == WESTERN_VOICES[0]
        assert pair.chinese == CHINESE_VOICES[0]


# ────────────────────────────────────────────────────────────────
# RUNNER — DI voice_caller, parsing, silent fallback
# ────────────────────────────────────────────────────────────────


def _make_voice_caller(
    western_output: str = "",
    chinese_output: str = "",
) -> Callable[[str, str], Awaitable[str]]:
    """Build a voice-caller mock that returns canned text per pool."""

    async def _caller(voice_id: str, _prompt: str) -> str:
        if voice_id in WESTERN_VOICES:
            return western_output
        if voice_id in CHINESE_VOICES:
            return chinese_output
        return ""

    return _caller


def _stub_diff(diff: str) -> Callable[..., str]:
    return lambda *_args, **_kwargs: diff


class TestRunner:
    @pytest.mark.asyncio
    async def test_parses_findings_from_both_voices(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = AuditQueueEntry(commit_sha="cafebab", repo_path=tmp_path)

        # Mock diff extraction to bypass git.
        monkeypatch.setattr(
            "polybuild.audit.runner.extract_commit_diff",
            _stub_diff("--- a/src/foo.py\n+++ b/src/foo.py\n+pass"),
        )

        caller = _make_voice_caller(
            western_output=json.dumps(
                {
                    "axis": "A_security",
                    "severity": "P0",
                    "file": "src/foo.py",
                    "line": 10,
                    "message": "command injection in subprocess",
                }
            )
            + "\n",
            chinese_output=json.dumps(
                {
                    "axis": "G_adversarial",
                    "severity": "P1",
                    "file": "src/foo.py",
                    "line": 12,
                    "message": "missing input sanitisation",
                }
            )
            + "\n",
        )

        findings = await audit_commit(
            entry, voice_caller=caller, state_dir=tmp_path
        )
        assert len(findings) == 2
        sevs = sorted(f.severity for f in findings)
        assert sevs == ["P0", "P1"]
        # Voices are correctly attributed.
        voices = {f.voice for f in findings}
        assert any(v in WESTERN_VOICES for v in voices)
        assert any(v in CHINESE_VOICES for v in voices)

    @pytest.mark.asyncio
    async def test_garbage_output_returns_no_findings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = AuditQueueEntry(commit_sha="cafebab", repo_path=tmp_path)
        monkeypatch.setattr(
            "polybuild.audit.runner.extract_commit_diff",
            _stub_diff("--- a/x\n+++ b/x\n+x"),
        )
        caller = _make_voice_caller(
            western_output="not json at all",
            chinese_output="this is also garbage",
        )
        findings = await audit_commit(
            entry, voice_caller=caller, state_dir=tmp_path
        )
        assert findings == []

    @pytest.mark.asyncio
    async def test_voice_exception_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = AuditQueueEntry(commit_sha="cafebab", repo_path=tmp_path)
        monkeypatch.setattr(
            "polybuild.audit.runner.extract_commit_diff",
            _stub_diff("--- a/x\n+++ b/x\n+x"),
        )

        async def boom(_voice_id: str, _prompt: str) -> str:
            raise RuntimeError("voice down")

        # Both voices throw → no findings, no exception.
        findings = await audit_commit(
            entry, voice_caller=boom, state_dir=tmp_path
        )
        assert findings == []

    @pytest.mark.asyncio
    async def test_invalid_axis_severity_filtered(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = AuditQueueEntry(commit_sha="cafebab", repo_path=tmp_path)
        monkeypatch.setattr(
            "polybuild.audit.runner.extract_commit_diff",
            _stub_diff("+x"),
        )

        # Bogus axis + bogus severity + missing fields — none should
        # produce a finding, the rest of the response is normal.
        bad = "\n".join(
            [
                json.dumps(
                    {
                        "axis": "Z_unknown",
                        "severity": "P0",
                        "file": "src/foo.py",
                        "message": "x",
                    }
                ),
                json.dumps(
                    {
                        "axis": "A_security",
                        "severity": "P9",  # invalid
                        "file": "src/foo.py",
                        "message": "x",
                    }
                ),
                json.dumps(
                    {"axis": "A_security", "severity": "P0", "file": "f"}
                ),  # missing message
                json.dumps(
                    {
                        "axis": "A_security",
                        "severity": "P0",
                        "file": "src/foo.py",
                        "message": "valid finding",
                    }
                ),
            ]
        )
        findings = await audit_commit(
            entry,
            voice_caller=_make_voice_caller(western_output=bad, chinese_output=""),
            state_dir=tmp_path,
        )
        assert len(findings) == 1
        assert findings[0].message == "valid finding"

    @pytest.mark.asyncio
    async def test_empty_diff_skips_audit(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        entry = AuditQueueEntry(commit_sha="cafebab", repo_path=tmp_path)
        monkeypatch.setattr(
            "polybuild.audit.runner.extract_commit_diff",
            _stub_diff(""),
        )
        # Voice caller should never be invoked.
        called = []

        async def caller(voice_id: str, _prompt: str) -> str:
            called.append(voice_id)
            return ""

        findings = await audit_commit(
            entry, voice_caller=caller, state_dir=tmp_path
        )
        assert findings == []
        assert called == []


# ────────────────────────────────────────────────────────────────
# DEFAULT VOICE CALLER — silent fallback when binaries missing
# ────────────────────────────────────────────────────────────────


class TestDefaultVoiceCaller:
    @pytest.mark.asyncio
    async def test_unknown_voice_returns_empty(self) -> None:
        from polybuild.audit.runner import default_voice_caller

        result = await default_voice_caller("totally-fake-voice-id", "prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_openrouter_no_key_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.runner import default_voice_caller

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        result = await default_voice_caller("z-ai/glm-5.1", "prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_western_cli_missing_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.runner import default_voice_caller

        # Pretend ``codex`` is not on PATH.
        with patch("shutil.which", return_value=None):
            result = await default_voice_caller("codex-gpt-5.5", "prompt")
        assert result == ""
