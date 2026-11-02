"""Supplier Directory endpoints — TinyDB-backed HealthCore registry."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.access.permissions import (
    assert_department_allowed,
    filter_department_rows,
    require_authenticated,
    require_create_record,
    require_delete_sensitive,
    require_update_record,
)
from app.core.irreversible import require_explicit_confirmation
from app.core.prohibited_text import has_labeled_patient_field

from app.database import get_suppliers_table
from app.schemas.supplier import RateUpdate, StatusUpdate, SupplierCreate, SupplierResponse
from app.schemas.user import UserInDB

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _document_to_response(doc_id: int, document: dict) -> SupplierResponse:
    payload = {"id": doc_id, **document}
    return SupplierResponse.model_validate(payload)


def _get_supplier_or_404(supplier_id: int) -> tuple[int, dict]:
    table = get_suppliers_table()
    document = table.get(doc_id=supplier_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found",
        )
    return supplier_id, dict(document)


def _reject_labeled_patient_text(*values: str | None) -> None:
    """Stop a write that carries a labeled patient field. Do not echo the text."""
    if any(has_labeled_patient_field(value) for value in values):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The submitted text was not stored.",
        )


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    current_user: UserInDB = Depends(require_create_record),
) -> SupplierResponse:
    """Register a new supplier after authentication and Pydantic validation."""
    _reject_labeled_patient_text(payload.name, payload.notes)
    # Own-department create: a missing caller department is not a match.
    assert_department_allowed(current_user, current_user.department_id)
    table = get_suppliers_table()
    record = payload.model_dump(mode="json")
    # Status enum serializes to its value via mode=json; stamp system updated_at.
    record["updated_at"] = _utc_now_iso()
    record["department_id"] = current_user.department_id
    doc_id = table.insert(record)
    return _document_to_response(doc_id, table.get(doc_id=doc_id))


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    country: str | None = Query(default=None),
    category: str | None = Query(default=None),
    current_user: UserInDB = Depends(require_authenticated),
) -> list[SupplierResponse]:
    """Return the directory, optionally filtered by country and/or category."""
    table = get_suppliers_table()
    documents = table.all()
    results: list[SupplierResponse] = []

    for document in documents:
        if country is not None and document.get("country") != country:
            continue
        categories = document.get("categories") or []
        if category is not None and category not in categories:
            continue
        results.append(_document_to_response(document.doc_id, document))

    return filter_department_rows(
        current_user,
        results,
        lambda row: row.department_id,
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    current_user: UserInDB = Depends(require_authenticated),
) -> SupplierResponse:
    doc_id, document = _get_supplier_or_404(supplier_id)
    record = _document_to_response(doc_id, document)
    assert_department_allowed(current_user, record.department_id)
    return record


@router.patch("/{supplier_id}/rate", response_model=SupplierResponse)
def update_supplier_rate(
    supplier_id: int,
    payload: RateUpdate,
    current_user: UserInDB = Depends(require_update_record),
) -> SupplierResponse:
    """Update monthly_rate and record the change timestamp for audit traceability."""
    doc_id, document = _get_supplier_or_404(supplier_id)
    assert_department_allowed(current_user, document.get("department_id"))
    table = get_suppliers_table()
    document["monthly_rate"] = payload.monthly_rate
    document["updated_at"] = _utc_now_iso()
    table.update(document, doc_ids=[doc_id])
    refreshed = table.get(doc_id=doc_id)
    return _document_to_response(doc_id, refreshed)


@router.patch("/{supplier_id}/status", response_model=SupplierResponse)
def update_supplier_status(
    supplier_id: int,
    payload: StatusUpdate,
    current_user: UserInDB = Depends(require_update_record),
) -> SupplierResponse:
    doc_id, document = _get_supplier_or_404(supplier_id)
    assert_department_allowed(current_user, document.get("department_id"))
    table = get_suppliers_table()
    table.update({"status": payload.status.value}, doc_ids=[doc_id])
    refreshed = table.get(doc_id=doc_id)
    return _document_to_response(doc_id, refreshed)


@router.delete("/{supplier_id}", status_code=status.HTTP_200_OK)
def delete_supplier(
    supplier_id: int,
    request: Request,
    current_user: UserInDB = Depends(require_delete_sensitive),
) -> dict[str, str]:
    """Physically remove a supplier after authentication and explicit confirmation."""
    require_explicit_confirmation(request, "delete_supplier")
    doc_id, document = _get_supplier_or_404(supplier_id)
    assert_department_allowed(current_user, document.get("department_id"))
    table = get_suppliers_table()
    table.remove(doc_ids=[doc_id])
    return {"detail": f"Supplier {supplier_id} deleted"}
