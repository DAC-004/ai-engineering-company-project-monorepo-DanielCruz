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


def test_revenue_payload_keeps_stated_population_category() -> None:
    captured: dict[str, object] = {}

    def complete(messages: list[dict[str, str]]) -> str:
        captured["payload"] = json.loads(messages[1]["content"])
        return (
            "Pricing is quoted in USD for this occupational health program. "
            "Covered population is employees in the United States. Numeric headcount was not stated. "
            "Budget was not stated, so this draft does not assume a price. "
            "The contract term aspect from the handoff is twelve months. "
            "Assumptions are limited to the stated currency and population category. "
            "Exclusions include any figure that was not supplied in the request. "
            "Information still required before a final quotation includes budget range. "
            "This section stays within the revenue scope and does not address clinical staffing."
        )

    generate_revenue_section(
        {
            "client_name": "Northbridge Community Services",
            "client_country": "US",
            "covered_population": "Employees in the United States",
            "budget_range": None,
        },
        {"aspects": ["No prices or discounts have been agreed."], "open_questions": []},
        complete,
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    metadata = payload["metadata"]
    assert metadata["covered_population"] == "Employees in the United States"
    assert "missing_population_instruction" not in metadata
    assert "Employees in the United States" in metadata["population_instruction"]
    assert "Do not write that covered population was not stated" in metadata["population_instruction"]


def test_compliance_payload_does_not_ask_to_quote_baa_in_usd() -> None:
    captured: dict[str, object] = {}

    def complete(messages: list[dict[str, str]]) -> str:
        captured["payload"] = json.loads(messages[1]["content"])
        return (
            "A Business Associate Agreement is required before PHI exchange for this US client. "
            "Consent requirements remain to be confirmed with the client. "
            "Workforce training remains an item to confirm rather than a completed measure. "
            "This section does not quote the BAA in USD and does not mention UK GDPR. "
            "Additional sentences keep the compliance draft inside the stated country rule "
            "and long enough for the readability floor while remaining faithful to the handoff."
        )

    generate_compliance_section(
        {"client_name": "Northbridge Community Services", "client_country": "US"},
        {"aspects": ["Explain contractual requirements (e.g., Business Associate Agreement)"], "open_questions": []},
        complete,
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    requirement = payload["metadata"]["country_requirement"]
    assert "Business Associate Agreement" in requirement
    assert "quoted" not in requirement.casefold() or "do not describe" in requirement.casefold()
    assert "quote in USD and include a Business Associate Agreement" not in requirement
