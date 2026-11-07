"""Allowlisted calculation tools. The model does not perform arithmetic."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from agents.financial_close.calendar import closing_period_for_load_date
from agents.financial_close.constants import (
    CURRENCY_GBP,
    CURRENCY_USD,
    DEVIATION_THRESHOLD,
    FX_GBP_USD,
    FX_SOURCE,
    LINE_IDS,
    LINE_SPEC,
)
from agents.financial_close.ingest import file_sha256, ingest_budget, ingest_ledger, ingest_operations
from agents.financial_close.money import (
    amount_deviation,
    convert_gbp_usd,
    display_percent,
    is_relevant,
    percentage_deviation,
    unsigned_cost,
)
from agents.financial_close.privacy import is_allowlisted_description
from agents.financial_close.types import CloseFacts, ConversionResult, LedgerRow, LineFact, SupplierFact

ALLOWED_TOOLS = (
    "ingest_and_normalize",
    "aggregate_lines",
    "actual_versus_budget",
    "convert_gbp_usd",
    "select_relevant_deviations",
    "completeness",
    "lookup_sources",
)

TOOL_DEPENDENCIES = {
    "ingest_and_normalize": (),
    "aggregate_lines": ("ingest_and_normalize",),
    "actual_versus_budget": ("ingest_and_normalize", "aggregate_lines"),
    "convert_gbp_usd": ("ingest_and_normalize", "aggregate_lines"),
    "select_relevant_deviations": ("ingest_and_normalize", "aggregate_lines", "actual_versus_budget"),
    "completeness": ("ingest_and_normalize",),
    "lookup_sources": ("ingest_and_normalize",),
}

_SUPPLIER_PARSE = re.compile(
    r"^(?P<label>.+) unit_price=(?P<price>\d+(?:\.\d+)?) quantity=(?P<qty>\d+)$"
)


def line_actual(row: LedgerRow) -> Decimal:
    if row.amount is None:
        raise ValueError("missing_amount")
    spec = LINE_SPEC.get(row.line_id or "")
    if spec and spec[4] == "expense":
        return unsigned_cost(row.amount)
    return row.amount


def _sum_rows(rows: list[LedgerRow]) -> Decimal | None:
    usable = [row for row in rows if row.amount is not None and not row.exclude_from_totals]
    if not usable:
        return None
    return sum((line_actual(row) for row in usable), start=Decimal("0"))


def aggregate_lines(ledger: list[LedgerRow], budget_rows) -> dict[str, LineFact]:
    facts: dict[str, LineFact] = {}
    for line_id in LINE_IDS:
        country, payer, category, currency, kind = LINE_SPEC[line_id]
        members = [row for row in ledger if row.line_id == line_id]
        budget_matches = [
            row
            for row in budget_rows
            if row.line_id == line_id and row.amount is not None and not row.exclude_from_totals
        ]
        budget = sum((row.amount for row in budget_matches), start=Decimal("0")) if budget_matches else None
        raw_actual = _sum_rows(members)
        verified = [
            row for row in members if not row.uncertain and row.amount is not None and not row.exclude_from_totals
        ]
        verified_actual = _sum_rows(verified)
        missing_actual = not any(row.amount is not None and not row.exclude_from_totals for row in members)
        missing_budget = budget is None
        line_issues = tuple(dict.fromkeys(code for row in members for code in row.issues))
        budget_issues = tuple(dict.fromkeys(code for row in budget_rows if row.line_id == line_id for code in row.issues))
        incomplete = (
            missing_actual
            or missing_budget
            or any(row.uncertain for row in members)
            or any(row.uncertain for row in budget_rows if row.line_id == line_id)
        )
        percent = None
        variance = amount_deviation(verified_actual, budget, incomplete=incomplete)
        if verified_actual is not None and budget is not None and not incomplete:
            percent = percentage_deviation(verified_actual, budget)
        facts[line_id] = LineFact(
            line_id=line_id,
            country=country,
            payer=payer,
            category=category,
            currency=currency,
            kind=kind,
            budget=budget,
            raw_actual=raw_actual,
            verified_actual=verified_actual,
            verified_entry_ids=tuple(sorted(row.public_entry_id for row in verified if row.public_entry_id)),
            raw_entry_ids=tuple(
                sorted(
                    row.public_entry_id
                    for row in members
                    if row.public_entry_id and row.amount is not None and not row.exclude_from_totals
                )
            ),
            budget_row_ids=tuple(sorted(row.row_id for row in budget_matches)),
            incomplete=incomplete,
            missing_actual=missing_actual,
            missing_budget=missing_budget,
            percent=percent,
            amount_variance=variance,
            relevant=is_relevant(percent, DEVIATION_THRESHOLD) and not incomplete,
            issues=tuple(dict.fromkeys([*line_issues, *budget_issues])),
            source_refs=tuple(sorted({row.source_ref for row in verified})),
        )
    return facts


def to_usd(amount: Decimal, currency: str) -> Decimal:
    if currency == CURRENCY_USD:
        return amount
    if currency == CURRENCY_GBP:
        return convert_gbp_usd(amount, FX_GBP_USD)
    raise ValueError("unknown_currency")


def facts_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def supplier_facts_from_ledger(ledger: list[LedgerRow]) -> tuple[SupplierFact, ...]:
    grouped: dict[str, list[tuple[Decimal, Decimal, str]]] = {}
    for row in ledger:
        if row.uncertain or row.line_id is None or not row.safe_description:
            continue
        if not is_allowlisted_description(row.safe_description):
            continue
        matched = _SUPPLIER_PARSE.fullmatch(row.safe_description)
        if not matched:
            continue
        grouped.setdefault(row.line_id, []).append(
            (Decimal(matched.group("price")), Decimal(matched.group("qty")), row.source_ref)
        )
    facts: list[SupplierFact] = []
    for line_id, parts in grouped.items():
        prices = {item[0] for item in parts}
        if len(prices) != 1:
            continue
        quantity = sum((item[1] for item in parts), start=Decimal("0"))
        facts.append(
            SupplierFact(
                line_id=line_id,
                unit_price=next(iter(prices)),
                quantity=quantity,
                source_refs=tuple(sorted(item[2] for item in parts)),
            )
        )
    return tuple(sorted(facts, key=lambda item: item.line_id))


def laboratory_support(facts: CloseFacts) -> dict[str, str] | None:
    lab = facts.lines["us_laboratory"]
    supplier = next((item for item in facts.supplier_facts if item.line_id == "us_laboratory"), None)
    # Incomplete lab actuals are a verified subset. Dividing the full budget by that
    # remaining quantity would publish a complete budget-implied unit price the
    # surviving rows do not support. The supplier unit_price*quantity mismatch cases
    # cover this edge; do not invent a complete implied price from partial quantity.
    if (
        lab.incomplete
        or lab.budget is None
        or lab.verified_actual is None
        or supplier is None
        or supplier.quantity == 0
    ):
        return None
    implied = lab.budget / supplier.quantity
    increase = lab.verified_actual - lab.budget
    # 19.26 - 18 = 1.26 is supplied so the writer never subtracts unit prices.
    unit_price_variance = supplier.unit_price - implied
    percent = percentage_deviation(lab.verified_actual, lab.budget)
    return {
        "observed_unit_price": str(supplier.unit_price),
        "observed_quantity": str(supplier.quantity),
        "budget": str(lab.budget),
        "verified_actual": str(lab.verified_actual),
        "budget_implied_unit_price": str(implied),
        "unit_price_variance": str(unit_price_variance),
        "increase": str(increase),
        "percent": str(percent) if percent is not None else None,
        "source_refs": list(supplier.source_refs),
    }


def canonical_identity(facts: CloseFacts) -> dict:
    return {
        "period": facts.period,
        "file_hashes": facts.file_hashes,
        "missing_files": list(facts.missing_files),
        "fx": facts.fx_rate,
        "fx_source": facts.fx_source,
        "lines": {
            line_id: {
                "budget": str(fact.budget) if fact.budget is not None else None,
                "verified_actual": str(fact.verified_actual) if fact.verified_actual is not None else None,
                "raw_actual": str(fact.raw_actual) if fact.raw_actual is not None else None,
                "percent": str(fact.percent) if fact.percent is not None else None,
                "incomplete": fact.incomplete,
                "issues": list(fact.issues),
                "entry_ids": list(fact.verified_entry_ids),
                "budget_row_ids": list(fact.budget_row_ids),
            }
            for line_id, fact in facts.lines.items()
        },
        "operations": [
            {
                "ingest_ref": row.ingest_ref,
                "row_id": row.row_id,
                "payer": row.payer,
                "metric": row.metric,
                "value": str(row.value) if row.value is not None and not row.uncertain else None,
                "uncertain": row.uncertain,
                "issues": list(row.issues),
            }
            for row in facts.operations
        ],
        "budget_issues": [
            {"ingest_ref": row.ingest_ref, "issues": list(row.issues)}
            for row in facts.budget_rows
            if row.issues
        ],
        "ledger_issues": [
            {
                "ingest_ref": row.ingest_ref,
                "entry_id": row.public_entry_id,
                "issues": list(row.issues),
                "quarantine_reason": row.quarantine_reason,
            }
            for row in facts.ledger_rows
            if row.issues or row.quarantine_reason
        ],
        "quarantined": list(facts.quarantined_entry_ids),
        "unmapped": list(facts.unmapped_ingest_refs),
        "supplier_facts": [
            {
                "line_id": item.line_id,
                "unit_price": str(item.unit_price),
                "quantity": str(item.quantity),
                "source_refs": list(item.source_refs),
            }
            for item in facts.supplier_facts
        ],
        "issues": list(facts.issues),
    }


def build_facts(*, raw_dir: Path, load_date, catch_up: bool, invoked_tools: tuple[str, ...] = ()) -> CloseFacts:
    period = closing_period_for_load_date(load_date)
    ledger_path = raw_dir / "ledger.csv"
    budget_path = raw_dir / "budget.csv"
    operations_path = raw_dir / "operations.csv"
    missing_files: list[str] = []
    issues: list[str] = []
    if not ledger_path.exists():
        missing_files.append("ledger.csv")
        issues.append("missing_ledger_file")
    if not budget_path.exists():
        missing_files.append("budget.csv")
        issues.append("missing_budget_file")
    if not operations_path.exists():
        missing_files.append("operations.csv")
        issues.append("missing_operations_file")
    ledger = ingest_ledger(ledger_path, period)
    budget = ingest_budget(budget_path, period)
    operations = ingest_operations(operations_path, period)
    lines = aggregate_lines(ledger, budget)
    quarantined = tuple(
        sorted(row.public_entry_id for row in ledger if row.quarantine_reason and row.public_entry_id)
    )
    unmapped = tuple(sorted(row.ingest_ref for row in ledger if row.line_id is None))
    missing = tuple(line_id for line_id, fact in lines.items() if fact.missing_actual)
    incomplete = (
        any(fact.incomplete for fact in lines.values())
        or bool(unmapped)
        or bool(quarantined)
        or bool(missing_files)
        or any(row.uncertain for row in operations)
    )
    facts = CloseFacts(
        period=period,
        load_date=load_date.isoformat(),
        catch_up=catch_up,
        fx_rate=str(FX_GBP_USD),
        fx_source=FX_SOURCE,
        lines=lines,
        operations=operations,
        ledger_rows=ledger,
        budget_rows=budget,
        quarantined_entry_ids=quarantined,
        unmapped_ingest_refs=unmapped,
        missing_lines=missing,
        missing_files=tuple(missing_files),
        incomplete=incomplete,
        digest="",
        issues=tuple(dict.fromkeys(issues)),
        file_hashes={
            "ledger.csv": file_sha256(ledger_path),
            "budget.csv": file_sha256(budget_path),
            "operations.csv": file_sha256(operations_path),
        },
        supplier_facts=supplier_facts_from_ledger(ledger),
        invoked_tools=invoked_tools,
    )
    facts.digest = facts_digest(canonical_identity(facts))
    return facts


def operations_value(facts: CloseFacts, payer: str, metric: str) -> Decimal | None:
    matches = [
        row
        for row in facts.operations
        if row.payer == payer and row.metric == metric and not row.uncertain and row.value is not None
    ]
    if not matches:
        return None
    return matches[0].value


class CalculationToolbox:
    """Bounded allowlisted tools. Each call is recorded; the model does not do math."""

    def __init__(self, *, raw_dir: Path, load_date, catch_up: bool) -> None:
        self.raw_dir = raw_dir
        self.load_date = load_date
        self.catch_up = catch_up
        self.invoked: list[str] = []
        self.facts: CloseFacts | None = None
        self.tool_results: dict[str, object] = {}

    def _ensure(self) -> CloseFacts:
        if self.facts is None:
            self.ingest_and_normalize()
        assert self.facts is not None
        return self.facts

    def ingest_and_normalize(self) -> CloseFacts:
        self.invoked.append("ingest_and_normalize")
        preserved = self.facts.conversion_results if self.facts is not None else ()
        preserved_fx = self.tool_results.get("convert_gbp_usd")
        self.facts = build_facts(
            raw_dir=self.raw_dir,
            load_date=self.load_date,
            catch_up=self.catch_up,
            invoked_tools=tuple(self.invoked),
        )
        if preserved:
            self.facts.conversion_results = preserved
        if preserved_fx is not None:
            self.tool_results["convert_gbp_usd"] = preserved_fx
        return self.facts

    def aggregate_lines(self) -> dict[str, LineFact]:
        self.invoked.append("aggregate_lines")
        return self._ensure().lines

    def actual_versus_budget(self) -> dict[str, dict[str, str | None]]:
        self.invoked.append("actual_versus_budget")
        facts = self._ensure()
        payload = {
            line_id: {
                "percent": str(fact.percent) if fact.percent is not None else None,
                "percent_display": display_percent(fact.percent) if fact.percent is not None else None,
                "amount_variance": str(fact.amount_variance) if fact.amount_variance is not None else None,
            }
            for line_id, fact in facts.lines.items()
        }
        self.tool_results["actual_versus_budget"] = payload
        self.tool_results["amount_versus_budget"] = {
            line_id: item["amount_variance"] for line_id, item in payload.items()
        }
        return payload

    def convert_gbp_usd(self, amount: Decimal | None = None) -> list[dict[str, object]]:
        """Convert each GBP line actual and budget. The FX rate is never an input amount."""
        del amount
        self.invoked.append("convert_gbp_usd")
        facts = self._ensure()
        results: list[ConversionResult] = []
        for fact in facts.lines.values():
            if fact.currency != CURRENCY_GBP:
                continue
            if fact.verified_actual is not None:
                results.append(
                    ConversionResult(
                        line_id=fact.line_id,
                        basis="verified_actual",
                        gbp_amount=str(fact.verified_actual),
                        usd_amount=str(to_usd(fact.verified_actual, CURRENCY_GBP)),
                        rate=str(FX_GBP_USD),
                        fx_source=FX_SOURCE,
                        source_refs=fact.source_refs,
                    )
                )
            if fact.budget is not None:
                results.append(
                    ConversionResult(
                        line_id=fact.line_id,
                        basis="budget",
                        gbp_amount=str(fact.budget),
                        usd_amount=str(to_usd(fact.budget, CURRENCY_GBP)),
                        rate=str(FX_GBP_USD),
                        fx_source=FX_SOURCE,
                        source_refs=fact.budget_row_ids,
                    )
                )
        facts.conversion_results = tuple(results)
        payload = [
            {
                "line_id": item.line_id,
                "basis": item.basis,
                "gbp_amount": item.gbp_amount,
                "usd_amount": item.usd_amount,
                "rate": item.rate,
                "fx_source": item.fx_source,
                "source_refs": list(item.source_refs),
            }
            for item in results
        ]
        self.tool_results["convert_gbp_usd"] = payload
        return payload

    def select_relevant_deviations(self) -> list[str]:
        self.invoked.append("select_relevant_deviations")
        facts = self._ensure()
        payload = [line_id for line_id, fact in facts.lines.items() if fact.relevant]
        self.tool_results["select_relevant_deviations"] = payload
        return payload

    def completeness(self) -> dict[str, object]:
        self.invoked.append("completeness")
        facts = self._ensure()
        return {
            "incomplete": facts.incomplete,
            "missing_lines": list(facts.missing_lines),
            "missing_files": list(facts.missing_files),
            "quarantined_entry_ids": list(facts.quarantined_entry_ids),
        }

    def lookup_sources(self) -> dict[str, list[str]]:
        self.invoked.append("lookup_sources")
        facts = self._ensure()
        return {line_id: list(fact.source_refs) for line_id, fact in facts.lines.items()}

    def invoke(self, names: list[str], *, mandatory: tuple[str, ...] = ()) -> CloseFacts:
        registry = {
            "ingest_and_normalize": self.ingest_and_normalize,
            "aggregate_lines": self.aggregate_lines,
            "actual_versus_budget": self.actual_versus_budget,
            "convert_gbp_usd": self.convert_gbp_usd,
            "select_relevant_deviations": self.select_relevant_deviations,
            "completeness": self.completeness,
            "lookup_sources": self.lookup_sources,
        }
        selected = [name for name in names if name in registry]
        fallback = not selected
        if fallback:
            selected = list(ALLOWED_TOOLS)
        ordered: list[str] = []

        def add(name: str) -> None:
            if name not in registry or name in ordered:
                return
            for dependency in TOOL_DEPENDENCIES.get(name, ()):
                add(dependency)
            ordered.append(name)

        for name in mandatory:
            add(name)
        for name in selected:
            add(name)
        for name in ordered:
            registry[name]()
        facts = self._ensure()
        facts.invoked_tools = tuple(self.invoked)
        facts.model_selected_tools = tuple(name for name in names if name in registry)
        facts.dependency_tools = tuple(name for name in ordered if name not in facts.model_selected_tools)
        facts.deterministic_fallback = fallback
        return facts
