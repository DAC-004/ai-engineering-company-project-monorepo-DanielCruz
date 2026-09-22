"""Minimal state carried between support-agent nodes."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    """Fields a node needs in order to route or execute the next step.

    Conversation history is intentionally absent. Each run is one question,
    the chunks ``retrieve()`` already accepted, and the answer or error
    produced from that input.
    """

    question: str
    context: list[dict[str, Any]]
    answer: str
    error: str
