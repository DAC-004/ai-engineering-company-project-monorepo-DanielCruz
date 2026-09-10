"""Celery tasks for HealthCore incident analysis. Queue payloads are identifiers only."""

from __future__ import annotations

import logging
import time

from app.celery_app import DEAD_LETTER_QUEUE, celery_app
from app.incidents_store import save_analysis
from app.storage import load_task_result, load_upload, save_task_result
from app.task_failures import record_terminal_failure
from shared.incident_analyzer import analyze_csv_bytes

logger = logging.getLogger(__name__)

# Third consecutive failure is terminal even though max_retries=3 would allow
# a fourth Celery retry (initial + 3). Attempt number is retries + 1.
_TERMINAL_ATTEMPT = 3


def _countdown_seconds(attempt: int) -> int:
    """Exponential backoff: 2s after attempt 1, 4s after attempt 2. Never zero."""
    return 2 ** attempt


@celery_app.task(name="app.tasks.record_dead_letter")
def record_dead_letter(task_id: str, attempt: int, error_message: str) -> dict[str, str | int]:
    """
    Lightweight DLQ payload. The analysis worker does not consume `dead_letter`,
    so this message remains queued for inspection unless a separate consumer runs.
    """
    return {
        "task_id": task_id,
        "attempt": attempt,
        "error_message": error_message,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.analyze_incidents_task",
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=120,
)
def analyze_incidents_task(self, upload_id: str) -> dict:
    """
    Analyze a previously stored incident CSV referenced only by upload_id.

    Success and terminal-failure side effects are idempotent so late acknowledgement
    or worker loss cannot duplicate last-analysis files or TaskFailure/DLQ records.
    """
    task_id = str(self.request.id)
    attempt = int(self.request.retries or 0) + 1
    started = time.perf_counter()

    def _duration_ms() -> float:
        return (time.perf_counter() - started) * 1000

    cached = load_task_result(task_id)
    if cached is not None:
        # Do not rewrite last.json: the operator may have cleared GET /results.
        logger.info(
            "task_id=%s attempt=%s status=%s duration_ms=%.1f",
            task_id,
            attempt,
            "success",
            _duration_ms(),
        )
        return cached

    try:
        csv_path, meta = load_upload(upload_id)
        source_name = str(meta.get("source_name") or "upload.csv")
        owner_user_id = str(meta.get("owner_user_id") or "")
        csv_bytes = csv_path.read_bytes()
        result = analyze_csv_bytes(csv_bytes, source_name=source_name)
        payload = result.to_dict()
        # Persist the per-task cache first so a redelivered success returns this
        # payload without re-running analysis or restoring a deleted last.json.
        save_task_result(task_id, payload)
        save_analysis(result, owner_user_id=owner_user_id)
        logger.info(
            "task_id=%s attempt=%s status=%s duration_ms=%.1f",
            task_id,
            attempt,
            "success",
            _duration_ms(),
        )
        return payload
    except Exception as exc:
        error_message = str(exc)
        logger.error(
            "task_id=%s attempt=%s status=%s duration_ms=%.1f error=%s",
            task_id,
            attempt,
            "failure",
            _duration_ms(),
            error_message,
            exc_info=True,
        )
        if attempt >= _TERMINAL_ATTEMPT:
            created = record_terminal_failure(
                task_id=task_id,
                attempt=attempt,
                error_message=error_message,
            )
            if created:
                record_dead_letter.apply_async(
                    args=[task_id, attempt, error_message],
                    queue=DEAD_LETTER_QUEUE,
                )
            raise
        raise self.retry(exc=exc, countdown=_countdown_seconds(attempt)) from exc
