"""Interrupted response recovery preserves its intake and completed sections."""
from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.rfp_models import RfpTicket, utc_now
from app.services import rfp_service


def _ticket(status="under_evaluation", *, old=True, complete=False):
    return RfpTicket(
        ticket_id="recovery-fixture",
        status=status,
        updated_at=utc_now() - (timedelta(hours=1) if old else timedelta()),
        part2_handoff={
            "ticket_id": "recovery-fixture", "metadata": {"client_country": "US"},
            "sections": [{"department_id": d, "key_aspects": {}} for d in ("revenue", "clinical", "compliance")],
        },
        part3_handoff={"response_complete": True} if complete else None,
    )


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + (tmp_path / "recovery.db").as_posix())
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(rfp_service, "RUNNING_TICKETS", set())
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize("status", ["drafting", "under_evaluation"])
def test_stale_interrupted_response_can_restart_same_ticket(store, status):
    ticket = _ticket(status); store.add(ticket); store.commit()
    resumed = rfp_service.begin_response(store, ticket.ticket_id)
    assert resumed.ticket_id == ticket.ticket_id and resumed.status == "drafting"
    assert resumed.part2_handoff["ticket_id"] == ticket.ticket_id
    assert not rfp_service._stalled(resumed)


@pytest.mark.parametrize("old,active,complete", [(False, False, False), (True, True, False), (True, False, True)])
def test_recent_active_or_completed_response_is_not_restarted(store, old, active, complete):
    ticket = _ticket(old=old, complete=complete); store.add(ticket); store.commit()
    if active: rfp_service.RUNNING_TICKETS.add(ticket.ticket_id)
    with pytest.raises(rfp_service.ResponseNotReady):
        rfp_service.begin_response(store, ticket.ticket_id)


def test_recovery_never_accepts_mismatched_intake_handoff(store):
    ticket = _ticket(); ticket.part2_handoff = {**ticket.part2_handoff, "ticket_id": "other-ticket"}
    store.add(ticket); store.commit()
    with pytest.raises(rfp_service.ResponseNotReady):
        rfp_service.begin_response(store, ticket.ticket_id)


def test_stale_response_is_reported_as_stalled():
    assert rfp_service._stalled(_ticket())


def test_stale_session_cannot_claim_work_already_claimed_by_another_process(store, monkeypatch):
    ticket = _ticket(); store.add(ticket); store.commit()
    with Session(store.get_bind()) as other:
        stale = other.get(RfpTicket, ticket.ticket_id)
        assert stale is not None
        rfp_service.begin_response(store, ticket.ticket_id)
        # Model another API process, whose in-memory running set is independent.
        monkeypatch.setattr(rfp_service, "RUNNING_TICKETS", set())
        with pytest.raises(rfp_service.ResponseNotReady):
            rfp_service.begin_response(other, ticket.ticket_id)


def test_completed_department_is_reused_without_generation(monkeypatch):
    from data.pipelines.rfp_intake import response_loop
    calls = []
    def run(dept, *args, **kwargs):
        calls.append(dept)
        return {"department_id": dept, "draft_content": "new " + dept, "evaluation_results": {}, "needs_human_review": False}
    monkeypatch.setattr(response_loop, "run_department", run)
    completed = {"clinical": {"department_id": "clinical", "draft_content": "saved clinical", "evaluation_results": {}, "needs_human_review": False}}
    result = response_loop.run_response_generation(_ticket().part2_handoff, lambda _: "unused", completed_outcomes=completed)
    assert set(calls) == {"revenue", "compliance"}
    assert next(s for s in result["sections"] if s["department_id"] == "clinical")["draft_content"] == "saved clinical"
