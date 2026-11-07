"""Password hashing (libpass/bcrypt) and JWT helpers (python-jose)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# libpass is the installed package; it exposes the passlib API surface.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Linking requires this claim to equal AUTH_METHOD_PASSWORD. Missing/unknown
# values are not treated as traditional and do not revoke ordinary access.
AUTH_METHOD_CLAIM = "auth_method"
AUTH_METHOD_PASSWORD = "password"
AUTH_METHOD_MICROSOFT = "microsoft"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt. Never persist the plaintext."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(*, subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Sign a JWT whose `sub` is the TinyDB user id and whose expiry comes from env config."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT; raises JWTError on failure."""
    settings = get_settings()
    # Sign only with the active key; accept bounded retired keys during a
    # rolling rotation window. No unsigned claim influences key selection.
    keys = [settings.secret_key] + [key.strip() for key in settings.jwt_previous_secret_keys.split(",") if key.strip()]
    for key in keys[:4]:
        try:
            return jwt.decode(token, key, algorithms=[settings.jwt_algorithm])
        except JWTError:
            continue
    raise JWTError("Invalid or expired access token")


__all__ = [
    "AUTH_METHOD_CLAIM",
    "AUTH_METHOD_MICROSOFT",
    "AUTH_METHOD_PASSWORD",
    "JWTError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
