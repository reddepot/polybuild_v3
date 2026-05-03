"""Validate MCP server contract via JSON-RPC handshake (round 4 + round 5).

Round 5 patches (post-audit):
    - [D] stderr drain task to prevent pipe-buffer deadlock (Audit 5 P0).
    - [D] tolerate non-JSON stdout lines (logs/warnings) — skip + keep reading.
    - [D] match JSON-RPC responses by `id` (Audit 1 — was racing on first line).
    - [E] portable cleanup: skip start_new_session/killpg on Windows (Audits 1+2).
    - [E] always await proc.wait() — was leaking zombies (Audit 1 P0).
    - [S] await drain() after notifications/initialized (Audits 1+5).
    - New: optional `golden_tool_call` parameter — validates a real tools/call,
      not just tools/list (Audits 1+3 trou de spec).

Synthèse round 4 (conservée):
    - Gemini : asyncio.subprocess + initialize JSON-RPC.
    - Kimi : tools/list + Pydantic schema validation ligne par ligne.
    - DeepSeek : staging port + RO volumes + golden tool call.
    - ChatGPT : start_new_session=True + killpg cleanup; capabilities check.
    - Grok : Docker isolation (rejeté : trop lourd pour tous les profils).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field, ValidationError

logger = structlog.get_logger()


class MCPToolSchema(BaseModel):
    """Subset of MCP tool spec we validate (round 4 convergence)."""

    name: str = Field(min_length=1)
    description: str | None = None
    # MCP wire-format keeps camelCase per the upstream JSON-RPC spec; we mirror
    # it on the Pydantic model and silence the naming linter for that field.
    inputSchema: dict[str, Any] = Field(default_factory=dict)  # noqa: N815


class MCPGateResult(BaseModel):
    """Result of MCP server validation."""

    passed: bool
    n_tools: int = 0
    tool_names: list[str] = []
    errors: list[str] = []
    elapsed_s: float = 0.0


async def _drain_stderr(proc: asyncio.subprocess.Process) -> None:
    """Round 5 fix [D] (Audit 5 P0): drain stderr continuously to prevent
    pipe buffer fill → MCP server deadlock. 4/5 audits flagged this."""
    if proc.stderr is None:
        return
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            logger.debug(
                "mcp_stderr",
                line=line.decode("utf-8", errors="replace").rstrip()[:300],
            )
    except (asyncio.CancelledError, BrokenPipeError):
        return


async def _send_jsonrpc(
    proc: asyncio.subprocess.Process,
    request: dict[str, Any],
    timeout_s: float = 5.0,
) -> dict[str, Any]:
    """Send a JSON-RPC request and read the matching response.

    Round 5 fixes [D, S]:
      - Tolerate non-JSON stdout lines (logs/warnings) — skip and keep reading.
      - Match response by `id` field (not just first line).
      - Always drain() after writing.
    """
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("Subprocess has no stdin/stdout")

    payload = (json.dumps(request) + "\n").encode("utf-8")
    proc.stdin.write(payload)
    await proc.stdin.drain()

    expected_id = request.get("id")
    deadline = asyncio.get_running_loop().time() + timeout_s

    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(
                f"No JSON-RPC response with id={expected_id} within {timeout_s}s"
            )
        try:
            line = await asyncio.wait_for(
                proc.stdout.readline(), timeout=remaining
            )
        except TimeoutError:
            raise
        if not line:
            raise RuntimeError("MCP server closed stdout unexpectedly")
        try:
            msg = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            # Tolerate log lines / warnings on stdout (Audit 4 + 5)
            logger.debug(
                "mcp_stdout_non_json_skipped",
                line=line.decode("utf-8", errors="replace")[:120].rstrip(),
            )
            continue

        # Match response by id (or accept first id-less response if expected_id None)
        if expected_id is not None and msg.get("id") == expected_id:
            return msg  # type: ignore[no-any-return]
        if expected_id is None and ("result" in msg or "error" in msg):
            return msg  # type: ignore[no-any-return]
        # Unrelated notification — log and keep reading.
        logger.debug(
            "mcp_unrelated_message_skipped", method=msg.get("method"), id=msg.get("id")
        )


async def validate_mcp_server(
    server_cmd: list[str],
    cwd: str | Path,
    expected_tools: set[str] | None = None,
    timeout_s: float = 30.0,
    extra_env: dict[str, str] | None = None,
    golden_tool_call: dict[str, Any] | None = None,
) -> MCPGateResult:
    """Spawn MCP server in stdio mode and run JSON-RPC handshake.

    Args:
        server_cmd: Command to launch the server (e.g. ["uv", "run", "python", "-m", "server"]).
        cwd: Working directory for the server.
        expected_tools: Set of tool names that must be present (subset check).
        timeout_s: Total timeout for the validation.
        extra_env: Additional environment variables (e.g. read-only mounts).
        golden_tool_call: Optional `{"name": str, "arguments": dict}` — invokes
            a real tools/call to catch tools that pass schema check but crash
            on invocation (Round 5 trou de spec, Audits 1+3).

    Returns:
        MCPGateResult with pass/fail + diagnostics.
    """
    import time

    start = time.time()
    errors: list[str] = []

    env = os.environ.copy()
    env.update(
        {
            "POLYBUILD_TEST_MODE": "1",
            "MCP_TRANSPORT": "stdio",
            "SQLITE_READONLY": "1",  # Volumes prod en RO (DeepSeek + ChatGPT)
            "QDRANT_READONLY": "1",
        }
    )
    if extra_env:
        env.update(extra_env)

    try:
        proc = await asyncio.create_subprocess_exec(
            *server_cmd,
            cwd=str(cwd),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Round 5 fix [E]: start_new_session non-portable on Windows.
            # Only enable on POSIX (audits 1+2 flagged this).
            start_new_session=(sys.platform != "win32"),
        )
    except (OSError, FileNotFoundError) as e:
        return MCPGateResult(passed=False, errors=[f"spawn_failed: {e}"])

    # Round 5 fix [D] (Audit 5 P0): drain stderr in a background task to prevent
    # pipe buffer fill → deadlock when the MCP server writes verbose logs.
    drain_task: asyncio.Task[None] = asyncio.create_task(_drain_stderr(proc))

    tool_names: list[str] = []

    try:
        # ── Step 1: initialize ──────────────────────────────────────────
        init_resp = await _send_jsonrpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "polybuild", "version": "3"},
                },
            },
            timeout_s=8.0,
        )
        if "result" not in init_resp:
            errors.append(f"initialize_no_result: {init_resp.get('error', '<missing>')}")
            return MCPGateResult(
                passed=False, errors=errors, elapsed_s=time.time() - start
            )
        if "capabilities" not in init_resp["result"]:
            errors.append("initialize_no_capabilities")

        # Send the initialized notification (no response expected)
        # Round 5 fix [S]: was missing await drain() — race on slow servers.
        if proc.stdin is not None:
            proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            await proc.stdin.drain()

        # ── Step 2: tools/list ──────────────────────────────────────────
        tools_resp = await _send_jsonrpc(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout_s=8.0,
        )
        if "result" not in tools_resp:
            errors.append(f"tools_list_failed: {tools_resp.get('error', '<missing>')}")
            return MCPGateResult(
                passed=False, errors=errors, elapsed_s=time.time() - start
            )

        raw_tools = tools_resp["result"].get("tools", [])
        for raw in raw_tools:
            try:
                tool = MCPToolSchema.model_validate(raw)
                tool_names.append(tool.name)
            except ValidationError as e:
                errors.append(f"tool_schema_invalid: {raw.get('name', '?')} → {e.errors()[:1]}")

        # ── Step 3: expected tools subset check ─────────────────────────
        if expected_tools:
            missing = expected_tools - set(tool_names)
            if missing:
                errors.append(f"missing_expected_tools: {sorted(missing)}")

        # ── Step 4: golden tool call (Round 5 — Audit 1+3 trou de spec) ─
        # tools/list only validates schema presence. A real call catches
        # tools that crash on invocation despite valid schemas.
        if golden_tool_call and not errors:
            tool_name = golden_tool_call.get("name")
            tool_args = golden_tool_call.get("arguments", {})
            if tool_name and tool_name in tool_names:
                try:
                    call_resp = await _send_jsonrpc(
                        proc,
                        {
                            "jsonrpc": "2.0",
                            "id": 3,
                            "method": "tools/call",
                            "params": {"name": tool_name, "arguments": tool_args},
                        },
                        timeout_s=10.0,
                    )
                    if "error" in call_resp:
                        errors.append(
                            f"golden_tool_call_failed: {tool_name} → "
                            f"{call_resp['error'].get('message', '<unknown>')}"
                        )
                except (TimeoutError, RuntimeError) as e:
                    errors.append(f"golden_tool_call_exception: {type(e).__name__}: {e}")

    except TimeoutError:
        errors.append(f"timeout > {timeout_s}s during JSON-RPC handshake")
    except json.JSONDecodeError as e:
        errors.append(f"json_decode_error: {e}")
    except Exception as e:
        errors.append(f"unexpected: {type(e).__name__}: {e}")

    finally:
        # Round 5 fix [E] (Audits 1+2): portable cleanup + always wait().
        # Audit 1 P0: previous version caught ProcessLookupError but never awaited
        # proc.wait() → zombies. Audit 2 P2: Windows portability.
        drain_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await drain_task

        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                if sys.platform != "win32":
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    proc.terminate()

            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                try:
                    if sys.platform != "win32":
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (TimeoutError, ProcessLookupError, PermissionError, OSError):
                    pass

    elapsed = time.time() - start
    passed = not errors
    logger.info(
        "mcp_gate_done",
        passed=passed,
        n_tools=len(tool_names),
        n_errors=len(errors),
        elapsed_s=round(elapsed, 2),
    )

    return MCPGateResult(
        passed=passed,
        n_tools=len(tool_names),
        tool_names=tool_names,
        errors=errors,
        elapsed_s=elapsed,
    )
