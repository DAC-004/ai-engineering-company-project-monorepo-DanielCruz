"""User account routes under /users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user, require_self_or_admin
from app.schemas.user import UserCreate, UserInDB, UserPublic, UserRole, UserUpdate
from app.services import profile_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


def _to_public(user: UserInDB) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate) -> UserPublic:
    """
    Public registration.

    Passwords are hashed before persistence. Role defaults to `user`.
    Optional name/phone/address create the linked Profile in the same operation.
    """
    try:
        user = user_service.create_user(payload, role=UserRole.user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # Always create the linked Profile so the 1:1 relationship is established.
    # Optional registration fields seed display/contact data on Profile, not User.
    profile_service.create_profile(
        user_id=user.id,
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
    )
    return _to_public(user)


@router.get("", response_model=list[UserPublic])
def list_users(_current_user: UserInDB = Depends(get_current_user)) -> list[UserPublic]:
    return [_to_public(user) for user in user_service.list_users()]


@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: str,
    _current_user: UserInDB = Depends(get_current_user),
) -> UserPublic:
    user = user_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_public(user)


@router.put("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
) -> UserPublic:
    """Update credential/account fields; caller must be the user themselves or an admin."""
    require_self_or_admin(target_user_id=user_id, current_user=current_user)

    # Non-admins may not escalate their own role.
    if payload.role is not None and current_user.role != UserRole.admin:
        if current_user.id == user_id and payload.role != current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an admin can change roles",
            )

    try:
        updated = user_service.update_user(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_public(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """Delete a user and the linked Profile. Requires self or admin."""
    require_self_or_admin(target_user_id=user_id, current_user=current_user)

    if not user_service.get_user_by_id(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile_service.delete_profile_for_user(user_id)
    user_service.delete_user(user_id)
