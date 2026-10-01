"""Department proposal generators. Each one sees only its own Part 1 extract."""

from __future__ import annotations

import json
from typing import Any

from data.pipelines.rfp_intake.departments import DEPARTMENTS, country_rule
from data.pipelines.rfp_intake.generation import ChatComplete

REVENUE_ROLE = (
    "You are the Revenue Cycle generator for Tom Callahan. "
    "Write only the financial section: currency, payment structure, and stated commercial terms. "
    "Use USD for a US client and GBP for a UK client. "
    "If covered population or budget is missing, say it was not stated and ask an open question. "
    "Do not invent a headcount or a price. Do not name a patient or state a patient diagnosis. "
    "Write at least 100 words of plain sentences."
)
CLINICAL_ROLE = (
    "You are the Clinical Operations generator for Dr. Marcus Reid. "
    "Write only the clinical feasibility section: clinics and staff capacity for the stated program. "
    "If covered population is missing, say it was not stated and ask an open question. "
    "Do not invent a headcount. Do not name a patient or state a patient diagnosis. "
    "Write at least 100 words of plain sentences."
)
COMPLIANCE_ROLE = (
    "You are the Compliance and Data Governance generator for Claire Whitfield. "
    "Write only the regulatory section. A US client needs a Business Associate Agreement clause. "
    "A UK client needs a Data Processing Agreement clause that references UK GDPR. "
    "Do not name a patient or state a patient diagnosis. "
    "Write at least 100 words of plain sentences."
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
    payload = {
        "department_id": department_id,
        "department_name": department["department_name"],
        "contact_name": department["contact_name"],
        "metadata": _shared_metadata(metadata),
        "key_aspects": {
            "aspects": list(key_aspects.get("aspects") or []),
            "open_questions": list(key_aspects.get("open_questions") or []),
        },
    }
    if feedback:
        payload["feedback_for_generator"] = feedback
    return payload


def _complete_section(role: str, payload: dict[str, Any], complete_fn: ChatComplete) -> str:
    text = complete_fn(
        [
            {"role": "system", "content": role},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]
    )
    return str(text).strip()


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
