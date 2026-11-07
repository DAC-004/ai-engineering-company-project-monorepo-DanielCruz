"""Celery tick and queued close jobs. Internal outbox only."""

from __future__ import annotations

from app.celery_app import celery_app


@celery_app.task(name="app.tasks_financial_close.tick_financial_close")
def tick_financial_close() -> dict:
    from app.services.financial_close_service import tick

    return tick()


@celery_app.task(bind=True, name="app.tasks_financial_close.run_financial_close_job")
def run_financial_close_job(self, job_id: str) -> dict:
    from app.services.financial_close_service import execute_queued_job

    return execute_queued_job(job_id, celery_task_id=self.request.id)
