"""Tests unitaires pour validate_mcp — JSON-RPC handshake gate."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polybuild.domain_gates.validate_mcp import (
    _drain_stderr,
    _send_jsonrpc,
    validate_mcp_server,
)


class FakeProcess:
    """Processus asyncio.subprocess simulé avec pipes contrôlables."""

    def __init__(self, stdout_lines: list[str], stderr_lines: list[bytes] | None = None):
        self._stdout_lines = stdout_lines
        self._stderr_lines = stderr_lines or []
        self._stdout_idx = 0
        self._stderr_idx = 0
        self.stdin = MagicMock()
        self.stdin.write = MagicMock()
        self.stdin.drain = AsyncMock()
        self.stdout = MagicMock()
        self.stderr = MagicMock()
        self.returncode: int | None = None
        self.pid = 12345

        async def _readline() -> bytes:
            if self._stdout_idx < len(self._stdout_lines):
                line = self._stdout_lines[self._stdout_idx]
                self._stdout_idx += 1
                return line.encode() + b"\n"
            return b""

        async def _stderr_readline() -> bytes:
            if self._stderr_idx < len(self._stderr_lines):
                line = self._stderr_lines[self._stderr_idx]
                self._stderr_idx += 1
                return line + b"\n"
            return b""

        self.stdout.readline = _readline
        self.stderr.readline = _stderr_readline

    async def wait(self) -> int:
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


class TestDrainStderr:
    @pytest.mark.asyncio
    async def test_drains_until_eof(self) -> None:
        proc = FakeProcess([], stderr_lines=[b"log1", b"log2"])
        task = asyncio.create_task(_drain_stderr(proc))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_none_stderr_returns_immediately(self) -> None:
        proc = FakeProcess([])
        proc.stderr = None
        await _drain_stderr(proc)


class TestSendJsonrpc:
    @pytest.mark.asyncio
    async def test_matching_id(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}),
        ])
        resp = await _send_jsonrpc(
            proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, timeout_s=2.0
        )
        assert resp["id"] == 1
        assert "result" in resp

    @pytest.mark.asyncio
    async def test_skips_non_json_lines(self) -> None:
        proc = FakeProcess([
            "log line warning",
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}),
        ])
        resp = await _send_jsonrpc(
            proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout_s=2.0
        )
        assert resp["id"] == 2

    @pytest.mark.asyncio
    async def test_skips_unrelated_messages(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "method": "notifications/progress", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
        ])
        resp = await _send_jsonrpc(
            proc, {"jsonrpc": "2.0", "id": 3, "method": "ping", "params": {}}, timeout_s=2.0
        )
        assert resp["id"] == 3

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        proc = FakeProcess([])  # pas de réponse
        with pytest.raises(TimeoutError):
            await _send_jsonrpc(
                proc, {"jsonrpc": "2.0", "id": 4, "method": "x", "params": {}}, timeout_s=0.1
            )

    @pytest.mark.asyncio
    async def test_closed_stdout_raises(self) -> None:
        proc = FakeProcess([])
        with pytest.raises(RuntimeError, match="closed stdout"):
            await _send_jsonrpc(
                proc, {"jsonrpc": "2.0", "id": 5, "method": "x", "params": {}}, timeout_s=0.5
            )


class TestValidateMcpServer:
    @pytest.mark.asyncio
    async def test_spawn_failed(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("cmd not found")):
            result = await validate_mcp_server(["fake-cmd"], cwd="/tmp")
        assert result.passed is False
        assert any("spawn_failed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_initialize_no_result(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"message": "bad"}}),
        ])
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await validate_mcp_server(["server"], cwd="/tmp")
        assert result.passed is False
        assert any("initialize_no_result" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_tools_list_success(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "tool_a", "inputSchema": {}}]}}),
        ])
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await validate_mcp_server(["server"], cwd="/tmp", expected_tools={"tool_a"})
        assert result.passed is True
        assert result.n_tools == 1
        assert "tool_a" in result.tool_names

    @pytest.mark.asyncio
    async def test_expected_tools_subset_fails(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "tool_a", "inputSchema": {}}]}}),
        ])
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await validate_mcp_server(["server"], cwd="/tmp", expected_tools={"tool_a", "tool_b"})
        assert result.passed is False
        assert any("missing_expected_tools" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_golden_tool_call(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "add", "inputSchema": {}}]}}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "2"}]}}),
        ])
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await validate_mcp_server(
                ["server"],
                cwd="/tmp",
                golden_tool_call={"name": "add", "arguments": {"a": 1, "b": 1}},
            )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_golden_tool_call_error(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "add", "inputSchema": {}}]}}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "error": {"message": "division by zero"}}),
        ])
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await validate_mcp_server(
                ["server"],
                cwd="/tmp",
                golden_tool_call={"name": "add", "arguments": {"a": 1, "b": 0}},
            )
        assert result.passed is False
        assert any("golden_tool_call_failed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_timeout_global(self) -> None:
        proc = FakeProcess([
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {}}}),
        ])
        # On simule un timeout en faisant attendre la seconde réponse
        original_readline = proc.stdout.readline
        async def slow_readline() -> bytes:
            await asyncio.sleep(10)
            return await original_readline()
        proc.stdout.readline = slow_readline  # type: ignore[method-assign]

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await validate_mcp_server(["server"], cwd="/tmp", timeout_s=0.2)
        assert result.passed is False
        assert any("timeout" in e.lower() for e in result.errors)
