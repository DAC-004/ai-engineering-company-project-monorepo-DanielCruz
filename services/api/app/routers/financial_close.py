"""Authenticated financial-close reviewer routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from agents.financial_close.identity import ActorRejected
from agents.financial_close.review import ReviewError
from agents.financial_close.store import StaleDraftError
from app.access.permissions import require_capability
from app.access.catalog import Capability
from app.schemas.financial_close import FinancialCloseApproval
from app.schemas.user import UserInDB
from app.services import financial_close_service as service

router = APIRouter(prefix="/financial-close", tags=["financial-close"])
require_reader = require_capability(Capability.read_department_data)


def _http_for(exc: Exception) -> HTTPException:
    if isinstance(exc, (service.UntrustedApproverError, ActorRejected)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Named review was not accepted.")
    if isinstance(exc, StaleDraftError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The draft approval is no longer valid.")
    if isinstance(exc, ReviewError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The review could not be applied.")
    if isinstance(exc, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested record was not found.")
    raise exc


@router.get("/drafts")
def read_drafts(current_user: UserInDB = Depends(require_reader)) -> list[dict]:
    return service.list_drafts(service.actor_from_user(current_user))


@router.get("/drafts/{draft_id}")
def read_draft(draft_id: str, current_user: UserInDB = Depends(require_reader)) -> dict:
    try:
        return service.get_draft(service.actor_from_user(current_user), draft_id)
    except Exception as exc:
        raise _http_for(exc) from exc


@router.get("/drafts/{draft_id}/figures/{figure_id}")
def read_figure(draft_id: str, figure_id: str, current_user: UserInDB = Depends(require_reader)) -> dict:
    try:
        return service.lookup_figure(service.actor_from_user(current_user), draft_id, figure_id)
    except Exception as exc:
        raise _http_for(exc) from exc


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def run_close(current_user: UserInDB = Depends(require_reader)) -> dict:
    try:
        return service.queue_run(service.actor_from_user(current_user))
    except Exception as exc:
        raise _http_for(exc) from exc


@router.get("/jobs/{job_id}")
def read_job(job_id: str, current_user: UserInDB = Depends(require_reader)) -> dict:
    try:
        return service.get_job(service.actor_from_user(current_user), job_id)
    except Exception as exc:
        raise _http_for(exc) from exc


@router.post("/approvals")
def decide(body: FinancialCloseApproval, current_user: UserInDB = Depends(require_reader)) -> dict:
    try:
        return service.decide(service.actor_from_user(current_user), body)
    except Exception as exc:
        raise _http_for(exc) from exc


@router.get("/outbox")
def read_outbox(current_user: UserInDB = Depends(require_reader)) -> list[dict]:
    try:
        return service.list_outbox(service.actor_from_user(current_user))
    except Exception as exc:
        raise _http_for(exc) from exc
