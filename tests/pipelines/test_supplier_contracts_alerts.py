"""Alert idempotency, extracted-DPA, and immediate Claire enqueue regressions."""

from __future__ import annotations

import multiprocessing
from datetime import date
from decimal import Decimal
from pathlib import Path

from agents.supplier_contracts.alerts import (
    emit_missing_dpa_alert,
    expiry_key,
    missing_dpa_key,
    multiprocess_emit,
    notice_key,
    price_increase_key,
    process_alerts,
)
from agents.supplier_contracts.identity import ALERTS_ID, CLAIRE
from agents.supplier_contracts.registry import BY_ID
from agents.supplier_contracts.store import JsonStore
from agents.supplier_contracts.types import ContractsResult, PricingResult


def _contracts(
    *,
    supplier_id: str,
    missing_dpa: bool,
    dpa_status: str,
    contract_id: str | None,
    pdf_sha256: str | None,
) -> ContractsResult:
    return ContractsResult(
        supplier_id=supplier_id,
        contract_id=contract_id,
        missing_contract=contract_id is None,
        terms=(),
        increase_allowed=None,
        cap_ratio=None,
        cap_price=None,
        missing_dpa=missing_dpa,
        processes_patient_data=True,
        dpa_status=dpa_status,
        exit_penalty_uncertain=False,
        expiry_offset_days=60,
        notice_days=45,
        pdf_sha256=pdf_sha256,
        actor_id="supplier-contracts-contracts",
    )


def _pricing(
    *,
    supplier_id: str = "HC-S03",
    observation_from: str = "2026-10",
    observation_to: str = "2026-11",
    previous: str = "18.00",
    current: str = "19.26",
    above: bool = True,
) -> PricingResult:
    return PricingResult(
        supplier_id=supplier_id,
        product="Basic metabolic panel",
        unit="test",
        currency="USD",
        previous_price=Decimal(previous),
        current_price=Decimal(current),
        change_ratio=Decimal("0.07"),
        above_threshold=above,
        annual_incremental=Decimal("37800"),
        annual_incremental_usd=Decimal("37800"),
        formula="test",
        source_row_ids=("prices.csv:1", "prices.csv:2"),
        alternatives=(),
        quote_only=False,
        missing=(),
        observation_from=observation_from,
        observation_to=observation_to,
        actor_id="supplier-contracts-pricing",
    )


def test_extracted_missing_dpa_alerts_even_when_registry_lists_baa(tmp_path: Path) -> None:
    """S03 registry dpa_kind is BAA; extracted uncertain/missing must still alert Claire."""
    assert BY_ID["HC-S03"].dpa_kind == "BAA"
    store = JsonStore(tmp_path / "projection.json")
    extracted = _contracts(
        supplier_id="HC-S03",
        missing_dpa=True,
        dpa_status="uncertain",
        contract_id="CT-HC-02",
        pdf_sha256="abc123removedbaa",
    )
    emitted = process_alerts(store, today=date(2026, 11, 6), contracts_by_supplier={"HC-S03": extracted})
    assert len(emitted) == 1
    assert emitted[0]["recipient"] == CLAIRE
    assert emitted[0]["kind"] == "missing_dpa"
    assert emitted[0]["channel"] == "internal_outbox"
    assert emitted[0]["actor_id"] == ALERTS_ID


def test_extracted_signed_dpa_does_not_alert_even_when_registry_has_none(tmp_path: Path) -> None:
    """S06 registry dpa_kind is empty; extracted signed status must not invent a Claire alert."""
    assert BY_ID["HC-S06"].dpa_kind not in {"BAA", "DPA"}
    store = JsonStore(tmp_path / "projection.json")
    extracted = _contracts(
        supplier_id="HC-S06",
        missing_dpa=False,
        dpa_status="signed_baa",
        contract_id="CT-HC-03",
        pdf_sha256="signed-revision",
    )
    emitted = process_alerts(store, today=date(2026, 11, 6), contracts_by_supplier={"HC-S06": extracted})
    assert emitted == []
    assert store.read()["alerts"] == []


