"""Named reviewer, recipients, and the automated close identity."""

from __future__ import annotations

from dataclasses import dataclass

from agents.financial_close.constants import AGENT_ID

TOM = "tom.callahan"
CLAIRE = "claire.whitfield"
SANDRA = "sandra.okonkwo"
JAMES = "james.osei"
MARCUS = "marcus.reid"
PRIYA = "priya.nair"
DIANE = "diane.foster"

TOM_EMAIL = "tom.billing@healthcore.example"
CLAIRE_EMAIL = "claire.compliance@healthcore.example"
SANDRA_EMAIL = "sandra.executive@healthcore.example"
JAMES_EMAIL = "james.admin@healthcore.example"
MARCUS_EMAIL = "marcus.clinical@healthcore.example"
PRIYA_EMAIL = "priya.access@healthcore.example"
DIANE_EMAIL = "diane.people@healthcore.example"

EMAIL_TO_PERSON = {
    TOM_EMAIL: TOM,
    CLAIRE_EMAIL: CLAIRE,
    SANDRA_EMAIL: SANDRA,
    JAMES_EMAIL: JAMES,
    MARCUS_EMAIL: MARCUS,
    PRIYA_EMAIL: PRIYA,
    DIANE_EMAIL: DIANE,
}

PERSON_DISPLAY = {
    TOM: "Tom Callahan",
    CLAIRE: "Claire Whitfield",
    SANDRA: "Dr. Sandra Okonkwo",
    JAMES: "James Osei",
    MARCUS: "Dr. Marcus Reid",
    PRIYA: "Priya Nair",
    DIANE: "Diane Foster",
}

# Recipients after Tom's approval, in briefing order.
DISTRIBUTION_EMAILS = (
    SANDRA_EMAIL,
    JAMES_EMAIL,
    MARCUS_EMAIL,
    PRIYA_EMAIL,
    TOM_EMAIL,
    CLAIRE_EMAIL,
    DIANE_EMAIL,
)

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

# Sandra and James are Admin in technology. That is not a seventh department
# and does not authorize Tom's review.
HOME_DEPARTMENT = {
    TOM: "revenue_cycle",
    CLAIRE: "compliance",
    MARCUS: "clinical_operations",
    PRIYA: "patient_experience",
    DIANE: "people_workforce",
    JAMES: "technology",
    SANDRA: "technology",
}

EXPECTED_ROLE = {
    TOM: "supervisor",
    CLAIRE: "employee",
    MARCUS: "supervisor",
    PRIYA: "employee",
    DIANE: "employee",
    JAMES: "admin",
    SANDRA: "admin",
}


@dataclass(frozen=True)
class ActorIdentity:
    user_id: str
    role: str
    department_id: str | None
    email: str
    is_active: bool = True
    is_admin: bool = False
    can_approve: bool = False


class ActorRejected(ValueError):
    pass


def actor_payload() -> dict[str, str]:
    return {"actor_type": "automated_process", "actor_id": AGENT_ID}


def person_from_email(email: str) -> str | None:
    return EMAIL_TO_PERSON.get(email.strip().lower())


def trusted_named_person(actor: ActorIdentity) -> str | None:
    """Active named staff whose email, role, and home department all match."""
    if not actor.is_active or not actor.user_id:
        return None
    person = person_from_email(actor.email)
    if person is None:
        return None
    if actor.department_id != HOME_DEPARTMENT.get(person):
        return None
    if actor.role != EXPECTED_ROLE.get(person):
        return None
    return person


def named_tom_from_actor(actor: ActorIdentity) -> str:
    """Only Tom Callahan may approve or reject. Admin cannot substitute."""
    if not actor.is_active:
        raise ActorRejected("inactive_account")
    if not actor.user_id:
        raise ActorRejected("missing_user_id")
    if not actor.can_approve:
        raise ActorRejected("employee_cannot_approve")
    if actor.is_admin:
        raise ActorRejected("admin_cannot_substitute_tom")
    if actor.role != EXPECTED_ROLE[TOM]:
        raise ActorRejected("wrong_role")
    if actor.department_id != HOME_DEPARTMENT[TOM]:
        raise ActorRejected("wrong_department")
    if person_from_email(actor.email) != TOM:
        raise ActorRejected("wrong_named_identity")
    return TOM
