"""Typed graph state and stage constants from the specialized briefing."""

from __future__ import annotations

from typing import Any, TypedDict

STAGE_WELCOME = 1
STAGE_COMPANY = 2
STAGE_OPERATIONS = 3
STAGE_COMPLIANCE = 4
STAGE_ROLE = 5
STAGE_HOW_WE_WORK = 6
STAGE_ACCESS_CLOSURE = 7

STAGE_NAMES: dict[int, str] = {
    1: "welcome_paperwork",
    2: "the_company",
    3: "how_we_operate",
    4: "compliance",
    5: "your_role",
    6: "how_we_work",
    7: "access_and_closure",
}

STAGE_DEADLINE_DAY: dict[int, int] = {
    1: 2,
    2: 3,
    3: 4,
    4: 6,
    5: 8,
    6: 9,
    7: 10,
}

CONTENT_STAGES: frozenset[int] = frozenset({2, 3, 4, 5, 6})
HUMAN_APPROVAL_STAGES: frozenset[int] = frozenset({1, 4, 5, 7})

ROLE_DIGITAL_ENGINEER = "digital_engineer"
ROLE_REVENUE_ANALYST = "revenue_cycle_analyst"

FRAMEWORK_HIPAA = "hipaa"
FRAMEWORK_UK_GDPR = "uk_gdpr"

PATIENT_INFORMATION_SYSTEMS: frozenset[str] = frozenset(
    {
        "us_ehr",
        "uk_ehr",
        "patient_billing",
        "claims_with_phi",
    }
)

CORPORATE_TOOLS: frozenset[str] = frozenset(
    {
        "jira",
        "notion",
        "slack",
        "microsoft365",
    }
)


class OnboardingState(TypedDict):
    onboarding_id: str
    hire_user_id: str
    display_name: str
    role_key: str
    department_id: str
    office: str
    framework: str
    manager_user_id: str
    people_team_department_id: str
    claire_user_id: str
    diane_user_id: str
    start_date: str
    current_stage: int
    status: str
    paperwork_received: bool
    background_check_completed: bool
    company_passed: bool
    operations_passed: bool
    compliance_check_passed: bool
    compliance_approved: bool
    role_check_passed: bool
    role_approved: bool
    how_we_work_passed: bool
    closure_approved: bool
    attempt_counts: dict[str, int]
    active_bank: dict[str, str]
    missed_topics: list[str]
    last_score: float
    last_rejection_comment: str
    pending_kind: str
    decision_nonce: str
    last_action: str


def empty_attempts() -> dict[str, int]:
    return {str(stage): 0 for stage in range(1, 8)}


def default_banks() -> dict[str, str]:
    return {str(stage): "a" for stage in CONTENT_STAGES}


def initial_state(spec: dict[str, Any]) -> OnboardingState:
    return {
        "onboarding_id": spec["onboarding_id"],
        "hire_user_id": spec["hire_user_id"],
        "display_name": spec["display_name"],
        "role_key": spec["role_key"],
        "department_id": spec["department_id"],
        "office": spec["office"],
        "framework": spec["framework"],
        "manager_user_id": spec["manager_user_id"],
        "people_team_department_id": spec.get("people_team_department_id", "people_workforce"),
        "claire_user_id": spec["claire_user_id"],
        "diane_user_id": spec["diane_user_id"],
        "start_date": spec["start_date"],
        "current_stage": STAGE_WELCOME,
        "status": "waiting_human",
        "paperwork_received": False,
        "background_check_completed": False,
        "company_passed": False,
        "operations_passed": False,
        "compliance_check_passed": False,
        "compliance_approved": False,
        "role_check_passed": False,
        "role_approved": False,
        "how_we_work_passed": False,
        "closure_approved": False,
        "attempt_counts": empty_attempts(),
        "active_bank": default_banks(),
        "missed_topics": [],
        "last_score": 0.0,
        "last_rejection_comment": "",
        "pending_kind": "paperwork",
        "decision_nonce": spec.get("decision_nonce", ""),
        "last_action": "started",
    }
