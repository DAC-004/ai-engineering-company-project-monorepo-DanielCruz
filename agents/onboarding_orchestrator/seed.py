"""Fictional fixture identities. Never writes live accounts unless a caller passes a store."""

from __future__ import annotations

from datetime import date

from agents.onboarding_orchestrator.state import (
    FRAMEWORK_HIPAA,
    FRAMEWORK_UK_GDPR,
    ROLE_DIGITAL_ENGINEER,
    ROLE_REVENUE_ANALYST,
)

FIXTURE_PASSWORD = "OnboardTest9!"

# Disposable fixture emails. These are not production identities.
FIXTURE_USERS: tuple[dict[str, str], ...] = (
    {
        "key": "manager_digital",
        "email": "manager.digital@onboarding.example",
        "name": "Alex Rivera",
        "role": "supervisor",
        "department_id": "technology",
    },
    {
        "key": "manager_revenue",
        "email": "manager.revenue@onboarding.example",
        "name": "Jordan Blake",
        "role": "supervisor",
        "department_id": "revenue_cycle",
    },
    {
        "key": "claire",
        "email": "claire.whitfield@onboarding.example",
        "name": "Claire Whitfield",
        "role": "supervisor",
        "department_id": "compliance",
    },
    {
        "key": "diane",
        "email": "diane.foster@onboarding.example",
        "name": "Diane Foster",
        "role": "supervisor",
        "department_id": "people_workforce",
    },
    {
        "key": "people_ops",
        "email": "people.ops@onboarding.example",
        "name": "Sam Patel",
        "role": "employee",
        "department_id": "people_workforce",
    },
    {
        "key": "hire_austin",
        "email": "hire.austin@onboarding.example",
        "name": "Casey Nguyen",
        "role": "employee",
        "department_id": "technology",
    },
    {
        "key": "hire_london",
        "email": "hire.london@onboarding.example",
        "name": "Riley Shaw",
        "role": "employee",
        "department_id": "revenue_cycle",
    },
    {
        "key": "hire_early",
        "email": "hire.early@onboarding.example",
        "name": "Morgan Ellis",
        "role": "employee",
        "department_id": "technology",
    },
)


def onboarding_specs(user_ids: dict[str, str], start: date) -> list[dict[str, str]]:
    """Three fictional onboardings: Austin, London, and early-access denial."""
    shared = {
        "start_date": start.isoformat(),
        "claire_user_id": user_ids["claire"],
        "diane_user_id": user_ids["diane"],
        "people_team_department_id": "people_workforce",
    }
    return [
        {
            **shared,
            "onboarding_id": "onb-austin",
            "hire_user_id": user_ids["hire_austin"],
            "display_name": "Casey Nguyen",
            "role_key": ROLE_DIGITAL_ENGINEER,
            "department_id": "technology",
            "office": "Austin",
            "framework": FRAMEWORK_HIPAA,
            "manager_user_id": user_ids["manager_digital"],
        },
        {
            **shared,
            "onboarding_id": "onb-london",
            "hire_user_id": user_ids["hire_london"],
            "display_name": "Riley Shaw",
            "role_key": ROLE_REVENUE_ANALYST,
            "department_id": "revenue_cycle",
            "office": "London",
            "framework": FRAMEWORK_UK_GDPR,
            "manager_user_id": user_ids["manager_revenue"],
        },
        {
            **shared,
            "onboarding_id": "onb-early",
            "hire_user_id": user_ids["hire_early"],
            "display_name": "Morgan Ellis",
            "role_key": ROLE_DIGITAL_ENGINEER,
            "department_id": "technology",
            "office": "Austin",
            "framework": FRAMEWORK_HIPAA,
            "manager_user_id": user_ids["manager_digital"],
        },
    ]
