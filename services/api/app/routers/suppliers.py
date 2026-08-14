"""Supplier Directory endpoints — TinyDB-backed HealthCore registry."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_suppliers_table
from app.models import RateUpdate, StatusUpdate, SupplierCreate, SupplierResponse

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


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate) -> SupplierResponse:
    """Register a new supplier after Pydantic validation."""
    table = get_suppliers_table()
    record = payload.model_dump(mode="json")
    # Status enum serializes to its value via mode=json; stamp system updated_at.
    record["updated_at"] = _utc_now_iso()
    doc_id = table.insert(record)
    return _document_to_response(doc_id, table.get(doc_id=doc_id))


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    country: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> list[SupplierResponse]:
    """Return the full directory, optionally filtered by country and/or category."""
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

    return results


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: int) -> SupplierResponse:
    doc_id, document = _get_supplier_or_404(supplier_id)
    return _document_to_response(doc_id, document)


@router.patch("/{supplier_id}/rate", response_model=SupplierResponse)
def update_supplier_rate(supplier_id: int, payload: RateUpdate) -> SupplierResponse:
    """Update monthly_rate and record the change timestamp for audit traceability."""
    doc_id, document = _get_supplier_or_404(supplier_id)
    table = get_suppliers_table()
    document["monthly_rate"] = payload.monthly_rate
    document["updated_at"] = _utc_now_iso()
    table.update(document, doc_ids=[doc_id])
    refreshed = table.get(doc_id=doc_id)
    return _document_to_response(doc_id, refreshed)


@router.patch("/{supplier_id}/status", response_model=SupplierResponse)
def update_supplier_status(supplier_id: int, payload: StatusUpdate) -> SupplierResponse:
    doc_id, _document = _get_supplier_or_404(supplier_id)
    table = get_suppliers_table()
    table.update({"status": payload.status.value}, doc_ids=[doc_id])
    refreshed = table.get(doc_id=doc_id)
    return _document_to_response(doc_id, refreshed)


@router.delete("/{supplier_id}", status_code=status.HTTP_200_OK)
def delete_supplier(supplier_id: int) -> dict[str, str]:
    """Physically remove a supplier (PNG / rubric requirement)."""
    doc_id, _document = _get_supplier_or_404(supplier_id)
    table = get_suppliers_table()
    table.remove(doc_ids=[doc_id])
    return {"detail": f"Supplier {supplier_id} deleted"}
