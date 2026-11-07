"""Normalize close CSVs. Keep every row; never drop missing or inconsistent input."""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from agents.financial_close.calendar import last_date_of_period, parse_period
from agents.financial_close.constants import LINE_SPEC
from agents.financial_close.money import decimal_from_text
from agents.financial_close.privacy import (
    ALLOWED_CATEGORIES,
    ALLOWED_COUNTRIES,
    ALLOWED_CURRENCIES,
    ALLOWED_METRICS,
    ALLOWED_PAYERS,
    COUNTRY_CURRENCY,
    METRIC_CLAIMS_ACTUAL,
    METRIC_CLAIMS_BUDGET,
    METRIC_DENIAL_ACTUAL,
    METRIC_DENIAL_BUDGET,
    PAYER_COUNTRY,
    description_quarantine_reason,
    is_valid_entry_id,
    is_valid_source_ref,
    safe_description_projection,
)
from agents.financial_close.types import BudgetRow, LedgerRow, OperationsRow

# Supporting supplier arithmetic is parsed from the allowlisted projection only.
_SUPPLIER_SUPPORT = re.compile(
    r" unit_price=(?P<price>\d+(?:\.\d+)?) quantity=(?P<qty>\d+)$"
)


def _supporting_amount_mismatch(safe_description: str | None, amount: Decimal | None) -> bool:
    """True when unit_price * quantity does not equal the negated signed expense amount."""
    if not safe_description or amount is None:
        return False
    match = _SUPPLIER_SUPPORT.search(safe_description)
    if match is None:
        return False
    product = Decimal(match.group("price")) * Decimal(match.group("qty"))
    return amount != -product


def file_sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _line_id(country: str, payer: str, category: str) -> str | None:
    for line_id, spec in LINE_SPEC.items():
        if spec[0] == country and spec[1] == payer and spec[2] == category:
            return line_id
    return None


def _parse_iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_amount(text: str) -> Decimal | None:
    try:
        return decimal_from_text(text)
    except (InvalidOperation, ValueError):
        return None


def _period_window(period: str) -> tuple[date, date]:
    year, month = parse_period(period)
    return date(year, month, 1), last_date_of_period(period)


