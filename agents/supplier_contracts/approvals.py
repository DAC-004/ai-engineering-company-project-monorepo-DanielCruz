"""Named approvers come only from authenticated identity. Drafts are immutable."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import uuid4

from agents.supplier_contracts.constants import GBP_USD, SANDRA_ANNUAL_USD
from agents.supplier_contracts.actor import ActorIdentity, ActorRejected, named_approver_from_actor
from agents.supplier_contracts.identity import CLAIRE, MARCUS, SANDRA
from agents.supplier_contracts.registry import require_supplier
from agents.supplier_contracts.store import JsonStore
from agents.supplier_contracts.types import ApprovalState


class UntrustedApproverError(ValueError):
    pass


class StaleDraftError(ValueError):
    pass


class ReplayError(ValueError):
    pass


class ConcurrentApprovalError(ValueError):
    pass


_CAS_ERRORS = {
    "stale_draft_version": StaleDraftError,
    "stale_draft_hash": StaleDraftError,
    "stale_or_replayed_nonce": ReplayError,
    "concurrent_terminal_state": ConcurrentApprovalError,
}


def resolve_authenticated_approver(actor: ActorIdentity) -> str:
    try:
        return named_approver_from_actor(actor)
    except ActorRejected as exc:
        raise UntrustedApproverError(str(exc)) from exc


def annual_usd_from_contract(contracts) -> Decimal | None:
    """Sandra's threshold uses the extracted contract figure, not a registry constant."""
    usd, evidenced = annual_evidence_from_contract(contracts)
    if not evidenced:
        return None
    return usd


def annual_evidence_from_contract(contracts) -> tuple[Decimal | None, bool]:
    """Return (usd, evidenced). Missing or altered annual clauses are not evidenced."""
    if contracts is None or getattr(contracts, "missing_contract", False):
        return None, False
    if getattr(contracts, "estimated_annual_uncertain", True):
        return None, False
    value = getattr(contracts, "estimated_annual_value", None)
    if value is None:
        return None, False
    currency = getattr(contracts, "estimated_annual_currency", None) or "USD"
    if currency == "GBP":
        return value * GBP_USD, True
    return value, True


def annual_usd_for_supplier(supplier_id: str) -> Decimal | None:
    """Registry metadata is not the approval-threshold source."""
    return None


def required_approvers(
    supplier_id: str,
    annual_usd: Decimal | None,
    *,
    annual_evidenced: bool | None = None,
) -> list[str]:
    """Unknown annual does not lower the tier: Sandra is required until a PDF figure is evidenced."""
    supplier = require_supplier(supplier_id)
    evidenced = annual_usd is not None if annual_evidenced is None else annual_evidenced
    required = [MARCUS]
    if supplier.processes_patient_data:
        required.append(CLAIRE)
    if (not evidenced) or (annual_usd is not None and annual_usd > SANDRA_ANNUAL_USD):
        required.append(SANDRA)
    return required


def content_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def create_draft(
    store: JsonStore,
    *,
    supplier_id: str,
    kind: str,
    body: str,
    annual_usd: Decimal | None = None,
    annual_evidenced: bool | None = None,
) -> dict:
    supplier = require_supplier(supplier_id)
    digest = content_sha256(body)
    value = annual_usd if annual_usd is not None else annual_usd_for_supplier(supplier_id)
    draft = {
        "draft_id": uuid4().hex,
        "supplier_id": supplier_id,
        "kind": kind,
        "version": 1,
        "content_sha256": digest,
        "approval_nonce": uuid4().hex,
        "required": required_approvers(supplier_id, value, annual_evidenced=annual_evidenced),
        "granted": [],
        "state": "pending",
        "body": body,
        "sent": False,
        "display_name": supplier.display_name,
    }
    return store.save_draft(draft)


def approve_draft(
    store: JsonStore,
    *,
    actor: ActorIdentity,
    draft_id: str,
    version: int,
    content_sha256_value: str,
    approval_nonce: str,
    payload_approver: str | None = None,
) -> dict:
    if payload_approver:
        raise UntrustedApproverError("payload_approver_rejected")
    identity = resolve_authenticated_approver(actor)

    def updater(current: dict) -> dict:
        if identity not in current["required"]:
            raise UntrustedApproverError("approver_not_required")
        if identity in current["granted"]:
            raise ReplayError("duplicate_approval")
        updated = dict(current)
        updated["granted"] = [*current["granted"], identity]
        updated["approval_nonce"] = uuid4().hex
        if set(updated["granted"]) == set(updated["required"]):
            updated["state"] = "approved"
        return updated

    try:
        return store.cas_update_draft(
            draft_id,
            expected_nonce=approval_nonce,
            expected_version=version,
            expected_hash=content_sha256_value,
            updater=updater,
        )
    except ValueError as exc:
        mapped = _CAS_ERRORS.get(str(exc))
        if mapped is None:
            raise
        raise mapped(str(exc)) from exc


def confirm_dpa_proceed(store: JsonStore, actor: ActorIdentity, supplier_id: str, *, contracts) -> None:
    identity = resolve_authenticated_approver(actor)
    if identity != CLAIRE:
        raise UntrustedApproverError("dpa_proceed_requires_claire")
    if contracts.supplier_id != supplier_id:
        raise UntrustedApproverError("dpa_proceed_supplier_mismatch")
    # A quote-only supplier may have no contract. Claire can acknowledge that
    # explicit absence; a later PDF/id changes the snapshot and requires recheck.
    if not contracts.missing_contract and (not contracts.pdf_sha256 or not contracts.contract_id):
        raise UntrustedApproverError("dpa_proceed_requires_evidenced_contract")
    store.set_dpa_proceed(supplier_id, True, pdf_sha256=contracts.pdf_sha256, contract_id=contracts.contract_id)


def as_state(draft: dict, claire_dpa_proceed: bool = False) -> ApprovalState:
    return ApprovalState(
        draft_id=draft["draft_id"],
        supplier_id=draft["supplier_id"],
        kind=draft["kind"],
        version=int(draft["version"]),
        content_sha256=draft["content_sha256"],
        approval_nonce=draft["approval_nonce"],
        required=list(draft["required"]),
        granted=list(draft["granted"]),
        state=draft["state"],
        claire_dpa_proceed=claire_dpa_proceed,
        sent=bool(draft.get("sent")),
    )
