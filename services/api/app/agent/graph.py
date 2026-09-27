"""Compiled HealthCore support-agent graph.

The graph is compiled with a SQLite checkpointer before any run. Structural
mistakes, such as an edge to a node that was never added, fail in ``compile``
rather than during a later request.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.memory_store import MemoryStore
from app.agent.memory_turn import (
    IntentClassifier,
    append_unverified_notes,
    finish_turn,
    prepare_turn,
)
from app.agent.nodes import (
    generate_from_context,
    lookup_ticket,
    receive_question,
    reject_question,
    respond_no_information,
    retrieve_context,
)
from app.agent.routing import classify_question
from app.agent.state import AgentState
from app.agent.tracing import load_trace, persist_trace, trace_directory
from shared.healthcore_rag.config import REPO_ROOT

logger = logging.getLogger(__name__)

GRAPH_EXECUTION_FAILED = "graph execution failed"

CHECKPOINT_DATABASE = (
    REPO_ROOT / "data" / "process" / "agent_checkpoints" / "support_agent.sqlite"
)


@dataclass(frozen=True)
class AgentRun:
    """Public result of one compiled-graph run."""

    answer: str
    error: str
    trace_id: str
    thread_id: str
    memory_proposal: str | None = None


def checkpoint_database_path() -> Path:
    """Return the gitignored SQLite file used for runtime checkpoints."""
    return CHECKPOINT_DATABASE


def route_after_question(
    state: AgentState,
) -> Literal["retrieve_context", "reject_question", "lookup_ticket"]:
    """Empty questions end before retrieval. Ticket questions look up first."""
    if not state["question"].strip():
        return "reject_question"
    kind = classify_question(state["question"])
    if kind in {"ticket", "both"}:
        return "lookup_ticket"
    return "retrieve_context"


def route_after_lookup(
    state: AgentState,
) -> Literal["retrieve_context", "end"]:
    """Combined questions retrieve after the ticket clause. Ticket-only stops."""
    if classify_question(state["question"]) == "both":
        return "retrieve_context"
    return "end"


def route_after_retrieval(
    state: AgentState,
) -> Literal["generate_from_context", "respond_no_information"]:
    """Skip generation when ``retrieve()`` kept no chunk at or above its floor."""
    if state["context"]:
        return "generate_from_context"
    return "respond_no_information"


def build_support_graph() -> StateGraph[AgentState]:
    """Wire nodes and conditional edges. This does not compile or execute."""
    builder: StateGraph[AgentState] = StateGraph(AgentState)
    builder.add_node("receive_question", receive_question)
    builder.add_node("lookup_ticket", lookup_ticket)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("generate_from_context", generate_from_context)
    builder.add_node("reject_question", reject_question)
    builder.add_node("respond_no_information", respond_no_information)
    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges(
        "receive_question",
        route_after_question,
        {
            "retrieve_context": "retrieve_context",
            "reject_question": "reject_question",
            "lookup_ticket": "lookup_ticket",
        },
    )
    builder.add_conditional_edges(
        "lookup_ticket",
        route_after_lookup,
        {
            "retrieve_context": "retrieve_context",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "retrieve_context",
        route_after_retrieval,
        {
            "generate_from_context": "generate_from_context",
            "respond_no_information": "respond_no_information",
        },
    )
    builder.add_edge("reject_question", END)
    builder.add_edge("respond_no_information", END)
    builder.add_edge("generate_from_context", END)
    return builder


def compile_support_graph(checkpointer: SqliteSaver) -> CompiledStateGraph:
    """Compile before execution so a broken edge fails here."""
    return build_support_graph().compile(checkpointer=checkpointer)


@contextmanager
def open_sqlite_checkpointer(database_path: Path) -> Iterator[SqliteSaver]:
    """Open a SQLite checkpointer and close the connection afterwards.

    The database file remains on disk after the connection closes, so a later
    process can reopen it and read ``get_state_history`` for the same thread.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path), check_same_thread=False)
    try:
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        yield checkpointer
    finally:
        connection.close()


def _initial_state(
    question: str,
    *,
    caller_is_authenticated: bool = False,
    approved_memory: list[str] | None = None,
) -> AgentState:
    return {
        "question": question,
        "context": [],
        "answer": "",
        "error": "",
        "caller_is_authenticated": caller_is_authenticated is True,
        "sources": [],
        "ticket_clause": "",
        "lookup_failure": "",
        "ticket_id": "",
        "ticket_status": "",
        "approved_memory": list(approved_memory or []),
    }


