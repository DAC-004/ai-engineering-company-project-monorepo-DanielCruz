"""Regression checks for ungrounded department claims and false disagreements."""

from __future__ import annotations

import json
import threading

from data.pipelines.rfp_intake.agents import analyze_department, synthesize_findings
from data.pipelines.rfp_intake.generation import _local_llm_lock
from data.pipelines.rfp_intake.graph import build_intake_graph
from data.pipelines.rfp_intake.grounding import apply_source_grounding
from data.pipelines.rfp_intake.readability import readability_metrics


def test_revenue_worker_drops_clinic_staffing_assigned_to_revenue() -> None:
    def complete(_messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "aspects": [
                    "The revenue cycle is staffed 3 days/week.",
                    "No budget amount is stated.",
                ],
                "open_questions": ["Budget was not stated."],
            }
        )

    section = analyze_department(
        "revenue",
        {"client_name": "Meridian Manufacturing, Inc.", "budget_range": None},
        "On-site clinic staffed 3 days/week. No budget amount is stated.",
        complete,
    )

    assert section["contact_name"] == "Tom Callahan"
    assert "3 days/week" not in " ".join(section["aspects"])
    assert "No budget amount is stated." in section["aspects"]
    assert "Budget was not stated." in section["open_questions"]


def test_missing_budget_is_not_labeled_as_a_disagreement() -> None:
    def complete(_messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "summary": "Ask Tom Callahan for the budget.",
                "unresolved_disagreements": [
                    "The budget range is missing from the metadata.",
                    "Is there a specific budget allocated for this program?",
                ],
            }
        )

    result = synthesize_findings(
        {"client_country": "US", "budget_range": None},
        [
            {
                "department_id": "revenue",
                "department_name": "Revenue Cycle",
                "contact_name": "Tom Callahan",
                "aspects": ["No budget amount is stated."],
                "open_questions": ["Budget was not stated."],
            }
        ],
        complete,
    )

    assert "Unresolved disagreement" not in result["summary"]
    assert result["unresolved_disagreements"] == []
    assert "USD" in result["summary"]


def test_conflicting_figures_remain_an_unresolved_disagreement() -> None:
    def complete(_messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "summary": "The worker findings do not match.",
                "unresolved_disagreements": ["Revenue states 10 employees but clinical states 50 employees."],
            }
        )

    result = synthesize_findings(
        {"client_country": "UK"},
        [],
        complete,
    )

    assert result["unresolved_disagreements"] == [
        "Revenue states 10 employees but clinical states 50 employees."
    ]
    assert "Unresolved disagreement:" in result["summary"]


def test_summary_drops_revenue_staffing_the_revenue_section_did_not_state() -> None:
    def complete(_messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "summary": (
                    "Ask Tom Callahan about the budget. "
                    "The revenue cycle is staffed 3 days/week."
                ),
                "unresolved_disagreements": [],
            }
        )

    result = synthesize_findings(
        {"client_country": "US"},
        [
            {
                "department_id": "revenue",
                "department_name": "Revenue Cycle",
                "aspects": ["No budget amount is stated."],
                "open_questions": ["Budget was not stated."],
            }
        ],
        complete,
    )

    assert "3 days/week" not in result["summary"]
    assert "budget" in result["summary"].lower()


def test_short_text_records_why_no_grade_was_calculated() -> None:
    metrics = readability_metrics("Too short to score.")

    assert metrics["flesch_kincaid_grade"] is None
    assert metrics["gunning_fog"] is None
    assert metrics["unavailable_reason"] == (
        "fewer than 100 words; py-readability-metrics did not return a grade"
    )


