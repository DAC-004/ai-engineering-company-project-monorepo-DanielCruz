"""Approved and rejected memory cycles for the HealthCore support agent.

The model boundary is injected. The SQLite store, PHI screen, audit rows,
and retrieval run for real. These tests do not call Qdrant.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
for import_path in (str(REPO_ROOT), str(API_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.agent.graph import run_support_agent  # noqa: E402
from app.agent.memory_policy import (  # noqa: E402
    PHI_REFUSAL,
    PHI_WITHHELD,
    IntentDecision,
    appears_to_contain_phi,
    classify_pending_intent,
    evaluate_memorable,
)
from app.agent.memory_store import (  # noqa: E402
    FACT_TTL,
    MAX_ACTIVE_FACTS,
    PENDING_TTL,
    MemoryStore,
)
from app.agent.tracing import load_trace  # noqa: E402
from app.routers.agent import router  # noqa: E402

MANCHESTER = (
    "At the Manchester clinic, internal referrals now go through the coordinator "
    "before the specialist — that changed last quarter."
)
AUSTIN = (
    "That high no-show alert at the Austin clinic was because of a road closure "
    "that week, not a real problem with the reminder programme."
)
DIANE = (
    "The weekly report for Diane Foster needs vacancies broken down by role, "
    "not just by clinic — she asked for that two weeks ago."
)
BATCH_INCIDENT = (
    "the referral system fails on Monday mornings because of the overnight batch job"
)
PATIENT_SMITH = "patient Smith had a failed referral"
COUNTRY_ADMIN = (
    "For UK clinics, the administrative exception changed last quarter: "
    "front-desk sign-off is no longer required; US clinics still require it."
)
JOHNSON = "Patient Johnson cancelled tomorrow's appointment, note that down."
FALSE_CORRECTION = "Internal referrals now take 1 day."
REFERRAL_CONTEXT = [
    {
        "source_document": "referral-process",
        "text": "Target completed-referral time: 11 days from creation to confirmed appointment.",
    }
]
ACTOR_A = "user-a"
ACTOR_B = "user-b"
THREAD = "thread-1"


def _approve(_message: str, _pending: str) -> IntentDecision:
    return IntentDecision(label="approve", confidence=1.0)


def _reject(_message: str, _pending: str) -> IntentDecision:
    return IntentDecision(label="reject", confidence=1.0)


def _unclear(_message: str, _pending: str) -> IntentDecision:
    return IntentDecision(label="unclear", confidence=0.2)


def _edit_weekdays(_message: str, _pending: str) -> IntentDecision:
    return IntentDecision(
        label="edit",
        confidence=0.95,
        revised_text=(
            "At the Manchester clinic, internal referrals now go through the "
            "coordinator on weekdays."
        ),
    )


def _approve_with_rate_question(_message: str, _pending: str) -> IntentDecision:
    return IntentDecision(
        label="approve",
        confidence=0.99,
        residual_question="What's this week's no-show rate?",
    )


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        self.current += timedelta(seconds=1)
        return self.current


@pytest.fixture
def patched_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("data.pipelines.rag.retrieve", lambda _query, **_kwargs: [])

    def _generate(question: str, context: list[dict[str, str]], operational_memory: list[str] | None = None) -> str:
        if any("11 days" in chunk.get("text", "") for chunk in context):
            return "The indexed policy says 11 days."
        return f"Answer for {question}"

    monkeypatch.setattr("data.pipelines.rag.generate_answer", _generate)

    def _fail_qdrant() -> None:
        raise AssertionError("memory must not open the company Qdrant client")

    monkeypatch.setattr("shared.healthcore_rag.qdrant.get_qdrant_client", _fail_qdrant)


def _run(
    tmp_path: Path,
    question: str,
    *,
    actor: str | None,
    thread_id: str = THREAD,
    classifier=None,
    clock=None,
):
    return run_support_agent(
        question,
        caller_is_authenticated=actor is not None,
        actor_user_id=actor,
        thread_id=thread_id,
        checkpoint_path=tmp_path / "checkpoints" / "support_agent.sqlite",
        trace_dir=tmp_path / "traces",
        memory_path=tmp_path / "memory.sqlite",
        intent_classifier=classifier,
        clock=clock,
    )


def _store(tmp_path: Path, clock=None) -> MemoryStore:
    return MemoryStore(tmp_path / "memory.sqlite", clock=clock)


def test_six_healthcore_examples_match_the_criterion() -> None:
    manchester = evaluate_memorable(MANCHESTER)
    austin = evaluate_memorable(AUSTIN)
    diane = evaluate_memorable(DIANE)
    assert manchester is not None and manchester.kind == "clinic_protocol"
    assert austin is not None and austin.kind == "incident_pattern"
    assert diane is not None and diane.kind == "staff_preference"
    assert evaluate_memorable("What's this week's no-show rate?") is None
    assert evaluate_memorable("Thanks, that settles my report.") is None
    assert evaluate_memorable(JOHNSON) is None
    assert appears_to_contain_phi(JOHNSON) is True
    assert appears_to_contain_phi(DIANE) is False
    batch = evaluate_memorable(BATCH_INCIDENT)
    assert batch is not None and batch.kind == "incident_pattern"
    assert appears_to_contain_phi(PATIENT_SMITH) is True
    assert evaluate_memorable(PATIENT_SMITH) is None


def test_country_administrative_exception_is_proposed_without_a_named_clinic(
    tmp_path: Path,
    patched_rag: None,
) -> None:
    candidate = evaluate_memorable(COUNTRY_ADMIN)
    assert candidate is not None
    assert candidate.kind == "clinic_protocol"
    assert candidate.subject_key == "uk_us_administrative_exception"
    assert evaluate_memorable("What's the administrative exception for UK clinics?") is None
    assert evaluate_memorable("What's this week's no-show rate?") is None

    proposed = _run(tmp_path, COUNTRY_ADMIN, actor=ACTOR_A)
    store = _store(tmp_path)
    assert proposed.memory_proposal == COUNTRY_ADMIN
    assert "Want me to remember this for next time?" in proposed.answer
    assert store.list_active_facts(ACTOR_A) == []
    assert store.get_pending(ACTOR_A, THREAD) is not None

    phi_sentence = f"{COUNTRY_ADMIN} Patient Johnson cancelled tomorrow's appointment."
    assert appears_to_contain_phi(phi_sentence) is True
    assert evaluate_memorable(phi_sentence) is None
    refused = _run(tmp_path, phi_sentence, actor=ACTOR_A, thread_id="thread-phi-country")
    assert refused.answer == PHI_REFUSAL
    assert refused.memory_proposal is None
    assert "Johnson" not in refused.answer
    assert "Johnson" not in store.database_text()


def test_uk_and_us_administrative_exceptions_stay_distinct(tmp_path: Path) -> None:
    uk_text = (
        "For UK clinics, the administrative exception changed: "
        "front-desk sign-off is no longer required."
    )
    us_text = (
        "For US clinics, the administrative exception changed: "
        "front-desk sign-off is still required."
    )
    uk_later = (
        "For UK clinics, the administrative exception changed: "
        "front-desk sign-off is required again."
    )
    uk_candidate = evaluate_memorable(uk_text)
    us_candidate = evaluate_memorable(us_text)
    assert uk_candidate is not None and uk_candidate.subject_key == "uk_administrative_exception"
    assert us_candidate is not None and us_candidate.subject_key == "us_administrative_exception"

    store = _store(tmp_path, _Clock(datetime(2026, 5, 1, tzinfo=UTC)))

    def _approve(candidate_text: str, candidate, thread_id: str) -> None:
        pending = store.stage_proposal(
            owner_user_id=ACTOR_A,
            thread_id=thread_id,
            text=candidate_text,
            kind=candidate.kind,
            subject_key=candidate.subject_key,
            originating_message=candidate_text,
        )
        assert pending is not None
        assert (
            store.write_approved(
                actor_user_id=ACTOR_A,
                proposal_id=pending.proposal_id,
                originating_message="Store that country exception.",
            )
            is not None
        )

    _approve(uk_text, uk_candidate, "thread-uk")
    _approve(us_text, us_candidate, "thread-us")
    active = {fact.subject_key: fact.text for fact in store.list_active_facts(ACTOR_A)}
    assert active == {
        "uk_administrative_exception": uk_text,
        "us_administrative_exception": us_text,
    }

    both = evaluate_memorable(COUNTRY_ADMIN)
    assert both is not None and both.subject_key == "uk_us_administrative_exception"
    _approve(COUNTRY_ADMIN, both, "thread-both")
    compared = {fact.subject_key: fact.text for fact in store.list_active_facts(ACTOR_A)}
    assert compared == {
        "uk_administrative_exception": COUNTRY_ADMIN,
        "us_administrative_exception": COUNTRY_ADMIN,
    }
    assert len([row for row in store.list_audit() if row.event == "approved"]) == 3

    later = evaluate_memorable(uk_later)
    assert later is not None
    _approve(uk_later, later, "thread-uk-later")
    current = {fact.subject_key: fact.text for fact in store.list_active_facts(ACTOR_A)}
    assert current == {
        "uk_administrative_exception": uk_later,
        "us_administrative_exception": COUNTRY_ADMIN,
    }
    uk_notes = store.read_relevant(
        ACTOR_A,
        "What should UK clinics follow for the administrative exception?",
    )
    assert [fact.subject_key for fact in uk_notes] == ["uk_administrative_exception"]
    assert uk_notes[0].text == uk_later


def test_intent_classifier_uses_structured_output_not_the_word_yes() -> None:
    pending = MANCHESTER

    def _model(_message: str, _pending_text: str) -> str:
        return json.dumps({"label": "reject", "confidence": 0.91, "revised_text": None, "residual_question": None})

    decision = classify_pending_intent("yes", pending, model=_model)
    assert decision.label == "reject"

    def _prose(_message: str, _pending_text: str) -> str:
        return "yes"

    assert classify_pending_intent("yes", pending, model=_prose).label == "unclear"

    def _low(_message: str, _pending_text: str) -> str:
        return json.dumps({"label": "approve", "confidence": 0.2})

    assert classify_pending_intent("store it", pending, model=_low).label == "unclear"


def test_generation_model_failure_discards_the_pending_proposal(
    tmp_path: Path,
    patched_rag: None,
) -> None:
    clock = _Clock(datetime(2026, 3, 1, 1, tzinfo=UTC))
    proposed = _run(tmp_path, MANCHESTER, actor=ACTOR_A, clock=clock)
    assert proposed.memory_proposal == MANCHESTER

    def _missing_model(_message: str, _pending_text: str) -> str:
        raise FileNotFoundError("local generation model file is not available")

    def _classify(message: str, pending_text: str) -> IntentDecision:
        return classify_pending_intent(message, pending_text, model=_missing_model)

    outcome = _run(tmp_path, "yes", actor=ACTOR_A, classifier=_classify, clock=clock)
    store = _store(tmp_path, clock)
    assert store.get_pending(ACTOR_A, THREAD) is None
    assert store.list_active_facts(ACTOR_A) == []
    assert outcome.memory_proposal is None
    assert "I'll store that" not in outcome.answer
    discarded = [row for row in store.list_audit() if row.event == "discarded_ambiguous"]
    assert len(discarded) == 1
    assert discarded[0].actor_user_id == ACTOR_A
    assert [row for row in store.list_audit() if row.event == "approved"] == []


def test_approved_cycle_is_visible_only_to_the_authorizing_user(
    tmp_path: Path,
    patched_rag: None,
) -> None:
    clock = _Clock(datetime(2026, 3, 1, tzinfo=UTC))
    proposed = _run(tmp_path, MANCHESTER, actor=ACTOR_A, clock=clock)
    store = _store(tmp_path, clock)
    assert proposed.memory_proposal == MANCHESTER
    assert "Want me to remember this for next time?" in proposed.answer
    assert store.list_active_facts(ACTOR_A) == []
    proposed_audit = [row for row in store.list_audit() if row.event == "proposed"]
    assert len(proposed_audit) == 1
    assert proposed_audit[0].actor_user_id == ACTOR_A
    assert proposed_audit[0].originating_ref
    assert proposed_audit[0].safe_text == MANCHESTER
    assert proposed_audit[0].occurred_at.tzinfo is not None

    approved = _run(
        tmp_path,
        "Store the pending operational note.",
        actor=ACTOR_A,
        classifier=_approve,
        clock=clock,
    )
    assert approved.memory_proposal is None
    assert "unverified" in approved.answer.casefold()
    facts = store.list_active_facts(ACTOR_A)
    assert len(facts) == 1
    assert facts[0].claim_status == "unverified"
    assert facts[0].authorized_by_user_id == ACTOR_A
    assert facts[0].text == MANCHESTER
    approved_rows = [row for row in store.list_audit() if row.event == "approved"]
    assert len(approved_rows) == 1
    assert approved_rows[0].actor_user_id == ACTOR_A
    assert approved_rows[0].originating_ref
    assert approved_rows[0].occurred_at > proposed_audit[0].occurred_at

    monkeypatch_retrieve = pytest.MonkeyPatch()
    monkeypatch_retrieve.setattr("data.pipelines.rag.retrieve", lambda _query, **_kwargs: REFERRAL_CONTEXT)
    try:
        later = _run(
            tmp_path,
            "What should staff follow for Manchester internal referrals?",
            actor=ACTOR_A,
            clock=clock,
        )
    finally:
        monkeypatch_retrieve.undo()
    assert "11 days" in later.answer
    assert "Unverified staff-approved note" in later.answer
    assert MANCHESTER in later.answer

    def _must_not_classify(_message: str, _pending: str) -> IntentDecision:
        raise AssertionError("another user must not be asked to decide this proposal")

    other = _run(
        tmp_path,
        "What should staff follow for Manchester internal referrals?",
        actor=ACTOR_B,
        classifier=_must_not_classify,
        clock=clock,
    )
    assert store.get_pending(ACTOR_B, THREAD) is None
    assert store.list_active_facts(ACTOR_B) == []
    assert MANCHESTER not in other.answer
    assert "healthcore_knowledge" not in store.database_text()


def test_rejected_cycle_leaves_memory_unchanged(tmp_path: Path, patched_rag: None) -> None:
    clock = _Clock(datetime(2026, 3, 2, tzinfo=UTC))
    proposed = _run(tmp_path, AUSTIN, actor=ACTOR_A, clock=clock)
    assert proposed.memory_proposal == AUSTIN
    rejected = _run(
        tmp_path,
        "Do not store that note.",
        actor=ACTOR_A,
        classifier=_reject,
        clock=clock,
    )
    store = _store(tmp_path, clock)
    assert store.list_active_facts(ACTOR_A) == []
    assert rejected.memory_proposal is None
    assert "won't store" in rejected.answer
    rejected_rows = [row for row in store.list_audit() if row.event == "rejected"]
    assert len(rejected_rows) == 1
    assert rejected_rows[0].actor_user_id == ACTOR_A
    assert rejected_rows[0].originating_ref
    assert rejected_rows[0].safe_text == AUSTIN
    proposed_rows = [row for row in store.list_audit() if row.event == "proposed"]
    assert rejected_rows[0].occurred_at > proposed_rows[0].occurred_at

    later = _run(tmp_path, "Tell me about the Austin no-show alert.", actor=ACTOR_A, clock=clock)
    assert AUSTIN not in later.answer
    assert store.list_active_facts(ACTOR_A) == []


def test_safe_edit_is_audited_and_not_written_until_approval(tmp_path: Path, patched_rag: None) -> None:
    clock = _Clock(datetime(2026, 3, 3, tzinfo=UTC))
    _run(tmp_path, MANCHESTER, actor=ACTOR_A, clock=clock)
    edited = _run(
        tmp_path,
        "Change the note so the coordinator step is weekdays.",
        actor=ACTOR_A,
        classifier=_edit_weekdays,
        clock=clock,
    )
    store = _store(tmp_path, clock)
    pending = store.get_pending(ACTOR_A, THREAD)
    assert pending is not None
    assert "weekdays" in pending.text
    assert store.list_active_facts(ACTOR_A) == []
    assert edited.memory_proposal == pending.text
    edited_rows = [row for row in store.list_audit() if row.event == "edited"]
    assert len(edited_rows) == 1
    assert edited_rows[0].actor_user_id == ACTOR_A
    assert edited_rows[0].safe_text == pending.text
    assert edited_rows[0].originating_ref

    _run(tmp_path, "Store the revised note.", actor=ACTOR_A, classifier=_approve, clock=clock)
    facts = store.list_active_facts(ACTOR_A)
    assert len(facts) == 1
    assert "weekdays" in facts[0].text
    assert facts[0].claim_status == "unverified"


def test_phi_edit_does_not_replace_the_safe_pending_text(tmp_path: Path, patched_rag: None) -> None:
    clock = _Clock(datetime(2026, 3, 4, tzinfo=UTC))
    _run(tmp_path, MANCHESTER, actor=ACTOR_A, clock=clock)
    refused = _run(tmp_path, JOHNSON, actor=ACTOR_A, clock=clock)
    store = _store(tmp_path, clock)
    pending = store.get_pending(ACTOR_A, THREAD)
    assert pending is not None
    assert pending.text == MANCHESTER
    assert refused.answer == PHI_REFUSAL
    assert refused.memory_proposal is None
    assert "Johnson" not in refused.answer
    phi_rows = [row for row in store.list_audit() if row.event == "rejected_phi"]
    assert len(phi_rows) == 1
    assert phi_rows[0].content_retained is False
    assert phi_rows[0].safe_text is None
    assert "Johnson" not in store.database_text()


def test_phi_request_is_refused_without_copying_patient_content(
    tmp_path: Path,
    patched_rag: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_retrieve(*_args: object, **_kwargs: object) -> list[dict[str, str]]:
        raise AssertionError("retrieve() must not see patient content")

    monkeypatch.setattr("data.pipelines.rag.retrieve", _fail_retrieve)
    outcome = _run(tmp_path, JOHNSON, actor=ACTOR_A)
    assert outcome.answer == PHI_REFUSAL
    assert outcome.memory_proposal is None
    stored = load_trace(outcome.trace_id, tmp_path / "traces")
    assert stored["question"] == PHI_WITHHELD
    assert "Johnson" not in json.dumps(stored)
    checkpoint = tmp_path / "checkpoints" / "support_agent.sqlite"
    if checkpoint.exists():
        blob = checkpoint.read_bytes()
        assert b"Johnson" not in blob
    store = _store(tmp_path)
    assert "Johnson" not in store.database_text()
    assert store.list_active_facts(ACTOR_A) == []


def test_endpoint_accepts_phi_example_and_does_not_echo_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agent.graph.checkpoint_database_path",
        lambda: tmp_path / "checkpoints" / "support_agent.sqlite",
    )
    monkeypatch.setattr("app.agent.graph.trace_directory", lambda: tmp_path / "traces")
    application = FastAPI()
    application.include_router(router)
    client = TestClient(application)
    response = client.post("/agent/query", json={"question": JOHNSON})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == PHI_REFUSAL
    assert body["memory_proposal"] is None
    assert "Johnson" not in response.text


def test_named_patient_in_a_memorable_sentence_is_not_retained(
    tmp_path: Path,
    patched_rag: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentence = f"{MANCHESTER} John Smith is a patient."
    assert evaluate_memorable(MANCHESTER) is not None
    assert appears_to_contain_phi(sentence) is True
    assert evaluate_memorable(sentence) is None
    assert appears_to_contain_phi(DIANE) is False

    def _fail_retrieve(*_args: object, **_kwargs: object) -> list[dict[str, str]]:
        raise AssertionError("retrieve() must not see patient content")

    monkeypatch.setattr("data.pipelines.rag.retrieve", _fail_retrieve)
    outcome = _run(tmp_path, sentence, actor=ACTOR_A)
    assert outcome.answer == PHI_REFUSAL
    assert outcome.memory_proposal is None
    assert "John Smith" not in outcome.answer
    assert "Smith" not in outcome.answer
    stored = load_trace(outcome.trace_id, tmp_path / "traces")
    assert stored["question"] == PHI_WITHHELD
    assert "Smith" not in json.dumps(stored)
    store = _store(tmp_path)
    assert "Smith" not in store.database_text()
    assert store.get_pending(ACTOR_A, THREAD) is None
    assert store.list_active_facts(ACTOR_A) == []


def _abort_audit_inserts(store: MemoryStore) -> None:
    connection = sqlite3.connect(store.database_path)
    connection.execute(
        """
        CREATE TRIGGER abort_audit_insert
        BEFORE INSERT ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit insert failed');
        END
        """
    )
    connection.commit()
    connection.close()


def test_audit_failure_does_not_keep_an_unaudited_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _abort_audit_inserts(store)
    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        store.stage_proposal(
            owner_user_id=ACTOR_A,
            thread_id=THREAD,
            text=MANCHESTER,
            kind="clinic_protocol",
            subject_key="manchester_internal_referrals",
            originating_message=MANCHESTER,
        )
    assert store.get_pending(ACTOR_A, THREAD) is None
    assert store.list_audit() == []
    assert store.list_active_facts(ACTOR_A) == []

    staged = MemoryStore(tmp_path / "decisions.sqlite")
    pending = staged.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=MANCHESTER,
        kind="clinic_protocol",
        subject_key="manchester_internal_referrals",
        originating_message=MANCHESTER,
    )
    assert pending is not None
    _abort_audit_inserts(staged)
    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        staged.write_approved(
            actor_user_id=ACTOR_A,
            proposal_id=pending.proposal_id,
            originating_message="Store the pending operational note.",
        )
    assert staged.get_pending(ACTOR_A, THREAD) is not None
    assert staged.get_pending(ACTOR_A, THREAD).proposal_id == pending.proposal_id
    assert staged.list_active_facts(ACTOR_A) == []
    assert [row for row in staged.list_audit() if row.event == "approved"] == []

    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        staged.reject_pending(
            actor_user_id=ACTOR_A,
            proposal_id=pending.proposal_id,
            originating_message="Do not store that note.",
        )
    assert staged.get_pending(ACTOR_A, THREAD) is not None
    assert staged.list_active_facts(ACTOR_A) == []
    assert [row for row in staged.list_audit() if row.event == "rejected"] == []
    proposed_rows = [row for row in staged.list_audit() if row.event == "proposed"]
    assert len(proposed_rows) == 1
    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        staged.edit_pending(
            actor_user_id=ACTOR_A,
            proposal_id=pending.proposal_id,
            revised_text="At the Manchester clinic, internal referrals now go through the coordinator on weekdays.",
            originating_message="Change the note so the coordinator step is weekdays.",
        )
    assert staged.get_pending(ACTOR_A, THREAD).text == MANCHESTER
    assert [row for row in staged.list_audit() if row.event == "edited"] == []
    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        staged.discard_pending(
            actor_user_id=ACTOR_A,
            proposal_id=pending.proposal_id,
            originating_message="What's this week's no-show rate?",
        )
    assert staged.get_pending(ACTOR_A, THREAD) is not None
    assert [row for row in staged.list_audit() if row.event == "discarded_ambiguous"] == []

    start = datetime(2026, 4, 1, tzinfo=UTC)
    expiring = MemoryStore(tmp_path / "expiry.sqlite", clock=lambda: start)
    expiring_pending = expiring.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=AUSTIN,
        kind="incident_pattern",
        subject_key="austin_incident_pattern",
        originating_message=AUSTIN,
    )
    assert expiring_pending is not None
    later = start + PENDING_TTL + timedelta(minutes=1)
    aged = MemoryStore(tmp_path / "expiry.sqlite", clock=lambda: later)
    _abort_audit_inserts(aged)
    with pytest.raises(sqlite3.IntegrityError, match="audit insert failed"):
        aged.expire_stale()
    assert aged.get_pending(ACTOR_A, THREAD) is not None
    assert [row for row in aged.list_audit() if row.event == "expired_unanswered"] == []


def test_topic_change_discards_pending_proposal(tmp_path: Path, patched_rag: None) -> None:
    clock = _Clock(datetime(2026, 3, 5, tzinfo=UTC))
    _run(tmp_path, MANCHESTER, actor=ACTOR_A, clock=clock)
    changed = _run(
        tmp_path,
        "What's this week's no-show rate?",
        actor=ACTOR_A,
        classifier=_unclear,
        clock=clock,
    )
    store = _store(tmp_path, clock)
    assert store.get_pending(ACTOR_A, THREAD) is None
    assert store.list_active_facts(ACTOR_A) == []
    assert changed.memory_proposal is None
    discarded = [row for row in store.list_audit() if row.event == "discarded_ambiguous"]
    assert len(discarded) == 1
    assert discarded[0].actor_user_id == ACTOR_A


def test_second_proposal_is_blocked_while_one_is_pending(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=MANCHESTER,
        kind="clinic_protocol",
        subject_key="manchester_internal_referrals",
        originating_message=MANCHESTER,
    )
    second = store.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=AUSTIN,
        kind="incident_pattern",
        subject_key="austin_incident_pattern",
        originating_message=AUSTIN,
    )
    assert first is not None
    assert second is None
    assert store.get_pending(ACTOR_A, THREAD) is not None
    assert store.get_pending(ACTOR_A, THREAD).text == MANCHESTER


def test_approval_plus_another_question_still_answers(tmp_path: Path, patched_rag: None) -> None:
    clock = _Clock(datetime(2026, 3, 6, tzinfo=UTC))
    _run(tmp_path, MANCHESTER, actor=ACTOR_A, clock=clock)
    combined = _run(
        tmp_path,
        "Yes, store it. What's this week's no-show rate?",
        actor=ACTOR_A,
        classifier=_approve_with_rate_question,
        clock=clock,
    )
    assert "unverified" in combined.answer.casefold()
    assert combined.memory_proposal is None
    store = _store(tmp_path, clock)
    assert len(store.list_active_facts(ACTOR_A)) == 1


def test_false_correction_does_not_replace_retrieved_knowledge_or_reach_other_users(
    tmp_path: Path,
    patched_rag: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _Clock(datetime(2026, 3, 7, tzinfo=UTC))
    monkeypatch.setattr("data.pipelines.rag.retrieve", lambda _query, **_kwargs: REFERRAL_CONTEXT)
    proposed = _run(tmp_path, FALSE_CORRECTION, actor=ACTOR_A, clock=clock)
    assert proposed.memory_proposal == FALSE_CORRECTION
    _run(tmp_path, "Store that correction.", actor=ACTOR_A, classifier=_approve, clock=clock)
    later = _run(
        tmp_path,
        "How long does an internal referral take?",
        actor=ACTOR_A,
        clock=clock,
    )
    assert "11 days" in later.answer
    assert "Unverified staff-approved note" in later.answer
    assert FALSE_CORRECTION in later.answer
    store = _store(tmp_path, clock)
    facts = store.list_active_facts(ACTOR_A)
    assert facts[0].claim_status == "unverified"
    other = _run(
        tmp_path,
        "How long does an internal referral take?",
        actor=ACTOR_B,
        clock=clock,
    )
    assert FALSE_CORRECTION not in other.answer
    assert "11 days" in other.answer


def test_other_actor_cannot_approve_someone_elses_proposal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    pending = store.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=MANCHESTER,
        kind="clinic_protocol",
        subject_key="manchester_internal_referrals",
        originating_message=MANCHESTER,
    )
    assert pending is not None
    assert store.write_approved(
        actor_user_id=ACTOR_B,
        proposal_id=pending.proposal_id,
        originating_message="Store it.",
    ) is None
    assert store.list_active_facts(ACTOR_A) == []
    assert store.get_pending(ACTOR_A, THREAD) is not None


def test_unanswered_proposal_expires_without_a_write(tmp_path: Path) -> None:
    start = datetime(2026, 4, 1, tzinfo=UTC)
    store = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: start)
    pending = store.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=MANCHESTER,
        kind="clinic_protocol",
        subject_key="manchester_internal_referrals",
        originating_message=MANCHESTER,
    )
    assert pending is not None
    later = start + PENDING_TTL + timedelta(minutes=1)
    aged = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: later)
    assert aged.expire_stale() == 1
    assert aged.get_pending(ACTOR_A, THREAD) is None
    assert aged.list_active_facts(ACTOR_A) == []
    expired = [row for row in aged.list_audit() if row.event == "expired_unanswered"]
    assert len(expired) == 1
    assert expired[0].actor_user_id is None
    assert expired[0].occurred_at == later


def test_consolidation_supersedes_expires_caps_and_rechecks_phi(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    store = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: start)
    older = store.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=MANCHESTER,
        kind="clinic_protocol",
        subject_key="manchester_internal_referrals",
        originating_message=MANCHESTER,
    )
    assert older is not None
    store.write_approved(actor_user_id=ACTOR_A, proposal_id=older.proposal_id, originating_message="Store the first.")
    revised = "At the Manchester clinic, internal referrals now go through the coordinator on weekdays."
    newer = store.stage_proposal(
        owner_user_id=ACTOR_A,
        thread_id=THREAD,
        text=revised,
        kind="clinic_protocol",
        subject_key="manchester_internal_referrals",
        originating_message=revised,
    )
    assert newer is not None
    store.write_approved(actor_user_id=ACTOR_A, proposal_id=newer.proposal_id, originating_message="Store the revision.")
    active = store.list_active_facts(ACTOR_A)
    assert len(active) == 1
    assert active[0].text == revised
    assert active[0].claim_status == "unverified"

    aged_clock = start + FACT_TTL + timedelta(days=1)
    aged = MemoryStore(tmp_path / "memory.sqlite", clock=lambda: aged_clock)
    aged.consolidate()
    assert aged.list_active_facts(ACTOR_A) == []

    cap_store = MemoryStore(tmp_path / "cap.sqlite", clock=lambda: start)
    for index in range(MAX_ACTIVE_FACTS + 1):
        text = f"At the Austin clinic, front desk protocol {index} now changed for local scheduling."
        pending = cap_store.stage_proposal(
            owner_user_id=ACTOR_A,
            thread_id=THREAD,
            text=text,
            kind="clinic_protocol",
            subject_key=f"austin_protocol_{index}",
            originating_message=text,
        )
        assert pending is not None
        assert cap_store.write_approved(
            actor_user_id=ACTOR_A,
            proposal_id=pending.proposal_id,
            originating_message="Store it.",
        ) is not None
    assert len(cap_store.list_active_facts(ACTOR_A)) == MAX_ACTIVE_FACTS

    phi_store = MemoryStore(tmp_path / "phi.sqlite", clock=lambda: start)
    with sqlite3.connect(phi_store.database_path) as connection:
        connection.execute(
            """
            INSERT INTO facts (
                fact_id, owner_user_id, authorized_by_user_id, kind, subject_key,
                text, claim_status, active, created_at, superseded_at
            ) VALUES ('phi-fact', ?, ?, 'clinic_protocol', 'bad', ?, 'unverified', 1, ?, NULL)
            """,
            (ACTOR_A, ACTOR_A, JOHNSON, start.isoformat()),
        )
    phi_store.consolidate()
    assert "Johnson" not in phi_store.database_text()
    assert phi_store.list_active_facts(ACTOR_A) == []


def test_non_memorable_turns_do_not_propose(tmp_path: Path, patched_rag: None) -> None:
    for question in (
        "What's this week's no-show rate?",
        "Thanks, that settles my report.",
        "How long does an internal referral take?",
    ):
        outcome = _run(tmp_path, question, actor=ACTOR_A, thread_id=f"thread-{question[:8]}")
        assert outcome.memory_proposal is None
    store = _store(tmp_path)
    assert store.list_active_facts(ACTOR_A) == []
    assert [row for row in store.list_audit() if row.event == "proposed"] == []