def ingest_ledger(path: Path, period: str) -> list[LedgerRow]:
    if not path.exists():
        return []
    start, last = _period_window(period)
    staged: list[dict] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(
            ("entry_id", "date", "country", "payer", "category", "description", "currency", "amount", "source_ref")
        ):
            raise ValueError("ledger_columns")
        for index, raw in enumerate(reader, start=1):
            issues: list[str] = []
            ingest_ref = f"ingest.ledger.{index}"
            raw_entry = (raw.get("entry_id") or "").strip()
            public_entry_id = raw_entry if is_valid_entry_id(raw_entry) else None
            if not raw_entry:
                issues.append("missing_entry_id")
            elif public_entry_id is None:
                issues.append("invalid_entry_id")
            amount = _parse_amount((raw.get("amount") or "").strip())
            if amount is None:
                issues.append("malformed_amount")
            parsed_day = _parse_iso_date((raw.get("date") or "").strip())
            if parsed_day is None:
                issues.append("invalid_date")
            elif parsed_day < start or parsed_day > last:
                issues.append("date_outside_period")
            country = (raw.get("country") or "").strip()
            payer = (raw.get("payer") or "").strip()
            category = (raw.get("category") or "").strip()
            currency = (raw.get("currency") or "").strip()
            if country not in ALLOWED_COUNTRIES:
                issues.append("unknown_country")
            if payer not in ALLOWED_PAYERS:
                issues.append("unknown_payer")
            if category not in ALLOWED_CATEGORIES:
                issues.append("unknown_category")
            if currency not in ALLOWED_CURRENCIES:
                issues.append("unknown_currency")
            expected_country = PAYER_COUNTRY.get(payer)
            if expected_country and country in ALLOWED_COUNTRIES and country != expected_country:
                issues.append("payer_country_mismatch")
            if country in COUNTRY_CURRENCY and currency in ALLOWED_CURRENCIES and currency != COUNTRY_CURRENCY[country]:
                issues.append("currency_country_mismatch")
            line_id = _line_id(country, payer, category)
            if line_id is None:
                issues.append("unknown_line")
            else:
                _line_country, _line_payer, _line_category, line_currency, kind = LINE_SPEC[line_id]
                if currency in ALLOWED_CURRENCIES and currency != line_currency:
                    issues.append("currency_line_mismatch")
                if amount is not None:
                    if amount == 0:
                        issues.append("zero_amount")
                    elif kind == "revenue" and amount <= 0:
                        issues.append("unexpected_sign")
                    elif kind == "expense" and amount >= 0:
                        issues.append("unexpected_sign")
            source_ref = (raw.get("source_ref") or "").strip() or f"ledger.csv:{index}"
            if not is_valid_source_ref(source_ref):
                issues.append("invalid_source_ref")
                source_ref = f"ledger.csv:{index}"
            description = raw.get("description") or ""
            reason = description_quarantine_reason(description)
            safe_description = safe_description_projection(description)
            if reason:
                issues.append(reason)
            if _supporting_amount_mismatch(safe_description, amount):
                issues.append("inconsistent_supporting_amount")
            staged.append(
                {
                    "ingest_ref": ingest_ref,
                    "public_entry_id": public_entry_id,
                    "raw_entry": raw_entry,
                    "date": parsed_day.isoformat() if parsed_day else None,
                    "country": country,
                    "payer": payer,
                    "category": category,
                    "currency": currency,
                    "amount": amount,
                    "source_ref": source_ref,
                    "line_id": line_id,
                    "quarantine_reason": reason,
                    "safe_description": safe_description,
                    "issues": issues,
                }
            )
    counts = Counter(item["raw_entry"] for item in staged if item["raw_entry"])
    rows: list[LedgerRow] = []
    for item in staged:
        issues = list(item["issues"])
        duplicated = bool(item["raw_entry"] and counts[item["raw_entry"]] > 1)
        if duplicated:
            issues.append("duplicate_entry_id")
        uncertain = bool(issues)
        exclude = duplicated or item["amount"] is None
        rows.append(
            LedgerRow(
                ingest_ref=item["ingest_ref"],
                public_entry_id=item["public_entry_id"],
                date=item["date"],
                country=item["country"],
                payer=item["payer"],
                category=item["category"],
                currency=item["currency"],
                amount=item["amount"],
                source_ref=item["source_ref"],
                line_id=item["line_id"],
                uncertain=uncertain,
                exclude_from_totals=exclude,
                quarantine_reason=item["quarantine_reason"],
                safe_description=item["safe_description"],
                issues=tuple(dict.fromkeys(issues)),
            )
        )
    return rows


