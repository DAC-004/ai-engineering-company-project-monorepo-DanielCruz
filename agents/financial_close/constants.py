"""Exact briefing identifiers. Do not invent a seventh department or FX rate."""

from __future__ import annotations

from decimal import Decimal

FX_GBP_USD = Decimal("1.27")
FX_SOURCE = "briefing:reference_exchange_rate:1 GBP = 1.27 USD"
DEVIATION_THRESHOLD = Decimal("0.05")
AUSTIN_TZ = "America/Chicago"
SCHEDULE_HOUR = 6
SCHEDULE_MINUTE = 0
BUSINESS_DAY_ORDINAL = 3
AGENT_ID = "financial-close-agent"
CURRENCY_USD = "USD"
CURRENCY_GBP = "GBP"
ALLOWED_CURRENCIES = frozenset({CURRENCY_USD, CURRENCY_GBP})
COUNTRY_US = "United States"
COUNTRY_UK = "United Kingdom"
PAYER_COMMERCIAL = "commercial insurance"
PAYER_MEDICARE = "Medicare / Medicaid"
PAYER_PRIVATE = "private"
PAYER_NHS = "NHS contract"
PAYER_NA = "n/a"
CAT_REVENUE = "revenue"
CAT_CONSUMABLES = "clinical consumables"
CAT_LAB = "laboratory"
CAT_INTERPRETING = "medical interpreting"
CAT_PAYROLL = "payroll"
CAT_RENT = "clinic rent"
CAT_SOFTWARE = "clinical software licences"
def phi_entry_id_for(period: str) -> str:
    return f"LED-{period.replace('-', '')}-PHI1"


PHI_ENTRY_ID = "LED-202610-PHI1"
PERIOD_OCT_2026 = "2026-10"
LEDGER_COLUMNS = (
    "entry_id",
    "date",
    "country",
    "payer",
    "category",
    "description",
    "currency",
    "amount",
    "source_ref",
)
BUDGET_COLUMNS = ("month", "country", "payer", "category", "currency", "amount")
OPERATIONS_COLUMNS = ("month", "country", "payer", "metric", "value")
METRIC_CLAIMS_BUDGET = "claims_submitted_budget"
METRIC_CLAIMS_ACTUAL = "claims_submitted_actual"
METRIC_DENIAL_BUDGET = "denial_rate_pct_budget"
METRIC_DENIAL_ACTUAL = "denial_rate_pct_actual"

# Line catalog used by aggregation. Expense payer is always n/a.
LINE_IDS = (
    "us_commercial_revenue",
    "us_medicare_medicaid_revenue",
    "uk_private_revenue",
    "uk_nhs_revenue",
    "us_consumables",
    "us_laboratory",
    "us_interpreting",
    "us_payroll",
    "us_rent",
    "uk_consumables",
    "uk_laboratory",
    "uk_payroll",
    "uk_rent",
    "uk_software",
)

LINE_SPEC = {
    "us_commercial_revenue": (COUNTRY_US, PAYER_COMMERCIAL, CAT_REVENUE, CURRENCY_USD, "revenue"),
    "us_medicare_medicaid_revenue": (COUNTRY_US, PAYER_MEDICARE, CAT_REVENUE, CURRENCY_USD, "revenue"),
    "uk_private_revenue": (COUNTRY_UK, PAYER_PRIVATE, CAT_REVENUE, CURRENCY_GBP, "revenue"),
    "uk_nhs_revenue": (COUNTRY_UK, PAYER_NHS, CAT_REVENUE, CURRENCY_GBP, "revenue"),
    "us_consumables": (COUNTRY_US, PAYER_NA, CAT_CONSUMABLES, CURRENCY_USD, "expense"),
    "us_laboratory": (COUNTRY_US, PAYER_NA, CAT_LAB, CURRENCY_USD, "expense"),
    "us_interpreting": (COUNTRY_US, PAYER_NA, CAT_INTERPRETING, CURRENCY_USD, "expense"),
    "us_payroll": (COUNTRY_US, PAYER_NA, CAT_PAYROLL, CURRENCY_USD, "expense"),
    "us_rent": (COUNTRY_US, PAYER_NA, CAT_RENT, CURRENCY_USD, "expense"),
    "uk_consumables": (COUNTRY_UK, PAYER_NA, CAT_CONSUMABLES, CURRENCY_GBP, "expense"),
    "uk_laboratory": (COUNTRY_UK, PAYER_NA, CAT_LAB, CURRENCY_GBP, "expense"),
    "uk_payroll": (COUNTRY_UK, PAYER_NA, CAT_PAYROLL, CURRENCY_GBP, "expense"),
    "uk_rent": (COUNTRY_UK, PAYER_NA, CAT_RENT, CURRENCY_GBP, "expense"),
    "uk_software": (COUNTRY_UK, PAYER_NA, CAT_SOFTWARE, CURRENCY_GBP, "expense"),
}

PHI_AMOUNT = Decimal("1000")
