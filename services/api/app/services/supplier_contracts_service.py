"""Thin adapter from authenticated API identity onto the supplier-contracts supervisor."""

from __future__ import annotations

from agents.supplier_contracts.actor import ActorIdentity, ActorRejected, named_approver_from_actor
from agents.supplier_contracts.approvals import (
    ConcurrentApprovalError,
    ReplayError,
    StaleDraftError,
    UntrustedApproverError,
    approve_draft,
)
from agents.supplier_contracts.identity import CLAIRE
from agents.supplier_contracts.registry import SUPPLIERS
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.serialize import public_draft, response_payload
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import SupervisorRequest
from app.access.catalog import Capability, has_capability, is_admin
from app.access.permissions import filter_department_rows
from app.schemas.user import UserInDB

_runtime: ContractRuntime | None = None


def runtime() -> ContractRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ContractRuntime()
        _runtime.ensure_seeded()
    return _runtime


def reset_runtime_for_tests() -> None:
    global _runtime
    _runtime = None


def _named_identity(actor: ActorIdentity) -> str | None:
    try:
        return named_approver_from_actor(actor)
    except ActorRejected:
        return None


def list_drafts(actor: ActorIdentity) -> list[dict]:
    identity = _named_identity(actor)
    if identity is None:
        return []
    stored = runtime().store.read().get("drafts", {})
    visible: list[dict] = []
    for draft in stored.values():
        if identity not in draft.get("required", []):
            continue
        published = public_draft(draft)
        if published is not None:
            visible.append(published)
    return visible


def get_draft(actor: ActorIdentity, draft_id: str) -> dict:
    for draft in list_drafts(actor):
        if draft["draft_id"] == draft_id:
            return draft
    raise KeyError(draft_id)


def actor_from_user(user: UserInDB) -> ActorIdentity:
    return ActorIdentity(
        user_id=user.id,
        role=user.role.value,
        department_id=user.department_id,
        email=user.email,
        is_active=user.is_active,
        is_admin=is_admin(user.role),
        can_approve=has_capability(user.role, Capability.approve_department_record),
    )


def _generation_transport():
    from agents.supplier_contracts.generation import configured_transport

    return configured_transport


def registry() -> list[dict[str, str | bool]]:
    return [
        {
            "supplier_id": item.supplier_id,
            "display_name": item.display_name,
            "country": item.country,
            "directory_country": item.directory_country,
            "category": item.category,
            "quote_only": item.quote_only,
            "has_contract": item.has_contract,
        }
        for item in SUPPLIERS
    ]


def ask(kind: str, question: str, supplier_id: str | None, actor: ActorIdentity) -> dict:
    if kind == "tick_alerts":
        raise PermissionError("worker_only_tick")
    supervisor = Supervisor(runtime(), transport=_generation_transport())
    response = supervisor.handle(
        SupervisorRequest(
            kind=kind,  # type: ignore[arg-type]
            question=question,
            supplier_id=supplier_id,
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            actor_department_id=actor.department_id or "",
            actor_email=actor.email,
        )
    )
    return response_payload(response)


def approve(
    actor: ActorIdentity,
    draft_id: str,
    version: int,
    content_sha256: str,
    approval_nonce: str,
) -> dict:
    draft = approve_draft(
        runtime().store,
        actor=actor,
        draft_id=draft_id,
        version=version,
        content_sha256_value=content_sha256,
        approval_nonce=approval_nonce,
    )
    published = public_draft(draft)
    if published is None:
        raise KeyError(draft_id)
    return published


def confirm_dpa(actor: ActorIdentity, supplier_id: str) -> dict[str, str]:
    Supervisor(runtime()).confirm_dpa(actor, supplier_id)
    return {"supplier_id": supplier_id, "status": "confirmed"}


def alerts(current_user: UserInDB) -> list[dict]:
    rows = list(runtime().store.read().get("alerts", []))
    return filter_department_rows(
        current_user,
        rows,
        lambda row: row.get("visibility_department")
        or ("compliance" if row.get("recipient") == CLAIRE else "clinical_operations"),
    )


def tick() -> dict:
    response = Supervisor(runtime()).handle(
        SupervisorRequest(kind="tick_alerts", question="tick", supplier_id=None)
    )
    return response_payload(response)