def ingest_budget(path: Path, period: str) -> list[BudgetRow]:
    if not path.exists():
        return []
    digest = file_sha256(path)
    staged: list[dict] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(("month", "country", "payer", "category", "currency", "amount")):
            raise ValueError("budget_columns")
        for index, raw in enumerate(reader, start=1):
            issues: list[str] = []
            ingest_ref = f"ingest.budget.{index}"
            month = (raw.get("month") or "").strip()
            try:
                parse_period(month)
            except ValueError:
                issues.append("invalid_month")
                month = None
            if month is not None and month != period:
                issues.append("month_mismatch")
            amount = _parse_amount((raw.get("amount") or "").strip())
            if amount is None:
                issues.append("malformed_amount")
            country = (raw.get("country") or "").strip()
            payer = (raw.get("payer") or "").strip()
            category = (raw.get("category") or "").strip()
            currency = (raw.get("currency") or "").strip()
            if country not in ALLOWED_COUNTRIES:
                issues.append("unknown_country")
            if payer not in ALLOWED_PAYERS:
                issues.append("unknown_payer")
            if category not in ALLOWED_CATEGORIES:
                issues.append("unknown_category")
            if currency not in ALLOWED_CURRENCIES:
                issues.append("unknown_currency")
            if country in COUNTRY_CURRENCY and currency in ALLOWED_CURRENCIES and currency != COUNTRY_CURRENCY[country]:
                issues.append("currency_country_mismatch")
            line_id = _line_id(country, payer, category)
            if line_id is None:
                issues.append("unknown_line")
            else:
                line_currency = LINE_SPEC[line_id][3]
                if currency in ALLOWED_CURRENCIES and currency != line_currency:
                    issues.append("currency_line_mismatch")
            staged.append(
                {
                    "ingest_ref": ingest_ref,
                    "row_id": f"budget.csv:{index}#{digest[:12]}",
                    "month": month,
                    "country": country,
                    "payer": payer,
                    "category": category,
                    "currency": currency,
                    "amount": amount,
                    "line_id": line_id,
                    "key": (month, country, payer, category),
                    "issues": issues,
                }
            )
    counts = Counter(item["key"] for item in staged)
    rows: list[BudgetRow] = []
    for item in staged:
        issues = list(item["issues"])
        duplicated = counts[item["key"]] > 1
        if duplicated:
            issues.append("duplicate_budget_key")
        uncertain = bool(issues)
        rows.append(
            BudgetRow(
                ingest_ref=item["ingest_ref"],
                row_id=item["row_id"],
                month=item["month"],
                country=item["country"],
                payer=item["payer"],
                category=item["category"],
                currency=item["currency"],
                amount=item["amount"],
                line_id=item["line_id"],
                uncertain=uncertain,
                exclude_from_totals=duplicated or item["amount"] is None,
                issues=tuple(dict.fromkeys(issues)),
            )
        )
    return rows


def ingest_operations(path: Path, period: str) -> list[OperationsRow]:
    if not path.exists():
        return []
    digest = file_sha256(path)
    staged: list[dict] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(("month", "country", "payer", "metric", "value")):
            raise ValueError("operations_columns")
        for index, raw in enumerate(reader, start=1):
            issues: list[str] = []
            ingest_ref = f"ingest.operations.{index}"
            month = (raw.get("month") or "").strip()
            try:
                parse_period(month)
            except ValueError:
                issues.append("invalid_month")
                month = None
            if month is not None and month != period:
                issues.append("month_mismatch")
            value = _parse_amount((raw.get("value") or "").strip())
            if value is None:
                issues.append("malformed_value")
            country = (raw.get("country") or "").strip()
            payer = (raw.get("payer") or "").strip()
            metric = (raw.get("metric") or "").strip()
            if country not in ALLOWED_COUNTRIES:
                issues.append("unknown_country")
                country = None
            if payer not in ALLOWED_PAYERS:
                issues.append("unknown_payer")
                payer = None
            if metric not in ALLOWED_METRICS:
                issues.append("unknown_metric")
                metric = None
            elif value is not None:
                if metric in {METRIC_CLAIMS_BUDGET, METRIC_CLAIMS_ACTUAL} and value < 0:
                    issues.append("metric_out_of_range")
                if metric in {METRIC_DENIAL_BUDGET, METRIC_DENIAL_ACTUAL} and (value < 0 or value > 100):
                    issues.append("metric_out_of_range")
            staged.append(
                {
                    "ingest_ref": ingest_ref,
                    "row_id": f"operations.csv:{index}#{digest[:12]}",
                    "month": month,
                    "country": country,
                    "payer": payer,
                    "metric": metric,
                    "value": value,
                    "key": (month, country, payer, metric),
                    "issues": issues,
                }
            )
    counts = Counter(item["key"] for item in staged)
    rows: list[OperationsRow] = []
    for item in staged:
        issues = list(item["issues"])
        duplicated = counts[item["key"]] > 1
        if duplicated:
            issues.append("duplicate_operations_key")
        uncertain = bool(issues)
        rows.append(
            OperationsRow(
                ingest_ref=item["ingest_ref"],
                row_id=item["row_id"],
                month=item["month"],
                country=item["country"],
                payer=item["payer"],
                metric=item["metric"],
                value=item["value"],
                uncertain=uncertain,
                exclude_from_totals=duplicated or item["value"] is None or uncertain,
                issues=tuple(dict.fromkeys(issues)),
            )
        )
    return rows
