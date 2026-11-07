"""Authenticated caller evidence. Payload names and emails are not identity."""

from __future__ import annotations

from dataclasses import dataclass

from agents.supplier_contracts.identity import (
    KNOWN_DEPARTMENTS,
    SANDRA,
    named_home_department,
)
from agents.supplier_contracts.identity import approver_from_email


class ActorRejected(ValueError):
    pass


@dataclass(frozen=True)
class ActorIdentity:
    user_id: str
    role: str
    department_id: str | None
    email: str
    is_active: bool = True
    is_admin: bool = False
    can_approve: bool = False


def named_approver_from_actor(actor: ActorIdentity) -> str:
    if not actor.is_active:
        raise ActorRejected("inactive_account")
    if not actor.user_id:
        raise ActorRejected("missing_user_id")
    if not actor.can_approve:
        raise ActorRejected("employee_cannot_approve")
    if not actor.department_id:
        raise ActorRejected("missing_department")
    if actor.department_id not in KNOWN_DEPARTMENTS:
        raise ActorRejected("unknown_department")
    identity = approver_from_email(actor.email)
    if identity is None:
        raise ActorRejected("wrong_named_identity")
    home = named_home_department(identity)
    if identity == SANDRA:
        if not actor.is_admin:
            raise ActorRejected("sandra_requires_admin")
        return identity
    if home is None:
        raise ActorRejected("wrong_named_identity")
    if actor.department_id != home and not actor.is_admin:
        raise ActorRejected("wrong_department")
    return identity
