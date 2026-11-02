"""Admin-only catalog of platform roles and departments."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.access.catalog import DEPARTMENTS, ROLES
from app.access.permissions import require_manage_access
from app.schemas.user import UserInDB

router = APIRouter(prefix="/access", tags=["access"])


@router.get("/roles")
def list_roles(_current_user: UserInDB = Depends(require_manage_access)) -> list[dict[str, str]]:
    return [dict(item) for item in ROLES]


@router.get("/departments")
def list_departments(
    _current_user: UserInDB = Depends(require_manage_access),
) -> list[dict[str, str]]:
    return [dict(item) for item in DEPARTMENTS]
