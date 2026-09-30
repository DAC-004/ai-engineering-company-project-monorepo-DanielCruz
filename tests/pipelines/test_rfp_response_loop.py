"""The revision loop keeps a provisional section while other departments are still running."""

from __future__ import annotations

import json
import threading

from data.pipelines.rfp_intake.response_loop import run_response_generation
from tests.pipelines.test_rfp_evaluator import PASSING_DRAFT

COMPLIANCE_DRAFT = (
    PASSING_DRAFT
    + " The compliance section includes a Business Associate Agreement clause for this US client."
)
CLINICAL_DRAFT = PASSING_DRAFT + " Austin clinic capacity covers the stated workforce."


def test_exhausted_section_stays_visible_until_every_department_finishes() -> None:
    release_clinical = threading.Event()
    revenue_finished = threading.Event()
    finished: dict[str, dict] = {}
    revenue_saw_feedback: list[bool] = []

    def complete(messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[-1]["content"])
        department_id = payload["department_id"]
        if department_id == "revenue":
            revenue_saw_feedback.append("feedback_for_generator" in payload)
            return "This quote uses GBP."
        if department_id == "clinical":
            assert release_clinical.wait(timeout=5)
            return CLINICAL_DRAFT
        return COMPLIANCE_DRAFT

    def on_department_done(outcome: dict) -> None:
        finished[outcome["department_id"]] = outcome
        if outcome["department_id"] == "revenue":
            revenue_finished.set()

    handoff_input = {
        "ticket_id": "ticket-loop",
        "metadata": {
            "client_name": "Meridian Manufacturing",
            "client_country": "US",
            "covered_population": "800 employees",
            "budget_range": None,
        },
        "sections": [
            {"department_id": "revenue", "key_aspects": {"aspects": ["Contract term is twelve months."], "open_questions": []}},
            {"department_id": "clinical", "key_aspects": {"aspects": ["Austin clinic capacity."], "open_questions": []}},
            {
                "department_id": "compliance",
                "key_aspects": {"aspects": ["Business Associate Agreement clause."], "open_questions": []},
            },
        ],
    }
    holder: dict[str, dict] = {}

    def run() -> None:
        holder["handoff"] = run_response_generation(
            handoff_input,
            complete,
            on_department_done=on_department_done,
        )

    worker = threading.Thread(target=run)
    worker.start()
    assert revenue_finished.wait(timeout=5)
    assert "clinical" not in finished
    assert "handoff" not in holder
    assert finished["revenue"]["needs_human_review"] is True
    assert finished["revenue"]["attempt_count"] == 3
    release_clinical.set()
    worker.join(timeout=5)

    handoff = holder["handoff"]
    assert handoff["response_complete"] is True
    assert [section["department_id"] for section in handoff["sections"]] == [
        "revenue",
        "clinical",
        "compliance",
    ]
    revenue = handoff["sections"][0]
    assert revenue["needs_human_review"] is True
    assert revenue["provisional"] is True
    assert revenue["draft_content"]
    assert revenue["evaluation_results"]["overall_pass"] is False
    assert handoff["sections"][1]["needs_human_review"] is False
    assert handoff["sections"][2]["needs_human_review"] is False
    assert revenue_saw_feedback == [False, True, True]
    assert "Alex Example" not in json.dumps(handoff)
