"""User account routes under /users. Create and list are Admin-only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.access.permissions import (
    INSUFFICIENT_ROLE_DETAIL,
    assert_known_department,
    require_authenticated,
    require_manage_users,
)
from app.core.irreversible import require_explicit_confirmation
from app.core.deps import require_self_or_admin
from app.schemas.access_admin import UserAdminCreate, UserAssignmentUpdate
from app.schemas.user import UserCreate, UserInDB, UserPublic, UserRole, UserUpdate
from app.services import profile_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


def _to_public(user: UserInDB) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        role_id=user.role,
        department_id=user.department_id,
        created_at=user.created_at,
    )


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserAdminCreate,
    _current_user: UserInDB = Depends(require_manage_users),
) -> UserPublic:
    """Admin-only user administration. Role and department are independent when supplied."""
    if payload.department_id is not None:
        assert_known_department(payload.department_id)
    create_payload = UserCreate(
        email=payload.email,
        password=payload.password,
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
    )
    role = payload.role_id if payload.role_id is not None else UserRole.employee
    try:
        user = user_service.create_user(
            create_payload,
            role=role,
            department_id=payload.department_id,
        )
    except ValueError as exc:
        message = str(exc)
        code = (
            status.HTTP_400_BAD_REQUEST
            if message == "Unknown department"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=message) from exc

    profile_service.create_profile(
        user_id=user.id,
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
    )
    return _to_public(user)


@router.get("", response_model=list[UserPublic])
def list_users(_current_user: UserInDB = Depends(require_manage_users)) -> list[UserPublic]:
    return [_to_public(user) for user in user_service.list_users()]


@router.patch("/{user_id}/assignment", response_model=UserPublic)
def patch_user_assignment(
    user_id: str,
    payload: UserAssignmentUpdate,
    _current_user: UserInDB = Depends(require_manage_users),
) -> UserPublic:
    """Change role_id and/or department_id independently. Omitted fields stay unchanged."""
    if "department_id" in payload.model_fields_set:
        assert_known_department(payload.department_id)
    updates_payload: dict[str, object] = {}
    if "role_id" in payload.model_fields_set:
        updates_payload["role"] = payload.role_id
    if "department_id" in payload.model_fields_set:
        updates_payload["department_id"] = payload.department_id
    try:
        updated = user_service.update_user(user_id, UserUpdate.model_validate(updates_payload))
    except ValueError as exc:
        message = str(exc)
        code = (
            status.HTTP_400_BAD_REQUEST
            if message == "Unknown department"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=message) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_public(updated)


@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: str,
    current_user: UserInDB = Depends(require_authenticated),
) -> UserPublic:
    require_self_or_admin(target_user_id=user_id, current_user=current_user)
    user = user_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_public(user)


@router.put("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: UserInDB = Depends(require_authenticated),
) -> UserPublic:
    """Update credential/account fields; caller must be the user themselves or an admin."""
    require_self_or_admin(target_user_id=user_id, current_user=current_user)

    access_fields_set = payload.model_fields_set.intersection({"role", "department_id"})
    if access_fields_set and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INSUFFICIENT_ROLE_DETAIL,
        )
    if "department_id" in payload.model_fields_set:
        assert_known_department(payload.department_id)

    try:
        updated = user_service.update_user(user_id, payload)
    except ValueError as exc:
        message = str(exc)
        code = (
            status.HTTP_400_BAD_REQUEST
            if message == "Unknown department"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=message) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_public(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    request: Request,
    current_user: UserInDB = Depends(require_authenticated),
) -> None:
    """Delete a user and the linked Profile. Requires self or admin and confirmation."""
    require_self_or_admin(target_user_id=user_id, current_user=current_user)
    require_explicit_confirmation(request, "delete_user")

    if not user_service.get_user_by_id(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile_service.delete_profile_for_user(user_id)
    user_service.delete_user(user_id)
