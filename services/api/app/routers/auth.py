"""Authentication routes under /auth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    PasswordActionResponse,
    ResetPasswordRequest,
    Token,
)
from app.schemas.user import UserInDB
from app.services import password_reset_service, profile_service, user_service
from app.services.password_reset_service import InvalidResetTokenError

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


@router.post("/forgot-password", response_model=PasswordActionResponse)
def forgot_password(payload: ForgotPasswordRequest) -> PasswordActionResponse:
    """
    Begin password recovery for an email address.

    Always returns HTTP 200 with the same body whether or not the email is registered,
    so the response cannot be used for account enumeration.
    """
    password_reset_service.request_password_reset(str(payload.email))
    return PasswordActionResponse(
        detail="If that address is registered, you'll receive a link shortly",
    )


@router.post("/reset-password", response_model=PasswordActionResponse)
def reset_password(payload: ResetPasswordRequest) -> PasswordActionResponse:
    """Consume a one-time reset token and set a new bcrypt-hashed password."""
    try:
        password_reset_service.reset_password_with_token(
            token=payload.token,
            new_password=payload.new_password,
        )
    except InvalidResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PasswordActionResponse(detail="Password has been reset")


@router.post("/change-password", response_model=PasswordActionResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: UserInDB = Depends(get_current_user),
) -> PasswordActionResponse:
    """Replace the authenticated user's password after verifying the current one."""
    try:
        password_reset_service.change_password(
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PasswordActionResponse(detail="Password has been changed")
