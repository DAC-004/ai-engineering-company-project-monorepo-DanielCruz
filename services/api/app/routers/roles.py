"""Admin-only role administration at /roles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.access.permissions import require_manage_access
from app.schemas.access_admin import RoleCreate, RolePublic, RoleUpdate
from app.schemas.user import UserInDB
from app.services import access_catalog_service
from app.services.access_catalog_service import (
    AccessCatalogConflictError,
    AccessCatalogNotFoundError,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RolePublic])
def list_roles(_current_user: UserInDB = Depends(require_manage_access)) -> list[RolePublic]:
    return access_catalog_service.list_roles()


@router.post("", response_model=RolePublic, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    _current_user: UserInDB = Depends(require_manage_access),
) -> RolePublic:
    try:
        return access_catalog_service.create_role(payload)
    except AccessCatalogConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{role_id}", response_model=RolePublic)
def get_role(
    role_id: str,
    _current_user: UserInDB = Depends(require_manage_access),
) -> RolePublic:
    try:
        return access_catalog_service.get_role(role_id)
    except AccessCatalogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found") from exc


@router.put("/{role_id}", response_model=RolePublic)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    _current_user: UserInDB = Depends(require_manage_access),
) -> RolePublic:
    try:
        return access_catalog_service.update_role(role_id, payload)
    except AccessCatalogNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found") from exc
