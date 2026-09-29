"""Revenue worker tests. The worker must not receive the rest of the document."""

from __future__ import annotations

import json

from data.pipelines.rfp_intake.agents import WORKER_ROLES, analyze_department


def test_revenue_worker_receives_its_extract_and_records_a_missing_budget() -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        return json.dumps(
            {
                "aspects": ["The term is 12 months."],
                "open_questions": ["Budget was not stated."],
            }
        )

    metadata = {
        "client_name": "Meridian Manufacturing, Inc.",
        "client_country": "US",
        "budget_range": None,
    }
    section = analyze_department(
        "revenue",
        metadata,
        "12-month term. No budget amount is stated.",
        complete,
    )

    assert calls[0][0]["content"] == WORKER_ROLES["revenue"]
    user_payload = json.loads(calls[0][1]["content"])
    assert user_payload["extract"] == "12-month term. No budget amount is stated."
    assert "FULL-DOCUMENT-SENTINEL" not in calls[0][1]["content"]
    assert section["contact_name"] == "Tom Callahan"
    assert section["open_questions"] == ["Budget was not stated."]
    assert section["aspects"] == ["The term is 12 months."]


def test_clinical_worker_does_not_see_the_revenue_extract() -> None:
    def complete(messages: list[dict[str, str]]) -> str:
        body = messages[1]["content"]
        assert "No budget amount" not in body
        assert "about 3,000" in body
        return json.dumps({"aspects": ["Satellite clinic request."], "open_questions": []})

    section = analyze_department(
        "clinical",
        {"client_country": "UK", "covered_population": "about 3,000 main-campus students"},
        "about 3,000 main-campus students and a satellite clinic.",
        complete,
    )

    assert section["contact_name"] == "Dr. Marcus Reid"
    assert section["aspects"] == ["Satellite clinic request."]
