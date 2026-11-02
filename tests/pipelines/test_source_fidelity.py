from data.pipelines.rfp_intake.grounding import sanitize_client_facing_draft
from data.pipelines.rfp_intake.source_fidelity import (
    draft_asserts_invented_capacity_commitment,
    draft_asserts_invented_facilities_in_place,
    draft_asserts_unsupported_compliance_assurance,
    draft_asserts_unsupported_price,
    handoff_allows_monetary_figures,
    is_generator_scaffolding_sentence,
    is_redundant_known_fact_question,
    keep_baa_requirement_without_usd_price,
    rewrite_consent_met_as_confirmation,
    rewrite_false_unstated_population,
)


def test_scaffolding_removed_but_gap_statement_kept() -> None:
    draft = (
        "Missing: Budget not stated, ask about budget. "
        "Budget and payment terms remain to be confirmed with Northbridge before a final quotation."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "revenue",
        {"budget_range": None, "client_country": "US"},
        key_aspects=["No prices or discounts have been agreed."],
    )
    assert "Missing:" not in cleaned
    assert "remain to be confirmed" in cleaned


def test_budget_stated_does_not_allow_invented_unit_price() -> None:
    aspects = ("Annual budget range USD 500000-750000 stated in source.",)
    assert handoff_allows_monetary_figures(aspects) is False
    assert draft_asserts_unsupported_price(
        "Estimated revenue per appointment is $100 in USD.",
        {"budget_range": "USD 500000-750000", "client_country": "US"},
        aspects,
    )


def test_agreed_price_aspect_allows_monetary_wording() -> None:
    aspects = ("Unit price of $85 per visit agreed with the client.",)
    assert handoff_allows_monetary_figures(aspects) is True
    assert (
        draft_asserts_unsupported_price(
            "The agreed unit price is $85 per visit in USD.",
            {"budget_range": None, "client_country": "US"},
            aspects,
        )
        is False
    )


def test_sanitize_does_not_empty_substantive_draft() -> None:
    draft = (
        "For Northbridge Community Services, quoting in USD. "
        "No prices or discounts have been agreed in the source request. "
        "Assumptions include approximately 40 outpatient appointments per month with a proposed start in January 2027. "
        "Budget and payment terms remain to be confirmed before HealthCore issues a final quotation."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "revenue",
        {"budget_range": None, "client_country": "US"},
        key_aspects=["No prices or discounts have been agreed."],
    )
    assert len(cleaned.split()) >= 25
    assert "$" not in cleaned


def test_104_word_compliance_sample_flags_content_issues() -> None:
    sample = (
        "For Northbridge Community Services in the US, include a Business Associate Agreement quoted in USD. "
        "This ensures compliance with applicable privacy and consent requirements. "
        "It is important to note that this does not apply to UK clients, where a Data Processing Agreement "
        "referencing UK GDPR would be required. "
        "Additionally, ensure all necessary patient consent forms are in place. "
        "Lastly, maintain regular training for all staff involved in handling personal or health information."
    )
    assert draft_asserts_unsupported_compliance_assurance(sample) is True


def test_no_extra_safeguards_matches_agreements_or_safeguards_phrase() -> None:
    sentence = (
        "No additional agreements or safeguards are needed for Northbridge Community Services, "
        "as per the client's country-specific requirements."
    )
    assert draft_asserts_unsupported_compliance_assurance(sentence) is True


def test_is_generator_scaffolding_sentence() -> None:
    assert is_generator_scaffolding_sentence("Missing: Budget not stated, ask about budget.")
    assert is_generator_scaffolding_sentence(
        "Additional sentences to bring the section to about 150 words:"
    )
    assert is_generator_scaffolding_sentence("Addition: Also, no exclusions or assumptions have been identified yet.")
    assert not is_generator_scaffolding_sentence(
        "Payment terms remain to be confirmed with the client."
    )


