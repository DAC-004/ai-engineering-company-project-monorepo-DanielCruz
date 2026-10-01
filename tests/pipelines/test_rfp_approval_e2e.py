"""Stubbed Part 1 through Part 3 path with a screened node trace.

This does not replace the live UI upload recorded in docs/rfp/part3-testing.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from data.pipelines.rfp_intake.approval_graph import ApprovalRun
from data.pipelines.rfp_intake.graph import run_intake_graph
from data.pipelines.rfp_intake.handoff import build_handoff
from data.pipelines.rfp_intake.node_trace import append_trace
from data.pipelines.rfp_intake.response_loop import run_response_generation

MARKDOWN = """
Meridian Manufacturing, Inc. is in Austin, United States.
The request is an on-site occupational health and corporate wellness program.
Covered population: 800 employees.
Deadline: August 23, 2026.
The contract term is 12 months.
"""

REVENUE = (
    "Pricing is quoted in USD for the occupational health program. "
    "Payment follows the twelve month contract already stated."
)
CLINICAL = (
    "Clinical Operations can staff the occupational health program. "
    "The covered population was stated as 800 employees."
)
COMPLIANCE = (
    "The compliance section includes a Business Associate Agreement clause for this United States client."
)


def _complete(messages: list[dict[str, str]]) -> str:
    system = messages[0]["content"]
    if "classifier agent" in system:
        return json.dumps({"decision": "accept", "reason_code": "healthcore_rfp"})
    if "orchestrator agent" in system:
        return json.dumps(
            {
                "client_name": "Meridian Manufacturing, Inc.",
                "client_country": "US",
                "program_type": "on-site occupational health and corporate wellness",
                "covered_population": "800 employees",
                "deadline": "August 23, 2026",
                "budget_range": None,
                "unknown_departments": [],
                "extracts": {
                    "revenue": "800 employees and a 12 month contract.",
                    "clinical": "on-site occupational health program.",
                    "compliance": "United States client.",
                },
            }
        )
    if "worker agent" in system:
        return json.dumps(
            {
                "aspects": ["on-site occupational health program"],
                "open_questions": [],
            }
        )
    if "synthesizer agent" in system:
        return json.dumps(
            {
                "summary": "Meridian Manufacturing requested an occupational health program for 800 employees.",
                "unresolved_disagreements": [],
            }
        )
    if "Revenue Cycle" in system:
        return REVENUE
    if "Clinical Operations" in system:
        return CLINICAL
    return COMPLIANCE


def _approve(run: ApprovalRun, department_id: str, approver: str) -> None:
    run.decide(
        department_id,
        actor_department_id=department_id,
        submitted_by_user_id=f"user-{department_id}",
        approver_name=approver,
        decision="approve",
        note=None,
    )


def test_part1_through_part3_trace_keeps_order_and_redacts(tmp_path: Path) -> None:
    state = run_intake_graph(MARKDOWN, _complete)
    assert state["classification"]["decision"] == "accept"
    trace = list(state["node_trace"])
    handoff = build_handoff(
        ticket_id="ticket-e2e",
        metadata=state["metadata"],
        readability={"flesch_kincaid_grade": 13.0, "gunning_fog": None},
        sections=state["worker_results"],
        summary=state["summary"],
        phi_detected=False,
        compliance_review_required=False,
    )
    part3 = run_response_generation(
        handoff,
        _complete,
        on_node=lambda event: append_trace(
            trace,
            str(event["node"]),
            str(event["agent"]),
            event.get("input"),
            event.get("output"),
        ),
    )
    sections = []
    for item in part3["sections"]:
        sections.append(
            {
                "department_id": item["department_id"],
                "draft_content": item["draft_content"],
                "evaluation_results": item["evaluation_results"],
                "key_aspects": {"aspects": [], "open_questions": []},
                "needs_human_review": item["needs_human_review"],
                "approval_status": None,
                "approver": None,
                "approved_at": None,
                "approved_content_sha256": None,
                "submitted_by_user_id": None,
                "approval_revision_count": 0,
                "iteration_limit_reached": False,
            }
        )
    metadata = dict(state["metadata"])
    run = ApprovalRun(
        "ticket-e2e",
        metadata,
        sections,
        part3,
        trace,
        tmp_path / "approvals.sqlite",
        _complete,
        phi_detected=False,
    )
    run.start()
    _approve(run, "clinical", "Dr. Marcus Reid")
    _approve(run, "revenue", "Tom Callahan")
    _approve(run, "compliance", "Claire Whitfield")
    append_trace(trace, "screen_probe", "compliance", {"text": "patient: REDACTME"}, {"text": "patient: REDACTME"})

    names = [record["node"] for record in trace]
    for node in (
        "classify",
        "orchestrate",
        "revenue_worker",
        "clinical_worker",
        "compliance_worker",
        "synthesize",
        "generate",
        "evaluate",
        "enter_part3",
        "clinical_await_approval",
        "revenue_await_approval",
        "compliance_await_approval",
        "validate_decision",
        "converge_eligibility",
        "synthesize_final_document",
        "persist_document_and_done",
    ):
        assert node in names
    for record in trace:
        assert {"sequence", "node", "agent", "input", "output", "timestamp"} <= set(record)
    sequences = [record["sequence"] for record in trace]
    assert sequences == sorted(sequences)

    def first_sequence(node: str, department_id: str | None = None) -> int:
        for record in trace:
            if record["node"] != node:
                continue
            if department_id is None:
                return record["sequence"]
            payload = record["input"]
            if isinstance(payload, dict) and payload.get("department_id") == department_id:
                return record["sequence"]
        raise AssertionError(node)

    assert first_sequence("clinical_await_approval") < first_sequence("validate_decision", "clinical")
    assert first_sequence("revenue_await_approval") < first_sequence("validate_decision", "revenue")
    clinical_validate = first_sequence("validate_decision", "clinical")
    revenue_validate = first_sequence("validate_decision", "revenue")
    assert clinical_validate < revenue_validate
    synthesize_at = first_sequence("synthesize_final_document")
    persist_at = first_sequence("persist_document_and_done")
    assert synthesize_at < persist_at
    assert persist_at > revenue_validate
    assert persist_at > clinical_validate
    rendered = json.dumps(trace)
    assert "REDACTME" not in rendered
    assert any(record.get("contains_phi") is True for record in trace)
    assert run.final_document is not None
    assert run.final_document["currency"] == "USD"
