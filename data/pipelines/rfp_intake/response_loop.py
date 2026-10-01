"""Bounded generator-evaluator loop for each HealthCore department.

Departments run together. One exhausted section stays provisional and does not
cancel the others. The Part 3 handoff is written only after every department
has a redacted draft and an evaluation.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from data.pipelines.rfp_intake.departments import DEPARTMENT_IDS
from data.pipelines.rfp_intake.evaluators import evaluate_in_parallel
from data.pipelines.rfp_intake.generation import ChatComplete
from data.pipelines.rfp_intake.generators import (
    generate_clinical_section,
    generate_compliance_section,
    generate_revenue_section,
)
from data.pipelines.rfp_intake.phi import screen_generated

MAX_ATTEMPTS = 3
ProgressCallback = Callable[[dict[str, Any]], None]

_GENERATORS = {
    "revenue": generate_revenue_section,
    "clinical": generate_clinical_section,
    "compliance": generate_compliance_section,
}


def _currency(client_country: object) -> str | None:
    if client_country == "US":
        return "USD"
    if client_country == "UK":
        return "GBP"
    return None


def _aspects(section: dict[str, Any]) -> list[str]:
    key_aspects = section.get("key_aspects")
    if not isinstance(key_aspects, dict):
        return []
    aspects = key_aspects.get("aspects")
    if not isinstance(aspects, list):
        return []
    return [aspect for aspect in aspects if isinstance(aspect, str)]


def run_department(
    department_id: str,
    metadata: dict[str, Any],
    section: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Revise one section at most three times. The last safe draft is kept."""
    generator = _GENERATORS[department_id]
    key_aspects = section.get("key_aspects") if isinstance(section.get("key_aspects"), dict) else {}
    aspects = _aspects(section)
    client_name = metadata.get("client_name")
    allowed_names = (client_name,) if isinstance(client_name, str) and client_name.strip() else ()
    feedback: str | None = None
    last_draft = ""
    last_evaluation: dict[str, Any] = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if on_progress is not None:
            on_progress({"department_id": department_id, "phase": "drafting", "attempt": attempt})
        raw_draft = generator(metadata, key_aspects, complete_fn, feedback=feedback)
        screened = screen_generated(raw_draft, allowed_names=allowed_names)
        if on_progress is not None:
            on_progress({"department_id": department_id, "phase": "under_evaluation", "attempt": attempt})
        evaluation = evaluate_in_parallel(
            raw_draft,
            aspects,
            department_id,
            metadata,
            allowed_names=allowed_names,
        )
        # Redaction can remove the only evidence. Keep the flag from the original screen.
        if screened.detected:
            evaluation["contains_phi"] = True
            compliance = evaluation.get("compliance")
            if isinstance(compliance, dict):
                compliance["contains_phi"] = True
                compliance["pass"] = False
                rule_ids = compliance.get("rule_ids")
                if isinstance(rule_ids, list) and "HC-NO-PHI" not in rule_ids:
                    rule_ids.append("HC-NO-PHI")
            evaluation["overall_pass"] = False
        last_draft = screened.text
        last_evaluation = evaluation
        if evaluation.get("overall_pass") and not screened.detected:
            return {
                "department_id": department_id,
                "draft_content": last_draft,
                "evaluation_results": last_evaluation,
                "needs_human_review": False,
                "attempt_count": attempt,
            }
        feedback_text = evaluation.get("feedback_for_generator")
        feedback = feedback_text if isinstance(feedback_text, str) else None
    return {
        "department_id": department_id,
        "draft_content": last_draft,
        "evaluation_results": last_evaluation,
        "needs_human_review": True,
        "attempt_count": MAX_ATTEMPTS,
    }


def build_part3_handoff(
    ticket_id: str,
    metadata: dict[str, Any],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Publish every department, including a provisional section, in one handoff."""
    by_department = {outcome["department_id"]: outcome for outcome in outcomes}
    ordered = [by_department[department_id] for department_id in DEPARTMENT_IDS]
    phi_detected = any(bool(outcome["evaluation_results"].get("contains_phi")) for outcome in ordered)
    return {
        "ticket_id": ticket_id,
        "response_complete": True,
        "client_country": metadata.get("client_country"),
        "currency": _currency(metadata.get("client_country")),
        "covered_population": metadata.get("covered_population"),
        "phi_detected": phi_detected,
        "compliance_review_required": phi_detected,
        "sections": [
            {
                "department_id": outcome["department_id"],
                "draft_content": outcome["draft_content"],
                "evaluation_results": outcome["evaluation_results"],
                "needs_human_review": outcome["needs_human_review"],
                "provisional": outcome["needs_human_review"],
            }
            for outcome in ordered
        ],
    }


def run_response_generation(
    handoff: dict[str, Any],
    complete_fn: ChatComplete,
    *,
    on_progress: ProgressCallback | None = None,
    on_department_done: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the three department loops together, then build the Part 3 handoff."""
    metadata = handoff.get("metadata") if isinstance(handoff.get("metadata"), dict) else {}
    sections = {
        section["department_id"]: section
        for section in handoff.get("sections", [])
        if isinstance(section, dict) and isinstance(section.get("department_id"), str)
    }

    def run_one(department_id: str) -> dict[str, Any]:
        outcome = run_department(
            department_id,
            metadata,
            sections[department_id],
            complete_fn,
            on_progress=on_progress,
        )
        if on_department_done is not None:
            on_department_done(outcome)
        return outcome

    with ThreadPoolExecutor(max_workers=len(DEPARTMENT_IDS)) as pool:
        outcomes = list(pool.map(run_one, DEPARTMENT_IDS))
    return build_part3_handoff(str(handoff.get("ticket_id")), metadata, outcomes)
