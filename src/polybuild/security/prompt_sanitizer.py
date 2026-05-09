"""Prompt-context sanitization to defeat injection via AGENTS.md / spec docs.

Round 10 audit (6/6 convergence : Grok / Qwen / Gemini / DeepSeek / ChatGPT /
Kimi) flagged that the privacy gate scans the raw text of AGENTS.md but the
content is then injected verbatim into the LLM prompt. HTML/Markdown comments
are invisible to the regex PII patterns (so they pass the gate) but are
read by the LLM (which executes their hidden instructions).

This module provides :
- ``sanitize_prompt_context(raw)`` — strips HTML/Markdown comments, XML
  processing instructions, zero-width / formatting Unicode, and emits a
  warning if obvious "ignore previous instructions" patterns are detected.
- ``contains_suspicious_directive(raw)`` — boolean helper for callers that
  want to bail out instead of stripping (e.g. paranoia mode).

Both functions are deterministic, side-effect-free (other than logging),
and fast enough to run on every Phase-1 entry without measurable overhead.
"""

from __future__ import annotations

import re
import unicodedata

import structlog

logger = structlog.get_logger()

# ── Public regex patterns (importable for tests) ──────────────────────

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_XML_PI = re.compile(r"<\?.*?\?>", re.DOTALL)
_HTML_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
# Round 10.2 add: Markdown link with hidden title attribute
# (``[visible](http://x 'malicious instructions')``). Strip the title
# attribute, keep the visible text and bare URL so legitimate cross-refs
# survive.
_MD_LINK_TITLE = re.compile(
    r"(\[[^\]]*\]\([^)\s]*?)\s+'[^']*'(\))",
)
_MD_LINK_TITLE_DQ = re.compile(
    r'(\[[^\]]*\]\([^)\s]*?)\s+"[^"]*"(\))',
)
# Round 10.2 add: fenced code block with hidden language directive
# (e.g. ```bash\n#!ignore previous\n…```). We drop the *content* of fenced
# blocks: legitimate code samples don't belong in an AGENTS.md instruction
# context anyway, and their content is the most flexible attack surface.
_FENCED_BLOCK = re.compile(r"```[\s\S]*?```")
# Zero-width / control / bidirectional Unicode often used to smuggle text
# past human review while still being read by the model.
# Ranges:
#   U+200B..U+200F  zero-width space, joiner, RTL/LTR mark
#   U+202A..U+202E  bidi overrides
#   U+2066..U+2069  isolate controls
#   U+FEFF          byte-order mark / ZWNBSP
# Built from explicit code-point escapes so the source file itself
# stays free of invisible characters (else ruff PLE2502).
_INVISIBLE_CHARS = re.compile(
    "[" + chr(0x200B) + "-" + chr(0x200F)
    + chr(0x202A) + "-" + chr(0x202E)
    + chr(0x2066) + "-" + chr(0x2069)
    + chr(0xFEFF)
    + "]"
)

_SUSPICIOUS_DIRECTIVES: tuple[str, ...] = (
    "ignore previous",
    "ignore all previous",
    "disregard prior",
    "disregard previous",
    "execute instead",
    "system prompt:",
    "you are now",
    "forget the above",
    "override your instructions",
)


def sanitize_prompt_context(raw: str) -> str:
    """Strip injection vectors from a free-text context block.

    The cleaning order matters: NFKC first so that homoglyph variants of
    e.g. ``<!--`` collapse to ASCII before the comment regex runs.

    POLYLENS run #3 P3 (KIMI Agent Swarm): the previous implementation
    ran the suspicious-directive check *after* HTML comment stripping.
    A directive hidden inside ``<!-- ignore previous instructions -->``
    was therefore silently removed without raising any warning, blinding
    the operator to the attack. We now scan the **raw** text first
    (still-attacker-controlled bytes) and emit a distinct warning, then
    scan the cleaned text again so directives that survive sanitisation
    (rare — the strippers are aggressive) still surface their own
    warning.
    """
    if not raw:
        return ""
    # POLYLENS run #3 P3: pre-sanitize directive scan. Catches HTML/MD
    # comment-hidden injection attempts before the strip pass erases
    # them. We do an NFKC-normalised lower compare so homoglyph
    # variants of "ignore" don't slip past.
    #
    # POLYLENS run #4 P2 (DeepSeek): a "directive" can also be a
    # benign citation in legitimate documentation
    # ("the linter must NOT ignore previous output of …"). Logging at
    # ``warning`` level created false-positive noise that drowned the
    # real attacks. Demoted to ``debug`` so the signal is preserved
    # for forensic review (structlog stores it) without polluting the
    # routine warning stream. The post-sanitize warning below stays
    # at ``warning`` because surviving the strippers is much rarer
    # and almost always intentional.
    raw_lower = unicodedata.normalize("NFKC", raw).lower()
    for needle in _SUSPICIOUS_DIRECTIVES:
        if needle in raw_lower:
            logger.debug(
                "prompt_context_suspicious_directive_raw",
                pattern=needle,
                hint=(
                    "Directive detected in the raw context BEFORE "
                    "comment/script stripping. May be a benign citation "
                    "or a hidden injection — review the source if you "
                    "see this for an unexpected document."
                ),
            )

    cleaned = unicodedata.normalize("NFKC", raw)
    # Round 10.2.1 fix [POLYLENS honeypot 1]: nested comments like
    # ``<!-- outer <!-- inner --> still here -->`` survived a single
    # non-greedy pass because the regex matched the inner pair only,
    # leaving ``still here -->``. We iterate the comment / fenced /
    # script strippers to a fixed point so any post-pass residue (or
    # adversarial nesting) is removed too. Bound the loop in case of
    # pathological input.
    for _ in range(8):
        before = cleaned
        cleaned = _HTML_COMMENT.sub("", cleaned)
        cleaned = _XML_PI.sub("", cleaned)
        cleaned = _HTML_SCRIPT.sub("", cleaned)
        cleaned = _FENCED_BLOCK.sub("", cleaned)
        if cleaned == before:
            break
    cleaned = _MD_LINK_TITLE.sub(r"\1\2", cleaned)
    cleaned = _MD_LINK_TITLE_DQ.sub(r"\1\2", cleaned)
    cleaned = _INVISIBLE_CHARS.sub("", cleaned)
    # Strip orphan comment terminators left over from adversarial input
    # (e.g. ``-->`` without a leading ``<!--`` after iteration).
    cleaned = cleaned.replace("-->", "").replace("<!--", "")

    lower = cleaned.lower()
    for needle in _SUSPICIOUS_DIRECTIVES:
        if needle in lower:
            logger.warning(
                "prompt_context_suspicious_directive_after_sanitize",
                pattern=needle,
            )

    return cleaned.strip()


def contains_suspicious_directive(raw: str) -> bool:
    """True if a sanitized version of *raw* still mentions an obvious
    prompt-injection directive. Useful for paranoia-mode callers that
    prefer to abort the run rather than ship a cleaned-but-suspicious
    context to the model.
    """
    if not raw:
        return False
    cleaned = sanitize_prompt_context(raw).lower()
    return any(needle in cleaned for needle in _SUSPICIOUS_DIRECTIVES)


__all__ = [
    "contains_suspicious_directive",
    "sanitize_prompt_context",
]
