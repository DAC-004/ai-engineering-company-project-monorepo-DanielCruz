"""Authenticated supplier-contract supervisor routes. Directory CRUD is unchanged."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from agents.supplier_contracts.actor import ActorRejected
from app.access.permissions import (
    require_approve_record,
    require_departments,
    require_update_record,
)
from app.schemas.supplier_contracts import (
    SupplierContractsApproval,
    SupplierContractsAsk,
    SupplierContractsDpaProceed,
    SupplierContractsResponse,
)
from app.schemas.user import UserInDB
from app.services import supplier_contracts_service as service

router = APIRouter(prefix="/supplier-contracts", tags=["supplier-contracts"])
require_contracts_read = require_departments("clinical_operations", "compliance")


def _http_for(exc: Exception) -> HTTPException:
    if isinstance(exc, (service.UntrustedApproverError, ActorRejected)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Named approval was not accepted.")
    if isinstance(exc, (service.StaleDraftError, service.ReplayError, service.ConcurrentApprovalError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The draft approval is no longer valid.")
    if isinstance(exc, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested record was not found.")
    raise exc


@router.get("/registry")
def read_registry(_current_user: UserInDB = Depends(require_contracts_read)) -> list[dict]:
    return service.registry()


@router.get("/alerts")
def read_alerts(current_user: UserInDB = Depends(require_contracts_read)) -> list[dict]:
    return service.alerts(current_user)


@router.get("/drafts")
def read_drafts(current_user: UserInDB = Depends(require_contracts_read)) -> list[dict]:
    return service.list_drafts(service.actor_from_user(current_user))


@router.get("/drafts/{draft_id}")
def read_draft(draft_id: str, current_user: UserInDB = Depends(require_contracts_read)) -> dict:
    try:
        return service.get_draft(service.actor_from_user(current_user), draft_id)
    except Exception as exc:
        raise _http_for(exc) from exc


@router.post("/ask", response_model=SupplierContractsResponse)
def ask(
    body: SupplierContractsAsk,
    current_user: UserInDB = Depends(require_contracts_read),
) -> SupplierContractsResponse:
    try:
        payload = service.ask(body.kind, body.question, body.supplier_id, service.actor_from_user(current_user))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker-only tick is not available on ask.") from exc
    return SupplierContractsResponse(payload=payload)


@router.post("/approvals")
def approve_draft(
    body: SupplierContractsApproval,
    current_user: UserInDB = Depends(require_approve_record),
) -> dict:
    try:
        return service.approve(
            service.actor_from_user(current_user),
            body.draft_id,
            body.version,
            body.content_sha256,
            body.approval_nonce,
        )
    except Exception as exc:
        raise _http_for(exc) from exc


@router.post("/dpa-proceed")
def dpa_proceed(
    body: SupplierContractsDpaProceed,
    current_user: UserInDB = Depends(require_approve_record),
) -> dict:
    try:
        return service.confirm_dpa(service.actor_from_user(current_user), body.supplier_id)
    except Exception as exc:
        raise _http_for(exc) from exc


@router.post("/tick")
def tick_alerts(
    _reader: UserInDB = Depends(require_contracts_read),
    _updater: UserInDB = Depends(require_update_record),
) -> dict:
    return service.tick()
