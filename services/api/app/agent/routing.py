"""Deterministic question routing for the support agent.

The classifier reads the question text only. It does not look at a bearer
token, and it is not the authorization boundary. A later lookup still refuses
the incident service when ``caller_is_authenticated`` is not true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

RouteKind = Literal["empty", "ticket", "knowledge", "both"]

HONEST_STATUS_SENTENCE = "I couldn't confirm that ticket's status right now"

_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HC_ID = re.compile(r"\bHC-\d{6}\b", re.IGNORECASE)
_RECORD_NUMBER = re.compile(
    r"\b(?:ticket|incident)\s+#?(\d+)\b|\bstatus of\s+#?(\d+)\b",
    re.IGNORECASE,
)
_KNOWLEDGE = re.compile(
    r"\b(?:how long|how does|how do|how is|how are|supposed to|policy|procedure|process|guideline)\b",
    re.IGNORECASE,
)
_RECORD_WORD = re.compile(r"\b(?:tickets?|incidents?)\b", re.IGNORECASE)
_TICKET_REQUEST = re.compile(
    r"\b(?:status of|current status|what is the status|show|list|find|which|lookup|look up)\b",
    re.IGNORECASE,
)
_FILTER_FIELD = re.compile(r"\b(?:status|origin|branch|category)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TicketRequest:
    """What an authorized lookup may pass to the incident service.

    ``unsupported`` means the question is a ticket request but its identifier
    or filters are not a UUID or an allowed filter. Those strings are not
    passed to ``get_incident``.
    """

    kind: Literal["id", "filters", "unsupported"]
    incident_id: str | None = None
    status: str | None = None
    origin: str | None = None
    branch: str | None = None
    category: str | None = None


def classify_question(question: str) -> RouteKind:
    """Return empty, ticket, knowledge, or both from the question alone."""
    text = question.strip()
    if not text:
        return "empty"
    ticket = _has_ticket_intent(text)
    knowledge = _KNOWLEDGE.search(text) is not None
    if ticket and knowledge:
        return "both"
    if ticket:
        return "ticket"
    return "knowledge"


def parse_ticket_request(question: str) -> TicketRequest:
    """Choose an id read, a filter read, or no service call.

    A UUID is the id form even when filter words are also present, because
    the incident API has no combined id-plus-filter endpoint. ``HC-######``
    and a bare ticket number such as 482 are unsupported identifiers.
    """
    uuid_match = _UUID.search(question)
    if uuid_match:
        return TicketRequest(kind="id", incident_id=uuid_match.group(0))
    if _HC_ID.search(question) or _RECORD_NUMBER.search(question):
        return TicketRequest(kind="unsupported")

    from manager_constants import BRANCHES, CATEGORIES, ORIGINS, STATUSES

    filters = {
        "status": _matching_value(question, STATUSES),
        "origin": _matching_value(question, ORIGINS),
        "branch": _matching_value(question, BRANCHES),
        "category": _matching_value(question, CATEGORIES),
    }
    # ``branch`` is both a field name and an origin value. Keep it as a branch
    # filter only when the question names a branch other than that overlap,
    # and keep origin=branch only when origin is requested explicitly.
    if filters["origin"] == "branch" and not re.search(r"\borigin\b", question, re.IGNORECASE):
        filters["origin"] = None
    if not any(filters.values()):
        return TicketRequest(kind="unsupported")
    return TicketRequest(
        kind="filters",
        status=filters["status"],
        origin=filters["origin"],
        branch=filters["branch"],
        category=filters["category"],
    )


def _has_ticket_intent(text: str) -> bool:
    """True when the question asks for a live ticket, not a policy topic.

    The word incident inside a how-it-works question is not enough. A UUID,
    an unsupported ticket id, or a record request with a filter is enough.
    """
    if _UUID.search(text) or _HC_ID.search(text) or _RECORD_NUMBER.search(text):
        return True
    if _RECORD_WORD.search(text) is None:
        return False
    return _TICKET_REQUEST.search(text) is not None or _FILTER_FIELD.search(text) is not None


def _matching_value(question: str, allowed: tuple[str, ...]) -> str | None:
    for value in allowed:
        if re.search(rf"\b{re.escape(value)}\b", question, re.IGNORECASE):
            return value
    return None
