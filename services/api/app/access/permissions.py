"""Centralized role and department permission checks.

Routers depend on these helpers. Insufficient role → 403. Department mismatch
for Employee/Supervisor → 403 on record GET. Admin cross-department access is
a role privilege and does not drop department membership.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.access.catalog import (
    DEPARTMENT_IDS,
    PLATFORM_TO_RFP_DEPARTMENT,
    Capability,
    has_capability,
    is_admin,
    is_known_department,
)
from app.core.deps import get_current_user
from app.schemas.rfp import FinalDocumentPublic, RfpTicketPublic
from app.schemas.user import UserInDB, UserRole

INSUFFICIENT_ROLE_DETAIL = "Insufficient role permissions"
INSUFFICIENT_DEPARTMENT_DETAIL = "Not authorized for this department"
UNKNOWN_DEPARTMENT_DETAIL = "Unknown department"


def require_capability(capability: Capability) -> Callable[..., UserInDB]:
    """FastAPI dependency: authenticated caller must hold `capability`."""

    def dependency(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if not has_capability(current_user.role, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=INSUFFICIENT_ROLE_DETAIL,
            )
        return current_user

    dependency.__name__ = f"require_capability_{capability.value}"
    return dependency


def can_access_department(current_user: UserInDB, department_id: str | None) -> bool:
    """Admin may read/write any department, including untagged rows.

    A missing department on the record or the caller is not a matching
    department for Employee/Supervisor. Untagged incident and supplier rows
    stay unauthorized until ownership is assigned.
    """
    if is_admin(current_user.role):
        return True
    if department_id is None or current_user.department_id is None:
        return False
    return current_user.department_id == department_id


def assert_department_allowed(current_user: UserInDB, department_id: str | None) -> None:
    if not can_access_department(current_user, department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INSUFFICIENT_DEPARTMENT_DETAIL,
        )


def require_departments(*department_ids: str) -> Callable[..., UserInDB]:
    """Require read-department capability and membership, unless Admin."""

    allowed = frozenset(department_ids)
    unknown = allowed - DEPARTMENT_IDS
    if unknown:
        raise ValueError(f"Unknown department ids: {sorted(unknown)}")

    def dependency(
        current_user: UserInDB = Depends(require_capability(Capability.read_department_data)),
    ) -> UserInDB:
        if is_admin(current_user.role):
            return current_user
        if current_user.department_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=INSUFFICIENT_DEPARTMENT_DETAIL,
            )
        return current_user

    dependency.__name__ = "require_departments_" + "_".join(sorted(allowed))
    return dependency


def assert_known_department(department_id: str | None) -> None:
    if not is_known_department(department_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UNKNOWN_DEPARTMENT_DETAIL,
        )


def rfp_department_for_user(current_user: UserInDB) -> str | None:
    if current_user.department_id is None:
        return None
    return PLATFORM_TO_RFP_DEPARTMENT.get(current_user.department_id)


def scoped_rfp_ticket(ticket: RfpTicketPublic, current_user: UserInDB) -> RfpTicketPublic:
    if is_admin(current_user.role):
        return ticket
    rfp_department_id = rfp_department_for_user(current_user)
    if rfp_department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INSUFFICIENT_DEPARTMENT_DETAIL,
        )
    return ticket.model_copy(
        update={
            "sections": [
                section
                for section in ticket.sections
                if section.department_id == rfp_department_id
            ]
        }
    )


def scoped_final_document(
    document: FinalDocumentPublic,
    current_user: UserInDB,
) -> FinalDocumentPublic:
    if is_admin(current_user.role):
        return document
    rfp_department_id = rfp_department_for_user(current_user)
    if rfp_department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INSUFFICIENT_DEPARTMENT_DETAIL,
        )
    visible_sections: list[dict] = []
    for section in document.sections:
        if not isinstance(section, dict):
            continue
        if section.get("department_id") == rfp_department_id:
            visible_sections.append(section)
    return document.model_copy(update={"sections": visible_sections})


def filter_department_rows(
    current_user: UserInDB,
    rows: list,
    department_id_of,
) -> list:
    """List scoping: caller department only; Admin sees all. Not a role-denial 403.

    Null-equality is not a department match. An unassigned caller sees no
    departmental rows; untagged rows are omitted from non-Admin lists.
    """
    if is_admin(current_user.role):
        return rows
    caller_department = current_user.department_id
    if caller_department is None:
        return []
    return [row for row in rows if department_id_of(row) == caller_department]


require_authenticated = require_capability(Capability.authenticated)
require_internal_tools = require_capability(Capability.use_internal_tools)
require_create_record = require_capability(Capability.create_department_record)
require_update_record = require_capability(Capability.update_department_record)
require_approve_record = require_capability(Capability.approve_department_record)
require_delete_sensitive = require_capability(Capability.delete_sensitive_record)
require_manage_users = require_capability(Capability.manage_users)
require_manage_access = require_capability(Capability.manage_access)

require_clinical_operations = require_departments("clinical_operations")
require_technology = require_departments("technology")
require_people_workforce = require_departments("people_workforce")
require_rfp_departments = require_departments(
    "clinical_operations",
    "revenue_cycle",
    "compliance",
)


def capability_values(role: UserRole) -> list[str]:
    from app.access.catalog import capabilities_for

    return sorted(item.value for item in capabilities_for(role))


def assert_capability(current_user: UserInDB, capability: Capability) -> None:
    if not has_capability(current_user.role, capability):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INSUFFICIENT_ROLE_DETAIL,
        )