def _append_stream_updates(
    compiled: CompiledStateGraph,
    config: dict[str, Any],
    initial_state: AgentState,
    node_records: list[dict[str, Any]],
) -> None:
    """Append each yielded node update before the next node runs.

    The list is owned by the caller. If a later node raises, updates that
    were already yielded stay in ``node_records`` instead of disappearing
    with the unfinished call.
    """
    for update in compiled.stream(initial_state, config, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        for node_name, node_output in update.items():
            output = node_output if isinstance(node_output, dict) else {"value": node_output}
            node_records.append({"node": str(node_name), "output": output})


def _state_after_completed_nodes(
    initial_state: AgentState,
    node_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fold completed node outputs onto the input state.

    Only nodes whose updates were yielded are included. The node that raised
    has no update, so its partial work is not stored.
    """
    collected = dict(initial_state)
    for record in node_records:
        output = record.get("output")
        if isinstance(output, dict):
            collected.update(output)
    return collected


def _trace_payload(
    *,
    trace_id: str,
    thread_id: str,
    question: str,
    node_records: list[dict[str, Any]],
    final_state: dict[str, Any],
    execution_error: str,
) -> dict[str, Any]:
    context = final_state.get("context", [])
    if not isinstance(context, list):
        context = []
    return {
        "trace_id": trace_id,
        "thread_id": thread_id,
        "question": question,
        "node_order": [record["node"] for record in node_records],
        "nodes": node_records,
        "context": context,
        "answer": str(final_state.get("answer", "")),
        "error": execution_error or str(final_state.get("error", "")),
        "sources": list(final_state.get("sources") or []),
        "lookup_failure": str(final_state.get("lookup_failure") or ""),
        "ticket_id": str(final_state.get("ticket_id") or ""),
        "ticket_status": str(final_state.get("ticket_status") or ""),
    }


def run_support_agent(
    question: str,
    *,
    caller_is_authenticated: bool = False,
    actor_user_id: str | None = None,
    thread_id: str | None = None,
    checkpoint_path: Path | None = None,
    trace_dir: Path | None = None,
    memory_path: Path | None = None,
    intent_classifier: IntentClassifier | None = None,
    clock: Any = None,
) -> AgentRun:
    """Compile the graph, run one question, and persist a queryable trace.

    Compilation happens before ``stream``. If a node raises, completed updates
    already appended to ``node_records`` are stored with a fixed error string.
    The ``trace_id`` is logged for operators. The original exception is
    re-raised, and the client response does not receive that id or the
    exception text.
    """
    resolved_thread_id = thread_id or uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    database_path = checkpoint_path or checkpoint_database_path()
    directory = trace_dir or trace_directory()
    store = MemoryStore(memory_path, clock=clock) if actor_user_id else None
    preparation = prepare_turn(
        store,
        actor_user_id=actor_user_id,
        thread_id=resolved_thread_id,
        message=question,
        intent_classifier=intent_classifier,
    )
    if preparation.skip_graph:
        answer = preparation.direct_answer
        persist_trace(
            _trace_payload(
                trace_id=trace_id,
                thread_id=resolved_thread_id,
                question=preparation.trace_question,
                node_records=[],
                final_state={"answer": answer, "error": "", "context": []},
                execution_error="",
            ),
            directory,
        )
        return AgentRun(
            answer=answer,
            error="",
            trace_id=trace_id,
            thread_id=resolved_thread_id,
            memory_proposal=preparation.memory_proposal,
        )

    config: dict[str, Any] = {"configurable": {"thread_id": resolved_thread_id}}
    initial_state = _initial_state(
        preparation.graph_question,
        caller_is_authenticated=caller_is_authenticated,
        approved_memory=preparation.approved_notes,
    )
    node_records: list[dict[str, Any]] = []

    with open_sqlite_checkpointer(database_path) as checkpointer:
        compiled = compile_support_graph(checkpointer)
        try:
            _append_stream_updates(compiled, config, initial_state, node_records)
            final_state = dict(compiled.get_state(config).values)
        except Exception:
            collected_state = _state_after_completed_nodes(initial_state, node_records)
            persist_trace(
                _trace_payload(
                    trace_id=trace_id,
                    thread_id=resolved_thread_id,
                    question=preparation.trace_question,
                    node_records=node_records,
                    final_state=collected_state,
                    execution_error=GRAPH_EXECUTION_FAILED,
                ),
                directory,
            )
            logger.error(
                "Support agent graph execution failed trace_id=%s",
                trace_id,
            )
            raise

    answer = str(final_state.get("answer", ""))
    memory_proposal = preparation.memory_proposal
    if not final_state.get("error"):
        if preparation.answer_prefix:
            prefix = preparation.answer_prefix.rstrip()
            answer = f"{prefix}\n\n{answer}" if answer else prefix
        answer = append_unverified_notes(answer, preparation.approved_notes)
        answer, staged_proposal = finish_turn(
            store,
            actor_user_id=actor_user_id,
            thread_id=resolved_thread_id,
            source_message=preparation.graph_question,
            answer=answer,
            preparation=preparation,
        )
        if staged_proposal:
            memory_proposal = staged_proposal
    final_state["answer"] = answer
    persist_trace(
        _trace_payload(
            trace_id=trace_id,
            thread_id=resolved_thread_id,
            question=preparation.trace_question,
            node_records=node_records,
            final_state=final_state,
            execution_error="",
        ),
        directory,
    )
    stored = load_trace(trace_id, directory)
    return AgentRun(
        answer=str(stored.get("answer", "")),
        error=str(stored.get("error", "")),
        trace_id=trace_id,
        thread_id=resolved_thread_id,
        memory_proposal=memory_proposal,
    )
