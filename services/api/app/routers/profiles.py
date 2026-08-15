"""Profile self-service routes under /profiles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.schemas.profile import ProfilePublic, ProfileUpdate
from app.schemas.user import UserInDB
from app.services import profile_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfilePublic)
def read_my_profile(current_user: UserInDB = Depends(get_current_user)) -> ProfilePublic:
    """Return the Profile associated with the authenticated caller."""
    profile = profile_service.get_profile_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.put("/me", response_model=ProfilePublic)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: UserInDB = Depends(get_current_user),
) -> ProfilePublic:
    """
    Update name/phone/address for the authenticated user's own Profile.

    Only the profile owner can reach this path (scoped to /me + bearer identity).
    """
    updated = profile_service.update_profile_for_user(current_user.id, payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return updated
