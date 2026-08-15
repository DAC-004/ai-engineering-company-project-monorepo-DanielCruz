"""Reusable FastAPI authentication dependencies (OAuth2 bearer + get_current_user)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import JWTError, decode_access_token
from app.schemas.user import UserInDB, UserRole
from app.services import user_service

# tokenUrl points at the JSON/form login route so /docs Authorize uses /auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """
    Extract the bearer token, validate/decode the JWT, and load the TinyDB user.

    Any missing, malformed, expired, or otherwise unusable authentication yields 401.
    """
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id or not isinstance(user_id, str):
            raise CREDENTIALS_EXCEPTION
    except JWTError as exc:
        raise CREDENTIALS_EXCEPTION from exc

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    return user


def require_self_or_admin(
    *,
    target_user_id: str,
    current_user: UserInDB,
) -> None:
    """Raise 403 when an authenticated caller is neither the resource owner nor an admin."""
    if current_user.id == target_user_id:
        return
    if current_user.role == UserRole.admin:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this resource",
    )