def test_sanitize_drops_run2_revenue_repetition_and_addition_label() -> None:
    """Saved integrated run 2 revenue draft (2026-10-22T00:41Z): padding and Addition: labels."""
    draft = (
        "For Northbridge Community Services, quoting in USD. Assumptions include covered population "
        "of employees in the US. No budget or payment terms agreed. Open questions: Is there a budget? "
        "Are there payment terms? Will there be exclusions or assumptions that need to be clarified? "
        "Addition: Also, no exclusions or assumptions have been identified yet. Payment terms and budget "
        "need to be confirmed. Will there be any exclusions or additional charges not covered in the "
        "initial proposal? Also, no exclusions or assumptions have been identified yet. Payment terms and "
        "budget need to Assumptions include covered population of employees in the US. Payment terms and "
        "budget need Payment terms and budget need to be confirmed. Payment terms and budget need to be "
        "clarified. Payment terms and budget need to be confirmed, and exclusions or assumptions should "
        "be identified. Will there be any additional charges or exclusions not included in the initial "
        "proposal? Payment terms and budget need to be confirmed, and exclusions or assumptions need to "
        "be identified. Payment terms and budget need to be clarified, and exclusions or assumptions "
        "should be identified. Payment terms and budget need to be confirmed, and exclusions or assumptions"
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "revenue",
        {"budget_range": None, "client_country": "US"},
        key_aspects=["No prices or discounts have been agreed."],
    )
    assert "Addition:" not in cleaned
    assert cleaned.casefold().count("payment terms and budget need") <= 1
    assert "quoting in USD" in cleaned
    assert "No budget or payment terms agreed" in cleaned


