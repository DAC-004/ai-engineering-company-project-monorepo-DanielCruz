"""Capacity, PHI, and BAA/DPA arbitration from stored handoff text."""

from __future__ import annotations

from pathlib import Path

import pytest

from data.pipelines.rfp_intake.approval_graph import ApprovalFlowError, ApprovalRun
from data.pipelines.rfp_intake.arbitration import assess_capacity

REVENUE = "Pricing is quoted in USD for the occupational health program and the twelve month term."
COMPLIANCE = "The compliance section includes a Business Associate Agreement clause for this US client."
UK_COMPLIANCE = (
    "The compliance section includes a Data Processing Agreement clause that references UK GDPR."
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


def _run(
    tmp_path: Path,
    *,
    population: str | None,
    clinical: str,
    compliance: str = COMPLIANCE,
    country: str = "US",
    currency: str = "USD",
    revenue: str = REVENUE,
    contains_phi: bool = False,
    complete_fn=None,
) -> ApprovalRun:
    metadata = {
        "client_name": "Example Employer",
        "client_country": country,
        "program_type": "occupational health",
        "covered_population": population,
        "deadline": None,
        "budget_range": None,
        "departments_needed": ["revenue", "clinical", "compliance"],
    }

    def default_complete(messages: list[dict[str, str]]) -> str:
        system = messages[0]["content"]
        if "Revenue Cycle" in system:
            return revenue
        if "Clinical Operations" in system:
            return clinical
        return compliance

    return ApprovalRun(
        "ticket-capacity",
        metadata,
        [
            _section("revenue", revenue),
            _section("clinical", clinical, contains_phi=contains_phi),
            _section("compliance", compliance),
        ],
        {
            "ticket_id": "ticket-capacity",
            "response_complete": True,
            "currency": currency,
            "covered_population": population,
        },
        [],
        tmp_path / "approvals.sqlite",
        complete_fn or default_complete,
        phi_detected=contains_phi,
    )


def test_capacity_record_uses_only_the_stored_counts() -> None:
    questions, conflict = assess_capacity(
        "800 employees",
        "The clinics cover 400 employees.",
        None,
    )
    assert questions == []
    assert conflict is not None
    assert conflict["population"]["count"] == 800
    assert conflict["coverage"]["count"] == 400
    assert conflict["population"]["unit"] == "employees"
    assert "400 employees" in conflict["coverage"]["source_text"]


def test_days_per_week_and_missing_population_do_not_fire() -> None:
    questions, conflict = assess_capacity("800 employees", "The clinic is staffed 3 days per week.", None)
    assert conflict is None
    assert "Clinical Operations did not state a committed coverage figure." in questions
    missing_population, missing_conflict = assess_capacity(None, "The clinics cover 10 employees.", None)
    assert missing_conflict is None
    assert "Covered population was not stated." in missing_population


def test_reduce_copies_the_extracted_coverage_figure(tmp_path: Path) -> None:
    run = _run(tmp_path, population="800 employees", clinical="The clinics cover 400 employees.")
    run.start()
    conflict = run.arbitration["capacity"]
    assert conflict["population"]["count"] == 800
    assert conflict["coverage"]["count"] == 400
    run.resolve_capacity(actor_department_id="revenue", resolution="reduce_covered_population")
    assert run.metadata["covered_population"].startswith("400 employees")
    assert run.section("revenue")["approval_revision_count"] == 1
    assert run.section("clinical")["approval_revision_count"] == 0
    assert run.arbitration["capacity"]["resolved"] is True
    assert run.arbitration["capacity"]["population"]["count"] == 800
    assert run.final_document is None


def test_add_sites_does_not_clear_a_conflict_when_the_coverage_sentence_disappears(tmp_path: Path) -> None:
    drafts = {
        "clinical": "Additional sites will be considered for the occupational health program.",
    }

    def complete(messages: list[dict[str, str]]) -> str:
        system = messages[0]["content"]
        if "Clinical Operations" in system:
            return drafts["clinical"]
        if "Revenue Cycle" in system:
            return REVENUE
        return COMPLIANCE

    run = _run(
        tmp_path,
        population="800 employees",
        clinical="The clinics cover 400 employees.",
        complete_fn=complete,
    )
    run.start()
    run.resolve_capacity(actor_department_id="revenue", resolution="add_sites")
    assert run.section("clinical")["approval_revision_count"] == 1
    assert run.section("revenue")["approval_revision_count"] == 0
    assert "400" not in run.section("clinical")["draft_content"]
    kept = run.arbitration["capacity"]
    assert kept["resolved"] is False
    assert kept["population"]["count"] == 800
    assert kept["coverage"]["count"] == 400
    with pytest.raises(ApprovalFlowError) as caught:
        run.decide(
            "clinical",
            actor_department_id="clinical",
            submitted_by_user_id="user-clinical",
            approver_name="Dr. Marcus Reid",
            decision="approve",
            note=None,
        )
    assert caught.value.code == "arbitration_unresolved"
    assert run.final_document is None
    drafts["clinical"] = "The clinics cover 800 employees for the occupational health program."
    run.decide(
        "clinical",
        actor_department_id="clinical",
        submitted_by_user_id="user-clinical",
        approver_name="Dr. Marcus Reid",
        decision="request_changes",
        note="State coverage for the population already on the ticket.",
    )
    assert run.arbitration["capacity"]["resolved"] is True
    assert run.arbitration["capacity"]["coverage"]["count"] == 400


def test_phi_blocks_capacity_and_approval(tmp_path: Path) -> None:
    run = _run(
        tmp_path,
        population="800 employees",
        clinical="The clinics cover 400 employees.",
        contains_phi=True,
    )
    run.start()
    assert run.arbitration["phi_detected"] is True
    assert run.arbitration["capacity"] is None
    with pytest.raises(ApprovalFlowError) as choice:
        run.resolve_capacity(actor_department_id="revenue", resolution="add_sites")
    assert choice.value.code == "resolution_not_open"
    with pytest.raises(ApprovalFlowError) as approval:
        run.decide(
            "compliance",
            actor_department_id="compliance",
            submitted_by_user_id="user-compliance",
            approver_name="Claire Whitfield",
            decision="approve",
            note=None,
        )
    assert approval.value.code == "approval_checks_failed"
    assert run.final_document is None


def test_non_revenue_account_cannot_choose(tmp_path: Path) -> None:
    run = _run(tmp_path, population="800 employees", clinical="The clinics cover 400 employees.")
    run.start()
    with pytest.raises(ApprovalFlowError) as caught:
        run.resolve_capacity(actor_department_id="clinical", resolution="reduce_covered_population")
    assert caught.value.code == "not_capacity_arbiter"


def test_uk_mismatch_targets_compliance(tmp_path: Path) -> None:
    run = _run(
        tmp_path,
        population="3000 students",
        clinical="The satellite clinic supports the referral program.",
        compliance="The draft mentions a Business Associate Agreement only.",
        country="UK",
        currency="GBP",
        revenue="Pricing is quoted in GBP for the referral program.",
    )
    run.start()
    assert run.arbitration["baa_dpa_mismatch"] is True
    assert "compliance" in run.arbitration["baa_targets"]
    assert run.section("compliance")["approval_revision_count"] == 1
    assert run.arbitration["capacity"] is None


def test_stale_baa_target_does_not_block_a_clean_approval(tmp_path: Path) -> None:
    run = _run(
        tmp_path,
        population="800 employees",
        clinical="The on-site clinic is staffed 3 days/week.",
    )
    run.start()
    run.arbitration = {
        "phi_detected": False,
        "baa_dpa_mismatch": True,
        "baa_targets": ["compliance"],
        "capacity": None,
        "open_questions": [],
    }
    run.decide(
        "compliance",
        actor_department_id="compliance",
        submitted_by_user_id="user-compliance",
        approver_name="Claire Whitfield",
        decision="approve",
        note=None,
    )
    assert run.section("compliance")["approval_status"] == "approved"
    assert run.arbitration["baa_dpa_mismatch"] is False


def test_us_rejection_of_uk_gdpr_does_not_open_a_mismatch(tmp_path: Path) -> None:
    run = _run(
        tmp_path,
        population="800 employees",
        clinical="The on-site clinic is staffed 3 days/week.",
        compliance=(
            "Meridian Manufacturing, Inc. requires a Business Associate Agreement, "
            "not a Data Processing Agreement related to UK GDPR."
        ),
    )
    run.start()
    assert run.arbitration["baa_dpa_mismatch"] is False
    assert run.arbitration["baa_targets"] == []
    assert run.section("compliance")["approval_revision_count"] == 0
