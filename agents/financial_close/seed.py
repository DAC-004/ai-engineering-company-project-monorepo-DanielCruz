"""Author briefing CSVs for a load date. Amounts stay exact; dates follow the last full month."""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

from agents.financial_close.calendar import clamp_day_in_period, closing_period_for_load_date, month_name
from agents.financial_close.constants import (
    BUDGET_COLUMNS,
    CAT_CONSUMABLES,
    CAT_INTERPRETING,
    CAT_LAB,
    CAT_PAYROLL,
    CAT_RENT,
    CAT_REVENUE,
    CAT_SOFTWARE,
    COUNTRY_UK,
    COUNTRY_US,
    CURRENCY_GBP,
    CURRENCY_USD,
    LEDGER_COLUMNS,
    METRIC_CLAIMS_ACTUAL,
    METRIC_CLAIMS_BUDGET,
    METRIC_DENIAL_ACTUAL,
    METRIC_DENIAL_BUDGET,
    OPERATIONS_COLUMNS,
    PAYER_COMMERCIAL,
    PAYER_MEDICARE,
    PAYER_NA,
    PAYER_NHS,
    PAYER_PRIVATE,
    phi_entry_id_for,
)

# day, country, payer, category, description, currency, amount
LEDGER_TEMPLATES: tuple[tuple[object, ...], ...] = (
    (3, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Austin North clinic commercial insurance aggregate", CURRENCY_USD, "180000"),
    (4, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Austin South clinic commercial insurance aggregate", CURRENCY_USD, "160000"),
    (5, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Houston clinic commercial insurance aggregate", CURRENCY_USD, "140000"),
    (6, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Dallas clinic commercial insurance aggregate", CURRENCY_USD, "130000"),
    (7, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "San Antonio clinic commercial insurance aggregate", CURRENCY_USD, "120000"),
    (8, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Miami clinic commercial insurance aggregate", CURRENCY_USD, "110000"),
    (9, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Orlando clinic commercial insurance aggregate", CURRENCY_USD, "100000"),
    (10, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Atlanta clinic commercial insurance aggregate", CURRENCY_USD, "90000"),
    (11, COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, "Savannah clinic commercial insurance aggregate", CURRENCY_USD, "90000"),
    (3, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Austin North clinic Medicare Medicaid aggregate", CURRENCY_USD, "80000"),
    (4, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Austin South clinic Medicare Medicaid aggregate", CURRENCY_USD, "70000"),
    (5, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Houston clinic Medicare Medicaid aggregate", CURRENCY_USD, "60000"),
    (6, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Dallas clinic Medicare Medicaid aggregate", CURRENCY_USD, "55000"),
    (7, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "San Antonio clinic Medicare Medicaid aggregate", CURRENCY_USD, "50000"),
    (8, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Miami clinic Medicare Medicaid aggregate", CURRENCY_USD, "45000"),
    (9, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Orlando clinic Medicare Medicaid aggregate", CURRENCY_USD, "40000"),
    (10, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Atlanta clinic Medicare Medicaid aggregate", CURRENCY_USD, "38000"),
    (11, COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, "Savannah clinic Medicare Medicaid aggregate", CURRENCY_USD, "30000"),
    (12, COUNTRY_UK, PAYER_PRIVATE, CAT_REVENUE, "London Central clinic private pay aggregate", CURRENCY_GBP, "120000"),
    (13, COUNTRY_UK, PAYER_PRIVATE, CAT_REVENUE, "London East clinic private pay aggregate", CURRENCY_GBP, "90000"),
    (14, COUNTRY_UK, PAYER_PRIVATE, CAT_REVENUE, "Manchester clinic private pay aggregate", CURRENCY_GBP, "61000"),
    (12, COUNTRY_UK, PAYER_NHS, CAT_REVENUE, "London Central clinic NHS contract aggregate", CURRENCY_GBP, "30000"),
    (13, COUNTRY_UK, PAYER_NHS, CAT_REVENUE, "London East clinic NHS contract aggregate", CURRENCY_GBP, "25000"),
    (14, COUNTRY_UK, PAYER_NHS, CAT_REVENUE, "Manchester clinic NHS contract aggregate", CURRENCY_GBP, "20000"),
    (15, COUNTRY_US, PAYER_NA, CAT_CONSUMABLES, "MedSupply Partners disposable consultation kit unit_price=3.344 quantity=8000", CURRENCY_USD, "-26752"),
    (16, COUNTRY_US, PAYER_NA, CAT_CONSUMABLES, "MedSupply Partners disposable consultation kit unit_price=3.344 quantity=6000", CURRENCY_USD, "-20064"),
    (15, COUNTRY_US, PAYER_NA, CAT_LAB, "ClearPath Labs basic metabolic panel unit_price=19.26 quantity=1500", CURRENCY_USD, "-28890"),
    (16, COUNTRY_US, PAYER_NA, CAT_LAB, "ClearPath Labs basic metabolic panel unit_price=19.26 quantity=1000", CURRENCY_USD, "-19260"),
    (17, COUNTRY_US, PAYER_NA, CAT_INTERPRETING, "LinguaCare Interpreting medical interpreting unit_price=1.95 quantity=5000", CURRENCY_USD, "-9750"),
    (18, COUNTRY_US, PAYER_NA, CAT_INTERPRETING, "LinguaCare Interpreting medical interpreting unit_price=1.95 quantity=4000", CURRENCY_USD, "-7800"),
    (20, COUNTRY_US, PAYER_NA, CAT_PAYROLL, "US_PAYROLL", CURRENCY_USD, "-600000"),
    (21, COUNTRY_US, PAYER_NA, CAT_PAYROLL, "US_PAYROLL_REMAINDER", CURRENCY_USD, "-460000"),
    (31, COUNTRY_US, PAYER_NA, CAT_RENT, "United States clinic rent Austin group", CURRENCY_USD, "-120000"),
    (6, COUNTRY_US, PAYER_NA, CAT_RENT, "United States clinic rent remaining locations", CURRENCY_USD, "-59000"),
    (18, COUNTRY_US, PAYER_NA, CAT_RENT, "PHI", CURRENCY_USD, "-1000"),
    (15, COUNTRY_UK, PAYER_NA, CAT_CONSUMABLES, "BritMed Supplies disposable consultation kit unit_price=2.70 quantity=2000", CURRENCY_GBP, "-5400"),
    (16, COUNTRY_UK, PAYER_NA, CAT_CONSUMABLES, "BritMed Supplies disposable consultation kit unit_price=2.70 quantity=1500", CURRENCY_GBP, "-4050"),
    (15, COUNTRY_UK, PAYER_NA, CAT_LAB, "Thames Pathology basic metabolic panel unit_price=14.79 quantity=400", CURRENCY_GBP, "-5916"),
    (16, COUNTRY_UK, PAYER_NA, CAT_LAB, "Thames Pathology basic metabolic panel unit_price=14.79 quantity=300", CURRENCY_GBP, "-4437"),
    (20, COUNTRY_UK, PAYER_NA, CAT_PAYROLL, "UK_PAYROLL", CURRENCY_GBP, "-120000"),
    (21, COUNTRY_UK, PAYER_NA, CAT_PAYROLL, "UK_PAYROLL_REMAINDER", CURRENCY_GBP, "-89000"),
    (5, COUNTRY_UK, PAYER_NA, CAT_RENT, "United Kingdom clinic rent London", CURRENCY_GBP, "-32000"),
    (6, COUNTRY_UK, PAYER_NA, CAT_RENT, "United Kingdom clinic rent Manchester", CURRENCY_GBP, "-20000"),
)

BUDGET_TEMPLATES: tuple[tuple[str, ...], ...] = (
    (COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, CURRENCY_USD, "1150000"),
    (COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, CURRENCY_USD, "520000"),
    (COUNTRY_UK, PAYER_PRIVATE, CAT_REVENUE, CURRENCY_GBP, "260000"),
    (COUNTRY_UK, PAYER_NHS, CAT_REVENUE, CURRENCY_GBP, "75000"),
    (COUNTRY_US, PAYER_NA, CAT_CONSUMABLES, CURRENCY_USD, "44800"),
    (COUNTRY_US, PAYER_NA, CAT_LAB, CURRENCY_USD, "45000"),
    (COUNTRY_US, PAYER_NA, CAT_INTERPRETING, CURRENCY_USD, "17550"),
    (COUNTRY_US, PAYER_NA, CAT_PAYROLL, CURRENCY_USD, "1050000"),
    (COUNTRY_US, PAYER_NA, CAT_RENT, CURRENCY_USD, "180000"),
    (COUNTRY_UK, PAYER_NA, CAT_CONSUMABLES, CURRENCY_GBP, "9450"),
    (COUNTRY_UK, PAYER_NA, CAT_LAB, CURRENCY_GBP, "10150"),
    (COUNTRY_UK, PAYER_NA, CAT_PAYROLL, CURRENCY_GBP, "210000"),
    (COUNTRY_UK, PAYER_NA, CAT_RENT, CURRENCY_GBP, "52000"),
    (COUNTRY_UK, PAYER_NA, CAT_SOFTWARE, CURRENCY_GBP, "8000"),
)

OPERATIONS_TEMPLATES: tuple[tuple[str, ...], ...] = (
    (COUNTRY_US, PAYER_MEDICARE, METRIC_CLAIMS_BUDGET, "4000"),
    (COUNTRY_US, PAYER_MEDICARE, METRIC_CLAIMS_ACTUAL, "4000"),
    (COUNTRY_US, PAYER_MEDICARE, METRIC_DENIAL_BUDGET, "14.0"),
    (COUNTRY_US, PAYER_MEDICARE, METRIC_DENIAL_ACTUAL, "22.6"),
    (COUNTRY_US, PAYER_COMMERCIAL, METRIC_CLAIMS_BUDGET, "6500"),
    (COUNTRY_US, PAYER_COMMERCIAL, METRIC_CLAIMS_ACTUAL, "6400"),
    (COUNTRY_US, PAYER_COMMERCIAL, METRIC_DENIAL_BUDGET, "12.0"),
    (COUNTRY_US, PAYER_COMMERCIAL, METRIC_DENIAL_ACTUAL, "12.0"),
)

# Test-only expected raw sums. Runtime calculation never reads this mapping.
FIXTURE_ORACLE = {
    "us_commercial_revenue": (Decimal("1150000"), Decimal("1120000")),
    "us_medicare_medicaid_revenue": (Decimal("520000"), Decimal("468000")),
    "uk_private_revenue": (Decimal("260000"), Decimal("271000")),
    "uk_nhs_revenue": (Decimal("75000"), Decimal("75000")),
    "us_consumables": (Decimal("44800"), Decimal("46816")),
    "us_laboratory": (Decimal("45000"), Decimal("48150")),
    "us_interpreting": (Decimal("17550"), Decimal("17550")),
    "us_payroll": (Decimal("1050000"), Decimal("1060000")),
    "us_rent": (Decimal("180000"), Decimal("180000")),
    "uk_consumables": (Decimal("9450"), Decimal("9450")),
    "uk_laboratory": (Decimal("10150"), Decimal("10353")),
    "uk_payroll": (Decimal("210000"), Decimal("209000")),
    "uk_rent": (Decimal("52000"), Decimal("52000")),
    "uk_software": (Decimal("8000"), None),
}

PHI_DESCRIPTION = "Mis-posted refund for patient Jordan Hale Austin North"


def _description(token: str, period: str) -> str:
    label = month_name(period)
    year = period[:4]
    if token == "US_PAYROLL":
        return f"United States payroll aggregate {label} {year}"
    if token == "US_PAYROLL_REMAINDER":
        return f"United States payroll aggregate remainder {label} {year}"
    if token == "UK_PAYROLL":
        return f"United Kingdom payroll aggregate {label} {year}"
    if token == "UK_PAYROLL_REMAINDER":
        return f"United Kingdom payroll aggregate remainder {label} {year}"
    if token == "PHI":
        return PHI_DESCRIPTION
    return token


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixtures(root: Path, load_date: date) -> dict[str, str]:
    period = closing_period_for_load_date(load_date)
    compact = period.replace("-", "")
    ledger_rows = []
    sequence = 1
    for index, template in enumerate(LEDGER_TEMPLATES, start=1):
        day, country, payer, category, token, currency, amount = template
        token_text = str(token)
        if token_text == "PHI":
            entry_id = phi_entry_id_for(period)
        else:
            entry_id = f"LED-{compact}-{sequence:03d}"
            sequence += 1
        ledger_rows.append(
            {
                "entry_id": entry_id,
                "date": clamp_day_in_period(period, int(day)).isoformat(),
                "country": str(country),
                "payer": str(payer),
                "category": str(category),
                "description": _description(token_text, period),
                "currency": str(currency),
                "amount": str(amount),
                "source_ref": f"ledger.csv:{index}",
            }
        )
    budget_rows = [
        {
            "month": period,
            "country": row[0],
            "payer": row[1],
            "category": row[2],
            "currency": row[3],
            "amount": row[4],
        }
        for row in BUDGET_TEMPLATES
    ]
    operations_rows = [
        {
            "month": period,
            "country": row[0],
            "payer": row[1],
            "metric": row[2],
            "value": row[3],
        }
        for row in OPERATIONS_TEMPLATES
    ]
    return {
        "ledger.csv": write_csv(root / "ledger.csv", LEDGER_COLUMNS, ledger_rows),
        "budget.csv": write_csv(root / "budget.csv", BUDGET_COLUMNS, budget_rows),
        "operations.csv": write_csv(root / "operations.csv", OPERATIONS_COLUMNS, operations_rows),
        "period": period,
    }
