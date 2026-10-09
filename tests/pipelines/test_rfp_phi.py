"""PHI screening tests. These do not prove a PostgreSQL read-back."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.agents import analyze_department
from data.pipelines.rfp_intake.handoff import build_handoff
from data.pipelines.rfp_intake.node_trace import append_trace
from data.pipelines.rfp_intake.phi import screen_structure, screen_text
from data.pipelines.rfp_intake.response_loop import run_response_generation
from tests.pipelines.test_rfp_evaluator import PASSING_DRAFT


def test_labeled_patient_fields_are_redacted() -> None:
    source = "Clinical case summary\nPatient name: Alex Example\nDiagnosis: example condition\n"
    screened = screen_text(source)

    assert screened.detected is True
    assert "Alex Example" not in screened.text
    assert "example condition" not in screened.text
    assert "[redacted]" in screened.text


def test_workforce_condition_list_without_a_patient_label_is_not_phi() -> None:
    source = "Chronic condition management support (diabetes, hypertension) for all 800 employees."
    screened = screen_text(source)

    assert screened.detected is False
    assert screened.text == source


def test_output_screen_removes_patient_text_before_a_payload_is_saved() -> None:
    generated = {
        "summary": "Ask Claire Whitfield about the BAA. Patient name: Alex Example. Diagnosis: example condition.",
        "aspects": ["Ask Claire Whitfield about the BAA."],
    }
    screened, detected, _blocked = screen_structure(generated)

    assert detected is True
    assert isinstance(screened, dict)
    assert "Alex Example" not in screened["summary"]
    assert "example condition" not in screened["summary"]
    assert screened["aspects"] == ["Ask Claire Whitfield about the BAA."]


def test_stored_rfp_text_omits_a_labeled_patient_field() -> None:
    """draft_content, sections, key aspects, and the node trace keep the screened copy."""
    labeled = "Patient name: Alex Example. Diagnosis: example condition."
    prose = "The patient named Alex Example was diagnosed with an example condition."

    def complete(messages: list[dict[str, str]]) -> str:
        if messages[0]["content"].startswith("{"):
            return PASSING_DRAFT
        return json.dumps(
            {
                "aspects": [prose],
                "open_questions": [labeled],
            }
        )

    section = analyze_department(
        "revenue",
        {"client_name": "Meridian Manufacturing", "client_country": "US"},
        prose,
        complete,
    )
    handoff = build_handoff(
        ticket_id="ticket-phi",
        metadata={"client_name": "Meridian Manufacturing", "client_country": "US", "covered_population": "800 employees"},
        readability={"flesch_kincaid_grade": 13.0, "gunning_fog": None},
        sections=[section],
        summary="Ask Tom Callahan about the commercial term.",
        phi_detected=False,
        compliance_review_required=False,
    )
    # The worker above is revenue only. The response loop expects three departments.
    stored_aspects = json.dumps(handoff["sections"])
    assert "Alex Example" not in stored_aspects
    assert "example condition" not in stored_aspects

    def draft_complete(messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[-1]["content"])
        if payload["department_id"] == "revenue":
            return f"{PASSING_DRAFT}\n{labeled}"
        if payload["department_id"] == "clinical":
            return f"{PASSING_DRAFT} Austin clinic capacity covers the stated workforce."
        return (
            f"{PASSING_DRAFT} The compliance section includes a Business Associate "
            "Agreement clause for this US client."
        )

    trace: list[dict[str, object]] = []
    generated = run_response_generation(
        {
            "ticket_id": "ticket-phi",
            "metadata": {
                "client_name": "Meridian Manufacturing",
                "client_country": "US",
                "covered_population": "800 employees",
            },
            "sections": [
                {"department_id": "revenue", "key_aspects": {"aspects": ["Contract term is twelve months."], "open_questions": []}},
                {"department_id": "clinical", "key_aspects": {"aspects": ["Austin clinic capacity."], "open_questions": []}},
                {
                    "department_id": "compliance",
                    "key_aspects": {"aspects": ["Business Associate Agreement clause."], "open_questions": []},
                },
            ],
        },
        draft_complete,
        on_node=lambda event: append_trace(
            trace,
            str(event["node"]),
            str(event["agent"]),
            event.get("input"),
            event.get("output"),
        ),
    )
    rendered = json.dumps({"handoff": generated, "trace": trace})
    assert "Alex Example" not in rendered
    assert "example condition" not in rendered
    assert any(section["draft_content"] for section in generated["sections"])
