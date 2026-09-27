"""Trace-fixture evals for the support agent.

These tests read JSON written by ``tests/pipelines/record_agent_traces.py``.
They do not compile the graph, call ``retrieve()``, or call ``generate_answer()``.
"""

from __future__ import annotations

import json
from pathlib import Path

from data.pipelines.rag import insufficient_information_answer

FIXTURE_DIRECTORY = Path(__file__).resolve().parent / "fixtures" / "agent_traces"
REFERRAL_DOCUMENT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "company-knowledge-base"
    / "healthcore-referral-process.en.md"
)


def _load_fixture(name: str) -> dict:
    fixture_path = FIXTURE_DIRECTORY / f"{name}.json"
    loaded = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{name} fixture is not a JSON object.")
    return loaded


def test_empty_question_trace_routes_to_rejection() -> None:
    trace = _load_fixture("empty_question")
    node_order = trace["node_order"]
    assert node_order[0] == "receive_question"
    assert node_order[1] == "reject_question"
    assert "retrieve_context" not in node_order
    assert "generate_from_context" not in node_order


def test_no_context_trace_returns_insufficient_information() -> None:
    trace = _load_fixture("no_context")
    assert "retrieve_context" in trace["node_order"]
    assert trace["context"] == []
    assert "generate_from_context" not in trace["node_order"]
    assert trace["answer"] == insufficient_information_answer()


def test_referral_trace_is_grounded_in_indexed_policy() -> None:
    trace = _load_fixture("referral_grounding")
    assert trace["node_order"] == [
        "receive_question",
        "retrieve_context",
        "generate_from_context",
    ]
    referral_chunks = [
        chunk
        for chunk in trace["context"]
        if isinstance(chunk, dict) and chunk.get("source_document") == "referral-process"
    ]
    assert referral_chunks
    referral_document = REFERRAL_DOCUMENT.read_text(encoding="utf-8").replace("\r\n", "\n")
    retrieved_text = str(referral_chunks[0].get("text", "")).replace("\r\n", "\n")
    assert retrieved_text
    assert retrieved_text in referral_document
    assert "11 days" in retrieved_text
    assert "11 days" in trace["answer"]
    assert "11 days" in referral_document
