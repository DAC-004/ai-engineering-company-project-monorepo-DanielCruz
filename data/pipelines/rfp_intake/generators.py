"""Department proposal generators. Each one sees only its own Part 1 extract."""

from __future__ import annotations

import json
from typing import Any, Callable

from data.pipelines.rfp_intake.departments import DEPARTMENTS, country_rule
from data.pipelines.rfp_intake.evaluators import READABILITY_HIGH, READABILITY_LOW
from data.pipelines.rfp_intake.generation import ChatComplete
from data.pipelines.rfp_intake.grounding import sanitize_client_facing_draft
from data.pipelines.rfp_intake.readability import readability_metrics
from data.pipelines.rfp_intake.source_fidelity import (
    aspects_state_appointment_volume,
    aspects_state_proposed_start,
)

REVENUE_ROLE = (
    "You are the Revenue Cycle generator for Tom Callahan. "
    "Write only the financial section: currency, payment structure, assumptions, exclusions, "
    "and information still required before a final quotation. "
    "Use USD for a US client and GBP for a UK client. "
    "If a covered population category is stated, name that category. "
    "If numeric headcount is absent, say the numeric headcount was not stated. Do not invent a headcount. "
    "Do not write that covered population was not stated when the category is present. "
    "If budget is missing, say the budget was not stated. "
    "Do not write instructions such as please provide an open question, record an open question, or do not invent a price. "
    "Do not invent a headcount, price, discount, or payment term. Do not name a patient or state a patient diagnosis. "
    "Write 140 to 170 words of plain business sentences in a Flesch-Kincaid grade band of 8 to 14."
)
CLINICAL_ROLE = (
    "You are the Clinical Operations generator for Dr. Marcus Reid. "
    "Write only the clinical feasibility section: service suitability, staffing and capacity assessment, "
    "scheduling, and limitations for the stated program. "
    "If covered population is missing, say it was not stated and ask an open question. "
    "Requested appointment volume is demand to assess, not committed capacity. "
    "If key_aspects already include a start month or appointment volume, state those facts; do not ask for them again. "
    "You may ask for missing no-show or cancellation rate assumptions, and those words must appear in the question. "
    "Do not ask what these rates would be without naming no-show or cancellation. "
    "Do not state that equipment or facilities are already in place. "
    "Do not invent staffing numbers or confirmed availability. Do not name a patient or state a patient diagnosis. "
    "Write 140 to 170 words of plain business sentences in a Flesch-Kincaid grade band of 8 to 14."
)
COMPLIANCE_ROLE = (
    "You are the Compliance and Data Governance generator for Claire Whitfield. "
    "Write only the regulatory section for the client_country in the metadata. "
    "If client_country is US, require a Business Associate Agreement before PHI exchange. "
    "Write the BAA as a contractual requirement, not as something quoted, included, or priced in USD. "
    "Use USD only for commercial pricing language in other departments. "
    "Do not mention GBP, UK GDPR, UK clients, or a UK Data Processing Agreement. "
    "Describe consent requirements and workforce training as items to confirm with the client, not as completed measures. "
    "If client_country is UK, require a Data Processing Agreement that references UK GDPR and use GBP wording. "
    "Do not describe the other country's instrument as a requirement for this client. "
    "Do not claim agreements are signed or safeguards are already implemented. "
    "Do not name a patient or state a patient diagnosis. "
    "Write 140 to 170 words of plain business sentences in a Flesch-Kincaid grade band of 8 to 14."
)


def _shared_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    population = metadata.get("covered_population")
    budget = metadata.get("budget_range")
    payload = {
        "client_name": metadata.get("client_name"),
        "client_country": metadata.get("client_country"),
        "program_type": metadata.get("program_type"),
        "covered_population": population,
        "deadline": metadata.get("deadline"),
        "budget_range": budget,
        "departments_needed": metadata.get("departments_needed"),
        "country_requirement": country_rule(metadata.get("client_country") if isinstance(metadata.get("client_country"), str) else None),
    }
    if not isinstance(population, str) or not population.strip():
        payload["missing_population_instruction"] = (
            "Covered population was not stated. Ask whether a population category exists. Do not invent a headcount."
        )
    elif not any(character.isdigit() for character in population):
        payload["stated_population_category"] = population.strip()
        payload["population_instruction"] = (
            f"Covered population category is {population.strip()}. State that category. "
            "A numeric headcount was not stated. Do not invent a headcount. "
            "Do not write that covered population was not stated."
        )
    if not isinstance(budget, str) or not budget.strip():
        payload["missing_budget_instruction"] = (
            "Budget was not stated. Ask whether a budget exists. Do not invent a price."
        )
    return payload


