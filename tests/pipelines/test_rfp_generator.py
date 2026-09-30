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

    def complete(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        return "Pricing is quoted in USD. Covered population was not stated."

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
    assert section == "Pricing is quoted in USD. Covered population was not stated."


def test_each_department_generator_receives_only_its_own_aspects() -> None:
    expected = {
        "revenue": "Contract term is twelve months.",
        "clinical": "Austin clinic capacity.",
        "compliance": "Business Associate Agreement clause.",
    }
    seen: dict[str, str] = {}

    def complete(messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[1]["content"])
        department_id = payload["department_id"]
        seen[department_id] = messages[0]["content"]
        assert payload["key_aspects"]["aspects"] == [expected[department_id]]
        for other_id, other_aspect in expected.items():
            if other_id != department_id:
                assert other_aspect not in messages[1]["content"]
        return department_id

    metadata = {"client_name": "Meridian Manufacturing", "client_country": "US", "covered_population": "800 employees"}
    generate_revenue_section(metadata, {"aspects": [expected["revenue"]], "open_questions": []}, complete)
    generate_clinical_section(metadata, {"aspects": [expected["clinical"]], "open_questions": []}, complete)
    generate_compliance_section(metadata, {"aspects": [expected["compliance"]], "open_questions": []}, complete)

    assert seen == {
        "revenue": REVENUE_ROLE,
        "clinical": CLINICAL_ROLE,
        "compliance": COMPLIANCE_ROLE,
    }
