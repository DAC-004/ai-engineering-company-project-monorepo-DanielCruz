"""Immediate Claire missing-DPA enqueue from contract evaluation and blocked brief."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from agents.supplier_contracts.identity import CLAIRE
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import ContractsResult, PricingResult, SupervisorRequest


def _pricing(supplier_id: str) -> PricingResult:
    return PricingResult(
        supplier_id=supplier_id,
        product="Basic metabolic panel",
        unit="test",
        currency="GBP",
        previous_price=Decimal("14.50"),
        current_price=Decimal("14.79"),
        change_ratio=Decimal("0.02"),
        above_threshold=False,
        annual_incremental=Decimal("2436"),
        annual_incremental_usd=Decimal("3093.72"),
        formula="test",
        source_row_ids=("prices.csv:1", "prices.csv:2"),
        alternatives=(),
        quote_only=False,
        missing=(),
        observation_from="2026-10",
        observation_to="2026-11",
        actor_id="supplier-contracts-pricing",
    )


def _extracted_missing(supplier_id: str = "HC-S06") -> ContractsResult:
    return ContractsResult(
        supplier_id=supplier_id,
        contract_id="CT-HC-03",
        missing_contract=False,
        terms=(),
        increase_allowed=True,
        cap_ratio=Decimal("0.03"),
        cap_price=Decimal("14.935"),
        missing_dpa=True,
        processes_patient_data=True,
        dpa_status="missing_dpa",
        exit_penalty_uncertain=False,
        expiry_offset_days=210,
        notice_days=90,
        pdf_sha256="extracted-no-dpa",
        actor_id="supplier-contracts-contracts",
    )


def _runtime(tmp_path: Path) -> ContractRuntime:
    return ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))


def _patch_specialists(monkeypatch, extracted: ContractsResult, pricing: PricingResult | None = None) -> None:
    monkeypatch.setattr(
        "agents.supplier_contracts.supervisor.run_pricing",
        lambda _rows, _request: pricing or _pricing(extracted.supplier_id),
    )
    monkeypatch.setattr(
        "agents.supplier_contracts.supervisor.run_contracts",
        lambda *args, **kwargs: extracted,
    )


def test_evaluate_increase_enqueues_claire_without_tick(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "ensure_seeded", lambda: None)
    monkeypatch.setattr(runtime, "price_rows", lambda: [])
    _patch_specialists(monkeypatch, _extracted_missing())
    supervisor = Supervisor(runtime)
    response = supervisor.handle(
        SupervisorRequest(kind="evaluate_increase", question="evaluate increase", supplier_id="HC-S06")
    )
    assert response.blocked is False
    claire = [row for row in response.alerts if row.get("kind") == "missing_dpa"]
    assert len(claire) == 1
    assert claire[0]["recipient"] == CLAIRE
    assert claire[0]["channel"] == "internal_outbox"
    persisted = runtime.store.read()["alerts"]
    assert len(persisted) == 1
    assert persisted[0]["recipient"] == CLAIRE
    assert persisted[0]["kind"] == "missing_dpa"


def test_blocked_brief_enqueues_claire_immediately(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "ensure_seeded", lambda: None)
    monkeypatch.setattr(runtime, "price_rows", lambda: [])
    _patch_specialists(monkeypatch, _extracted_missing())
    supervisor = Supervisor(runtime)
    response = supervisor.handle(
        SupervisorRequest(kind="brief", question="write a renegotiation brief", supplier_id="HC-S06")
    )
    assert response.blocked is True
    assert response.block_reason == "missing_dpa_blocks_brief_and_draft"
    claire = [row for row in response.alerts if row.get("kind") == "missing_dpa"]
    assert len(claire) == 1
    assert claire[0]["recipient"] == CLAIRE
    persisted = [row for row in runtime.store.read()["alerts"] if row["kind"] == "missing_dpa"]
    assert len(persisted) == 1
    assert persisted[0]["recipient"] == CLAIRE


def test_blocked_brief_does_not_duplicate_evaluate_alert(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(runtime, "ensure_seeded", lambda: None)
    monkeypatch.setattr(runtime, "price_rows", lambda: [])
    _patch_specialists(monkeypatch, _extracted_missing())
    supervisor = Supervisor(runtime)
    supervisor.handle(SupervisorRequest(kind="evaluate_increase", question="evaluate", supplier_id="HC-S06"))
    supervisor.handle(SupervisorRequest(kind="brief", question="brief", supplier_id="HC-S06"))
    persisted = [row for row in runtime.store.read()["alerts"] if row["kind"] == "missing_dpa"]
    assert len(persisted) == 1
