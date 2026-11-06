"""Separate agent identities and tool allowlists."""

from __future__ import annotations

SUPERVISOR_ID = "supplier-contracts-supervisor"
PRICING_ID = "supplier-contracts-pricing"
CONTRACTS_ID = "supplier-contracts-contracts"
ALERTS_ID = "supplier-contracts-alerts"

PRICING_TOOLS = frozenset(
    {
        "load_price_rows",
        "detect_increase",
        "calculate_annual_impact",
        "compare_same_country_category",
        "convert_gbp_usd",
    }
)
CONTRACTS_TOOLS = frozenset(
    {
        "load_sanitized_terms",
        "evaluate_revision_cap",
        "expiry_and_notice",
        "data_protection_status",
    }
)
SUPERVISOR_TOOLS = frozenset(
    {
        "consult_pricing",
        "consult_contracts",
        "compose_brief",
        "draft_communication",
        "enqueue_internal_alert",
    }
)
FORBIDDEN_TOOLS = frozenset(
    {
        "send_supplier_message",
        "execute_payment",
        "change_contract",
        "bypass_dpa_gate",
    }
)

MARCUS = "marcus.reid"
CLAIRE = "claire.whitfield"
SANDRA = "sandra.okonkwo"

EMAIL_TO_APPROVER = {
    "marcus.clinical@healthcore.example": MARCUS,
    "claire.compliance@healthcore.example": CLAIRE,
    "sandra.executive@healthcore.example": SANDRA,
}

# Matches app.access.catalog.DEPARTMENT_IDS. Sandra uses Admin cross-department
# privilege; do not invent a seventh executive department.
KNOWN_DEPARTMENTS = frozenset(
    {
        "clinical_operations",
        "patient_experience",
        "revenue_cycle",
        "compliance",
        "people_workforce",
        "technology",
    }
)
NAMED_HOME_DEPARTMENT = {
    MARCUS: "clinical_operations",
    CLAIRE: "compliance",
}
CONTRACTS_READ_DEPARTMENTS = frozenset({"clinical_operations", "compliance"})


def actor_payload(agent_id: str) -> dict[str, str]:
    return {"actor_type": "automated_process", "actor_id": agent_id}


def approver_from_email(email: str) -> str | None:
    return EMAIL_TO_APPROVER.get(email.strip().lower())


def named_home_department(approver_id: str) -> str | None:
    return NAMED_HOME_DEPARTMENT.get(approver_id)