def test_sanitize_drops_run2_compliance_instruction_leak_and_baa_in_usd() -> None:
    """Saved integrated run 2 compliance draft leaked the continuation instruction."""
    draft = (
        "For Northbridge Community Services in the US, ensure a Business Associate Agreement is included in USD. "
        "Consent requirements are necessary for exchanging personal or health information. "
        "Additional agreements or safeguards are needed for US clients, specifically a Business Associate Agreement in USD. "
        "Contractual requirements also include a clear understanding of how information will be used and disclosed, "
        "and the measures in place to protect the data. Additional sentences to bring the section to about 150 words: "
        "For Northbridge Community Services in the US, ensure a Business Associate Agreement is included in USD. "
        "This includes specifying the purpose of the information use, the data security measures, and the duration "
        "of data retention. Additionally, ensure there is a process for handling data breaches and a mechanism for "
        "resolving disputes related to data use."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    assert "150 words" not in cleaned.casefold()
    assert "included in USD" not in cleaned
    assert "Business Associate Agreement in USD" not in cleaned
    assert cleaned.casefold().count("for northbridge community services in the us") <= 1
    assert "Consent requirements are necessary" in cleaned


def test_sanitize_keeps_separate_usd_quote_and_baa_requirement() -> None:
    """Commercial USD quoting plus a BAA requirement are two instructions, not BAA-as-price."""
    sentence = "Quote in USD and include a Business Associate Agreement."
    assert draft_asserts_unsupported_compliance_assurance(sentence) is False
    cleaned = sanitize_client_facing_draft(
        sentence,
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    assert "Quote in USD" in cleaned
    assert "Business Associate Agreement" in cleaned


def test_sanitize_b56d02cf_clinical_drops_capacity_facilities_and_repetition() -> None:
    """Exact clinical draft from ticket b56d02cf-4367-47f8-a642-726818dd1893."""
    draft = (
        "For the outpatient services program covering employees in the United States, we need to assess if it's feasible. "
        "With approximately 40 appointments per month, we'll need to look at staffing and capacity. "
        "Scheduling will also be important to manage these appointments effectively. "
        "Any limitations might include availability of staff and potential patient capacity. "
        "What specific staffing and scheduling challenges do you foresee? "
        "Given the need for approximately 40 appointments per month, we'll need to ensure there's enough staffing and capacity to handle these effectively. "
        "Scheduling will be crucial to manage these appointments efficiently. "
        "Potential limitations might include availability of staff and patient capacity. "
        "How do you anticipate these challenges will impact the program's feasibility and implementation? "
        "Considering the proposed start in January 2027, we should also look at the readiness of the staff and the availability of resources. "
        "It's important to ensure that all necessary equipment and facilities are in place by the start date. "
        "What additional resources or preparations might be needed to ensure a smooth transition and successful implementation of the program?"
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "clinical",
        {"client_country": "US", "covered_population": "Employees in the United States"},
        key_aspects=["Approximately 40 appointments per month.", "Proposed start in January 2027."],
    )
    lowered = cleaned.casefold()
    assert "enough staffing and capacity to handle" not in lowered
    assert "equipment and facilities are in place" not in lowered
    assert cleaned.casefold().count("approximately 40 appointments per month") <= 1
    assert "employees in the united states" in lowered
    assert "january 2027" in lowered
    keep = sanitize_client_facing_draft(
        "Requested demand does not establish committed capacity. "
        "HealthCore still needs to assess whether approximately 40 appointments per month can be supported. "
        "Do you foresee any scheduling constraints at the employer site?",
        "clinical",
        {"client_country": "US"},
        key_aspects=["Approximately 40 appointments per month."],
    )
    assert "does not establish committed capacity" in keep.casefold()
    assert "approximately 40 appointments per month" in keep.casefold()
    assert "scheduling constraints at the employer site" in keep.casefold()


def test_sanitize_b56d02cf_compliance_drops_completed_in_place_and_repetition() -> None:
    draft = (
        "Confirm consent requirements and workforce training are in place. "
        "Additional agreements or safeguards, such as a Business Associate Agreement, are needed for US clients. "
        "Identify applicable consent requirements and workforce training as items to confirm with the client, not as completed measures. "
        "Confirm that additional agreements or safeguards, such as a Business Associate Agreement, are needed for the exchange of personal or health information with Northbridge Community Services. "
        "Identify specific consent requirements and workforce training as items to confirm with the client, not as completed measures. "
        "Ensure that additional agreements or safeguards, such as a Business Associate Agreement, are needed for the exchange of personal or health information with Northbridge Community Services."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    lowered = cleaned.casefold()
    assert "confirm consent requirements and workforce training are in place" not in lowered
    assert "items to confirm with the client" in lowered
    assert "business associate agreement" in lowered
    keep = sanitize_client_facing_draft(
        "Quote in USD and include a Business Associate Agreement. "
        "Confirm whether consent requirements and workforce training are in place.",
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    assert "Quote in USD" in keep
    assert "Business Associate Agreement" in keep
    assert "confirm whether consent requirements and workforce training are in place" in keep.casefold()


def test_sanitize_b56d02cf_revenue_drops_open_question_instruction_keeps_facts() -> None:
    draft = (
        "For Northbridge Community Services, we will quote in USD. "
        "Assumptions include covered population of employees in the US. "
        "No budget or payment terms have been agreed upon. "
        "Open questions: Is there a budget for this project? Are there any payment terms? "
        "Missing budget information was not stated, so please provide an open question for that as well."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "revenue",
        {"budget_range": None, "client_country": "US"},
        key_aspects=["No prices or discounts have been agreed."],
    )
    lowered = cleaned.casefold()
    assert "please provide an open question" not in lowered
    assert "quote in usd" in lowered
    assert "no budget or payment terms have been agreed" in lowered
    assert "is there a budget for this project" in lowered


def test_sanitize_drops_do_not_invent_price_and_record_open_question_instructions() -> None:
    draft = (
        "For Northbridge Community Services, quoting in USD. "
        "No budget or payment terms agreed. "
        "Do not invent a price. "
        "Covered population of employees in the US was not stated. Record an open question."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "revenue",
        {"budget_range": None, "client_country": "US"},
        key_aspects=["No prices or discounts have been agreed."],
    )
    lowered = cleaned.casefold()
    assert "do not invent a price" not in lowered
    assert "record an open question" not in lowered
    assert "quoting in usd" in lowered
    assert "no budget or payment terms agreed" in lowered


def test_sanitize_rewrites_category_as_stated_not_missing_population() -> None:
    draft = (
        "For Northbridge Community Services, quoting in USD. "
        "Assumptions include covered population of employees in the US. "
        "Covered population of employees in the US was not stated."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "revenue",
        {
            "budget_range": None,
            "client_country": "US",
            "covered_population": "Employees in the United States",
        },
        key_aspects=["No prices or discounts have been agreed."],
    )
    lowered = cleaned.casefold()
    assert "employees in the united states" in lowered
    assert "numeric headcount was not stated" in lowered
    assert "covered population of employees in the us was not stated" not in lowered
    rewritten = rewrite_false_unstated_population(
        "Covered population of employees in the US was not stated.",
        "Employees in the United States",
    )
    assert rewritten is not None
    assert "numeric headcount" in rewritten.casefold()
    assert rewrite_false_unstated_population(
        "A numeric headcount was not stated.",
        "Employees in the United States",
    ) is None


def test_sanitize_drops_baa_treated_as_usd_instrument() -> None:
    defective = "Include a Business Associate Agreement quoted in USD."
    assert draft_asserts_unsupported_compliance_assurance(defective) is True
    cleaned = sanitize_client_facing_draft(
        defective + " Consent requirements remain to be confirmed with the client.",
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    assert "quoted in USD" not in cleaned
    assert "Business Associate Agreement" in cleaned
    assert "Consent requirements remain to be confirmed" in cleaned


def test_sanitize_drops_parenthetical_baa_quoted_in_usd() -> None:
    defective = (
        "For Northbridge Community Services in the US, we need to ensure that a "
        "Business Associate Agreement (BAA) is quoted in USD."
    )
    assert draft_asserts_unsupported_compliance_assurance(defective) is True
    cleaned = sanitize_client_facing_draft(
        defective + " Consent requirements remain to be confirmed with the client.",
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    assert "quoted in USD" not in cleaned
    assert "Business Associate Agreement" in cleaned
    assert "Consent requirements remain to be confirmed" in cleaned
    assert draft_asserts_unsupported_compliance_assurance(cleaned) is False


def test_sanitize_rewrites_consent_met_claim_and_keeps_baa() -> None:
    draft = (
        "For Northbridge Community Services in the US, a Business Associate Agreement "
        "is required before exchanging Protected Health Information (PHI). "
        "Ensure all consent requirements are met and workforce is trained on data governance. "
        "Contracts and training are items to confirm with the client, not yet completed."
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    lowered = cleaned.casefold()
    assert "business associate agreement" in lowered
    assert "ensure all consent requirements are met" not in lowered
    assert "items to confirm with the client" in lowered
    rewritten = rewrite_consent_met_as_confirmation(
        "Ensure all consent requirements are met and workforce is trained on data governance."
    )
    assert rewritten is not None
    assert "items to confirm" in rewritten.casefold()


def test_baa_in_usd_phrase_keeps_requirement_not_the_price() -> None:
    rewritten = keep_baa_requirement_without_usd_price(
        "Claire Whitfield needs a Business Associate Agreement in USD for the US client."
    )
    assert rewritten is not None
    assert "business associate agreement" in rewritten.casefold()
    assert "in usd" not in rewritten.casefold()


def test_clinical_drops_orphaned_rate_question_keeps_assessment_ensure() -> None:
    aspects = ["Approximately 40 appointments per month.", "Proposed start in January 2027."]
    assessment = (
        "Staffing and capacity will be assessed to ensure there are enough resources "
        "to handle the 40 appointments monthly, including scheduling."
    )
    assert draft_asserts_invented_capacity_commitment(assessment) is False
    cleaned = sanitize_client_facing_draft(
        "The proposed start in January 2027 and 40 appointments per month are requested demand. "
        "What would you estimate these rates to be? "
        f"{assessment} "
        "What no-show and cancellation rate assumptions should we use?",
        "clinical",
        {"client_country": "US"},
        key_aspects=aspects,
    )
    lowered = cleaned.casefold()
    assert "what would you estimate these rates to be" not in lowered
    assert "enough resources" in lowered
    assert "no-show and cancellation rate assumptions" in lowered
    assert "january 2027" in lowered


def test_sanitize_strips_headcount_and_volume_instructions_keeps_facts() -> None:
    draft = (
        "Given the covered population is Employees in the United States, state that category. "
        "A numeric headcount was not stated. Do not invent a headcount. "
        "Requested appointment volume is 40 appointments per month. "
        "Do not ask what the expected volume is. "
        "What no-show and cancellation rate assumptions should we use?"
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "clinical",
        {"client_country": "US", "covered_population": "Employees in the United States"},
        key_aspects=["Approximately 40 appointments per month.", "Proposed start in January 2027."],
    )
    lowered = cleaned.casefold()
    assert "employees in the united states" in lowered
    assert "numeric headcount was not stated" in lowered
    assert "40 appointments per month" in lowered
    assert "do not invent a headcount" not in lowered
    assert "do not ask what the expected volume is" not in lowered
    assert "state that category" not in lowered
    assert "no-show and cancellation" in lowered


def test_sanitize_drops_continue_to_150_words_instruction() -> None:
    cleaned = sanitize_client_facing_draft(
        "Requested appointment volume is 40 appointments per month. "
        "Add enough new sentences to bring the full section to about 150 words. "
        "What no-show and cancellation rate assumptions should we use?",
        "clinical",
        {"client_country": "US"},
        key_aspects=["Approximately 40 appointments per month."],
    )
    lowered = cleaned.casefold()
    assert "about 150 words" not in lowered
    assert "40 appointments per month" in lowered
    assert "no-show and cancellation" in lowered


def test_clinical_drops_questions_for_supplied_start_and_volume_keeps_no_show_assumption() -> None:
    aspects = ["Approximately 40 appointments per month.", "Proposed start in January 2027."]
    draft = (
        "With approximately 40 appointments per month, HealthCore will assess staffing and capacity. "
        "The proposed start is January 2027. "
        "What is the proposed start date for this program? "
        "What is the expected patient volume, including no-shows and cancellations? "
        "What no-show and cancellation rate assumptions should we use?"
    )
    assert is_redundant_known_fact_question("What is the proposed start date for this program?", aspects) is True
    assert (
        is_redundant_known_fact_question(
            "What is the expected patient volume, including no-shows and cancellations?",
            aspects,
        )
        is True
    )
    assert (
        is_redundant_known_fact_question(
            "What no-show and cancellation rate assumptions should we use?",
            aspects,
        )
        is False
    )
    cleaned = sanitize_client_facing_draft(
        draft,
        "clinical",
        {"client_country": "US"},
        key_aspects=aspects,
    )
    lowered = cleaned.casefold()
    assert "what is the proposed start date" not in lowered
    assert "expected patient volume" not in lowered
    assert "january 2027" in lowered
    assert "40 appointments per month" in lowered
    assert "no-show and cancellation rate assumptions" in lowered


def test_assessment_and_precondition_are_not_capacity_commitments() -> None:
    assessment = "We will need to assess whether staffing can support the requested volume."
    precondition = "We need to ensure sufficient capacity before committing."
    assert draft_asserts_invented_capacity_commitment(assessment) is False
    assert draft_asserts_invented_capacity_commitment(precondition) is False
    cleaned = sanitize_client_facing_draft(
        f"{assessment} {precondition} Approximately 40 appointments per month is requested demand.",
        "clinical",
        {"client_country": "US"},
        key_aspects=["Approximately 40 appointments per month."],
    )
    lowered = cleaned.casefold()
    assert "assess whether staffing can support" in lowered
    assert "ensure sufficient capacity before committing" in lowered
    assert "40 appointments per month" in lowered
    assert draft_asserts_invented_capacity_commitment(
        "We'll need to ensure there's enough staffing and capacity to handle these effectively."
    )


def test_consent_whether_request_kept_assertion_dropped() -> None:
    request = "Confirm whether consent requirements and workforce training are in place."
    assertion = "Consent requirements and workforce training are in place."
    assert draft_asserts_unsupported_compliance_assurance(request) is False
    assert draft_asserts_unsupported_compliance_assurance(assertion) is True
    cleaned = sanitize_client_facing_draft(
        f"{request} {assertion} A Business Associate Agreement is required before PHI exchange.",
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    lowered = cleaned.casefold()
    assert "confirm whether consent requirements and workforce training are in place" in lowered
    assert cleaned.casefold().count("consent requirements and workforce training are in place") == 1
    assert "business associate agreement is required before phi exchange" in lowered


def test_client_resource_questions_are_not_generator_instructions() -> None:
    staffing = "What additional resources will Northbridge provide on site?"
    scheduling = "Do you foresee any scheduling constraints at the employer site?"
    assert is_generator_scaffolding_sentence(staffing) is False
    assert is_generator_scaffolding_sentence(scheduling) is False
    assert is_generator_scaffolding_sentence(
        "Missing budget information was not stated, so please provide an open question for that as well."
    )
    cleaned = sanitize_client_facing_draft(
        f"{staffing} {scheduling} Approximately 40 appointments per month is requested.",
        "clinical",
        {"client_country": "US"},
        key_aspects=["Approximately 40 appointments per month."],
    )
    lowered = cleaned.casefold()
    assert "what additional resources will northbridge provide on site" in lowered
    assert "scheduling constraints at the employer site" in lowered
    assert "40 appointments per month" in lowered


def test_near_duplicate_preserves_negation_quantity_condition_and_baa_duty() -> None:
    clinical = sanitize_client_facing_draft(
        "Capacity is confirmed. Capacity is not confirmed. "
        "The program requests 40 appointments per month. The program requests 80 appointments per month. "
        "Proposed start is January 2027. Proposed start is June 2027.",
        "clinical",
        {"client_country": "US"},
        key_aspects=["Approximately 40 appointments per month.", "Proposed start in January 2027."],
    )
    lowered = clinical.casefold()
    assert "capacity is confirmed" in lowered
    assert "capacity is not confirmed" in lowered
    assert "40 appointments per month" in lowered
    assert "80 appointments per month" in lowered
    assert "january 2027" in lowered
    assert "june 2027" in lowered

    compliance = sanitize_client_facing_draft(
        "A Business Associate Agreement is required before PHI exchange. "
        "A Business Associate Agreement is required only after the client names the covered entity. "
        "HealthCore must also maintain a documented breach-notification process.",
        "compliance",
        {"client_country": "US"},
        key_aspects=["Explain contractual requirements (e.g., Business Associate Agreement)"],
    )
    folded = compliance.casefold()
    assert "required before phi exchange" in folded
    assert "only after the client names the covered entity" in folded
    assert "breach-notification process" in folded or "breach notification process" in folded


def test_facilities_whether_request_is_not_an_in_place_assertion() -> None:
    request = "Confirm whether equipment and facilities are in place before January 2027."
    assertion = "All necessary equipment and facilities are in place."
    assert draft_asserts_invented_facilities_in_place(request) is False
    assert draft_asserts_invented_facilities_in_place(assertion) is True
    cleaned = sanitize_client_facing_draft(
        f"{request} {assertion} Proposed start is January 2027.",
        "clinical",
        {"client_country": "US"},
        key_aspects=["Proposed start in January 2027."],
    )
    lowered = cleaned.casefold()
    assert "confirm whether equipment and facilities are in place" in lowered
    assert "all necessary equipment and facilities are in place" not in lowered
    assert "january 2027" in lowered
