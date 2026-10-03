"""Check model text before a generation node returns it.

The accepted shape is non-empty plain text: a coordinator sentence, a ticket
clause, or one of the fixed refusals. A JSON value, an HTML tag, or a fenced
code block is an unexpected shape even when the words are not prohibited.
"""

from __future__ import annotations

import json
import re

from app.agent.guardrails.text_rules import disclosure_is_prohibited

SAFE_OUTPUT = (
    "I can't return that response. Ask a HealthCore policy question without "
    "patient identifiers or requests to change my instructions."
)
_PROMPT_LEAK = "you are an experienced healthcore patient coordinator"
_CODE_FENCE = re.compile(r"```")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")


def output_failure(text: str | None) -> str | None:
    """Return structural, content, or None when the text may be returned.

    Empty text is left to the existing empty-question and empty-generation
    paths. Those paths do not use this shape check.
    """
    if not text or not text.strip():
        return None
    if not _is_plain_text(text):
        return "structural"
    lowered = text.lower()
    if _PROMPT_LEAK in lowered or disclosure_is_prohibited(text):
        return "content"
    return None


def output_is_blocked(text: str | None) -> bool:
    """True when generated text must be replaced before it is stored."""
    return output_failure(text) is not None


def safe_output(text: str) -> str:
    """Return the model text, or a fixed sentence when it is blocked."""
    if output_is_blocked(text):
        return SAFE_OUTPUT
    return text


def _is_plain_text(text: str) -> bool:
    """Accept prose. Reject a JSON document, markup, or a code fence."""
    stripped = text.strip()
    if not re.search(r"[A-Za-z]", stripped):
        return False
    if _CODE_FENCE.search(stripped) or _HTML_TAG.search(stripped):
        return False
    if stripped[0] in "{[":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, (dict, list)):
            return False
    return True
