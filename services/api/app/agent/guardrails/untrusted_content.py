"""Treat retrieved chunks as data. Drop a chunk that carries instructions."""

from __future__ import annotations

from typing import Any

from app.agent.guardrails.text_rules import disclosure_is_prohibited


def chunk_is_prohibited(payload: dict[str, Any] | None) -> bool:
    """True when a chunk's text or section must not be logged or returned."""
    if not isinstance(payload, dict):
        return False
    # The filename is checked on its own. Joining it to the body makes
    # "appointment-policy" combine with cancellation wording that never names
    # an appointment. An instruction or disclosure that is only in the
    # filename is still rejected.
    body = "\n".join(
        str(payload.get(field) or "")
        for field in ("text", "section")
    )
    source_name = str(payload.get("source_document") or "")
    return disclosure_is_prohibited(body) or disclosure_is_prohibited(source_name)


def keep_chunks(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop prohibited chunks. Clean payloads stay unchanged for traces."""
    return [payload for payload in payloads if not chunk_is_prohibited(payload)]
