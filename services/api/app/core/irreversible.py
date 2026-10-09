"""Explicit confirmation for an irreversible HTTP action.

The header is a server precondition. It is sent only after a person takes the
confirming action in the calling workflow. The log records the action name
and the result. It does not record the target id or the request body.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

CONFIRM_HEADER = "X-HealthCore-Confirm"
CONFIRM_VALUE = "confirmed"
CONFIRM_FLAG = "--confirm"


def confirmation_headers(argv: list[str]) -> dict[str, str]:
    """Return the confirmation header only when the operator passed ``--confirm``.

    An acceptance script must not attach this header by itself. The person
    running the script passes the flag when that run is allowed to delete.
    """
    if CONFIRM_FLAG in argv:
        return {CONFIRM_HEADER: CONFIRM_VALUE}
    return {}


def require_explicit_confirmation(request: Request, action_name: str) -> None:
    """Stop the action unless the confirmation header is exactly ``confirmed``."""
    provided = request.headers.get(CONFIRM_HEADER, "")
    if provided != CONFIRM_VALUE:
        logger.info("irreversible_action action=%s result=rejected_unconfirmed", action_name)
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="This irreversible action requires explicit confirmation.",
        )
    logger.info("irreversible_action action=%s result=confirmed", action_name)
