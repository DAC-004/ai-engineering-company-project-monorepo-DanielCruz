"""Celery application: Redis broker and result backend from REDIS_URL."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from celery import Celery
from celery.signals import worker_process_init
from dotenv import load_dotenv
from kombu import Queue

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from agents.onboarding_orchestrator.deadline_sweep import celery_beat_schedule

load_dotenv(API_DIR / ".env")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DEAD_LETTER_QUEUE = "dead_letter"
DEFAULT_QUEUE = "celery"

celery_app = Celery("healthcore")

# AUTH-01 TestClient sets this so delay() runs in-process without a broker.
_eager = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes")


def _eager_result_backend() -> str:
    """In-process result store for eager/isolated runs. Never Redis.

    Isolated REDIS_URL points at unused loopback port 1. AsyncResult still
    talks to result_backend unless eager results are stored locally with
    task_store_eager_result. This is not evidence of a live worker.
    """
    return "cache+memory://"


_eager_backend = _eager_result_backend() if _eager else REDIS_URL

celery_app.conf.update(
    broker_url="memory://" if _eager else REDIS_URL,
    result_backend=_eager_backend,
    task_store_eager_result=_eager,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_time_limit=120,
    task_always_eager=_eager,
    task_eager_propagates=False,
    task_default_queue=DEFAULT_QUEUE,
    task_create_missing_queues=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_queues=(
        Queue(DEFAULT_QUEUE),
        Queue(DEAD_LETTER_QUEUE),
    ),
    imports=("app.tasks", "app.onboarding_tasks", "app.tasks_supplier_contracts", "app.tasks_financial_close"),
    beat_schedule=celery_beat_schedule(),
    timezone="America/Chicago",
    enable_utc=True,
)

_close_interval = int(os.environ.get("FINANCIAL_CLOSE_BEAT_SECONDS", "0") or "0")
if _close_interval > 0:
    celery_app.conf.beat_schedule.update({
        "financial-close-sweep": {
            "task": "app.tasks_financial_close.tick_financial_close",
            "schedule": _close_interval,
        }
    })
elif os.environ.get("FINANCIAL_CLOSE_ENABLE_CRONTAB", "").strip() in {"1", "true", "yes"}:
    from celery.schedules import crontab

    celery_app.conf.beat_schedule.update({
        "financial-close-third-business-day": {
            "task": "app.tasks_financial_close.tick_financial_close",
            "schedule": crontab(hour=6, minute=0),
        }
    })


_alert_interval = int(os.environ.get("SUPPLIER_CONTRACTS_ALERT_INTERVAL_SECONDS", "0") or "0")
if _alert_interval > 0:
    # Preserve the approved onboarding sweep while adding Task 4 alerts.
    celery_app.conf.beat_schedule.update({
        "supplier-contract-alerts": {
            "task": "app.tasks_supplier_contracts.tick_supplier_contract_alerts",
            "schedule": _alert_interval,
        }
    })


def ensure_broker_connection() -> None:
    """Open Redis broker and result backend so the first 202 enqueue is not a cold handshake."""
    if celery_app.conf.task_always_eager:
        return
    with celery_app.connection_for_write() as connection:
        connection.ensure_connection(max_retries=3)
    celery_app.backend.client.ping()


@worker_process_init.connect
def _init_worker_databases(**_kwargs: object) -> None:
    """Ensure SQLModel tables (including task_failure) exist in the worker process."""
    from app.db.database import init_databases

    init_databases()
