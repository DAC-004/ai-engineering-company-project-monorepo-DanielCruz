"""Deterministic Decimal pricing tools. Never reads Supplier Directory floats."""

from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path

from agents.supplier_contracts.constants import GBP_USD, PRICE_ALERT_THRESHOLD
from agents.supplier_contracts.identity import PRICING_ID, PRICING_TOOLS
from agents.supplier_contracts.registry import BY_ID, require_supplier
from agents.supplier_contracts.types import AlternativeQuote, PriceRow, PricingRequest, PricingResult

TWELVE = Decimal("12")
CENT = Decimal("0.01")
RATIO = Decimal("0.0001")
MONTH_KEY = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PriceDataError(ValueError):
    """Malformed price history. Callers must not calculate across the bad rows."""


def _dec(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise PriceDataError(f"invalid_{field}") from exc
    if not parsed.is_finite():
        raise PriceDataError(f"nonfinite_{field}")
    return parsed


def load_price_rows(csv_path: Path) -> list[PriceRow]:
    rows: list[PriceRow] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for index, raw in enumerate(csv.DictReader(handle), start=1):
            missing = [name for name in ("supplier_id", "product", "unit", "currency", "month", "unit_price", "monthly_volume") if not raw.get(name)]
            if missing:
                raise PriceDataError("missing_price_fields")
            if not MONTH_KEY.match(raw["month"]):
                raise PriceDataError("invalid_month")
            unit_price = _dec(raw["unit_price"], "unit_price")
            monthly_volume = _dec(raw["monthly_volume"], "monthly_volume")
            if unit_price <= 0:
                raise PriceDataError("nonpositive_unit_price")
            if monthly_volume < 0:
                raise PriceDataError("negative_monthly_volume")
            rows.append(
                PriceRow(
                    row_id=f"{csv_path.name}:{index}",
                    supplier_id=raw["supplier_id"],
                    product=raw["product"],
                    unit=raw["unit"],
                    currency=raw["currency"],
                    month=raw["month"],
                    unit_price=unit_price,
                    monthly_volume=monthly_volume,
                    source_path=str(csv_path),
                )
            )
    return rows


def _month_tuple(month: str) -> tuple[int, int]:
    year, month_number = month.split("-")
    return int(year), int(month_number)


def _consecutive(previous: str, current: str) -> bool:
    year, month = _month_tuple(previous)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    actual_year, actual_month = _month_tuple(current)
    return actual_year == next_year and actual_month == next_month


def _in_range(month: str, month_from: str | None, month_to: str | None) -> bool:
    if month_from and month < month_from:
        return False
    if month_to and month > month_to:
        return False
    return True


def _ordered(rows: list[PriceRow], supplier_id: str, request: PricingRequest) -> list[PriceRow]:
    selected = [
        row
        for row in rows
        if row.supplier_id == supplier_id
        and (request.product is None or row.product == request.product)
        and _in_range(row.month, request.month_from, request.month_to)
    ]
    ordered = sorted(selected, key=lambda row: row.month)
    if not ordered:
        return []
    product, unit, currency = ordered[0].product, ordered[0].unit, ordered[0].currency
    if any(row.product != product or row.unit != unit or row.currency != currency for row in ordered):
        raise PriceDataError("mixed_product_unit_currency")
    for previous, current in zip(ordered, ordered[1:]):
        if not _consecutive(previous.month, current.month):
            raise PriceDataError("nonconsecutive_months")
    return ordered


def convert_gbp_usd(amount: Decimal) -> Decimal:
    return (amount * GBP_USD).quantize(CENT, rounding=ROUND_HALF_EVEN)


def detect_increase(previous: Decimal, current: Decimal) -> tuple[Decimal, bool]:
    if previous == 0:
        raise PriceDataError("previous_price_zero")
    ratio = (current - previous) / previous
    return ratio, ratio > PRICE_ALERT_THRESHOLD


def annual_incremental(previous: Decimal, current: Decimal, volume: Decimal) -> Decimal:
    return ((current - previous) * volume * TWELVE).quantize(CENT, rounding=ROUND_HALF_EVEN)


def _require_pricing_tool(tool: str) -> None:
    if tool not in PRICING_TOOLS:
        raise PriceDataError("tool_not_allowed")


def compare_same_country_category(
    rows: list[PriceRow],
    supplier_id: str,
    current_price: Decimal,
    volume: Decimal,
    product: str,
    month_from: str | None = None,
    month_to: str | None = None,
) -> tuple[AlternativeQuote, ...]:
    """Hypothetical impact uses the subject's evidenced volume only. Zero volume stays unknown."""
    _require_pricing_tool("compare_same_country_category")
    subject = require_supplier(supplier_id)
    alternatives: list[AlternativeQuote] = []
    for other in BY_ID.values():
        if other.supplier_id == supplier_id:
            continue
        if other.country != subject.country or other.category != subject.category:
            continue
        history = [
            row
            for row in rows
            if row.supplier_id == other.supplier_id
            and row.product == product
            and _in_range(row.month, month_from, month_to)
        ]
        history = sorted(history, key=lambda row: row.month)
        if not history:
            continue
        latest = history[-1]
        difference = annual_incremental(latest.unit_price, current_price, volume) if volume > 0 else None
        alternatives.append(
            AlternativeQuote(
                supplier_id=other.supplier_id,
                display_name=other.display_name,
                unit_price=latest.unit_price,
                currency=latest.currency,
                quote_only=other.quote_only,
                same_country=True,
                same_category=True,
                hypothetical_annual_difference=difference,
                source_row_ids=(latest.row_id,),
                availability_assumed=False,
            )
        )
    return tuple(alternatives)


def _empty_result(supplier, missing: tuple[str, ...], history: list[PriceRow]) -> PricingResult:
    return PricingResult(
        supplier_id=supplier.supplier_id,
        product=supplier.product,
        unit=supplier.unit,
        currency=supplier.currency,
        previous_price=None,
        current_price=None,
        change_ratio=None,
        above_threshold=False,
        annual_incremental=None,
        annual_incremental_usd=None,
        formula="",
        source_row_ids=tuple(row.row_id for row in history),
        alternatives=(),
        quote_only=supplier.quote_only,
        missing=missing,
        observation_from=history[0].month if history else None,
        observation_to=history[-1].month if history else None,
        actor_id=PRICING_ID,
    )


def run_pricing(rows: list[PriceRow], request: PricingRequest) -> PricingResult:
    supplier = require_supplier(request.supplier_id)
    history = _ordered(rows, request.supplier_id, request)
    if len(history) < 2:
        return _empty_result(supplier, ("price_history",), history)
    previous, current = history[-2], history[-1]
    _require_pricing_tool("detect_increase")
    _require_pricing_tool("calculate_annual_impact")
    ratio, above = detect_increase(previous.unit_price, current.unit_price)
    # Quote-only zero volume is evidenced, not invented. Impact is then zero.
    impact = annual_incremental(previous.unit_price, current.unit_price, current.monthly_volume)
    impact_usd = convert_gbp_usd(impact) if current.currency == "GBP" else impact
    formula = (
        f"({format(current.unit_price, 'f')}-{format(previous.unit_price, 'f')})"
        f"*{format(current.monthly_volume, 'f')}*12"
        f"; ratio=({format(current.unit_price, 'f')}-{format(previous.unit_price, 'f')})"
        f"/{format(previous.unit_price, 'f')}"
    )
    alternatives = ()
    if request.calculation in {"compare", "increase", "impact"}:
        alternatives = compare_same_country_category(
            rows,
            supplier.supplier_id,
            current.unit_price,
            current.monthly_volume,
            current.product,
            month_from=request.month_from,
            month_to=request.month_to,
        )
    return PricingResult(
        supplier_id=supplier.supplier_id,
        product=current.product,
        unit=current.unit,
        currency=current.currency,
        previous_price=previous.unit_price,
        current_price=current.unit_price,
        change_ratio=ratio.quantize(RATIO, rounding=ROUND_HALF_EVEN),
        above_threshold=above,
        annual_incremental=impact,
        annual_incremental_usd=impact_usd,
        formula=formula,
        source_row_ids=(previous.row_id, current.row_id),
        alternatives=alternatives,
        quote_only=supplier.quote_only,
        missing=(),
        observation_from=previous.month,
        observation_to=current.month,
        actor_id=PRICING_ID,
    )
