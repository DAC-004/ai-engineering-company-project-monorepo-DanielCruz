"""Part 2 entry uses the stored handoff. It does not read the PDF."""

from __future__ import annotations

from data.pipelines.rfp_intake.readiness import assess_readiness


def _handoff(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "metadata": {"client_name": "Meridian Manufacturing", "client_country": "US"},
        "sections": [
            {"department_id": "revenue", "key_aspects": {"aspects": ["12-month term."], "open_questions": []}},
            {"department_id": "clinical", "key_aspects": {"aspects": ["Austin clinic."], "open_questions": []}},
            {"department_id": "compliance", "key_aspects": {"aspects": ["BAA."], "open_questions": []}},
        ],
        "synthesizer_summary": "Not sent to a generator as the whole summary.",
    }


def test_intake_complete_handoff_is_accepted() -> None:
    decision = assess_readiness("intake_complete", "ticket-1", _handoff("ticket-1"))

    assert decision.accepted is True
    assert decision.handoff is not None
    assert decision.handoff["ticket_id"] == "ticket-1"
    assert {section["department_id"] for section in decision.handoff["sections"]} == {
        "revenue",
        "clinical",
        "compliance",
    }


def test_discarded_and_analyzing_tickets_are_refused() -> None:
    handoff = _handoff("ticket-1")

    discarded = assess_readiness("discarded", "ticket-1", handoff)
    analyzing = assess_readiness("analyzing", "ticket-1", handoff)

    assert discarded.accepted is False
    assert discarded.reason == "not_intake_complete"
    assert analyzing.accepted is False
    assert analyzing.reason == "not_intake_complete"


def test_mismatched_or_incomplete_handoff_is_refused() -> None:
    missing = assess_readiness("intake_complete", "ticket-1", None)
    mismatched = assess_readiness("intake_complete", "ticket-1", _handoff("other-ticket"))
    incomplete = _handoff("ticket-1")
    incomplete["sections"] = incomplete["sections"][:2]

    assert missing.reason == "handoff_missing"
    assert mismatched.reason == "handoff_mismatch"
    assert assess_readiness("intake_complete", "ticket-1", incomplete).reason == "handoff_incomplete"
