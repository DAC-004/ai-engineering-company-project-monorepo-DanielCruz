"""Owned process paths and seeded raw inputs. TinyDB supplier floats stay unused."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from agents.supplier_contracts.audit import AuditLog
from agents.supplier_contracts.contracts import run_contracts, schedule_dates
from agents.supplier_contracts.pricing import load_price_rows
from agents.supplier_contracts.registry import SUPPLIERS
from agents.supplier_contracts.seed import seed_raw
from agents.supplier_contracts.store import JsonStore
from agents.supplier_contracts.types import ContractsRequest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = REPO_ROOT / "data" / "raw" / "healthcore-supplier-contracts"
DEFAULT_PROCESS = REPO_ROOT / "data" / "process" / "supplier-contracts"
DEFAULT_LOAD_DATE = date(2026, 11, 6)


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def raw_dir() -> Path:
    return _path_from_env("SUPPLIER_CONTRACTS_RAW_DIR", DEFAULT_RAW)


def process_dir() -> Path:
    return _path_from_env("SUPPLIER_CONTRACTS_PROCESS_DIR", DEFAULT_PROCESS)


def load_date() -> date:
    raw = os.environ.get("SUPPLIER_CONTRACTS_LOAD_DATE", "").strip()
    return date.fromisoformat(raw) if raw else DEFAULT_LOAD_DATE


class ContractRuntime:
    def __init__(
        self,
        *,
        raw: Path | None = None,
        process: Path | None = None,
        as_of: date | None = None,
    ) -> None:
        self.raw = raw or raw_dir()
        self.process = process or process_dir()
        self.load_date = as_of or load_date()
        today_raw = os.environ.get("SUPPLIER_CONTRACTS_TODAY", "").strip()
        self.today = date.fromisoformat(today_raw) if today_raw else self.load_date
        self.process.mkdir(parents=True, exist_ok=True)
        self.store = JsonStore(self.process / "projection.json")
        self.audit = AuditLog(self.process / "audit.jsonl")
        self.csv_path = self.raw / "prices.csv"
        self.pdf_dir = self.raw / "pdfs"

    def pdf_path(self, contract_id: str | None) -> Path | None:
        if not contract_id:
            return None
        path = self.pdf_dir / f"{contract_id}.pdf"
        return path if path.exists() else None

    def ensure_seeded(self) -> None:
        if not self.csv_path.exists() or not self.pdf_dir.exists():
            seed_raw(self.raw, self.load_date)
        self.refresh_calendars()

    def refresh_calendars(self) -> None:
        for supplier in SUPPLIERS:
            if not supplier.contract_id:
                continue
            result = run_contracts(
                ContractsRequest(supplier_id=supplier.supplier_id, question="calendar"),
                pdf_path=self.pdf_path(supplier.contract_id),
                load_date=self.load_date,
            )
            if result.expiry_offset_days is None or result.notice_days is None:
                continue
            dates = schedule_dates(result.expiry_offset_days, result.notice_days, self.load_date)
            self.store.save_calendar(
                supplier.supplier_id,
                {key: value.isoformat() for key, value in dates.items()},
            )

    def price_rows(self):
        self.ensure_seeded()
        return load_price_rows(self.csv_path)
