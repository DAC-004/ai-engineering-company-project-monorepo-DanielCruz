"""Sanitation must not leave drafts below the readability word floor."""

from __future__ import annotations

from data.pipelines.rfp_intake.grounding import sanitize_client_facing_draft
from data.pipelines.rfp_intake.generators import _MIN_SECTION_WORDS, _word_count, reinforce_section_length_after_edit
from data.pipelines.rfp_intake.response_loop import run_department


def _expansion_prompt(messages: list[dict[str, str]]) -> bool:
    blob = " ".join(message.get("content", "") for message in messages).casefold()
    return (
        "too short" in blob
        or "short_draft_to_expand" in blob
        or "rewrite the entire section" in blob
    )


def test_reinforce_restores_word_floor_after_scaffolding_removed() -> None:
    short_after_sanitize = sanitize_client_facing_draft(
        "Missing: Budget not stated. Missing information: Payment terms unknown. "
        "Budget and payment terms were not stated in the source request.",
        "compliance",
        {"client_country": "US", "budget_range": None},
        key_aspects=[],
    )
    assert _word_count(short_after_sanitize) < _MIN_SECTION_WORDS

    def complete(messages: list[dict[str, str]]) -> str:
        if _expansion_prompt(messages):
            return (
                "HealthCore will execute a Business Associate Agreement before any PHI is exchanged. "
                "Operational safeguards, workforce training, and incident reporting remain open items "
                "to confirm with Northbridge during contracting. USD pricing applies to this US client. "
                "UK GDPR and a UK Data Processing Agreement do not apply to this engagement. "
                "Security risk analysis, access controls, encryption standards, and vendor management "
                "will be documented in the BAA schedule before go-live. "
                "Business continuity planning, disaster recovery testing, and annual compliance reviews "
                "will be scoped with Northbridge before services begin. "
                "Subprocessor notifications, minimum necessary access, and audit cooperation "
                "will be addressed in the agreement exhibits."
            )
        return short_after_sanitize

    expanded = reinforce_section_length_after_edit(
        short_after_sanitize,
        "compliance",
        {"client_country": "US", "budget_range": None},
        {"aspects": ["Business Associate Agreement required."], "open_questions": []},
        complete,
    )
    cleaned = sanitize_client_facing_draft(
        expanded,
        "compliance",
        {"client_country": "US", "budget_range": None},
        key_aspects=[],
    )
    assert _word_count(cleaned) >= 100


def test_run_department_continues_until_published_word_floor() -> None:
    """Published (post-sanitize) length is measured inside the existing continuation budget."""

    calls = {"n": 0}

    def complete(messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        if _expansion_prompt(messages):
            return (
                "HealthCore will confirm budget and payment terms with Northbridge before quoting. "
                "USD pricing applies to this United States client engagement. "
                "No unit prices or discounts have been agreed in the source request. "
                "Assumptions include outpatient volume near forty appointments per month. "
                "Exclusions remain open until contracting defines pass-through costs and billing cadence. "
                "Payment structure, invoicing milestones, and renewal terms require client confirmation. "
                "HealthCore will document assumptions and exclusions in the formal quotation package. "
                "Final pricing will follow discovery workshops and signed scope confirmation. "
                "Northbridge will receive a written summary of open commercial questions before contract signature. "
                "HealthCore will document invoicing milestones and renewal terms during contracting."
            )
        return (
            "Missing: Budget not stated. Ask for these details first. "
            "For Northbridge Community Services in the United States, HealthCore quotes in USD."
        )

    outcome = run_department(
        "revenue",
        {"client_country": "US", "client_name": "Northbridge", "budget_range": None},
        {"key_aspects": {"aspects": ["No prices agreed."], "open_questions": []}},
        complete,
    )
    draft = outcome["draft_content"]
    assert "Ask for these details first" not in draft
    assert _word_count(draft) >= 100


def test_run_department_evaluates_post_sanitize_text() -> None:
    """Evaluation and stored draft use the same screened, sanitized body."""

    def complete(messages: list[dict[str, str]]) -> str:
        if _expansion_prompt(messages):
            return (
                "Payment milestones, invoicing cadence, and pass-through cost handling will be confirmed "
                "with Northbridge before contract execution. HealthCore will not quote unit prices until "
                "scope, staffing assumptions, and appointment volumes are validated during discovery. "
                "Assumptions include approximately forty outpatient appointments per month with a proposed "
                "service start in January 2027. No unit prices or discounts have been agreed in the source request. "
                "Exclusions include travel, third-party lab fees, and pass-through costs until confirmed. "
                "HealthCore will confirm payment structure and billing cadence before issuing a final quotation. "
                "Northbridge will receive a written summary of open commercial questions before contract signature."
            )
        return (
            "Missing: Budget not stated. "
            "For Northbridge Community Services in the United States, HealthCore quotes in USD. "
            "Budget and payment terms were not stated in the source request and remain open questions. "
            "Assumptions include approximately forty outpatient appointments per month with a proposed "
            "service start in January 2027. No unit prices or discounts have been agreed. "
            "Exclusions include travel, third-party lab fees, and pass-through costs until confirmed. "
            "HealthCore will confirm payment structure and billing cadence before issuing a final quotation."
        )

    outcome = run_department(
        "revenue",
        {"client_country": "US", "client_name": "Northbridge", "budget_range": None},
        {"key_aspects": {"aspects": ["No prices agreed."], "open_questions": []}},
        complete,
    )
    draft = outcome["draft_content"]
    assert "Missing:" not in draft
    assert "Budget and payment terms were not stated" in draft
    assert _word_count(draft) >= 100
    readability = outcome["evaluation_results"].get("readability") or {}
    assert readability.get("pass") is True or "fewer than 100 words" not in str(readability.get("details", ""))
