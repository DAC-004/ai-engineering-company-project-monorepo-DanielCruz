"""Password hashing and JWT helpers in app.core.security."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import (
    JWTError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_create_and_decode_access_token_round_trip() -> None:
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert "exp" in payload


def test_matching_password_verifies() -> None:
    hashed = hash_password("SecurePass1!")
    assert hashed != "SecurePass1!"
    assert verify_password("SecurePass1!", hashed) is True


def test_extra_claims_survive_decoding() -> None:
    token = create_access_token(subject="user-123", extra_claims={"role": "user"})
    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["role"] == "user"


def test_expired_token_raises_jwt_error() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": "user-123",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(JWTError):
        decode_access_token(expired)


def test_incorrect_password_does_not_verify() -> None:
    hashed = hash_password("SecurePass1!")
    assert verify_password("WrongPass1!", hashed) is False
