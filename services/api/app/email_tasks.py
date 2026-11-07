"""Independent reset-mail worker. No recipient/token in Celery task arguments."""

from __future__ import annotations
import logging
from app.celery_app import celery_app
from app.services import email_outbox, email_service
from app.services import user_service
from app.services.password_reset_service import _load_valid_token_row, InvalidResetTokenError
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.email_tasks.deliver_reset_email",
    max_retries=2,
    acks_late=True,
    reject_on_worker_lost=True,
)
def deliver_reset_email(self, operation_id):
    payload = email_outbox.claim(operation_id)
    if payload is None:
        return {"operation_id": operation_id, "claimed": False}
    try:
        user = user_service.get_user_by_id(payload["user_id"])
        if user is None or not user.is_active or user.email != payload["to_email"]:
            raise InvalidResetTokenError("invalidated")
        raw_token = parse_qs(urlparse(payload["reset_url"]).query).get("token", [""])[0]
        _load_valid_token_row(raw_token)
    except InvalidResetTokenError:
        email_outbox.fail(operation_id, "reset_invalidated", permanent=True)
        return {"operation_id": operation_id, "state": "failed"}
    try:
        provider_id = email_service.send_password_reset_email(
            to_email=payload["to_email"],
            reset_url=payload["reset_url"],
            idempotency_key="healthcore-reset-" + operation_id,
        )
    except email_service.EmailDeliveryError:
        delay = email_outbox.fail(operation_id)
        state = email_outbox.public_status(operation_id)
        logger.warning(
            "email_delivery operation=%s attempts=%s state=%s",
            operation_id,
            state["attempts"],
            state["state"],
        )
        if delay is not None:
            raise self.retry(countdown=delay, exc=RuntimeError("provider_unavailable"))
        return {"operation_id": operation_id, "state": "failed"}
    email_outbox.complete(operation_id, provider_id)
    logger.info(
        "email_delivery operation=%s attempts=%s state=completed",
        operation_id,
        email_outbox.public_status(operation_id)["attempts"],
    )
    return {"operation_id": operation_id, "state": "completed"}


@celery_app.task(name="app.email_tasks.dispatch_pending_email")
def dispatch_pending_email():
    ids = email_outbox.pending_jobs()
    for operation_id in ids:
        deliver_reset_email.apply_async(args=[operation_id], task_id=operation_id, queue="email")
    return {"dispatched": len(ids)}
