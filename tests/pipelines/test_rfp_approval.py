"""Part 3 interruption, resume, iteration limit, and parallel branches."""

from __future__ import annotations

from pathlib import Path

import pytest

from data.pipelines.rfp_intake.approval_graph import (
    ApprovalFlowError,
    ApprovalRun,
    department_interrupted,
)
from data.pipelines.rfp_intake.checkpointer import thread_id
from data.pipelines.rfp_intake.response_loop import MAX_ATTEMPTS

REVENUE = (
    "Pricing is quoted in USD for the occupational health program. "
    "Payment follows the twelve month contract. No other currency is used."
)
CLINICAL = (
    "Clinical Operations can staff the occupational health program at the stated clinics. "
    "The schedule already on the ticket is unchanged."
)
COMPLIANCE = (
    "The compliance section includes a Business Associate Agreement clause for this US client."
)


def _section(department_id: str, draft: str, *, contains_phi: bool = False) -> dict:
    return {
        "department_id": department_id,
        "draft_content": draft,
        "evaluation_results": {"contains_phi": contains_phi, "overall_pass": not contains_phi},
        "key_aspects": {"aspects": [], "open_questions": []},
        "needs_human_review": False,
        "approval_status": None,
        "approver": None,
        "approved_at": None,
        "approved_content_sha256": None,
        "submitted_by_user_id": None,
        "approval_revision_count": 0,
        "iteration_limit_reached": False,
    }


def _metadata() -> dict:
    return {
        "client_name": "Meridian Manufacturing",
        "client_country": "US",
        "program_type": "occupational health",
        "covered_population": "800 employees",
        "deadline": "August 23, 2026",
        "budget_range": None,
        "departments_needed": ["revenue", "clinical", "compliance"],
    }


def _complete(messages: list[dict[str, str]]) -> str:
    system = messages[0]["content"]
    if "Revenue Cycle" in system:
        return REVENUE
    if "Clinical Operations" in system:
        return CLINICAL
    return COMPLIANCE


def _run(tmp_path: Path, ticket_id: str = "ticket-a") -> ApprovalRun:
    return ApprovalRun(
        ticket_id,
        _metadata(),
        [
            _section("revenue", REVENUE),
            _section("clinical", CLINICAL),
            _section("compliance", COMPLIANCE),
        ],
        {"ticket_id": ticket_id, "response_complete": True, "currency": "USD", "covered_population": "800 employees"},
        [],
        tmp_path / "approvals.sqlite",
        _complete,
    )


def _approve(run: ApprovalRun, department_id: str) -> None:
    run.decide(
        department_id,
        actor_department_id=department_id,
        submitted_by_user_id=f"user-{department_id}",
        approver_name={"revenue": "Tom Callahan", "clinical": "Dr. Marcus Reid", "compliance": "Claire Whitfield"}[
            department_id
        ],
        decision="approve",
        note=None,
    )


def test_interrupt_persists_and_resume_recompiles(tmp_path: Path) -> None:
    run = _run(tmp_path)
    run.start()
    path = tmp_path / "approvals.sqlite"
    assert department_interrupted(path, "ticket-a", "revenue")
    assert thread_id("ticket-a", "revenue") == "rfp-ticket-a:revenue"
    resumed = ApprovalRun(
        run.ticket_id,
        run.metadata,
        run.sections,
        run.handoff,
        run.trace,
        path,
        _complete,
        arbitration=run.arbitration,
    )
    _approve(resumed, "revenue")
    assert run.sections[0]["approval_status"] == "approved"
    assert run.sections[0]["approver"] == "Tom Callahan"
    assert not department_interrupted(path, "ticket-a", "revenue")
    assert department_interrupted(path, "ticket-a", "clinical")
    assert "classify" not in {record["node"] for record in run.trace}


def test_approving_clinical_leaves_revenue_interrupted(tmp_path: Path) -> None:
    run = _run(tmp_path)
    run.start()
    _approve(run, "clinical")
    assert department_interrupted(tmp_path / "approvals.sqlite", "ticket-a", "revenue")
    assert run.final_document is None
    assert run.sections[1]["approval_status"] == "approved"
    assert run.sections[0]["approval_status"] != "approved"


def test_two_tickets_do_not_share_a_checkpoint(tmp_path: Path) -> None:
    first = _run(tmp_path, "ticket-a")
    second = ApprovalRun(
        "ticket-b",
        _metadata(),
        [
            _section("revenue", REVENUE),
            _section("clinical", CLINICAL),
            _section("compliance", COMPLIANCE),
        ],
        {"ticket_id": "ticket-b", "response_complete": True, "currency": "USD", "covered_population": "800 employees"},
        [],
        tmp_path / "approvals.sqlite",
        _complete,
    )
    first.start()
    second.start()
    _approve(first, "revenue")
    assert department_interrupted(tmp_path / "approvals.sqlite", "ticket-b", "revenue")


