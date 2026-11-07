"""Quarantine unsafe text and allow only validated typed identifiers downstream."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from agents.financial_close.constants import (
    AGENT_ID,
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
    LINE_IDS,
    METRIC_CLAIMS_ACTUAL,
    METRIC_CLAIMS_BUDGET,
    METRIC_DENIAL_ACTUAL,
    METRIC_DENIAL_BUDGET,
    PAYER_COMMERCIAL,
    PAYER_MEDICARE,
    PAYER_NA,
    PAYER_NHS,
    PAYER_PRIVATE,
)

SENSITIVE_INGRESS_ERROR = "sensitive_data_excluded"
REDACTED = "[redacted-sensitive]"

ALLOWED_COUNTRIES = frozenset({COUNTRY_US, COUNTRY_UK})
ALLOWED_PAYERS = frozenset({PAYER_COMMERCIAL, PAYER_MEDICARE, PAYER_PRIVATE, PAYER_NHS, PAYER_NA})
ALLOWED_CATEGORIES = frozenset(
    {CAT_REVENUE, CAT_CONSUMABLES, CAT_LAB, CAT_INTERPRETING, CAT_PAYROLL, CAT_RENT, CAT_SOFTWARE}
)
ALLOWED_METRICS = frozenset(
    {METRIC_CLAIMS_BUDGET, METRIC_CLAIMS_ACTUAL, METRIC_DENIAL_BUDGET, METRIC_DENIAL_ACTUAL}
)
ALLOWED_CURRENCIES = frozenset({CURRENCY_USD, CURRENCY_GBP})
COUNTRY_CURRENCY = {COUNTRY_US: CURRENCY_USD, COUNTRY_UK: CURRENCY_GBP}
PAYER_COUNTRY = {
    PAYER_COMMERCIAL: COUNTRY_US,
    PAYER_MEDICARE: COUNTRY_US,
    PAYER_PRIVATE: COUNTRY_UK,
    PAYER_NHS: COUNTRY_UK,
}

ENTRY_ID_RE = re.compile(r"^LED-[0-9]{6}-(?:[0-9]{3}|PHI[0-9]+)$")
INGEST_REF_RE = re.compile(r"^ingest\.(ledger|budget|operations)\.[1-9][0-9]*$")
SOURCE_REF_RE = re.compile(r"^(ledger|budget|operations)\.csv:[1-9][0-9]*(?:#[0-9a-f]{12})?$")
PERIOD_RE = re.compile(r"^[0-9]{4}-(?:0[1-9]|1[0-2])$")
UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")
UUID_HYPHEN_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NONCE_RE = re.compile(r"^[0-9a-f]{32}$")
ACTOR_ID_RE = re.compile(r"^financial-close-agent$")
FIGURE_ID_RE = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
FIGURE_FIELDS = ("verified_actual", "budget", "percent", "amount_variance", "known_subtotal")
ALLOWED_FIGURE_IDS = frozenset(
    [f"{line_id}.{field}" for line_id in LINE_IDS for field in FIGURE_FIELDS]
    + [
        "consolidated.result_budget_usd",
        "consolidated.revenue_budget_usd",
        "consolidated.expense_budget_usd",
        "consolidated.known_revenue_actual_usd",
        "consolidated.known_expense_actual_usd",
        "fx.rate",
        "operations.medicare.claims_submitted_actual",
        "operations.medicare.claims_submitted_budget",
        "operations.medicare.denial_rate_pct_actual",
        "operations.medicare.denial_rate_pct_budget",
        "operations.commercial.claims_submitted_actual",
        "operations.commercial.claims_submitted_budget",
        "operations.commercial.denial_rate_pct_actual",
        "operations.commercial.denial_rate_pct_budget",
        "us_laboratory.unit_price",
        "us_laboratory.observed_quantity",
        "us_laboratory.budget_implied_unit_price",
        "us_laboratory.increase",
        "us_laboratory.unit_price_variance",
    ]
)
ISSUE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,60}$")
EMAIL_RE = re.compile(r"^[a-z0-9._+-]+@healthcore\.example$")
NOTICE_KEY_RE = re.compile(
    r"^(?:privacy:[0-9]{4}-(?:0[1-9]|1[0-2]):[1-9][0-9]*:LED-[0-9]{6}-(?:[0-9]{3}|PHI[0-9]+)|(?:report|review):[0-9]{4}-(?:0[1-9]|1[0-2]):[1-9][0-9]*:[0-9a-f]{32}:[a-z0-9._+-]+@healthcore\.example)$"
)
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_CLINICS = (
    "Austin North",
    "Austin South",
    "Houston",
    "Dallas",
    "San Antonio",
    "Miami",
    "Orlando",
    "Atlanta",
    "Savannah",
    "London Central",
    "London East",
    "Manchester",
)
_REVENUE_LABELS = (
    "commercial insurance",
    "Medicare Medicaid",
    "private pay",
    "NHS contract",
)
_SUPPLIERS = (
    "MedSupply Partners disposable consultation kit",
    "ClearPath Labs basic metabolic panel",
    "LinguaCare Interpreting medical interpreting",
    "BritMed Supplies disposable consultation kit",
    "Thames Pathology basic metabolic panel",
)
_RENT_LABELS = (
    "United States clinic rent Austin group",
    "United States clinic rent remaining locations",
    "United Kingdom clinic rent London",
    "United Kingdom clinic rent Manchester",
)
_REVENUE_DESC = re.compile(
    r"^(?:%s) clinic (?:%s) aggregate$" % (
        "|".join(re.escape(item) for item in _CLINICS),
        "|".join(re.escape(item) for item in _REVENUE_LABELS),
    )
)
_SUPPLIER_DESC = re.compile(
    r"^(?:%s) unit_price=\d+(?:\.\d+)? quantity=\d+$"
    % "|".join(re.escape(item) for item in _SUPPLIERS)
)
_PAYROLL_DESC = re.compile(
    r"^(?:United States|United Kingdom) payroll aggregate(?: remainder)? (?:%s) [0-9]{4}$"
    % "|".join(MONTH_NAMES)
)
_PERSON = re.compile(r"\b[A-Za-z]{2,} [A-Za-z]{2,}\b")
_TITLE_PERSON = re.compile(
    r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)+\b"
)
_PATIENT_WORD = re.compile(r"\bpatients?\b", re.I)
_VISIT = re.compile(r"\b(visit|refund|mrn|nhs number|patient id|date of birth|\bdob\b|diagnosis)\b", re.I)
_SALARY = re.compile(r"\b(salary|compensation|base pay|individual pay|named payroll)\b", re.I)
_BANK = re.compile(
    r"\b(iban|sort code|routing number|swift|account number)\b|[A-Z]{2}\d{2}[A-Z0-9]{11,30}|\b\d{2}-\d{2}-\d{2}(?:\s+|\s*/\s*)\d{8}\b",
    re.I,
)
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_NI = re.compile(r"\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b", re.I)
_FORBIDDEN_KEYS = frozenset(
    {
        "description",
        "raw_description",
        "exception",
        "traceback",
        "exc_info",
        "source_text",
    }
)
_ISSUE_CODES = frozenset(
    {
        "missing_entry_id",
        "invalid_entry_id",
        "duplicate_entry_id",
        "malformed_amount",
        "malformed_value",
        "unknown_currency",
        "currency_country_mismatch",
        "currency_line_mismatch",
        "invalid_date",
        "date_outside_period",
        "unknown_country",
        "unknown_payer",
        "unknown_category",
        "unknown_line",
        "payer_country_mismatch",
        "unexpected_sign",
        "zero_amount",
        "invalid_source_ref",
        "unexpected_description",
        "patient_identifying_description",
        "individual_salary",
        "supplier_bank_details",
        "month_mismatch",
        "invalid_month",
        "unknown_metric",
        "metric_out_of_range",
        "duplicate_budget_key",
        "duplicate_operations_key",
        "missing_field",
        "missing_ledger_file",
        "missing_budget_file",
        "missing_operations_file",
        "inconsistent_supporting_amount",
    }
)


class SensitiveDataError(ValueError):
    code = SENSITIVE_INGRESS_ERROR


def is_valid_entry_id(value: str) -> bool:
    return bool(ENTRY_ID_RE.fullmatch(value))


def is_valid_ingest_ref(value: str) -> bool:
    return bool(INGEST_REF_RE.fullmatch(value))


def is_valid_source_ref(value: str) -> bool:
    return bool(SOURCE_REF_RE.fullmatch(value))


def is_valid_period(value: str) -> bool:
    return bool(PERIOD_RE.fullmatch(value))


def is_uuid_id(value: str) -> bool:
    token = value.strip()
    return bool(UUID_HEX_RE.fullmatch(token) or UUID_HYPHEN_RE.fullmatch(token))


def is_sha256(value: str) -> bool:
    return bool(SHA256_RE.fullmatch(value))


def is_valid_figure_id(value: str) -> bool:
    return value in ALLOWED_FIGURE_IDS


def is_allowlisted_description(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _REVENUE_DESC.fullmatch(stripped) or _SUPPLIER_DESC.fullmatch(stripped) or _PAYROLL_DESC.fullmatch(stripped):
        return True
    return stripped in _RENT_LABELS


def description_quarantine_reason(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped:
        return "unexpected_description"
    if _BANK.search(stripped) or _SSN.search(stripped) or _NI.search(stripped):
        return "supplier_bank_details" if _BANK.search(stripped) else "patient_identifying_description"
    if _SALARY.search(stripped):
        return "individual_salary"
    if _PATIENT_WORD.search(stripped) or _VISIT.search(stripped):
        return "patient_identifying_description"
    if is_allowlisted_description(stripped):
        return None
    if _PERSON.search(stripped):
        return "patient_identifying_description"
    return "unexpected_description"


def safe_description_projection(text: str) -> str | None:
    if description_quarantine_reason(text) is None and is_allowlisted_description(text):
        return text.strip()
    return None


def _is_decimal_text(value: str) -> bool:
    try:
        Decimal(value)
    except (InvalidOperation, ValueError):
        return False
    return "e" not in value.lower() and "n" not in value.lower()


def _validator_or_false(predicate: Callable[[str], bool], value: Any) -> bool:
    return isinstance(value, str) and predicate(value)


_KEY_VALIDATORS: dict[str, Callable[[Any], bool]] = {
    "entry_id": lambda value: _validator_or_false(is_valid_entry_id, value),
    "public_entry_id": lambda value: value is None or _validator_or_false(is_valid_entry_id, value),
    "ingest_ref": lambda value: _validator_or_false(is_valid_ingest_ref, value),
    "source_ref": lambda value: _validator_or_false(is_valid_source_ref, value),
    "draft_id": lambda value: _validator_or_false(is_uuid_id, value),
    "approval_nonce": lambda value: _validator_or_false(lambda item: bool(NONCE_RE.fullmatch(item)), value),
    "content_sha256": lambda value: _validator_or_false(is_sha256, value),
    "period": lambda value: _validator_or_false(is_valid_period, value),
    "actor_id": lambda value: value == AGENT_ID,
    "user_id": lambda value: _validator_or_false(is_uuid_id, value),
    "figure_id": lambda value: _validator_or_false(is_valid_figure_id, value),
    "row_id": lambda value: _validator_or_false(is_valid_source_ref, value),
    "line_id": lambda value: value in LINE_IDS,
    "metric": lambda value: value is None or value in ALLOWED_METRICS,
    "country": lambda value: value is None or value in ALLOWED_COUNTRIES,
    "payer": lambda value: value is None or value in ALLOWED_PAYERS,
    "category": lambda value: value in ALLOWED_CATEGORIES,
    "currency": lambda value: value in ALLOWED_CURRENCIES,
    "email": lambda value: _validator_or_false(lambda item: bool(EMAIL_RE.fullmatch(item)), value),
    "recipient_email": lambda value: _validator_or_false(lambda item: bool(EMAIL_RE.fullmatch(item)), value),
    "notice_key": lambda value: _validator_or_false(lambda item: bool(NOTICE_KEY_RE.fullmatch(item)), value),
    "safe_description": lambda value: value is None or (isinstance(value, str) and is_allowlisted_description(value)),
    "comments": lambda value: value is None or (isinstance(value, str) and is_safe_prose(value)),
    "reviewer_guidance": lambda value: value is None or (isinstance(value, str) and is_safe_prose(value)),
    "hypothesis": lambda value: isinstance(value, str) and is_safe_prose(value),
    "executive_summary": lambda value: isinstance(value, str) and is_safe_prose(value),
}


def _allowlisted_proper_names() -> set[str]:
    from agents.financial_close.identity import PERSON_DISPLAY

    names = set(PERSON_DISPLAY.values()) | set(_CLINICS) | {
        "United States",
        "United Kingdom",
        "HealthCore",
        "ClearPath Labs",
        "MedSupply Partners",
        "LinguaCare Interpreting",
        "BritMed Supplies",
        "Thames Pathology",
        "Medicare Medicaid",
        "NHS",
    }
    names.update(name.removeprefix("Dr. ").strip() for name in PERSON_DISPLAY.values())
    return names


def is_safe_prose(text: str) -> bool:
    """Reject unlabeled personal names and sensitive categories, not ordinary financial wording."""
    if not isinstance(text, str) or not text.strip():
        return False
    if _BANK.search(text) or _SSN.search(text) or _NI.search(text) or _SALARY.search(text):
        return False
    if _PATIENT_WORD.search(text) or _VISIT.search(text):
        return False
    remainder = text
    for name in sorted(_allowlisted_proper_names(), key=len, reverse=True):
        remainder = remainder.replace(name, "")
    if _TITLE_PERSON.search(remainder):
        return False
    return True


def assert_clean_text(value: str) -> None:
    if is_valid_entry_id(value) or is_valid_ingest_ref(value) or is_valid_source_ref(value):
        return
    if is_uuid_id(value) or is_sha256(value) or value == AGENT_ID:
        return
    if is_allowlisted_description(value) or is_valid_period(value) or is_valid_figure_id(value):
        return
    if value in LINE_IDS or value in ALLOWED_METRICS or value in _ISSUE_CODES:
        return
    if is_safe_prose(value):
        return
    raise SensitiveDataError("unvalidated_text")


def assert_clean_mapping(payload: Any) -> None:
    if payload is None or isinstance(payload, (bool, int)):
        return
    if isinstance(payload, Decimal):
        return
    if isinstance(payload, str):
        assert_clean_text(payload)
        return
    if isinstance(payload, dict):
        for key, item in payload.items():
            key_text = str(key)
            if key_text in _FORBIDDEN_KEYS:
                raise SensitiveDataError("forbidden_key")
            validator = _KEY_VALIDATORS.get(key_text)
            if validator is not None:
                if not validator(item):
                    raise SensitiveDataError(f"invalid_{key_text}")
                continue
            if key_text == "issues":
                if not isinstance(item, (list, tuple)) or any(code not in _ISSUE_CODES for code in item):
                    raise SensitiveDataError("invalid_issues")
                continue
            assert_clean_mapping(item)
        return
    if isinstance(payload, (list, tuple)):
        for item in payload:
            assert_clean_mapping(item)
        return
    raise SensitiveDataError("unsupported_payload_type")
