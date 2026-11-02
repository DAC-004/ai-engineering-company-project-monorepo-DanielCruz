"""Demonstration identities for the three CONTEXT department owners.

These accounts are not verified identities of real people. The email is only
the lookup key. Authorization uses the TinyDB user id stored on
rfp_department_account. The password comes from the environment and is not logged.
"""

from __future__ import annotations

import logging
import os

from sqlmodel import Session

logger = logging.getLogger(__name__)

from app.access.catalog import RFP_DEPARTMENT_TO_PLATFORM
from app.rfp_models import RfpDepartmentAccount
from app.schemas.user import UserCreate, UserRole
from app.services import user_service


def demonstration_password() -> str:
    """Return the demonstration password from the environment.

    An empty value refuses account creation. The password is not stored in
    source and is not written to logs.
    """
    value = os.environ.get("RFP_DEMONSTRATION_PASSWORD", "").strip()
    if len(value) < 12:
        raise RuntimeError(
            "RFP_DEMONSTRATION_PASSWORD must be set before demonstration accounts are created."
        )
    return value

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
    """Create each missing account once and bind its id when no binding exists.

    An existing user keeps its id, credentials, role, and department. An existing
    RFP department-owner binding is left in place. Specialized seed identities use
    different emails and are not selected here.

    When the password is not configured, no account is created and no password
    is invented. Callers that need the accounts set ``RFP_DEMONSTRATION_PASSWORD``.
    """
    configured = os.environ.get("RFP_DEMONSTRATION_PASSWORD", "").strip()
    if len(configured) < 12:
        logger.info("rfp_demonstration_accounts result=skipped reason=password_not_configured")
        return
    for spec in DEMONSTRATION_ACCOUNTS:
        existing_user = user_service.get_user_by_email(spec["email"])
        if existing_user is None:
            platform_department = RFP_DEPARTMENT_TO_PLATFORM[spec["department_id"]]
            existing_user = user_service.create_user(
                UserCreate(email=spec["email"], password=demonstration_password()),
                role=UserRole.supervisor,
                department_id=platform_department,
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
