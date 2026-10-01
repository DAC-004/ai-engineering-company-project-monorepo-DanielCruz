"""Evaluator tests for a passing section, a relevance miss, and a HealthCore rule failure."""

from __future__ import annotations

import json
import threading

from data.pipelines.rfp_intake.evaluators import (
    evaluate_compliance,
    evaluate_in_parallel,
    evaluate_readability,
    evaluate_relevance,
)
from data.pipelines.rfp_intake.phi import screen_generated

PASSING_DRAFT = """
HealthCore proposes a twelve month occupational health agreement for Meridian Manufacturing in Austin. Revenue Cycle will quote the commercial terms in USD. Payment is due monthly in arrears after each service month under the written schedule. The contract term is twelve months, and the client may review renewal only after that term ends. No separate budget figure was stated in the request, so the price remains an open question rather than an assumed amount. The covered workforce is the group described in the request, and this section does not add people beyond that description. Tom Callahan owns these financial terms for the proposal. The payment structure is a monthly invoice in USD, with no alternative currency. This language stays with the institutional client and the workforce program. It does not describe an individual clinical case. The section repeats the twelve month term so the commercial offer matches the request. HealthCore will confirm the invoice calendar with the client before release.
""".strip()


def test_revenue_section_passes_readability_relevance_and_compliance() -> None:
    result = evaluate_in_parallel(
        PASSING_DRAFT,
        ["Contract term is twelve months."],
        "revenue",
        {"client_country": "US", "client_name": "Meridian Manufacturing", "covered_population": "800 employees"},
    )

    assert result["department_id"] == "revenue"
    assert result["readability"]["pass"] is True
    assert result["readability"]["score"] == 9.0
    assert result["relevance"]["pass"] is True
    assert result["relevance"]["missing_aspects"] == []
    assert result["compliance"]["pass"] is True
    assert result["compliance"]["contains_phi"] is False
    assert result["overall_pass"] is True
    assert "passed readability" in result["feedback_for_generator"]


def test_relevance_fails_when_a_handoff_aspect_is_missing() -> None:
    result = evaluate_relevance(PASSING_DRAFT, ["Satellite clinic coverage for the campus."])

    assert result["pass"] is False
    assert result["missing_aspects"] == ["Satellite clinic coverage for the campus."]


def test_uk_compliance_requires_gbp_and_a_dpa_referencing_uk_gdpr() -> None:
    metadata = {"client_country": "UK", "covered_population": "students"}

    missing_clause = evaluate_compliance(
        "This UK proposal does not name the required instrument.",
        "compliance",
        metadata,
    )
    wrong_instrument = evaluate_compliance(
        "This UK proposal includes a Business Associate Agreement and quotes USD.",
        "compliance",
        metadata,
    )
    wrong_currency = evaluate_compliance("The price is stated in USD.", "revenue", metadata)
    revenue = evaluate_compliance("The price is stated in GBP.", "revenue", metadata)
    compliance = evaluate_compliance(
        "The compliance section includes a Data Processing Agreement referencing UK GDPR. The price is stated in GBP.",
        "compliance",
        metadata,
    )

    assert missing_clause["pass"] is False
    assert missing_clause["rule_ids"] == ["HC-UK-DPA"]
    assert wrong_instrument["pass"] is False
    assert "HC-UK-DPA" in wrong_instrument["rule_ids"]
    assert "HC-CURRENCY" in wrong_instrument["rule_ids"]
    assert wrong_currency["pass"] is False
    assert wrong_currency["rule_ids"] == ["HC-CURRENCY"]
    assert revenue["pass"] is True
    assert revenue["rule_ids"] == []
    assert compliance["pass"] is True
    assert compliance["contains_phi"] is False


def test_us_compliance_fails_when_gbp_replaces_the_baa_clause() -> None:
    draft = "This US proposal quotes GBP and does not include the required clause."
    result = evaluate_compliance(draft, "compliance", {"client_country": "US", "covered_population": "800 employees"})

    assert result["pass"] is False
    assert "HC-US-BAA" in result["rule_ids"]
    assert "HC-CURRENCY" in result["rule_ids"]


def test_us_compliance_allows_a_sentence_that_rejects_uk_gdpr() -> None:
    rejected = evaluate_compliance(
        "Meridian Manufacturing, Inc. requires a Business Associate Agreement, not a Data Processing Agreement related to UK GDPR.",
        "compliance",
        {"client_country": "US", "covered_population": "800 employees"},
    )
    adopted = evaluate_compliance(
        "The compliance section uses a Business Associate Agreement and also applies UK GDPR.",
        "compliance",
        {"client_country": "US", "covered_population": "800 employees"},
    )

    assert rejected["pass"] is True
    assert rejected["rule_ids"] == []
    assert adopted["pass"] is False
    assert "HC-US-BAA" in adopted["rule_ids"]


def test_missing_population_rejects_an_invented_headcount() -> None:
    result = evaluate_compliance(
        "The program covers 800 employees.",
        "clinical",
        {"client_country": "US", "covered_population": None},
    )

    assert result["pass"] is False
    assert "HC-NO-INVENTED-VOLUME" in result["rule_ids"]


def test_unlabeled_patient_prose_sets_contains_phi_and_redacts_stored_text() -> None:
    original = (
        "The patient named Alex Example was diagnosed with an example condition. "
        + PASSING_DRAFT
    )
    result = evaluate_in_parallel(
        original,
        ["Contract term is twelve months."],
        "revenue",
        {"client_country": "US", "covered_population": "800 employees"},
        allowed_names=("Meridian Manufacturing",),
    )
    stored = json.dumps(result)
    rescreened = screen_generated(stored)

    assert result["contains_phi"] is True
    assert result["compliance"]["contains_phi"] is True
    assert result["compliance"]["pass"] is False
    assert "HC-NO-PHI" in result["compliance"]["rule_ids"]
    assert "Alex Example" not in stored
    assert "example condition" not in stored
    assert rescreened.detected is False
    assert result["contains_phi"] is True


def test_workforce_condition_list_is_not_phi() -> None:
    result = evaluate_compliance(
        "Chronic condition management support (diabetes, hypertension) for the covered workforce.",
        "clinical",
        {"client_country": "US", "covered_population": "800 employees"},
    )

    assert result["contains_phi"] is False


def test_evaluators_enter_together() -> None:
    import data.pipelines.rfp_intake.evaluators as evaluators

    barrier = threading.Barrier(3)
    originals = (
        evaluators.evaluate_readability,
        evaluators.evaluate_relevance,
        evaluators.evaluate_compliance,
    )

    def wrap(function):
        def wrapped(*args, **kwargs):
            barrier.wait(timeout=2)
            return function(*args, **kwargs)

        return wrapped

    evaluators.evaluate_readability = wrap(originals[0])
    evaluators.evaluate_relevance = wrap(originals[1])
    evaluators.evaluate_compliance = wrap(originals[2])
    try:
        result = evaluators.evaluate_in_parallel(
            PASSING_DRAFT,
            ["Contract term is twelve months."],
            "revenue",
            {"client_country": "US", "covered_population": "800 employees"},
        )
    finally:
        evaluators.evaluate_readability = originals[0]
        evaluators.evaluate_relevance = originals[1]
        evaluators.evaluate_compliance = originals[2]

    assert result["overall_pass"] is True


def test_readability_failure_names_the_grade_band() -> None:
    result = evaluate_readability("Too short.")

    assert result["pass"] is False
    assert "100 words" in result["details"]
