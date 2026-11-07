"""Onboarding HTTP surface. Graph work is enqueued as a background task."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.access.catalog import Capability, has_capability
from app.access.permissions import require_authenticated
from app.celery_app import celery_app
from app.schemas.onboarding import (
    AccessRequestBody,
    CheckSubmitRequest,
    DecisionRequest,
    OnboardingStartRequest,
    PeopleReceiptRequest,
    QuestionRequest,
)
from app.schemas.user import UserInDB
from app.onboarding_tasks import run_onboarding_event, start_onboarding_task
from app.services.onboarding_service import actor_from_user, get_runtime
from agents.onboarding_orchestrator.runtime import OnboardingError, validate_start_spec
from agents.onboarding_orchestrator.sensitive import SensitiveDataError
from celery.result import AsyncResult

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_HUMAN_APPROVAL_KINDS = frozenset({"compliance_approval", "manager_approval", "closure"})


def _unwrap(exc: BaseException) -> BaseException:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, (OnboardingError, SensitiveDataError)):
            return current
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return exc


def _http(error: OnboardingError) -> HTTPException:
    mapping = {
        "unauthorized_approver": status.HTTP_403_FORBIDDEN,
        "unauthorized_actor": status.HTTP_403_FORBIDDEN,
        "not_own_onboarding": status.HTTP_403_FORBIDDEN,
        "unknown_onboarding": status.HTTP_404_NOT_FOUND,
        "patient_system_before_compliance_approval": status.HTTP_403_FORBIDDEN,
        "stale_or_duplicate_decision": status.HTTP_409_CONFLICT,
        "unexpected_event": status.HTTP_409_CONFLICT,
        "sensitive_data_excluded": status.HTTP_400_BAD_REQUEST,
        "invalid_office": status.HTTP_400_BAD_REQUEST,
        "invalid_framework": status.HTTP_400_BAD_REQUEST,
        "framework_office_mismatch": status.HTTP_400_BAD_REQUEST,
        "invalid_role_key": status.HTTP_400_BAD_REQUEST,
        "invalid_department": status.HTTP_400_BAD_REQUEST,
    }
    return HTTPException(status_code=mapping.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.code)


def _is_people(user: UserInDB, record: dict[str, Any] | None = None) -> bool:
    if user.department_id == "people_workforce":
        return True
    if record and user.id == record.get("diane_user_id"):
        return True
    return False


def _can_read(user: UserInDB, record: dict[str, Any]) -> bool:
    if user.id == record["hire_user_id"]:
        return True
    if user.id == record["manager_user_id"]:
        return True
    if user.id == record["claire_user_id"]:
        return True
    if _is_people(user, record):
        return True
    return False


def _accepted(task_id: str, onboarding_id: str) -> dict[str, Any]:
    return {
        "accepted": True,
        "task_id": task_id,
        "onboarding_id": onboarding_id,
        "actor_type": "automated_process",
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_onboarding(
    payload: OnboardingStartRequest,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    if current_user.department_id != "people_workforce":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="people_team_only")
    spec = payload.model_dump()
    spec["onboarding_id"] = spec.get("onboarding_id") or uuid4().hex
    try:
        validate_start_spec(spec)
    except OnboardingError as error:
        raise _http(error) from error
    async_result = start_onboarding_task.delay(spec)
    return _accepted(str(async_result.id), spec["onboarding_id"])


@router.get("")
def list_onboardings(current_user: UserInDB = Depends(require_authenticated)) -> list[dict[str, Any]]:
    runtime = get_runtime()
    rows = runtime.people_list()
    if current_user.department_id == "people_workforce":
        return rows
    visible: list[dict[str, Any]] = []
    for row in rows:
        record = runtime.current(row["onboarding_id"])
        if current_user.id in {record["manager_user_id"], record["claire_user_id"], record["diane_user_id"]}:
            visible.append(row)
    return visible


@router.get("/me")
def my_onboarding(current_user: UserInDB = Depends(require_authenticated)) -> dict[str, Any]:
    runtime = get_runtime()
    mine = [row for row in runtime.store.list_all() if row["hire_user_id"] == current_user.id]
    if not mine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_onboarding")
    return runtime.hire_view(mine[0]["onboarding_id"], current_user.id)


@router.get("/jobs/{task_id}")
def get_onboarding_job(
    task_id: str,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    backend = str(celery_app.conf.result_backend or "")
    if backend.startswith("redis://") or backend.startswith("rediss://"):
        if celery_app.conf.task_always_eager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="eager_result_backend_misconfigured",
            )
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "state": str(result.state),
        "ready": bool(result.ready()),
        "actor_type": "automated_process",
    }


@router.get("/{onboarding_id}")
def get_onboarding(
    onboarding_id: str,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    runtime = get_runtime()
    try:
        record = runtime.current(onboarding_id)
    except OnboardingError as error:
        raise _http(error) from error
    if not _can_read(current_user, record):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_authorized")
    if current_user.id == record["hire_user_id"]:
        return runtime.hire_view(onboarding_id, current_user.id)
    return record


def _enqueue_event(onboarding_id: str, event: dict[str, Any], user: UserInDB) -> dict[str, Any]:
    runtime = get_runtime()
    actor = actor_from_user(user)
    try:
        record = runtime.assert_event_allowed(onboarding_id, event, actor)
    except OnboardingError as error:
        raise _http(error) from error
    except SensitiveDataError as error:
        raise HTTPException(status_code=400, detail="sensitive_data_excluded") from error
    if record["pending_kind"] in _HUMAN_APPROVAL_KINDS:
        if not has_capability(user.role, Capability.approve_department_record):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="unauthorized_approver")
    try:
        async_result = run_onboarding_event.delay(onboarding_id, event, actor)
    except Exception as error:
        unwrapped = _unwrap(error)
        if isinstance(unwrapped, OnboardingError):
            raise _http(unwrapped) from error
        if isinstance(unwrapped, SensitiveDataError):
            raise HTTPException(status_code=400, detail="sensitive_data_excluded") from error
        raise
    return _accepted(str(async_result.id), onboarding_id)


@router.post("/{onboarding_id}/paperwork", status_code=status.HTTP_202_ACCEPTED)
def submit_paperwork(
    onboarding_id: str,
    payload: PeopleReceiptRequest,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    event = {
        "type": "people_receipt",
        "documents_received": payload.documents_received,
        "background_check_completed": payload.background_check_completed,
        "decision_nonce": payload.decision_nonce,
    }
    return _enqueue_event(onboarding_id, event, current_user)


@router.post("/{onboarding_id}/check", status_code=status.HTTP_202_ACCEPTED)
def submit_check(
    onboarding_id: str,
    payload: CheckSubmitRequest,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    return _enqueue_event(
        onboarding_id,
        {"type": "submit_check", "answers": payload.answers, "decision_nonce": payload.decision_nonce},
        current_user,
    )


@router.post("/{onboarding_id}/decision", status_code=status.HTTP_202_ACCEPTED)
def submit_decision(
    onboarding_id: str,
    payload: DecisionRequest,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    return _enqueue_event(
        onboarding_id,
        {
            "type": "human_decision",
            "decision": payload.decision,
            "comment": payload.comment,
            "decision_nonce": payload.decision_nonce,
        },
        current_user,
    )


@router.post("/{onboarding_id}/questions")
def ask_question(
    onboarding_id: str,
    payload: QuestionRequest,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        return get_runtime().ask(onboarding_id, payload.question, current_user.id)
    except OnboardingError as error:
        raise _http(error) from error
    except SensitiveDataError as error:
        raise HTTPException(status_code=400, detail="sensitive_data_excluded") from error


@router.post("/{onboarding_id}/access-requests", status_code=status.HTTP_202_ACCEPTED)
def request_access(
    onboarding_id: str,
    payload: AccessRequestBody,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    try:
        row = get_runtime().request_access(onboarding_id, payload.system_id, current_user.id)
    except OnboardingError as error:
        raise _http(error) from error
    return {"accepted": True, "request": row, "actor_type": "automated_process"}


@router.post("/{onboarding_id}/deadlines/tick")
def tick_deadlines(
    onboarding_id: str,
    current_user: UserInDB = Depends(require_authenticated),
) -> dict[str, Any]:
    record = get_runtime().current(onboarding_id)
    if not _is_people(current_user, record) and current_user.id not in {
        record["manager_user_id"],
        record["claire_user_id"],
        record["diane_user_id"],
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_authorized")
    notices = get_runtime().process_deadlines(onboarding_id)
    return {"notices": notices, "actor_type": "automated_process"}