def _department_payload(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    feedback: str | None,
) -> dict[str, Any]:
    department = DEPARTMENTS[department_id]
    aspect_list = [aspect for aspect in (key_aspects.get("aspects") or []) if isinstance(aspect, str)]
    questions = [question for question in (key_aspects.get("open_questions") or []) if isinstance(question, str)]
    country = metadata.get("client_country")
    if department_id == "compliance" and country == "US":
        def _us_only(text: str) -> bool:
            folded = text.casefold()
            return "uk client" not in folded and "gbp" not in folded and "uk gdpr" not in folded

        aspect_list = [aspect for aspect in aspect_list if _us_only(aspect)]
        questions = [question for question in questions if _us_only(question)]
    payload = {
        "department_id": department_id,
        "department_name": department["department_name"],
        "contact_name": department["contact_name"],
        "metadata": _shared_metadata(metadata),
        "key_aspects": {
            "aspects": aspect_list,
            "open_questions": questions,
        },
    }
    if department_id == "compliance" and country == "US":
        metadata_payload = dict(payload["metadata"])
        metadata_payload["country_requirement"] = (
            "US client: require a Business Associate Agreement before PHI exchange. "
            "Do not describe the BAA as quoted, included, or priced in USD."
        )
        payload["metadata"] = metadata_payload
    if department_id == "clinical":
        known_facts: list[str] = []
        if aspects_state_proposed_start(aspect_list):
            known_facts.append(
                "The proposed start date is already in key_aspects. State it. Do not ask what the start date is."
            )
        if aspects_state_appointment_volume(aspect_list):
            known_facts.append(
                "Requested appointment volume is already in key_aspects. State it as demand to assess. "
                "Do not ask what the expected volume is. You may ask only for missing no-show or cancellation rate assumptions."
            )
        if known_facts:
            payload["known_fact_instruction"] = " ".join(known_facts)
    if feedback:
        payload["feedback_for_generator"] = feedback
    return payload


# Local qwen2.5-3b often stops near 60 words even when max_tokens is higher.
# Continue the same draft until the readability floor can be scored.
_MIN_SECTION_WORDS = 120
_MAX_CONTINUATIONS = 6
_CONTINUE_INSTRUCTION = (
    "The draft above is too short. Output ONLY new plain business sentences to append. "
    "Do not repeat any sentence already written. Do not restart the section. "
    "Do not invent prices, discounts, staffing headcounts, signed agreements, "
    "or confirmed availability. Add enough new sentences to bring the full section "
    "to about 150 words."
)


def _word_count(text: str) -> int:
    return len([part for part in text.split() if part])


def _novel_continuation(existing: str, candidate: str) -> str:
    """Keep only appended prose when the model restarts or repeats the draft."""
    more = candidate.strip()
    if not more:
        return ""
    if more == existing.strip():
        return ""
    if more.startswith(existing.strip()):
        return more[len(existing.strip()) :].strip()
    existing_fold = existing.casefold()
    if more.casefold() in existing_fold:
        return ""
    # Drop a repeated opening sentence when the model partially restarts.
    first_sentence = existing.split(".")[0].strip().casefold()
    if first_sentence and more.casefold().startswith(first_sentence):
        clipped = more.split(".", 1)
        if len(clipped) == 2:
            return clipped[1].strip()
    return more


def _continue_draft(
    messages: list[dict[str, str]],
    text: str,
    complete_fn: ChatComplete,
) -> str:
    continue_messages = [
        messages[0],
        messages[1],
        {"role": "assistant", "content": text},
        {"role": "user", "content": _CONTINUE_INSTRUCTION},
    ]
    more = _novel_continuation(text, str(complete_fn(continue_messages)))
    if not more:
        return text
    return f"{text} {more}".strip()


def _published_words(text: str, finalize: Callable[[str], str] | None) -> int:
    if finalize is None:
        return _word_count(text)
    return _word_count(finalize(text))


