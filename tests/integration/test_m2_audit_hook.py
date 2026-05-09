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

    def test_drain_returns_entries_without_truncating(self, tmp_path: Path) -> None:
        # POLYLENS-FIX-3 P1: drain_queue is now a snapshot read; entries
        # remain in the queue until ``mark_entry_processed`` removes them.
        for sha in ("aaaaaaa", "bbbbbbb", "ccccccc"):
            append_queue_entry(
                AuditQueueEntry(commit_sha=sha, repo_path=tmp_path),
                queue_dir=tmp_path,
            )
        drained = list(drain_queue(queue_dir=tmp_path))
        assert [e.commit_sha for e in drained] == ["aaaaaaa", "bbbbbbb", "ccccccc"]
        # Queue is NOT cleared by drain_queue alone — entries persist for
        # replay if the caller crashes mid-processing.
        assert len(read_queue(queue_dir=tmp_path)) == 3

    def test_mark_entry_processed_removes_one(self, tmp_path: Path) -> None:
        from polybuild.audit import mark_entry_processed

        entries = [
            AuditQueueEntry(commit_sha=sha, repo_path=tmp_path)
            for sha in ("aaaaaaa", "bbbbbbb", "ccccccc")
        ]
        for e in entries:
            append_queue_entry(e, queue_dir=tmp_path)

        # Mark only the middle one processed. The other two stay.
        assert mark_entry_processed(entries[1], queue_dir=tmp_path) is True
        remaining = read_queue(queue_dir=tmp_path)
        assert [e.commit_sha for e in remaining] == ["aaaaaaa", "ccccccc"]

        # Marking the same entry again is a no-op (idempotent).
        assert mark_entry_processed(entries[1], queue_dir=tmp_path) is False

    def test_drain_replay_safety_on_caller_crash(self, tmp_path: Path) -> None:
        from polybuild.audit import mark_entry_processed

        for sha in ("aaaaaaa", "bbbbbbb", "ccccccc"):
            append_queue_entry(
                AuditQueueEntry(commit_sha=sha, repo_path=tmp_path),
                queue_dir=tmp_path,
            )
        # Simulate a caller crash mid-iteration: we drain, mark one,
        # then "crash" without marking the others.
        drained = list(drain_queue(queue_dir=tmp_path))
        mark_entry_processed(drained[0], queue_dir=tmp_path)
        # raise RuntimeError("simulate crash") would happen here.
        # On the next drain, the un-marked entries are still available.
        survivors = read_queue(queue_dir=tmp_path)
        assert {e.commit_sha for e in survivors} == {"bbbbbbb", "ccccccc"}

    def test_mark_entry_processed_atomic(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # POLYLENS run #2 P0 regression: a crash mid-rewrite must NOT
        # lose any unprocessed entries from the queue. We simulate the
        # crash by forcing the atomic helper to raise after we've
        # decided what to keep but before the rename lands.
        from polybuild.audit import _atomic_io, mark_entry_processed

        e1 = AuditQueueEntry(commit_sha="aaaaaaa", repo_path=tmp_path)
        e2 = AuditQueueEntry(commit_sha="bbbbbbb", repo_path=tmp_path)
        for e in (e1, e2):
            append_queue_entry(e, queue_dir=tmp_path)

        def boom(*_a: object, **_kw: object) -> None:
            raise OSError("simulated crash")

        monkeypatch.setattr(_atomic_io, "atomic_write_text", boom)
        # mark_entry_processed imports the helper at module scope, so
        # patch the binding it actually uses too.
        from polybuild.audit import queue as queue_mod

        monkeypatch.setattr(queue_mod, "atomic_write_text", boom)

        with pytest.raises(OSError, match="simulated crash"):
            mark_entry_processed(e1, queue_dir=tmp_path)

        # Both entries still in the queue (not lost).
        assert {x.commit_sha for x in read_queue(queue_dir=tmp_path)} == {
            "aaaaaaa",
            "bbbbbbb",
        }

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
    *,
    inject_canary: bool = True,
) -> Callable[[str, str], Awaitable[str]]:
    """Build a voice-caller mock that returns canned text per pool.

    POLYLENS-FIX-2 P1: the runner now requires every voice response to
    echo ``_AUDIT_CANARY``; we auto-append it so existing fixtures stay
    valid. Tests that exercise the canary-missing path pass
    ``inject_canary=False`` explicitly.
    """
    from polybuild.audit.runner import _AUDIT_CANARY

    if inject_canary:
        if western_output and _AUDIT_CANARY not in western_output:
            western_output = western_output.rstrip("\n") + "\n" + _AUDIT_CANARY
        if chinese_output and _AUDIT_CANARY not in chinese_output:
            chinese_output = chinese_output.rstrip("\n") + "\n" + _AUDIT_CANARY

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
    async def test_canary_missing_discards_all_findings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POLYLENS-FIX-2 P1: a response without the canary is treated as
        evidence of prompt-injection — all findings dropped."""
        entry = AuditQueueEntry(commit_sha="cafebab", repo_path=tmp_path)
        monkeypatch.setattr(
            "polybuild.audit.runner.extract_commit_diff",
            _stub_diff("--- a/x\n+++ b/x\n+x"),
        )
        # Voices respond with valid JSON-Lines but FORGET the canary
        # (simulating a successful prompt injection). Findings discarded.
        valid_json = json.dumps(
            {
                "axis": "A_security",
                "severity": "P0",
                "file": "src/x.py",
                "line": 1,
                "message": "would be a real finding",
            }
        )
        caller = _make_voice_caller(
            western_output=valid_json,
            chinese_output=valid_json,
            inject_canary=False,
        )
        findings = await audit_commit(
            entry, voice_caller=caller, state_dir=tmp_path
        )
        assert findings == []

    def test_canary_in_middle_is_rejected(self) -> None:
        """POLYLENS run #2 P1: a canary anywhere but the last line is
        treated as evidence of injection. The diff coerced the voice to
        echo the canary early so the trailing junk could suppress real
        findings."""
        from polybuild.audit.runner import _AUDIT_CANARY, _parse_voice_output

        valid = json.dumps(
            {
                "axis": "A_security",
                "severity": "P0",
                "file": "x.py",
                "line": 1,
                "message": "x",
            }
        )
        # Canary in the middle, garbage at the end → rejected.
        raw = f"{_AUDIT_CANARY}\n{valid}\nfoo bar baz"
        assert _parse_voice_output(raw, "codex-gpt-5.5", "abc1234") == []

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

    def test_extract_commit_diff_arg_max_byte_guard(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POLYLENS run #2 P2: a single ENORMOUS minified line slips
        past ``MAX_DIFF_LINES`` because the line cap counts newlines.
        The byte cap must still kick in to keep the prompt from
        blowing ARG_MAX when passed to a CLI."""
        from polybuild.audit.runner import (
            MAX_DIFF_BYTES,
            extract_commit_diff,
        )

        # Build a fake `git show` output: one line, 2 MB long.
        giant = "+x" + ("A" * (2 * 1024 * 1024))

        class _FakeProc:
            returncode = 0
            stdout = giant

        monkeypatch.setattr(
            "polybuild.audit.runner.shutil.which", lambda _name: "/usr/bin/git"
        )
        monkeypatch.setattr(
            "polybuild.audit.runner.subprocess.run",
            lambda *_a, **_kw: _FakeProc(),
        )
        result = extract_commit_diff(tmp_path, "abc1234")
        assert len(result.encode("utf-8")) <= MAX_DIFF_BYTES + 200
        assert "ARG_MAX guard" in result


