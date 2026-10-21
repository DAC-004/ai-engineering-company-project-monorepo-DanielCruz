"""Department proposal generators. Each one sees only its own Part 1 extract."""

from __future__ import annotations

import json
from typing import Any

from data.pipelines.rfp_intake.departments import DEPARTMENTS, country_rule
from data.pipelines.rfp_intake.evaluators import READABILITY_HIGH, READABILITY_LOW
from data.pipelines.rfp_intake.generation import ChatComplete
from data.pipelines.rfp_intake.readability import readability_metrics

REVENUE_ROLE = (
    "You are the Revenue Cycle generator for Tom Callahan. "
    "Write only the financial section: currency, payment structure, assumptions, exclusions, "
    "and information still required before a final quotation. "
    "Use USD for a US client and GBP for a UK client. "
    "If covered population or budget is missing, say it was not stated and ask an open question. "
    "Do not invent a headcount, price, discount, or payment term. Do not name a patient or state a patient diagnosis. "
    "Write 140 to 170 words of plain business sentences in a Flesch-Kincaid grade band of 8 to 14."
)
CLINICAL_ROLE = (
    "You are the Clinical Operations generator for Dr. Marcus Reid. "
    "Write only the clinical feasibility section: service suitability, staffing and capacity assessment, "
    "scheduling, and limitations for the stated program. "
    "If covered population is missing, say it was not stated and ask an open question. "
    "Do not invent staffing numbers or confirmed availability. Do not name a patient or state a patient diagnosis. "
    "Write 140 to 170 words of plain business sentences in a Flesch-Kincaid grade band of 8 to 14."
)
COMPLIANCE_ROLE = (
    "You are the Compliance and Data Governance generator for Claire Whitfield. "
    "Write only the regulatory section for the client_country in the metadata. "
    "If client_country is US, require a Business Associate Agreement, use USD wording only, "
    "and do not mention GBP, UK GDPR, or a UK Data Processing Agreement except to say they do not apply. "
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
            "Covered population was not stated. Record an open question. Do not invent a headcount."
        )
    if not isinstance(budget, str) or not budget.strip():
        payload["missing_budget_instruction"] = (
            "Budget was not stated. Record an open question. Do not invent a price."
        )
    return payload


def _department_payload(
    department_id: str,
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    feedback: str | None,
) -> dict[str, Any]:
    department = DEPARTMENTS[department_id]
    aspect_list = list(key_aspects.get("aspects") or [])
    country = metadata.get("client_country")
    if department_id == "compliance" and country == "US":
        aspect_list = [
            aspect
            for aspect in aspect_list
            if isinstance(aspect, str)
            and "uk client" not in aspect.casefold()
            and "gbp" not in aspect.casefold()
            and "uk gdpr" not in aspect.casefold()
        ]
    payload = {
        "department_id": department_id,
        "department_name": department["department_name"],
        "contact_name": department["contact_name"],
        "metadata": _shared_metadata(metadata),
        "key_aspects": {
            "aspects": aspect_list,
            "open_questions": list(key_aspects.get("open_questions") or []),
        },
    }
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


def _complete_section(role: str, payload: dict[str, Any], complete_fn: ChatComplete) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": role},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
    ]
    text = str(complete_fn(messages)).strip()
    continuations = 0
    while _word_count(text) < _MIN_SECTION_WORDS and continuations < _MAX_CONTINUATIONS:
        continuations += 1
        continue_messages = [
            messages[0],
            messages[1],
            {"role": "assistant", "content": text},
            {"role": "user", "content": _CONTINUE_INSTRUCTION},
        ]
        more = _novel_continuation(text, str(complete_fn(continue_messages)))
        if not more:
            break
        text = f"{text} {more}".strip()
    if _word_count(text) < _MIN_SECTION_WORDS:
        # Last resort: rewrite the whole section from the short draft as an outline.
        rewrite_payload = dict(payload)
        rewrite_payload["short_draft_to_expand"] = text
        rewrite_payload["length_instruction"] = (
            "The short_draft_to_expand is only an outline. Rewrite the full section as one "
            "cohesive draft of 140 to 170 plain business words. Keep every required fact. "
            "Do not invent prices, staffing headcounts, signed agreements, or confirmed availability."
        )
        rewritten = str(
            complete_fn(
                [
                    {
                        "role": "system",
                        "content": (
                            role
                            + " The previous draft was too short. Rewrite the entire section now."
                        ),
                    },
                    {"role": "user", "content": json.dumps(rewrite_payload, ensure_ascii=True)},
                ]
            )
        ).strip()
        if _word_count(rewritten) > _word_count(text):
            text = rewritten
    metrics = readability_metrics(text)
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
        if _word_count(simplified) >= 100:
            text = simplified
    return text


def generate_revenue_section(
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Draft the Revenue Cycle section from revenue aspects and shared metadata."""
    payload = _department_payload("revenue", metadata, key_aspects, feedback)
    return _complete_section(REVENUE_ROLE, payload, complete_fn)


def generate_clinical_section(
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Draft the Clinical Operations section from clinical aspects and shared metadata."""
    payload = _department_payload("clinical", metadata, key_aspects, feedback)
    return _complete_section(CLINICAL_ROLE, payload, complete_fn)


def generate_compliance_section(
    metadata: dict[str, Any],
    key_aspects: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    feedback: str | None = None,
) -> str:
    """Draft the Compliance section from compliance aspects and shared metadata."""
    payload = _department_payload("compliance", metadata, key_aspects, feedback)
    return _complete_section(COMPLIANCE_ROLE, payload, complete_fn)