def test_invalid_decision_does_not_resume(tmp_path: Path) -> None:
    run = _run(tmp_path)
    run.start()
    with pytest.raises(ApprovalFlowError) as caught:
        run.decide(
            "revenue",
            actor_department_id="revenue",
            submitted_by_user_id="user-revenue",
            approver_name="Tom Callahan",
            decision="hold",
            note=None,
        )
    assert caught.value.code == "invalid_decision"
    assert department_interrupted(tmp_path / "approvals.sqlite", "ticket-a", "revenue")


def test_approval_note_keeps_operational_text_and_drops_a_labeled_field(tmp_path: Path) -> None:
    """The checkpoint, trace, and revision prompt keep the commentary and drop the labeled field."""
    seen: list[str] = []

    def complete(messages: list[dict[str, str]]) -> str:
        seen.append(messages[-1]["content"])
        return _complete(messages)

    run = _run(tmp_path, "ticket-note")
    run.complete_fn = complete
    run.start()
    note = "Keep the twelve month term. patient: AUDIT-NOTE-1"
    run.decide(
        "revenue",
        actor_department_id="revenue",
        submitted_by_user_id="user-revenue",
        approver_name="Tom Callahan",
        decision="request_changes",
        note=note,
    )
    blob = (tmp_path / "approvals.sqlite").read_bytes()
    rendered = "\n".join(seen) + "\n" + str(run.trace)
    assert b"AUDIT-NOTE-1" not in blob
    assert "AUDIT-NOTE-1" not in rendered
    assert "Keep the twelve month term." in rendered


def test_iteration_limit_blocks_another_revision_and_still_allows_a_clean_approval(tmp_path: Path) -> None:
    calls = {"count": 0}

    def complete(messages: list[dict[str, str]]) -> str:
        calls["count"] += 1
        return _complete(messages)

    run = _run(tmp_path)
    run.complete_fn = complete
    run.start()
    for _ in range(MAX_ATTEMPTS):
        run.decide(
            "clinical",
            actor_department_id="clinical",
            submitted_by_user_id="user-clinical",
            approver_name="Dr. Marcus Reid",
            decision="request_changes",
            note="State the clinic schedule already on the ticket.",
        )
    assert run.section("clinical")["approval_revision_count"] == MAX_ATTEMPTS
    assert run.section("clinical")["iteration_limit_reached"] is True
    calls_at_limit = calls["count"]
    with pytest.raises(ApprovalFlowError) as caught:
        run.decide(
            "clinical",
            actor_department_id="clinical",
            submitted_by_user_id="user-clinical",
            approver_name="Dr. Marcus Reid",
            decision="request_changes",
            note="One more revision.",
        )
    assert caught.value.code == "iteration_limit_reached"
    assert calls["count"] == calls_at_limit
    run.section("clinical")["evaluation_results"] = {"contains_phi": True, "overall_pass": False}
    with pytest.raises(ApprovalFlowError) as blocked:
        _approve(run, "clinical")
    assert blocked.value.code == "approval_checks_failed"
    assert department_interrupted(tmp_path / "approvals.sqlite", "ticket-a", "clinical")
    run.section("clinical")["evaluation_results"] = {"contains_phi": False, "overall_pass": True}
    _approve(run, "clinical")
    assert run.section("clinical")["approval_status"] == "approved"


def test_other_account_does_not_resume_the_branch(tmp_path: Path) -> None:
    run = _run(tmp_path)
    run.start()
    with pytest.raises(ApprovalFlowError) as caught:
        run.decide(
            "revenue",
            actor_department_id="clinical",
            submitted_by_user_id="user-clinical",
            approver_name="Dr. Marcus Reid",
            decision="approve",
            note=None,
        )
    assert caught.value.code == "not_department_owner"
    assert run.section("revenue")["approver"] is None
    assert department_interrupted(tmp_path / "approvals.sqlite", "ticket-a", "revenue")


def test_changed_draft_clears_only_that_approval(tmp_path: Path) -> None:
    run = _run(tmp_path)
    run.start()
    _approve(run, "revenue")
    _approve(run, "clinical")
    run.decide(
        "compliance",
        actor_department_id="compliance",
        submitted_by_user_id="user-compliance",
        approver_name="Claire Whitfield",
        decision="request_changes",
        note="Keep the Business Associate Agreement clause.",
    )
    assert run.section("revenue")["approval_status"] == "approved"
    assert run.section("compliance")["approval_status"] != "approved"
    assert run.final_document is None
    _approve(run, "compliance")
    assert run.final_document is not None
    assert run.final_document["currency"] == "USD"
    assert [section["department_id"] for section in run.final_document["sections"]] == [
        "revenue",
        "clinical",
        "compliance",
    ]
