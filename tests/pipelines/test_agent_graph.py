"""Graph compilation, routing, checkpoints, and trace lookup.

These tests execute the compiled graph with patched RAG functions.
``tests/pipelines/test_agent_evals.py`` does not execute the graph.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import StateSnapshot

from app.agent.graph import (
    GRAPH_EXECUTION_FAILED,
    compile_support_graph,
    open_sqlite_checkpointer,
    run_support_agent,
)
from app.agent.nodes import EMPTY_QUESTION_ERROR, receive_question
from app.agent.state import AgentState
from app.agent.tracing import load_trace
from data.pipelines.rag import insufficient_information_answer
from tests.pipelines.record_agent_traces import record_reviewed_traces

REFERRAL_PAYLOAD: dict[str, Any] = {
    "company": "healthcore",
    "source_document": "referral-process",
    "section": "Target completed-referral time",
    "language": "en",
    "chunk_index": 1,
    "text": "Target completed-referral time: 11 days from creation to confirmed appointment.",
}


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "checkpoints" / "support_agent.sqlite", tmp_path / "traces"


def test_valid_graph_compiles(tmp_path: Path) -> None:
    database_path, _trace_dir = _paths(tmp_path)
    with open_sqlite_checkpointer(database_path) as checkpointer:
        compiled = compile_support_graph(checkpointer)
    assert compiled is not None
    assert hasattr(compiled, "stream")
    assert hasattr(compiled, "get_state_history")


def test_unknown_node_fails_during_compile(tmp_path: Path) -> None:
    builder: StateGraph = StateGraph(AgentState)
    builder.add_node("receive_question", receive_question)
    builder.add_edge(START, "receive_question")
    builder.add_edge("receive_question", "missing_node")
    builder.add_edge("missing_node", END)
    database_path, _trace_dir = _paths(tmp_path)
    with open_sqlite_checkpointer(database_path) as checkpointer:
        with pytest.raises(ValueError, match="unknown node"):
            builder.compile(checkpointer=checkpointer)


def test_empty_question_skips_retrieval_and_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"retrieve": 0, "generate": 0}

    def fail_retrieve(*_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        calls["retrieve"] += 1
        return []

    def fail_generate(*_args: object, **_kwargs: object) -> str:
        calls["generate"] += 1
        return "should not run"

    monkeypatch.setattr("data.pipelines.rag.retrieve", fail_retrieve)
    monkeypatch.setattr("data.pipelines.rag.generate_answer", fail_generate)
    database_path, trace_dir = _paths(tmp_path)

    outcome = run_support_agent(
        "   \n\t",
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )

    stored = load_trace(outcome.trace_id, trace_dir)
    assert outcome.error == EMPTY_QUESTION_ERROR
    assert stored["node_order"] == ["receive_question", "reject_question"]
    assert "retrieve_context" not in stored["node_order"]
    assert "generate_from_context" not in stored["node_order"]
    assert calls == {"retrieve": 0, "generate": 0}


def test_no_context_skips_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"retrieve": 0, "generate": 0}

    def empty_retrieve(query: str, **kwargs: object) -> list[dict[str, Any]]:
        calls["retrieve"] += 1
        assert query == "What is the capital of France?"
        assert "min_score" not in kwargs
        return []

    def fail_generate(*_args: object, **_kwargs: object) -> str:
        calls["generate"] += 1
        return "should not run"

    monkeypatch.setattr("data.pipelines.rag.retrieve", empty_retrieve)
    monkeypatch.setattr("data.pipelines.rag.generate_answer", fail_generate)
    database_path, trace_dir = _paths(tmp_path)

    outcome = run_support_agent(
        "What is the capital of France?",
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )

    stored = load_trace(outcome.trace_id, trace_dir)
    assert calls["retrieve"] == 1
    assert calls["generate"] == 0
    assert stored["context"] == []
    assert "retrieve_context" in stored["node_order"]
    assert "generate_from_context" not in stored["node_order"]
    assert outcome.answer == insufficient_information_answer()
    assert outcome.error == ""


def test_generation_receives_retrieved_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_retrieve(query: str, **_kwargs: object) -> list[dict[str, Any]]:
        seen["retrieve_query"] = query
        return [REFERRAL_PAYLOAD]

    def fake_generate(question: str, context: list[dict[str, Any]]) -> str:
        seen["question"] = question
        seen["context"] = context
        return "The indexed referral policy says the target is 11 days."

    monkeypatch.setattr("data.pipelines.rag.retrieve", fake_retrieve)
    monkeypatch.setattr("data.pipelines.rag.generate_answer", fake_generate)
    database_path, trace_dir = _paths(tmp_path)

    outcome = run_support_agent(
        "How long does an internal referral take?",
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )

    assert seen["retrieve_query"] == "How long does an internal referral take?"
    assert seen["question"] == "How long does an internal referral take?"
    assert seen["context"] == [REFERRAL_PAYLOAD]
    assert outcome.answer == "The indexed referral policy says the target is 11 days."
    stored = load_trace(outcome.trace_id, trace_dir)
    assert stored["node_order"] == [
        "receive_question",
        "retrieve_context",
        "generate_from_context",
    ]
    assert stored["context"] == [REFERRAL_PAYLOAD]


def _checkpoint_history(database_path: Path, thread_id: str) -> list[StateSnapshot]:
    """Reopen the SQLite file and return this thread's checkpoints.

    Installed LangGraph 1.2 returns ``get_state_history`` newest-first.
    Callers search for semantic states instead of assuming a fixed length
    or a fixed index.
    """
    connection = sqlite3.connect(database_path, check_same_thread=False)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        compiled = compile_support_graph(checkpointer)
        return list(
            compiled.get_state_history({"configurable": {"thread_id": thread_id}})
        )
    finally:
        connection.close()


def _upcoming(snapshot: StateSnapshot) -> tuple[str, ...]:
    return tuple(snapshot.next)


def _has_state(
    history: list[StateSnapshot],
    *,
    upcoming: tuple[str, ...],
    values: dict[str, Any],
) -> bool:
    for snapshot in history:
        if _upcoming(snapshot) != upcoming:
            continue
        if all(snapshot.values.get(key) == expected for key, expected in values.items()):
            return True
    return False


def test_empty_question_checkpoints_stop_before_retrieval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "data.pipelines.rag.retrieve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("retrieve ran")),
    )
    database_path, trace_dir = _paths(tmp_path)
    outcome = run_support_agent(
        "   \n\t",
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )
    history = _checkpoint_history(database_path, outcome.thread_id)

    assert _has_state(
        history,
        upcoming=("reject_question",),
        values={"question": "", "context": [], "answer": "", "error": ""},
    )
    assert _has_state(
        history,
        upcoming=(),
        values={"question": "", "error": EMPTY_QUESTION_ERROR, "answer": "", "context": []},
    )
    assert all(
        _upcoming(snapshot) not in {("retrieve_context",), ("generate_from_context",)}
        for snapshot in history
    )


def test_no_context_checkpoints_stop_before_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("data.pipelines.rag.retrieve", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "data.pipelines.rag.generate_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generate ran")),
    )
    database_path, trace_dir = _paths(tmp_path)
    outcome = run_support_agent(
        "What is the capital of France?",
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )
    history = _checkpoint_history(database_path, outcome.thread_id)
    question = "What is the capital of France?"

    assert _has_state(
        history,
        upcoming=("retrieve_context",),
        values={"question": question, "context": [], "answer": "", "error": ""},
    )
    assert _has_state(
        history,
        upcoming=("respond_no_information",),
        values={"question": question, "context": [], "answer": "", "error": ""},
    )
    assert _has_state(
        history,
        upcoming=(),
        values={
            "question": question,
            "context": [],
            "answer": insufficient_information_answer(),
            "error": "",
        },
    )
    assert all(_upcoming(snapshot) != ("generate_from_context",) for snapshot in history)


def test_supporting_context_checkpoints_include_retrieval_and_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_answer = "The indexed referral policy says the target is 11 days."
    monkeypatch.setattr(
        "data.pipelines.rag.retrieve",
        lambda *_args, **_kwargs: [REFERRAL_PAYLOAD],
    )
    monkeypatch.setattr(
        "data.pipelines.rag.generate_answer",
        lambda *_args, **_kwargs: generated_answer,
    )
    database_path, trace_dir = _paths(tmp_path)
    question = "How long does an internal referral take?"
    outcome = run_support_agent(
        question,
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )
    history = _checkpoint_history(database_path, outcome.thread_id)

    assert _has_state(
        history,
        upcoming=("retrieve_context",),
        values={"question": question, "context": [], "answer": "", "error": ""},
    )
    assert _has_state(
        history,
        upcoming=("generate_from_context",),
        values={"question": question, "context": [REFERRAL_PAYLOAD], "error": ""},
    )
    assert _has_state(
        history,
        upcoming=(),
        values={
            "question": question,
            "context": [REFERRAL_PAYLOAD],
            "answer": generated_answer,
            "error": "",
        },
    )


def test_failed_generation_persists_completed_nodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_detail = "SECRET_EXCEPTION_DETAIL"
    monkeypatch.setattr(
        "data.pipelines.rag.retrieve",
        lambda *_args, **_kwargs: [REFERRAL_PAYLOAD],
    )

    def raise_during_generation(_question: str, _context: list[dict[str, Any]]) -> str:
        raise RuntimeError(secret_detail)

    monkeypatch.setattr("data.pipelines.rag.generate_answer", raise_during_generation)
    database_path, trace_dir = _paths(tmp_path)
    caplog.set_level(logging.ERROR, logger="app.agent.graph")

    with pytest.raises(RuntimeError, match=secret_detail):
        run_support_agent(
            "How long does an internal referral take?",
            checkpoint_path=database_path,
            trace_dir=trace_dir,
        )

    logged_ids = [
        match.group(1)
        for record in caplog.records
        if (match := re.search(r"trace_id=([0-9a-f]{32})", record.getMessage()))
    ]
    assert logged_ids
    for record in caplog.records:
        message = record.getMessage()
        assert secret_detail not in message
        assert "RuntimeError" not in message
        assert "Traceback" not in message

    stored = load_trace(logged_ids[0], trace_dir)
    trace_text = str(stored)
    assert stored["node_order"] == ["receive_question", "retrieve_context"]
    assert "generate_from_context" not in stored["node_order"]
    assert stored["context"] == [REFERRAL_PAYLOAD]
    assert stored["error"] == GRAPH_EXECUTION_FAILED
    assert secret_detail not in trace_text
    assert "RuntimeError" not in trace_text
    assert "Traceback" not in trace_text


def test_first_node_failure_persists_empty_node_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The first node raises before any stream update is yielded."""
    secret_detail = "SECRET_FIRST_NODE_DETAIL"

    def raise_before_completion(_state: dict[str, Any]) -> dict[str, str]:
        raise RuntimeError(secret_detail)

    monkeypatch.setattr("app.agent.graph.receive_question", raise_before_completion)
    database_path, trace_dir = _paths(tmp_path)
    caplog.set_level(logging.ERROR, logger="app.agent.graph")

    with pytest.raises(RuntimeError, match=secret_detail):
        run_support_agent(
            "How long does an internal referral take?",
            checkpoint_path=database_path,
            trace_dir=trace_dir,
        )

    logged_ids = [
        match.group(1)
        for record in caplog.records
        if (match := re.search(r"trace_id=([0-9a-f]{32})", record.getMessage()))
    ]
    assert logged_ids
    for record in caplog.records:
        message = record.getMessage()
        assert secret_detail not in message
        assert "RuntimeError" not in message
        assert "Traceback" not in message

    stored = load_trace(logged_ids[0], trace_dir)
    trace_text = str(stored)
    assert stored["node_order"] == []
    assert stored["error"] == GRAPH_EXECUTION_FAILED
    assert secret_detail not in trace_text
    assert "RuntimeError" not in trace_text
    assert "Traceback" not in trace_text