def _rewrite_short_section(
    role: str,
    payload: dict[str, Any],
    complete_fn: ChatComplete,
    short_draft: str,
) -> str:
    rewrite_payload = dict(payload)
    rewrite_payload["short_draft_to_expand"] = short_draft
    rewrite_payload["length_instruction"] = (
        "The short_draft_to_expand is only an outline. Rewrite the full section as one "
        "cohesive draft of 140 to 170 plain business words. Keep every required fact. "
        "Do not invent prices, staffing headcounts, signed agreements, or confirmed availability."
    )
    return str(
        complete_fn(
            [
                {
                    "role": "system",
                    "content": role + " The previous draft was too short. Rewrite the entire section now.",
                },
                {"role": "user", "content": json.dumps(rewrite_payload, ensure_ascii=True)},
            ]
        )
    ).strip()


def _complete_section(
    role: str,
    payload: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    initial_text: str | None = None,
    finalize: Callable[[str], str] | None = None,
) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": role},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
    ]
    if initial_text is None:
        text = str(complete_fn(messages)).strip()
    else:
        text = initial_text.strip()
    continuations = 0
    while _published_words(text, finalize) < _MIN_SECTION_WORDS and continuations < _MAX_CONTINUATIONS:
        continuations += 1
        next_text = _continue_draft(messages, text, complete_fn)
        if next_text == text:
            break
        text = next_text
    published = finalize(text) if finalize is not None else text
    if _word_count(published) < _MIN_SECTION_WORDS:
        rewritten = _rewrite_short_section(role, payload, complete_fn, published)
        if _published_words(rewritten, finalize) > _word_count(published):
            text = rewritten
    metrics = readability_metrics(finalize(text) if finalize is not None else text)
    fk = metrics.get("flesch_kincaid_grade")
    if isinstance(fk, (int, float)) and (fk < READABILITY_LOW or fk > READABILITY_HIGH):
        simplify_payload = dict(payload)
        simplify_payload["draft_to_simplify"] = text
        simplify_payload["readability_instruction"] = (
            f"Rewrite the draft_to_simplify in {READABILITY_LOW:g} to {READABILITY_HIGH:g} "
            "Flesch-Kincaid using shorter plain sentences. Keep the same facts and length near 150 words."
        )
        simplified = str(
            complete_fn(
                [
                    {
                        "role": "system",
                        "content": role + " Simplify sentence length only. Do not add new facts.",
                    },
                    {"role": "user", "content": json.dumps(simplify_payload, ensure_ascii=True)},
                ]
            )
        ).strip()
        if _published_words(simplified, finalize) >= 100:
            text = simplified
    if finalize is not None:
        return finalize(text)
    return text


def _finalize_for_department(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
) -> Callable[[str], str]:
    aspects = [aspect for aspect in (key_aspects.get("aspects") or []) if isinstance(aspect, str)]

    def finalize(draft: str) -> str:
        return sanitize_client_facing_draft(
            draft,
            department_id,
            metadata,
            key_aspects=aspects,
        )

    return finalize


def generate_revenue_section(
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Draft the Revenue Cycle section from revenue aspects and shared metadata."""
    payload = _department_payload("revenue", metadata, key_aspects, feedback)
    return _complete_section(
        REVENUE_ROLE,
        payload,
        complete_fn,
        finalize=_finalize_for_department("revenue", metadata, key_aspects),
    )


def generate_clinical_section(
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Draft the Clinical Operations section from clinical aspects and shared metadata."""
    payload = _department_payload("clinical", metadata, key_aspects, feedback)
    return _complete_section(
        CLINICAL_ROLE,
        payload,
        complete_fn,
        finalize=_finalize_for_department("clinical", metadata, key_aspects),
    )


def generate_compliance_section(
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Draft the Compliance section from compliance aspects and shared metadata."""
    payload = _department_payload("compliance", metadata, key_aspects, feedback)
    return _complete_section(
        COMPLIANCE_ROLE,
        payload,
        complete_fn,
        finalize=_finalize_for_department("compliance", metadata, key_aspects),
    )


_SECTION_ROLES = {
    "revenue": REVENUE_ROLE,
    "clinical": CLINICAL_ROLE,
    "compliance": COMPLIANCE_ROLE,
}


def reinforce_section_length_after_edit(
    draft: str,
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Test helper: continue a short sanitized draft using the same finalize path as production."""
    role = _SECTION_ROLES[department_id]
    payload = _department_payload(department_id, metadata, key_aspects, feedback)
    return _complete_section(
        role,
        payload,
        complete_fn,
        initial_text=draft,
        finalize=_finalize_for_department(department_id, metadata, key_aspects),
    )
