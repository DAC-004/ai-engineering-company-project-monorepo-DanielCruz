"""Typed close records. Sanitized projections never carry raw descriptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class LedgerRow:
    ingest_ref: str
    public_entry_id: str | None
    date: str | None
    country: str
    payer: str
    category: str
    currency: str
    amount: Decimal | None
    source_ref: str
    line_id: str | None
    uncertain: bool
    exclude_from_totals: bool
    quarantine_reason: str | None
    safe_description: str | None
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class BudgetRow:
    ingest_ref: str
    row_id: str
    month: str | None
    country: str
    payer: str
    category: str
    currency: str
    amount: Decimal | None
    line_id: str | None
    uncertain: bool
    exclude_from_totals: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationsRow:
    ingest_ref: str
    row_id: str
    month: str | None
    country: str | None
    payer: str | None
    metric: str | None
    value: Decimal | None
    uncertain: bool
    exclude_from_totals: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversionResult:
    line_id: str
    basis: str
    gbp_amount: str
    usd_amount: str
    rate: str
    fx_source: str
    source_refs: tuple[str, ...]


@dataclass
class LineFact:
    line_id: str
    country: str
    payer: str
    category: str
    currency: str
    kind: str
    budget: Decimal | None
    raw_actual: Decimal | None
    verified_actual: Decimal | None
    verified_entry_ids: tuple[str, ...]
    raw_entry_ids: tuple[str, ...]
    budget_row_ids: tuple[str, ...]
    incomplete: bool
    missing_actual: bool
    missing_budget: bool
    percent: Decimal | None
    amount_variance: Decimal | None
    relevant: bool
    issues: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupplierFact:
    line_id: str
    unit_price: Decimal
    quantity: Decimal
    source_refs: tuple[str, ...]


@dataclass
class CloseFacts:
    period: str
    load_date: str
    catch_up: bool
    fx_rate: str
    fx_source: str
    lines: dict[str, LineFact]
    operations: list[OperationsRow]
    ledger_rows: list[LedgerRow]
    budget_rows: list[BudgetRow]
    quarantined_entry_ids: tuple[str, ...]
    unmapped_ingest_refs: tuple[str, ...]
    missing_lines: tuple[str, ...]
    missing_files: tuple[str, ...]
    incomplete: bool
    digest: str
    issues: tuple[str, ...] = ()
    file_hashes: dict[str, str] = field(default_factory=dict)
    supplier_facts: tuple[SupplierFact, ...] = ()
    invoked_tools: tuple[str, ...] = ()
    conversion_results: tuple[ConversionResult, ...] = ()
    model_selected_tools: tuple[str, ...] = ()
    dependency_tools: tuple[str, ...] = ()
    deterministic_fallback: bool = False
