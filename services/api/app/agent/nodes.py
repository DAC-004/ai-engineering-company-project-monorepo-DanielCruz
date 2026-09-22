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
    return {"context": payloads, "error": ""}


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
    return {"answer": answer, "error": ""}


def reject_question(_state: AgentState) -> dict[str, str]:
    """Record a clear error for empty input. Do not retrieve or generate."""
    return {"answer": "", "error": EMPTY_QUESTION_ERROR}


def respond_no_information(_state: AgentState) -> dict[str, str]:
    """Return the existing refusal when retrieval kept no chunk.

    ``retrieve()`` already dropped scores below its threshold, so an empty
    context means nothing met that bar. Generation is not called, and
    retrieval is not repeated.
    """
    return {
        "answer": rag_pipeline.insufficient_information_answer(),
        "error": "",
    }