def test_clinic_schedule_stays_on_clinical_and_revenue_staffing_question_is_removed() -> None:
    source = (
        "On-site occupational health clinic staffed 3 days/week. "
        "Annual wellness screenings for all 800 employees. "
        "Proposal Due Date: August 23, 2026."
    )
    metadata, sections, summary = apply_source_grounding(
        source,
        {"deadline": "August 23, 2026", "budget_range": None},
        [
            {
                "department_id": "clinical",
                "department_name": "Clinical Operations",
                "aspects": ["Annual wellness screenings are required for all employees."],
                "open_questions": [
                    "Is there a specific staffing requirement for the revenue department?",
                    "How many days per week is the clinic staffed?",
                ],
            },
            {
                "department_id": "revenue",
                "department_name": "Revenue Cycle",
                "aspects": [
                    "The revenue cycle is staffed 3 days/week.",
                    "Clinical staff not mentioned, but assumed to be staffed",
                    "No budget amount is stated.",
                ],
                "open_questions": ["Is there a specific budget allocated?"],
            },
        ],
        (
            "Open questions include the specific staffing requirement for the revenue department, "
            "the specific vendor required. "
            "The open question regarding the budget remains unresolved."
        ),
    )
    clinical = next(section for section in sections if section["department_id"] == "clinical")
    revenue = next(section for section in sections if section["department_id"] == "revenue")
    clinical_text = " ".join(clinical["aspects"]).lower()

    assert "clinic" in clinical_text
    assert "3 days/week" in clinical_text
    assert clinical["open_questions"] == []
    assert "assumed to be staffed" not in " ".join(revenue["aspects"]).lower()
    assert "3 days/week" not in " ".join(revenue["aspects"])
    assert "No budget amount is stated." in revenue["aspects"]
    assert "staffing requirement for the revenue" not in summary.lower()
    assert "remains unresolved" in summary
    assert metadata["deadline"] == "August 23, 2026"


def test_equivalent_clinic_paraphrase_is_not_duplicated() -> None:
    _metadata, sections, _summary = apply_source_grounding(
        "On-site occupational health clinic staffed 3 days/week.",
        {},
        [
            {
                "department_id": "clinical",
                "aspects": ["The on-site clinic is staffed 3 days a week."],
                "open_questions": [],
            }
        ],
        "",
    )

    assert sections[0]["aspects"] == ["The on-site clinic is staffed 3 days a week."]


def test_both_deadline_qualifiers_are_kept_without_a_year_or_reasonable() -> None:
    source = "We need this running in about 25 days if possible, around August 28th. No budget is stated."
    metadata, sections, summary = apply_source_grounding(
        source,
        {"deadline": "August 28, 2026"},
        [
            {
                "department_id": "revenue",
                "aspects": [
                    "The deadline is about 25 days, which is a reasonable timeframe for a proposal to be completed and submitted."
                ],
                "open_questions": ["Is there a specific budget or payment terms for this proposal?"],
            }
        ],
        (
            "The deadline is set at about 25 days, which is reasonable for proposal completion. "
            "The open question regarding the budget remains unresolved.\n"
            "UK client: quote in GBP and include a Data Processing Agreement referencing UK GDPR."
        ),
    )
    deadline = metadata["deadline"] or ""
    stored = json.dumps({"deadline": deadline, "sections": sections, "summary": summary})

    assert "about 25 days" in deadline
    assert "around August 28" in deadline
    assert "2026" not in deadline
    assert "reasonable" not in stored.lower()
    assert "about 25 days" in stored
    assert "August 28" in stored
    assert "remains unresolved" in summary
    assert "GBP" in summary
    assert sections[0]["open_questions"] == [
        "Is there a specific budget or payment terms for this proposal?"
    ]


def test_missing_budget_question_is_added_when_the_worker_omits_it() -> None:
    _metadata, sections, _summary = apply_source_grounding(
        "No budget is stated. The proposal is needed in about 25 days, around August 28th.",
        {"budget_range": None, "deadline": "about 25 days"},
        [
            {
                "department_id": "revenue",
                "aspects": ["UK GDPR compliance for student health data"],
                "open_questions": ["Is there a specific deadline for GDPR compliance?"],
            }
        ],
        "Ask Claire Whitfield about UK GDPR.",
    )

    assert sections[0]["open_questions"][-1] == "Budget or payment terms were not stated."


def test_department_workers_stay_separate_while_model_access_is_locked() -> None:
    graph = build_intake_graph()
    node_names = set(graph.nodes)
    assert {"revenue_worker", "clinical_worker", "compliance_worker"} <= node_names
    assert isinstance(_local_llm_lock, type(threading.Lock()))
