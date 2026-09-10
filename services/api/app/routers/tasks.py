"""Celery task status endpoint. JWT required; does not weaken incident auth."""

from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.celery_app import celery_app
from app.core.deps import get_current_user
from app.db.database import get_engine
from app.models import TaskFailure
from app.schemas.tasks import TaskStatusResponse
from app.schemas.user import UserInDB
from app.storage import load_task_result

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Assignment API contract is lowercase. RETRY is an in-flight backoff, not a
# distinct exposed lifecycle state.
_CELERY_STATUS_MAP = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "STARTED": "started",
    "SUCCESS": "success",
    "FAILURE": "failure",
    "RETRY": "pending",
    "REVOKED": "failure",
}


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    _current_user: UserInDB = Depends(get_current_user),
) -> TaskStatusResponse:
    """Protected: current Celery state and result when the task has finished."""
    cached = load_task_result(task_id)
    if cached is not None:
        return TaskStatusResponse(task_id=task_id, status="success", result=cached)

    with Session(get_engine()) as session:
        failure = session.exec(
            select(TaskFailure).where(TaskFailure.task_id == task_id)
        ).first()
    if failure is not None:
        return TaskStatusResponse(task_id=task_id, status="failure", result=None)

    async_result = AsyncResult(task_id, app=celery_app)
    status = _CELERY_STATUS_MAP.get(async_result.state, "pending")
    payload = None
    if status == "success":
        payload = async_result.result
    return TaskStatusResponse(task_id=task_id, status=status, result=payload)
