"""Reject and redact identity/tax, bank, compensation, and background-check details.

Only background-check completion may be stored. Outcomes and contents must not
appear in logs, stored prompts, messages, or API bodies.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_INGRESS_ERROR = "sensitive_data_excluded"

# Deterministic uuid4().hex shape used to lock the nonce/IBAN collision.
# ab12 + 28 hex letters is the executed false-positive case; do not randomize.
DETERMINISTIC_DECISION_NONCE = "ab12cdefabcdefabcdefabcdefabcdef"

_UUID_HEX = re.compile(r"^[0-9a-f]{32}$", re.I)
_UUID_HYPHEN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_IBAN_COMPACT = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.I)
_INTERNAL_IDENTIFIER_KEYS = frozenset(
    {
        "decision_nonce",
        "onboarding_id",
        "id",
        "task_id",
        "actor_id",
        "hire_user_id",
        "manager_user_id",
        "claire_user_id",
        "diane_user_id",
    }
)

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bssn\b", re.I),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"social\s*security", re.I),
    re.compile(r"national\s*insurance|\bnino\b", re.I),
    # Unlabeled NI: two letters, six digits, suffix A-D, optional grouping spaces.
    re.compile(r"\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b", re.I),
    re.compile(r"\bpassport\b", re.I),
    # Conservative unlabelled passport/bank/tax identifiers in free text.
    re.compile(r"\b[A-Z]{1,2}\d{6,9}\b", re.I),
    re.compile(r"\b\d{8,19}\b"),
    re.compile(r"\biban\b", re.I),
    re.compile(r"\b[A-Z]{2}\d{2}(?:\s[A-Z0-9]{4}){3,7}(?:\s[A-Z0-9]{1,4})?\b", re.I),
    re.compile(r"routing\s*number", re.I),
    re.compile(r"\b(bank|account)\s*number\b", re.I),
    # Unlabeled UK sort-code plus 8-digit account.
    re.compile(r"\b\d{2}-\d{2}-\d{2}(?:\s+|\s*/\s*)\d{8}\b"),
    re.compile(r"\bsalary\b", re.I),
    re.compile(r"\bcompensation\b", re.I),
    re.compile(r"\bbase\s*pay\b", re.I),
    re.compile(r"background[_\s-]*check[_\s-]*(outcome|result|detail|contents?|failed|passed|criminal)", re.I),
    re.compile(r"\b(criminal|conviction)\s+record\b", re.I),
)


_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "ssn",
        "national_insurance",
        "nino",
        "passport",
        "passport_number",
        "bank_account",
        "iban",
        "routing_number",
        "salary",
        "compensation",
        "background_check_outcome",
        "background_check_result",
        "background_check_detail",
        "background_check_contents",
    }
)


class SensitiveDataError(ValueError):
    code = SENSITIVE_INGRESS_ERROR


def is_generated_internal_id(value: str) -> bool:
    token = value.strip()
    return bool(_UUID_HEX.fullmatch(token) or _UUID_HYPHEN.fullmatch(token))


def _contains_unlabeled_iban(value: str) -> bool:
    """Compact IBAN tokens, excluding generated 32-hex UUID/nonces."""
    for match in _IBAN_COMPACT.finditer(value):
        if not is_generated_internal_id(match.group(0)):
            return True
    return False


def contains_sensitive_text(value: str) -> bool:
    if not value:
        return False
    if is_generated_internal_id(value):
        return False
    if any(pattern.search(value) for pattern in _PATTERNS):
        return True
    return _contains_unlabeled_iban(value)


def scan_mapping(payload: dict[str, Any]) -> None:
    """Throw if a forbidden key or sensitive string is present."""
    for key, raw in payload.items():
        lowered = str(key).lower()
        if lowered in _FORBIDDEN_KEYS:
            raise SensitiveDataError(SENSITIVE_INGRESS_ERROR)
        if (
            lowered in _INTERNAL_IDENTIFIER_KEYS
            and isinstance(raw, str)
            and is_generated_internal_id(raw)
        ):
            continue
        if isinstance(raw, str) and contains_sensitive_text(raw):
            raise SensitiveDataError(SENSITIVE_INGRESS_ERROR)
        if isinstance(raw, dict):
            scan_mapping(raw)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    scan_mapping(item)
                elif isinstance(item, str) and contains_sensitive_text(item):
                    raise SensitiveDataError(SENSITIVE_INGRESS_ERROR)


def redact_text(value: str) -> str:
    if not contains_sensitive_text(value):
        return value
    return "[redacted-sensitive]"
