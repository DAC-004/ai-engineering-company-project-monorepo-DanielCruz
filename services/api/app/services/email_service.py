"""Transactional email delivery via Resend (AUTH-03 password-reset mail)."""

from __future__ import annotations

import logging

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when Resend cannot accept or send a message."""


def send_password_reset_email(*, to_email: str, reset_url: str, idempotency_key: str | None = None) -> str | None:
    """
    Send a mobile-readable password-reset email containing the reset link.

    The Resend API key is loaded from RESEND_API_KEY — never hard-coded.
    """
    settings = get_settings()
    api_key = settings.resend_api_key
    if not api_key:
        raise EmailDeliveryError(
            "RESEND_API_KEY is not configured. Set it in services/api/.env."
        )

    resend.api_key = api_key

    # Plain text body stays readable on narrow mobile viewports without HTML.
    text_body = (
        "HealthCore Digital — password reset\n\n"
        "We received a request to reset your password.\n"
        "Open this link on your phone or computer to choose a new password:\n\n"
        f"{reset_url}\n\n"
        "This link expires soon and can only be used once.\n"
        "If you did not request a reset, you can ignore this email.\n"
    )

    try:
        result = resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": "Reset your HealthCore password",
                "text": text_body,
            },
            {"idempotency_key": idempotency_key} if idempotency_key else {},
        )
        provider_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(provider_id, str) or not provider_id:
            raise EmailDeliveryError("Provider acknowledgement unavailable")
        return provider_id
    except Exception:  # noqa: BLE001 — normalize provider failures
        logger.warning("Resend password-reset delivery unavailable")
        raise EmailDeliveryError("Failed to send password-reset email") from None
