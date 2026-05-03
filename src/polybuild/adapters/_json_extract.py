"""JSON extraction helper for CLI adapters.

Round 10.8 prod-launch follow-up: codex CLI 0.128 and claude CLI v2 emit the
model's structured output as text on stdout. The model may wrap the JSON in
markdown fencing (`` ```json ... ``` ``) or emit prose around it. This module
provides a robust fallback chain to extract a ``dict`` from such raw strings.
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


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    """Attempt to extract a JSON ``dict`` from *raw* using multiple strategies.

    Strategies (in order):
      1. Direct ``json.loads``.
      2. Search inside a fenced markdown ``json`` block.
      3. Greedy scan from the first ``{`` to the last ``}``.

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

    # 3. Greedy brace scan (first '{' to last '}')
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        if isinstance(data, dict):
            return data
    except (ValueError, json.JSONDecodeError):
        pass

    return None