def test_later_contract_revision_is_not_suppressed(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "projection.json")
    first = _contracts(
        supplier_id="HC-S06",
        missing_dpa=True,
        dpa_status="missing_dpa",
        contract_id="CT-HC-03",
        pdf_sha256="revision-one",
    )
    second = _contracts(
        supplier_id="HC-S06",
        missing_dpa=True,
        dpa_status="missing_dpa",
        contract_id="CT-HC-03",
        pdf_sha256="revision-two",
    )
    assert missing_dpa_key(first) != missing_dpa_key(second)
    emit_missing_dpa_alert(store, first)
    emit_missing_dpa_alert(store, first)
    emit_missing_dpa_alert(store, second)
    keys = [item["idempotency_key"] for item in store.read()["alerts"]]
    assert keys == [missing_dpa_key(first), missing_dpa_key(second)]


def test_later_price_observation_period_is_not_suppressed(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "projection.json")
    first = _pricing(observation_from="2025-10", observation_to="2025-11")
    second = _pricing(observation_from="2026-10", observation_to="2026-11")
    assert price_increase_key(first) != price_increase_key(second)
    process_alerts(store, today=date(2026, 11, 6), pricing_by_supplier={"HC-S03": first})
    process_alerts(store, today=date(2026, 11, 6), pricing_by_supplier={"HC-S03": first})
    process_alerts(store, today=date(2026, 11, 6), pricing_by_supplier={"HC-S03": second})
    keys = [item["idempotency_key"] for item in store.read()["alerts"]]
    assert keys == [price_increase_key(first), price_increase_key(second)]


def test_later_expiry_date_is_not_suppressed(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "projection.json")
    first_expiry = date(2026, 12, 6)
    renewed = date(2027, 12, 6)
    assert expiry_key("HC-S07", 90, first_expiry) != expiry_key("HC-S07", 90, renewed)
    process_alerts(
        store,
        today=date(2026, 11, 6),
        dates_by_supplier={"HC-S07": {"expiry": first_expiry, "notice_deadline": date(2026, 11, 21)}},
    )
    process_alerts(
        store,
        today=date(2026, 11, 6),
        dates_by_supplier={"HC-S07": {"expiry": first_expiry, "notice_deadline": date(2026, 11, 21)}},
    )
    process_alerts(
        store,
        today=date(2027, 11, 6),
        dates_by_supplier={"HC-S07": {"expiry": renewed, "notice_deadline": date(2027, 11, 21)}},
    )
    expiry_keys = [item["idempotency_key"] for item in store.read()["alerts"] if item["kind"] == "expiry"]
    assert expiry_key("HC-S07", 90, first_expiry) in expiry_keys
    assert expiry_key("HC-S07", 90, renewed) in expiry_keys
    notice_keys = [item["idempotency_key"] for item in store.read()["alerts"] if item["kind"] == "notice"]
    assert notice_key("HC-S07", date(2026, 11, 21)) in notice_keys
    assert notice_key("HC-S07", date(2027, 11, 21)) in notice_keys


def test_multiprocess_duplicate_check_and_append(tmp_path: Path) -> None:
    store_path = tmp_path / "projection.json"
    JsonStore(store_path)
    key = "HC-S06:missing_dpa:CT-HC-03:revision-one:missing_dpa"
    fields = {
        "kind": "missing_dpa",
        "recipient": CLAIRE,
        "supplier_id": "HC-S06",
        "template": "missing_data_protection_agreement",
        "idempotency_key": key,
    }
    ctx = multiprocessing.get_context("spawn")
    workers = [ctx.Process(target=multiprocess_emit, args=(str(store_path), fields)) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert worker.exitcode == 0
    alerts = JsonStore(store_path).read()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["idempotency_key"] == key
    assert alerts[0]["recipient"] == CLAIRE
    assert alerts[0]["channel"] == "internal_outbox"
