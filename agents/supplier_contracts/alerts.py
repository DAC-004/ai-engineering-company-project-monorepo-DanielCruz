"""Idempotent catch-up alerts. Internal outbox only. No external transport."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from agents.supplier_contracts.constants import EXPIRY_ALERT_OFFSETS_DAYS, NOTICE_ALERT_OFFSET_DAYS
from agents.supplier_contracts.identity import ALERTS_ID, CLAIRE, MARCUS, NAMED_HOME_DEPARTMENT
from agents.supplier_contracts.store import JsonStore
from agents.supplier_contracts.types import ContractsResult, PricingResult


def missing_dpa_key(result: ContractsResult) -> str:
    revision = result.pdf_sha256 or "missing_contract"
    contract_id = result.contract_id or "none"
    return f"{result.supplier_id}:missing_dpa:{contract_id}:{revision}:{result.dpa_status}"


def price_increase_key(pricing: PricingResult) -> str:
    return (
        f"{pricing.supplier_id}:price:{pricing.observation_from}:{pricing.observation_to}:"
        f"{pricing.previous_price}:{pricing.current_price}"
    )


def expiry_key(supplier_id: str, offset: int, expiry: date) -> str:
    return f"{supplier_id}:expiry:{offset}:{expiry.isoformat()}"


def notice_key(supplier_id: str, notice_deadline: date) -> str:
    return f"{supplier_id}:notice:{notice_deadline.isoformat()}"


def _emit(store: JsonStore, **fields) -> dict:
    recipient = fields.get("recipient")
    visibility = NAMED_HOME_DEPARTMENT.get(str(recipient), "clinical_operations")
    alert = {
        "id": uuid4().hex,
        "channel": "internal_outbox",
        "actor_id": ALERTS_ID,
        "visibility_department": visibility,
        **fields,
    }
    return store.append_alert_if_absent(alert)


def _contract_sources(result: ContractsResult | None, fields: set[str]) -> list[dict]:
    if result is None:
        return []
    return [{"field": term.field, "clause": term.clause, "page": term.page,
             "pdf_sha256": term.pdf_sha256, "confidence": term.confidence}
            for term in result.terms if term.field in fields and term.clause and term.page > 0]


def emit_missing_dpa_alert(store: JsonStore, result: ContractsResult) -> dict:
    """Enqueue Claire as soon as extracted terms show a missing or uncertain DPA."""
    if not result.missing_dpa:
        return {}
    return _emit(
        store,
        kind="missing_dpa",
        recipient=CLAIRE,
        supplier_id=result.supplier_id,
        template="missing_data_protection_agreement",
        dpa_status=result.dpa_status,
        contract_id=result.contract_id,
        source_citations=_contract_sources(result, {"data_protection"}),
        pdf_sha256=result.pdf_sha256,
        idempotency_key=missing_dpa_key(result),
    )


def emit_price_increase_alert(store: JsonStore, pricing: PricingResult) -> dict:
    if not pricing.above_threshold:
        return {}
    return _emit(
        store,
        kind="price_increase",
        recipient=MARCUS,
        supplier_id=pricing.supplier_id,
        template="price_increase_above_threshold",
        observation_from=pricing.observation_from,
        observation_to=pricing.observation_to,
        source_row_ids=list(pricing.source_row_ids),
        idempotency_key=price_increase_key(pricing),
    )


def process_alerts(
    store: JsonStore,
    *,
    today: date,
    pricing_by_supplier: dict[str, PricingResult] | None = None,
    contracts_by_supplier: dict[str, ContractsResult] | None = None,
    dates_by_supplier: dict[str, dict[str, date]] | None = None,
) -> list[dict]:
    emitted: list[dict] = []
    calendars = dates_by_supplier or {}
    stored = store.read().get("calendars", {})
    # DPA uses extracted specialist output only. Registry dpa_kind is not consulted.
    for extracted in (contracts_by_supplier or {}).values():
        row = emit_missing_dpa_alert(store, extracted)
        if row:
            emitted.append(row)
    for pricing in (pricing_by_supplier or {}).values():
        row = emit_price_increase_alert(store, pricing)
        if row:
            emitted.append(row)
    supplier_ids = set(calendars) | set(stored)
    for supplier_id in sorted(supplier_ids):
        calendar = calendars.get(supplier_id)
        if calendar is None:
            raw = stored.get(supplier_id)
            if raw:
                calendar = {key: date.fromisoformat(value) for key, value in raw.items()}
        if not calendar:
            continue
        expiry = calendar["expiry"]
        notice_deadline = calendar["notice_deadline"]
        extracted = (contracts_by_supplier or {}).get(supplier_id)
        provenance = {
            "contract_id": extracted.contract_id if extracted else None,
            "source_citations": _contract_sources(extracted, {"term", "non-renewal_notice"}),
            "source_status": "attached" if extracted else "not_attached",
        }
        for offset in EXPIRY_ALERT_OFFSETS_DAYS:
            window_start = expiry - timedelta(days=offset)
            if today >= window_start:
                row = _emit(
                    store,
                    kind="expiry",
                    recipient=MARCUS,
                    supplier_id=supplier_id,
                    template=f"expiry_{offset}",
                    expiry=expiry.isoformat(),
                    **provenance,
                    idempotency_key=expiry_key(supplier_id, offset, expiry),
                )
                if row:
                    emitted.append(row)
        notice_alert_on = notice_deadline - timedelta(days=NOTICE_ALERT_OFFSET_DAYS)
        if today >= notice_alert_on:
            row = _emit(
                store,
                kind="notice",
                recipient=MARCUS,
                supplier_id=supplier_id,
                template="notice_deadline",
                notice_deadline=notice_deadline.isoformat(),
                **provenance,
                idempotency_key=notice_key(supplier_id, notice_deadline),
            )
            if row:
                emitted.append(row)
    return emitted


def multiprocess_emit(store_path: str, fields: dict) -> None:
    """Spawn-safe helper for multi-process duplicate regressions."""
    store = JsonStore(Path(store_path))
    _emit(store, **fields)