def test_trace_can_be_loaded_by_trace_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("data.pipelines.rag.retrieve", lambda _query, **_kwargs: [])
    monkeypatch.setattr(
        "data.pipelines.rag.generate_answer",
        lambda _question, _context: "should not run",
    )
    database_path, trace_dir = _paths(tmp_path)
    outcome = run_support_agent(
        "What is the capital of France?",
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )

    stored = load_trace(outcome.trace_id, trace_dir)
    assert stored["trace_id"] == outcome.trace_id
    assert stored["thread_id"] == outcome.thread_id
    assert stored["question"] == "What is the capital of France?"
    assert isinstance(stored["node_order"], list)
    assert stored["context"] == []
    assert stored["answer"] == insufficient_information_answer()
    with pytest.raises(FileNotFoundError, match="missing-trace-id"):
        load_trace("missing-trace-id", trace_dir)


def test_record_utility_writes_three_reviewed_traces(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    export_path = tmp_path / "sample-agent-trace.json"
    written = record_reviewed_traces(fixture_dir, export_path)

    assert set(written) == {"empty_question", "no_context", "referral_grounding"}
    empty_trace = written["empty_question"]
    no_context_trace = written["no_context"]
    grounded_trace = written["referral_grounding"]
    assert empty_trace["node_order"] == ["receive_question", "reject_question"]
    assert no_context_trace["context"] == []
    assert "generate_from_context" not in no_context_trace["node_order"]
    assert "11 days" in grounded_trace["answer"]
    assert export_path.is_file()
    assert (fixture_dir / "referral_grounding.json").is_file()
