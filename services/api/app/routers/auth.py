"""Authentication routes under /auth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.schemas.auth import AuthMeResponse, Token
from app.schemas.user import UserInDB
from app.services import profile_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    Validate credentials and return a signed JWT access token.

    OAuth2PasswordRequestForm uses the standard `username` + `password` form fields.
    For this API, `username` is the account email address.
    """
    user = user_service.get_user_by_email(form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token)


@router.get("/me", response_model=AuthMeResponse)
def read_auth_me(current_user: UserInDB = Depends(get_current_user)) -> AuthMeResponse:
    """Return the authenticated user's email, role, and linked Profile."""
    profile = profile_service.get_profile_by_user_id(current_user.id)
    return AuthMeResponse(
        email=current_user.email,
        role=current_user.role,
        profile=profile,
    )
