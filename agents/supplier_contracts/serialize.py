"""JSON-safe specialist payloads. Decimals travel as strings."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from decimal import Decimal
from typing import Any

from agents.supplier_contracts.privacy import (
    REDACTED,
    contains_bank_or_contact,
    is_credible_clause_number,
)
from agents.supplier_contracts.types import ContractsResult, SupervisorResponse


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if is_dataclass(value) and not isinstance(value, type):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return str(value)


def public_contracts(result: ContractsResult | None) -> ContractsResult | None:
    """Drop billing-clause bodies from the public payload; keep clause/page/hash."""
    if result is None:
        return None
    terms = tuple(
        replace(item, value=REDACTED) if item.field == "billing" or contains_bank_or_contact(item.value) else item
        for item in result.terms
        if is_credible_clause_number(item.clause)
    )
    return replace(result, terms=terms)


def public_draft(draft: dict | None) -> dict | None:
    if not draft:
        return None
    return {
        "draft_id": draft["draft_id"],
        "supplier_id": draft["supplier_id"],
        "kind": draft["kind"],
        "body": draft["body"],
        "version": int(draft["version"]),
        "content_sha256": draft["content_sha256"],
        "approval_nonce": draft["approval_nonce"],
        "required": list(draft["required"]),
        "granted": list(draft["granted"]),
        "state": draft["state"],
        "sent": bool(draft.get("sent", False)),
        "display_name": draft.get("display_name"),
    }


def response_payload(response: SupervisorResponse) -> dict[str, Any]:
    cleaned = replace(
        response,
        contracts=public_contracts(response.contracts),
        draft=public_draft(response.draft) if response.draft else None,
    )
    return jsonable(cleaned)
