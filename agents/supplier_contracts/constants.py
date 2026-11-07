"""Briefing-bound figures. CPI and FX are supplied references, not live feeds."""

from __future__ import annotations

from decimal import Decimal

PRICE_ALERT_THRESHOLD = Decimal("0.04")  # strictly more than 4%
US_CPI = Decimal("0.029")
GBP_USD = Decimal("1.27")
SANDRA_ANNUAL_USD = Decimal("500000")  # strictly greater than
CONSULTATION_LIMIT = 4  # implementation setting, not HR policy
EXPIRY_ALERT_OFFSETS_DAYS = (90, 30)
NOTICE_ALERT_OFFSET_DAYS = 15
MAX_MONTHLY_VARIATION = Decimal("0.01")

DIRECTORY_COUNTRY_USA = "USA"
BRIEFING_COUNTRY_US = "United States"
