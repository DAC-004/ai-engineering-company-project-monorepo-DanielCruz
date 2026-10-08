"""Synthetic checks for the PHI surfaces named in the HealthCore context.

The positive term is the detector category ``medical record``. It is not a
patient identifier. A passing run does not guarantee later content.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.guardrails.audit import record, reset
from app.agent.guardrails.output_validation import SAFE_OUTPUT, safe_output
from app.agent.memory_policy import PHI_REFUSAL, appears_to_contain_phi
from data.pipelines.rag import generate_answer
from app.agent.memory_store import MemoryStore
from app.routers.agent import router

POSITIVE = "medical record"
NEGATIVE = "Cancelling more than 24 hours in advance has no charge."
ACTOR = "user-synth-714"


def test_detector_accepts_policy_text_and_flags_the_category_term() -> None:
    assert appears_to_contain_phi(NEGATIVE) is False
    assert appears_to_contain_phi(f"staff asked about a {POSITIVE}") is True


def test_response_surface_replaces_the_category_term_and_keeps_policy_text() -> None:
    blocked = safe_output(f"The {POSITIVE} was requested.")
    assert blocked == SAFE_OUTPUT
    assert POSITIVE not in blocked
    assert safe_output(NEGATIVE) == NEGATIVE


def test_guardrail_log_records_the_action_and_not_the_category_term(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reset()
    with caplog.at_level(logging.INFO, logger="app.agent.guardrails.audit"):
        record("output_validation", "block", "content")
    rendered = "\n".join(record.message for record in caplog.records)
    assert "guardrail=output_validation" in rendered
    assert "action=block" in rendered
    assert "failure_type=content" in rendered
    assert POSITIVE not in rendered


def test_memory_table_withholds_the_category_term_and_stores_policy_text(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "phi-surfaces.sqlite", clock=lambda: datetime(2026, 10, 6, tzinfo=UTC))
    withheld = store.stage_proposal(
        owner_user_id=ACTOR,
        thread_id="thread-phi",
        text=f"note about a {POSITIVE}",
        kind="clinic_protocol",
        subject_key="withheld",
        originating_message=f"note about a {POSITIVE}",
    )
    assert withheld is None
    assert POSITIVE not in store.database_text()

    kept = store.stage_proposal(
        owner_user_id=ACTOR,
        thread_id="thread-policy",
        text=NEGATIVE,
        kind="clinic_protocol",
        subject_key="policy",
        originating_message="Store the cancellation rule.",
    )
    assert kept is not None
    approved = store.write_approved(
        actor_user_id=ACTOR,
        proposal_id=kept.proposal_id,
        originating_message="Store it.",
    )
    assert approved is not None
    audit_rows = [row for row in store.list_audit() if row.event == "approved"]
    assert audit_rows
    assert audit_rows[-1].actor_user_id == ACTOR
    assert audit_rows[-1].occurred_at is not None
    assert POSITIVE not in store.database_text()


def test_endpoint_response_and_trace_omit_the_category_term(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agent.graph.checkpoint_database_path",
        lambda: tmp_path / "checkpoints" / "support_agent.sqlite",
    )
    trace_dir = tmp_path / "traces"
    monkeypatch.setattr("app.agent.graph.trace_directory", lambda: trace_dir)
    application = FastAPI()
    application.include_router(router)
    response = TestClient(application).post(
        "/agent/query",
        json={"question": f"staff asked about a {POSITIVE}"},
    )
    assert response.status_code == 200
    assert response.json()["answer"] == PHI_REFUSAL
    assert POSITIVE not in response.text
    rendered_traces = "\n".join(path.read_text(encoding="utf-8") for path in trace_dir.glob("*.json"))
    assert rendered_traces
    assert POSITIVE not in rendered_traces


def test_generate_answer_file_log_and_return_omit_the_category_term(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_path = tmp_path / "guardrail.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    audit_logger = logging.getLogger("app.agent.guardrails.audit")
    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)
    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "")
    monkeypatch.setattr(
        "data.pipelines.rag._local_llm_complete",
        lambda _messages: f"The {POSITIVE} was requested.",
    )
    try:
        answer = generate_answer(
            "What is the cancellation charge?",
            [{"text": NEGATIVE, "source_document": "appointment-policy", "section": "Cancellation"}],
        )
    finally:
        handler.close()
        audit_logger.removeHandler(handler)

    assert answer == SAFE_OUTPUT
    assert POSITIVE not in answer
    stored = log_path.read_text(encoding="utf-8")
    assert "guardrail=output_validation" in stored
    assert POSITIVE not in stored
    assert not (tmp_path / "phi-surfaces.sqlite").exists()
