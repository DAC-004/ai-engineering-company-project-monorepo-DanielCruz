"""Classifier agent tests. The stub proves input boundaries, not a live model."""

from __future__ import annotations

from data.pipelines.rfp_intake.agents import CLASSIFIER_ROLE, classify_rfp


def test_classifier_sends_only_its_role_and_the_markdown() -> None:
    calls: list[list[dict[str, str]]] = []

    def complete(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        return '{"decision":"discard","reason_code":"not_healthcore_rfp"}'

    result = classify_rfp("MedFlow is offering an EHR system to HealthCore.", complete)

    assert result == {"decision": "discard", "reason_code": "not_healthcore_rfp"}
    assert calls[0][0]["content"] == CLASSIFIER_ROLE
    assert calls[0][1]["content"] == "MedFlow is offering an EHR system to HealthCore."
    assert "revenue worker" not in calls[0][0]["content"]


def test_classifier_results_stay_independent() -> None:
    def complete(messages: list[dict[str, str]]) -> str:
        document = messages[1]["content"]
        if "MedFlow" in document:
            return '{"decision":"discard","reason_code":"not_healthcore_rfp"}'
        return '{"decision":"accept","reason_code":"healthcore_rfp"}'

    accepted = classify_rfp("Meridian Manufacturing requests an occupational health proposal.", complete)
    discarded = classify_rfp("MedFlow wants to sell HealthCore an EHR.", complete)

    assert accepted["decision"] == "accept"
    assert discarded["decision"] == "discard"
