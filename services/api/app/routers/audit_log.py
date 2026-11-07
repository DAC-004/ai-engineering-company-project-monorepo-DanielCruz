"""Read-only metadata viewer. No append, update, or delete endpoint exists."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.access.catalog import Capability
from app.access.permissions import require_authenticated, assert_capability
from app.schemas.user import UserInDB, UserRole
from app.audit.capture import configured_store
from shared.healthcore_audit.store import AuditError

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


def require_viewer(user: UserInDB = Depends(require_authenticated)):
    assert_capability(user, Capability.read_audit_log)
    if user.role == UserRole.supervisor and not user.department_id:
        raise HTTPException(403, "A department is required")
    return user


@router.get("/integrity")
def integrity(user: UserInDB = Depends(require_viewer)):
    if user.role != UserRole.admin:
        raise HTTPException(403, "Full ledger verification requires Admin")
    try:
        return configured_store().verify()
    except AuditError:
        raise HTTPException(503, "Audit storage unavailable") from None


@router.get("")
def list_events(
    actor_ref: str | None = None,
    action: str | None = None,
    resource_kind: str | None = None,
    resource_ref: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    user: UserInDB = Depends(require_viewer),
):
    try:
        return configured_store().query(
            department_id=user.department_id if user.role == UserRole.supervisor else None,
            actor_ref=actor_ref,
            action=action,
            resource_kind=resource_kind,
            resource_ref=resource_ref,
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None,
            limit=limit,
            offset=offset,
        )
    except ValueError:
        raise HTTPException(422, "Invalid structural filter or date range") from None
    except AuditError:
        raise HTTPException(503, "Audit log integrity/storage check failed") from None
