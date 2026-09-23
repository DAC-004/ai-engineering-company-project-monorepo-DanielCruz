"""Single-responsibility nodes for the support-agent graph.

Retrieval and generation stay separate. ``query()`` is not used here because
it always searches and then generates, and it cannot accept chunks that
were already retrieved.
"""

from __future__ import annotations

from typing import Any

from data.pipelines import rag as rag_pipeline

from app.agent.state import AgentState

EMPTY_QUESTION_ERROR = (
    "The question is empty. Provide a HealthCore support question before retrieval."
)


def receive_question(state: AgentState) -> dict[str, str]:
    """Normalize the incoming question. Do not retrieve or generate."""
    raw_question = state.get("question", "")
    normalized_question = raw_question.strip() if isinstance(raw_question, str) else ""
    return {"question": normalized_question}


def retrieve_context(state: AgentState) -> dict[str, Any]:
    """Call ``retrieve()`` and store its payloads. Do not generate."""
    # Default k and min_score stay inside retrieve(), including the 0.45 floor.
    payloads = rag_pipeline.retrieve(state["question"])
    return {"context": payloads, "error": "", "sources": _append_source(state, "rag")}


def generate_from_context(state: AgentState) -> dict[str, str]:
    """Generate from the context already stored by ``retrieve_context``.

    This node must not call ``retrieve()`` or ``query()``. An empty context
    is a routing bug: the no-information edge should have been taken instead.
    """
    if not state["context"]:
        raise RuntimeError(
            "generate_from_context requires retrieval context and does not search again."
        )
    answer = rag_pipeline.generate_answer(state["question"], state["context"])
    return {"answer": _with_ticket_clause(state, answer), "error": ""}


def reject_question(_state: AgentState) -> dict[str, str]:
    """Record a clear error for empty input. Do not retrieve or generate."""
    return {"answer": "", "error": EMPTY_QUESTION_ERROR}


def respond_no_information(state: AgentState) -> dict[str, str]:
    """Return the existing refusal when retrieval kept no chunk.

    ``retrieve()`` already dropped scores below its threshold, so an empty
    context means nothing met that bar. Generation is not called, and
    retrieval is not repeated.
    """
    return {
        "answer": _with_ticket_clause(state, rag_pipeline.insufficient_information_answer()),
        "error": "",
    }


def lookup_ticket(state: AgentState) -> dict[str, Any]:
    """Read tickets through MCP, or refuse before any MCP call.

    Authorization is this node's responsibility. The route classifier can
    disagree and still send the question here. A missing or false
    ``caller_is_authenticated`` flag does not call MCP and does not read the
    incident service. A rejected or missing MCP credential uses the honest
    fallback and does not fall back to ``incident_service``. Title and
    description are not copied into the graph state.
    """
    if state.get("caller_is_authenticated") is not True:
        return _lookup_failure(state, "unauthorized")

    from app.agent.lookup_slot import run_bounded_read
    from app.agent.mcp_tickets import McpTicketError, read_tickets_via_mcp
    from app.agent.routing import parse_ticket_request
    from app.services.ticket_lookup import TicketLookupQuery

    request = parse_ticket_request(state["question"])
    if request.kind == "unsupported":
        return _lookup_failure(state, "unsupported")

    query = TicketLookupQuery(
        incident_id=request.incident_id,
        status=request.status,
        origin=request.origin,
        branch=request.branch,
        category=request.category,
    )
    outcome = run_bounded_read(lambda: read_tickets_via_mcp(query))
    if outcome.failure == "capacity":
        return _lookup_failure(state, "capacity")
    if outcome.failure == "timeout":
        return _lookup_failure(state, "timeout")
    if outcome.failure == "error":
        if isinstance(outcome.error, McpTicketError) and outcome.error.failure == "missing":
            return _lookup_failure(state, "missing")
        return _lookup_failure(state, "error")

    rows = outcome.rows if isinstance(outcome.rows, list) else []
    if not rows:
        return _lookup_failure(state, "missing")
    return _lookup_success(state, rows)


def _append_source(state: AgentState, source: str) -> list[str]:
    sources = [item for item in state.get("sources", []) if isinstance(item, str)]
    if source not in sources:
        sources.append(source)
    return sources


def _with_ticket_clause(state: AgentState, answer: str) -> str:
    clause = state.get("ticket_clause") or ""
    if not clause:
        return answer
    return f"{clause}\n{answer}"


def _lookup_failure(state: AgentState, failure: str) -> dict[str, Any]:
    from app.agent.routing import HONEST_STATUS_SENTENCE

    return {
        "answer": HONEST_STATUS_SENTENCE,
        "ticket_clause": HONEST_STATUS_SENTENCE,
        "sources": _append_source(state, "ticket_tool"),
        "lookup_failure": failure,
        "ticket_id": "",
        "ticket_status": "",
        "error": "",
    }


def _lookup_success(state: AgentState, rows: list[Any]) -> dict[str, Any]:
    clause = "\n".join(_row_clause(row) for row in rows)
    ticket_ids = ", ".join(str(getattr(row, "id", "")) for row in rows)
    ticket_statuses = ", ".join(str(getattr(row, "status", "")) for row in rows)
    return {
        "answer": clause,
        "ticket_clause": clause,
        "sources": _append_source(state, "ticket_tool"),
        "lookup_failure": "",
        "ticket_id": ticket_ids,
        "ticket_status": ticket_statuses,
        "error": "",
    }


def _row_clause(row: Any) -> str:
    """Expose the fields the routing checks compare, not the ticket body."""
    return (
        f"Incident {row.id} status is {row.status}. "
        f"Category: {row.category}. Origin: {row.origin}. Branch: {row.branch}."
    )
