"""Demonstration identities for the three CONTEXT department owners.

These accounts are not verified identities of real people. The email is only
the lookup key. Authorization uses the TinyDB user id stored on
rfp_department_account. The password stays in this module and is not logged.
"""

from __future__ import annotations

from sqlmodel import Session

from app.rfp_models import RfpDepartmentAccount
from app.schemas.user import UserCreate, UserRole
from app.services import user_service

DEMONSTRATION_ACCOUNT_PASSWORD = "HealthCoreRfpDemo1!"

DEMONSTRATION_ACCOUNTS: tuple[dict[str, str], ...] = (
    {
        "department_id": "revenue",
        "email": "rfp.revenue.demonstration@healthcore.com",
        "owner_name": "Tom Callahan",
    },
    {
        "department_id": "clinical",
        "email": "rfp.clinical.demonstration@healthcore.com",
        "owner_name": "Dr. Marcus Reid",
    },
    {
        "department_id": "compliance",
        "email": "rfp.compliance.demonstration@healthcore.com",
        "owner_name": "Claire Whitfield",
    },
)


def ensure_demonstration_accounts(session: Session) -> None:
    """Create each account once and bind its id. An existing binding is left in place."""
    for spec in DEMONSTRATION_ACCOUNTS:
        existing_user = user_service.get_user_by_email(spec["email"])
        if existing_user is None:
            existing_user = user_service.create_user(
                UserCreate(email=spec["email"], password=DEMONSTRATION_ACCOUNT_PASSWORD),
                role=UserRole.user,
            )
        binding = session.get(RfpDepartmentAccount, spec["department_id"])
        if binding is None:
            session.add(
                RfpDepartmentAccount(
                    department_id=spec["department_id"],
                    user_id=existing_user.id,
                    owner_name=spec["owner_name"],
                )
            )
    session.commit()