# ────────────────────────────────────────────────────────────────
# DEFAULT VOICE CALLER — silent fallback when binaries missing
# ────────────────────────────────────────────────────────────────


class TestNotifier:
    def _make_finding(
        self,
        severity: str = "P0",
        fingerprint: str = "fp" + "0" * 30,
        message: str = "test finding",
    ) -> BacklogFinding:
        return BacklogFinding(
            fingerprint=fingerprint,
            commit_sha="cafebab",
            file="src/foo.py",
            line=10,
            axis="A_security",
            severity=severity,  # type: ignore[arg-type]
            message=message,
            voice="codex-gpt-5.5",
        )

    def test_notify_persists_all_severities(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polybuild.audit.notifier import notify_findings

        # Disable both surfaces so we don't actually fire osascript /
        # write to stderr in the test runner.
        monkeypatch.setattr(
            "polybuild.audit.notifier._send_macos_banner", lambda **_: True
        )

        findings = [
            self._make_finding(severity=sev, fingerprint=f"fp{i:030d}")
            for i, sev in enumerate(["P0", "P1", "P2", "P3"])
        ]
        counts = notify_findings(findings, backlog_dir=tmp_path)
        assert counts == {"P0": 1, "P1": 1, "P2": 1, "P3": 1}
        # All four (incl. P2/P3) reach the backlog.
        loaded = read_backlog(backlog_dir=tmp_path)
        assert {f.severity for f in loaded} == {"P0", "P1", "P2", "P3"}

    def test_notify_dry_run_skips_persist(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polybuild.audit.notifier import notify_findings

        monkeypatch.setattr(
            "polybuild.audit.notifier._send_macos_banner", lambda **_: True
        )

        notify_findings([self._make_finding("P0")], backlog_dir=tmp_path, persist=False)
        # Backlog is untouched.
        assert read_backlog(backlog_dir=tmp_path) == []

    def test_notify_p0_p1_only_use_banner(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polybuild.audit.notifier import notify_findings

        called_with: list[tuple[str, str]] = []

        def _record(*, title: str, message: str) -> bool:
            called_with.append((title, message))
            return True

        monkeypatch.setattr(
            "polybuild.audit.notifier._send_macos_banner", _record
        )

        findings = [
            self._make_finding("P0", fingerprint="fp" + "0" * 30, message="p0 issue"),
            self._make_finding("P1", fingerprint="fp" + "1" * 30, message="p1 issue"),
            self._make_finding("P2", fingerprint="fp" + "2" * 30, message="p2 issue"),
            self._make_finding("P3", fingerprint="fp" + "3" * 30, message="p3 issue"),
        ]
        notify_findings(findings, backlog_dir=tmp_path)
        # Exactly P0 + P1 reach the banner; P2 / P3 stay quiet.
        assert len(called_with) == 2
        assert any("P0" in title for title, _ in called_with)
        assert any("P1" in title for title, _ in called_with)


class TestLLMCache:
    def test_cache_key_deterministic(self) -> None:
        from polybuild.audit.cache import make_cache_key

        a = make_cache_key("codex-gpt-5.5", "prompt body")
        b = make_cache_key("codex-gpt-5.5", "prompt body")
        assert a == b

    def test_cache_key_sensitive_to_voice(self) -> None:
        from polybuild.audit.cache import make_cache_key

        a = make_cache_key("codex-gpt-5.5", "p")
        b = make_cache_key("kimi-k2.6", "p")
        assert a != b

    def test_cache_key_sensitive_to_prompt(self) -> None:
        from polybuild.audit.cache import make_cache_key

        a = make_cache_key("codex-gpt-5.5", "p1")
        b = make_cache_key("codex-gpt-5.5", "p2")
        assert a != b

    def test_cache_key_sensitive_to_params(self) -> None:
        from polybuild.audit.cache import make_cache_key

        a = make_cache_key("codex-gpt-5.5", "p", {"max_tokens": 100})
        b = make_cache_key("codex-gpt-5.5", "p", {"max_tokens": 200})
        assert a != b
        # Order-insensitive params
        c = make_cache_key("codex-gpt-5.5", "p", {"x": 1, "y": 2})
        d = make_cache_key("codex-gpt-5.5", "p", {"y": 2, "x": 1})
        assert c == d

    def test_cache_get_put_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.cache import cache_get, cache_put, make_cache_key

        # POLYLENS run #2 P1: cache is opt-in by default, so the test
        # must enable it to exercise put + get.
        monkeypatch.setenv("POLYBUILD_LLM_CACHE_ENABLE", "1")

        key = make_cache_key("codex-gpt-5.5", "test prompt")
        # Miss before put.
        assert cache_get(key, cache_dir=tmp_path) is None
        cache_put(
            key,
            voice_id="codex-gpt-5.5",
            response="cached output",
            tokens_total=1500,
            latency_s=12.3,
            cache_dir=tmp_path,
        )
        # Hit after put.
        assert cache_get(key, cache_dir=tmp_path) == "cached output"

    def test_cache_off_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POLYLENS run #2 P1: without ``POLYBUILD_LLM_CACHE_ENABLE=1``,
        both put and get are no-ops. A poisoned response cannot be
        served back on subsequent runs because there is no cache file."""
        from polybuild.audit.cache import cache_get, cache_put, make_cache_key

        monkeypatch.delenv("POLYBUILD_LLM_CACHE_ENABLE", raising=False)
        key = make_cache_key("codex-gpt-5.5", "test")
        cache_put(key, voice_id="codex-gpt-5.5", response="x", cache_dir=tmp_path)
        assert cache_get(key, cache_dir=tmp_path) is None

    def test_cache_ttl_expiry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POLYLENS run #2 P1: entries older than the TTL are treated as
        misses even if the row is still in the database."""
        from polybuild.audit.cache import (
            _get_conn,
            cache_db_path,
            cache_get,
            cache_put,
            make_cache_key,
        )

        monkeypatch.setenv("POLYBUILD_LLM_CACHE_ENABLE", "1")
        monkeypatch.setenv("POLYBUILD_LLM_CACHE_TTL_DAYS", "7")

        key = make_cache_key("codex-gpt-5.5", "stale")
        cache_put(key, voice_id="codex-gpt-5.5", response="ok", cache_dir=tmp_path)
        # Forge the row's cached_at to be 30 days old.
        from datetime import UTC, datetime, timedelta

        old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        conn = _get_conn(cache_db_path(tmp_path))
        conn.execute("UPDATE llm_cache SET cached_at = ? WHERE key = ?", (old, key))
        assert cache_get(key, cache_dir=tmp_path) is None

    def test_cache_stats_and_clear(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.cache import (
            cache_clear,
            cache_put,
            cache_stats,
            make_cache_key,
        )

        monkeypatch.setenv("POLYBUILD_LLM_CACHE_ENABLE", "1")
        for i in range(3):
            cache_put(
                make_cache_key("codex-gpt-5.5", f"p{i}"),
                voice_id="codex-gpt-5.5",
                response="r",
                cache_dir=tmp_path,
            )
        stats = cache_stats(cache_dir=tmp_path)
        assert stats["rows"] == 3
        assert stats["voices"] == 1
        cleared = cache_clear(cache_dir=tmp_path)
        assert cleared == 3
        assert cache_stats(cache_dir=tmp_path)["rows"] == 0


class TestCostLog:
    def test_estimate_usd_known_voice(self) -> None:
        from polybuild.audit.cost_log import estimate_usd

        # Known voice: 1M in @ $1.25 + 1M out @ $5 = $6.25
        usd = estimate_usd("google/gemini-3.1-pro-preview", 1_000_000, 1_000_000)
        assert usd == pytest.approx(6.25, rel=1e-3)

    def test_estimate_usd_unknown_voice_returns_none(self) -> None:
        # POLYLENS run #3 P2 (Gemini + Qwen + DeepSeek convergent):
        # an unknown voice now returns ``None`` (instead of silently
        # booking $0) so dashboards distinguish "we don't know" from
        # "no work was done".
        from polybuild.audit.cost_log import estimate_usd

        assert estimate_usd("totally/unknown", 100, 200) is None

    def test_estimate_usd_missing_tokens(self) -> None:
        from polybuild.audit.cost_log import estimate_usd

        assert estimate_usd("openai/gpt-5.5", None, 100) == 0.0
        assert estimate_usd("openai/gpt-5.5", 100, None) == 0.0

    def test_estimate_usd_string_tokens(self) -> None:
        """POLYLENS run #2 P2: OpenRouter sometimes returns token
        counts as strings; defensive int coercion must keep the
        multiplication from raising ``TypeError``."""
        from polybuild.audit.cost_log import estimate_usd

        # String inputs that look like ints are accepted (parsed).
        assert estimate_usd("z-ai/glm-5.1", "1000", "500") > 0.0
        # Non-numeric strings fall back to 0.0 instead of raising.
        assert estimate_usd("z-ai/glm-5.1", "abc", "def") == 0.0

    def test_log_voice_call_appends(self, tmp_path: Path) -> None:
        from polybuild.audit.cost_log import log_voice_call, read_cost_log

        log_voice_call(
            "z-ai/glm-5.1",
            pool="chinese",
            commit_sha="abc1234",
            tokens_prompt=1000,
            tokens_completion=500,
            latency_s=2.5,
            success=True,
            cost_dir=tmp_path,
        )
        log_voice_call(
            "openai/gpt-5.5",
            pool="western",
            commit_sha="abc1234",
            tokens_prompt=2000,
            tokens_completion=1000,
            latency_s=4.0,
            success=False,
            cost_dir=tmp_path,
        )
        entries = read_cost_log(cost_dir=tmp_path)
        assert len(entries) == 2
        assert {e.voice_id for e in entries} == {
            "z-ai/glm-5.1",
            "openai/gpt-5.5",
        }
        # GLM 5.1 cost: (1000 * 0.50 + 500 * 2.00) / 1e6 = 0.0015
        glm = next(e for e in entries if e.voice_id == "z-ai/glm-5.1")
        assert glm.estimated_usd == pytest.approx(0.0015, rel=1e-3)

    def test_summarize_costs_empty(self, tmp_path: Path) -> None:
        from polybuild.audit.cost_log import summarize_costs

        out = summarize_costs(window="week", cost_dir=tmp_path)
        assert out == "no audit calls in window"


class TestDigest:
    def test_digest_empty_window(self, tmp_path: Path) -> None:
        from polybuild.audit.notifier import build_digest

        out = build_digest(since="yesterday", backlog_dir=tmp_path)
        assert out == "no findings in window"

    def test_digest_groups_by_severity(self, tmp_path: Path) -> None:
        from polybuild.audit.notifier import build_digest

        for i, sev in enumerate(["P0", "P0", "P1", "P2"]):
            append_findings(
                [
                    BacklogFinding(
                        fingerprint=f"fp{i:030d}",
                        commit_sha="abc",
                        file=f"f{i}.py",
                        line=10 + i,
                        axis="A_security",
                        severity=sev,  # type: ignore[arg-type]
                        message=f"msg-{i}",
                        voice="codex-gpt-5.5",
                    )
                ],
                backlog_dir=tmp_path,
            )
        out = build_digest(since="week", backlog_dir=tmp_path)
        assert "Total findings: 4" in out
        assert "P0: 2" in out
        assert "P1: 1" in out
        assert "P2: 1" in out
        # Each section header present in order.
        assert out.index("## P0") < out.index("## P1") < out.index("## P2")


class TestDefaultVoiceCaller:
    @pytest.mark.asyncio
    async def test_unknown_voice_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.runner import default_voice_caller

        # POLYLENS run #2 P1: opt-in covers ALL voice paths, so each
        # of these tests must enable it explicitly to reach the path
        # they actually exercise (otherwise the gate short-circuits
        # first and the result is "" for the wrong reason).
        monkeypatch.setenv("POLYBUILD_AUDIT_REMOTE_OPT_IN", "1")
        result = await default_voice_caller("totally-fake-voice-id", "prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_openrouter_no_key_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.runner import default_voice_caller

        monkeypatch.setenv("POLYBUILD_AUDIT_REMOTE_OPT_IN", "1")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        result = await default_voice_caller("z-ai/glm-5.1", "prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_western_cli_missing_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from polybuild.audit.runner import default_voice_caller

        monkeypatch.setenv("POLYBUILD_AUDIT_REMOTE_OPT_IN", "1")
        # Pretend ``codex`` is not on PATH.
        with patch("shutil.which", return_value=None):
            result = await default_voice_caller("codex-gpt-5.5", "prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_no_opt_in_skips_all_voices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POLYLENS run #2 P1: without the opt-in env var, every voice
        path returns '' before any subprocess or HTTP call."""
        from polybuild.audit.runner import default_voice_caller

        monkeypatch.delenv("POLYBUILD_AUDIT_REMOTE_OPT_IN", raising=False)
        # Even a Western voice with the binary on PATH must be skipped.
        with patch("shutil.which", return_value="/usr/bin/codex"):
            assert await default_voice_caller("codex-gpt-5.5", "p") == ""
        assert await default_voice_caller("z-ai/glm-5.1", "p") == ""
