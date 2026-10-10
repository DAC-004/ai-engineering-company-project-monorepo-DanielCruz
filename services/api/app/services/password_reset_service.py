"""
Password-reset credential lifecycle (AUTH-03).

Implementation decision (not a rubric mandate): store an opaque random token's
SHA-256 hash in TinyDB with expiry and used_at so one-time use is enforceable.
A JWT with only exp cannot satisfy the consumed-token rule by itself.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tinydb import Query

from app.core.config import get_settings
from app.core.security import verify_password
from app.db.tinydb import password_reset_tokens_table
from app.schemas.user import UserInDB, UserUpdate
from app.services import email_service, user_service
from app.services.email_service import EmailDeliveryError

logger = logging.getLogger(__name__)


class InvalidResetTokenError(ValueError):
    """Reset credential is missing, expired, forged, or already consumed."""


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _parse_expiry(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        expires = value
    else:
        expires = datetime.fromisoformat(value)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires.astimezone(UTC)


def create_reset_token_for_user(user: UserInDB) -> str:
    """
    Create a one-time reset credential for the user and persist only its hash.

    Returns the raw token for inclusion in the emailed reset URL.
    Prior unused tokens for the same user are marked used so only the latest works.
    """
    settings = get_settings()
    table = password_reset_tokens_table()
    Token = Query()
    now = datetime.now(UTC)

    # Invalidate outstanding unused tokens for this account (single active reset).
    outstanding = table.search(
        (Token.user_id == user.id) & (Token.used_at == None)  # noqa: E711
    )
    for row in outstanding:
        table.update({"used_at": now.isoformat()}, doc_ids=[row.doc_id])

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=settings.password_reset_token_expire_minutes)
    table.insert(
        {
            "id": str(uuid4()),
            "user_id": user.id,
            "token_hash": _hash_token(raw_token),
            "expires_at": expires_at.isoformat(),
            "used_at": None,
            "created_at": now.isoformat(),
        }
    )
    return raw_token


def build_reset_url(raw_token: str) -> str:
    settings = get_settings()
    return f"{settings.frontend_base_url}/reset-password?token={raw_token}"


def request_password_reset(email: str) -> None:
    """
    Start forgot-password for an email when the account exists.

    Callers must always return HTTP 200 regardless of whether a user was found.
    Email provider failures are logged; they must not change the public response
    shape in a way that reveals account existence.
    """
    user = user_service.get_user_by_email(email)
    if user is None or not user.is_active:
        return

    raw_token = create_reset_token_for_user(user)
    reset_url = build_reset_url(raw_token)
    try:
        email_service.send_password_reset_email(
            to_email=user.email,
            reset_url=reset_url,
        )
    except EmailDeliveryError:
        # Keep outward behavior identical for registered vs unregistered emails.
        logger.exception(
            "Password-reset email could not be delivered for a registered account"
        )


def _load_valid_token_row(raw_token: str) -> dict:
    """Return the TinyDB row for a still-valid unused token, or raise."""
    if not raw_token.strip():
        raise InvalidResetTokenError("Invalid or expired reset token")

    table = password_reset_tokens_table()
    Token = Query()
    row = table.get(Token.token_hash == _hash_token(raw_token))
    if row is None:
        raise InvalidResetTokenError("Invalid or expired reset token")

    if row.get("used_at") is not None:
        raise InvalidResetTokenError("Invalid or expired reset token")

    expires_at = _parse_expiry(row["expires_at"])
    if datetime.now(UTC) >= expires_at:
        raise InvalidResetTokenError("Invalid or expired reset token")

    return row


def reset_password_with_token(*, token: str, new_password: str) -> None:
    """Validate the reset credential, update the password hash, and consume the token."""
    row = _load_valid_token_row(token)
    user = user_service.get_user_by_id(row["user_id"])
    if user is None or not user.is_active:
        raise InvalidResetTokenError("Invalid or expired reset token")

    updated = user_service.update_user(
        user.id,
        UserUpdate(password=new_password),
    )
    if updated is None:
        raise InvalidResetTokenError("Invalid or expired reset token")

    # Persist consumption after password update so a crash mid-flight still leaves
    # the token usable only until expiry; successful path marks it used once.
    password_reset_tokens_table().update(
        {"used_at": datetime.now(UTC).isoformat()},
        doc_ids=[row.doc_id],
    )


def change_password(
    *,
    user: UserInDB,
    current_password: str,
    new_password: str,
) -> None:
    """Replace the authenticated user's password after verifying the current one."""
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")

    # user_service.update_user hashes via bcrypt — never store plaintext.
    updated = user_service.update_user(user.id, UserUpdate(password=new_password))
    if updated is None:
        raise ValueError("Unable to update password")
