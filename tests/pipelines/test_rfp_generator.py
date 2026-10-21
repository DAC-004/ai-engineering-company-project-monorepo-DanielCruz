"""Revenue generator tests. The generator receives only its own handoff extract."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.generators import (
    CLINICAL_ROLE,
    COMPLIANCE_ROLE,
    REVENUE_ROLE,
    generate_clinical_section,
    generate_compliance_section,
    generate_revenue_section,
)


def test_revenue_generator_uses_its_aspects_and_does_not_invent_population() -> None:
    calls: list[list[dict[str, str]]] = []

    long_draft = (
        "Pricing is quoted in USD for this occupational health program. "
        "Covered population was not stated, so no headcount is assumed in this section. "
        "The contract term aspect from the handoff is twelve months. "
        "Budget was not stated, so this draft does not invent a price, discount, or payment schedule. "
        "Assumptions are limited to the stated currency and term. "
        "Exclusions include any figure that was not supplied in the request. "
        "Information still required before a final quotation includes budget range, "
        "billing contact, invoice cadence, and any site-specific commercial constraints. "
        "This section stays within the revenue scope and does not address clinical staffing."
    )

    def complete(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        return long_draft

    section = generate_revenue_section(
        {
            "client_name": "Meridian Manufacturing",
            "client_country": "US",
            "program_type": "occupational health",
            "covered_population": None,
            "budget_range": None,
            "clinical_only": "CLINICAL-ONLY-SENTINEL",
        },
        {"aspects": ["Contract term is twelve months."], "open_questions": ["Budget was not stated."]},
        complete,
    )

    assert calls[0][0]["content"] == REVENUE_ROLE
    payload = json.loads(calls[0][1]["content"])
    assert payload["department_id"] == "revenue"
    assert payload["contact_name"] == "Tom Callahan"
    assert payload["key_aspects"]["aspects"] == ["Contract term is twelve months."]
    assert payload["metadata"]["covered_population"] is None
    assert "Do not invent a headcount" in payload["metadata"]["missing_population_instruction"]
    assert "CLINICAL-ONLY-SENTINEL" not in calls[0][1]["content"]
    assert "synthesizer_summary" not in calls[0][1]["content"]
    assert section == long_draft


def test_each_department_generator_receives_only_its_own_aspects() -> None:
    expected = {
        "revenue": "Contract term is twelve months.",
        "clinical": "Austin clinic capacity.",
        "compliance": "Business Associate Agreement clause.",
    }
    seen: dict[str, str] = {}

    def complete(messages: list[dict[str, str]]) -> str:
        # Continuation passes an assistant turn; only the first user payload is JSON.
        user_payload = messages[1]["content"]
        payload = json.loads(user_payload)
        department_id = payload["department_id"]
        if department_id not in seen:
            seen[department_id] = messages[0]["content"]
        assert payload["key_aspects"]["aspects"] == [expected[department_id]]
        for other_id, other_aspect in expected.items():
            if other_id != department_id:
                assert other_aspect not in user_payload
        # Return enough words so continuation, rewrite, and simplify passes do not run.
        return (
            f"{department_id} draft for Meridian Manufacturing covers the stated aspect. "
            "This paragraph stays inside the department scope and uses plain business sentences. "
            "It records open questions when a figure is missing and does not invent prices, "
            "staffing headcounts, signed agreements, or confirmed availability for the program. "
            "Additional sentences keep the section long enough for the readability floor while "
            "remaining faithful to the shared metadata already supplied in the handoff payload."
        )

    metadata = {"client_name": "Meridian Manufacturing", "client_country": "US", "covered_population": "800 employees"}
    generate_revenue_section(metadata, {"aspects": [expected["revenue"]], "open_questions": []}, complete)
    generate_clinical_section(metadata, {"aspects": [expected["clinical"]], "open_questions": []}, complete)
    generate_compliance_section(metadata, {"aspects": [expected["compliance"]], "open_questions": []}, complete)

    assert seen == {
        "revenue": REVENUE_ROLE,
        "clinical": CLINICAL_ROLE,
        "compliance": COMPLIANCE_ROLE,
    }
