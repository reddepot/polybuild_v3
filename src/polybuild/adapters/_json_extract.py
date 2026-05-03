"""JSON extraction helper for CLI adapters.

Round 10.8 prod-launch follow-up: codex CLI 0.128 and claude CLI v2 emit the
model's structured output as text on stdout. The model may wrap the JSON in
markdown fencing (`` ```json ... ``` ``) or emit prose around it. This module
provides a robust fallback chain to extract a ``dict`` from such raw strings.

Round 10.8 POLYLENS [Qwen F1 P1 + Kimi B-01 P1, 2/4 cross-voice convergence]:
the original strategy 3 used ``raw.index('{')`` + ``raw.rindex('}')`` —
which fails when the model emits ``{"msg": "ok}not"}`` (the rindex finds
the ``}`` inside the string literal, not the closing brace). Replaced
with a proper string-aware brace counter that respects double-quoted
string state and backslash escapes.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Relaxed pattern for fenced markdown blocks containing JSON.
# Matches ```json, ```, or no language tag.
_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*"      # opening fence
    r"(\{.*?)"              # capture group 1: content starting with {
    r"\s*```",              # closing fence
    re.DOTALL,
)


def _balanced_json_blocks(raw: str) -> list[str]:
    """Yield every top-level balanced ``{ ... }`` block found in *raw*.

    String-aware brace counter: opening/closing braces inside double-quoted
    strings (with backslash escapes) are NOT counted. Comment from
    ``phase_5_triade._all_balanced_json_blocks`` ported here so both
    adapter parsing and triade verdict parsing share the same primitive.
    """
    blocks: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        escape = False
        start = i
        while i < n:
            c = raw[i]
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = not in_str
            elif not in_str:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        blocks.append(raw[start : i + 1])
                        i += 1
                        break
            i += 1
        else:
            # End of string reached without closing the block — drop.
            break
    return blocks


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    """Attempt to extract a JSON ``dict`` from *raw* using multiple strategies.

    Strategies (in order):
      1. Direct ``json.loads``.
      2. Search inside a fenced markdown ``json`` block.
      3. String-aware balanced-brace scan; pick the LARGEST block that
         parses successfully (handles prose-wrapped JSON, multiple
         candidates, JSON containing ``}`` inside string literals).

    Returns:
        The parsed ``dict`` if any strategy succeeds, otherwise ``None``.
    """
    # 1. Direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Fenced markdown block
    match = _FENCED_JSON_RE.search(raw)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. String-aware balanced brace scan. Prefer the LARGEST parsable
    # block — that's typically the structured payload, distinguished
    # from small snippets the model may emit in prose.
    blocks = _balanced_json_blocks(raw)
    blocks.sort(key=len, reverse=True)
    for candidate in blocks:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    return None
