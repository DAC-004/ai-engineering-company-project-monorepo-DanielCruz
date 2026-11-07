"""Admin-only metadata status and durable dead letters; no email/token payloads."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.access.permissions import require_manage_users
from app.schemas.user import UserInDB
from app.services import email_outbox

router = APIRouter(prefix="/tasks/email", tags=["email-jobs"])


@router.get("/dead-letters")
def list_dead_letters(_user: UserInDB = Depends(require_manage_users)):
    return {"items": email_outbox.dead_letters()}


@router.get("/{operation_id}")
def email_status(operation_id: UUID, _user: UserInDB = Depends(require_manage_users)):
    result = email_outbox.public_status(str(operation_id))
    if result is None:
        raise HTTPException(404, "Email operation not found")
    return result
