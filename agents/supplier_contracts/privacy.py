"""Sanitize billing clauses and reject patient-level payloads before persistence."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from data.pipelines.rfp_intake.phi import screen_text

SENSITIVE_INGRESS_ERROR = "sensitive_data_excluded"
PATIENT_LEVEL_ERROR = "patient_level_data_rejected"
REDACTED = "[redacted-sensitive]"

_UUID_HEX = re.compile(r"^[0-9a-f]{32}$", re.I)
_UUID_HYPHEN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.I)
# Account numbers wrap onto their own line as "44556677. ". Unbounded ^\d+\.\s
# treats those digits as a clause heading and publishes them as a clause id.
CLAUSE_TITLES = (
    "Parties",
    "Term",
    "Non-renewal notice",
    "Price revision",
    "Exit",
    "Data protection",
    "Governing language",
    "Estimated annual value",
    "Billing",
    "Notices",
    "Payment",
    "Bank details",
    "Invoicing",
)
_BILLING_TITLES = frozenset({"billing", "payment", "bank details", "invoicing"})
_FIELD_LABELS = frozenset(
    {title.lower() for title in CLAUSE_TITLES} | {title.lower().replace(" ", "_") for title in CLAUSE_TITLES}
)
_TITLE_ALT = "|".join(re.escape(title) for title in CLAUSE_TITLES)
CLAUSE_HEADING = re.compile(
    rf"^(?P<number>[1-9]\d?)\.\s+(?P<title>{_TITLE_ALT})\b",
    re.IGNORECASE | re.MULTILINE,
)
_REDACTED_BILLING_LINE = re.compile(
    rf"^(?:[1-9]\d?\.\s+)?Billing details {re.escape(REDACTED)}\.?\s*$",
    re.IGNORECASE,
)
# Numbered billing headings, or "Billing contact" wrap lines. A lone field
# label "billing" is not a block. Already-redacted "Billing details ..." is
# skipped so a second sanitize pass is a no-op.
_BILLING_OPEN = re.compile(
    rf"^(?:(?P<number>[1-9]\d?)\.\s+|(?=(?:Billing|Payment|Bank details|Invoicing)\b[\s.]))"
    rf"(?P<title>Billing|Payment|Bank details|Invoicing)\b"
    rf"(?!\s*details\s+{re.escape(REDACTED)})",
    re.IGNORECASE | re.MULTILINE,
)
_BANK_LABEL = re.compile(
    r"(?i)\b(?:iban|sort code|account(?:\s+number)?|routing number|swift)\b\s*[:#]?\s*\S+"
)
_BILLING_CONTACT = re.compile(
    r"(?i)\bbilling contact:\s*[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+"
)
_PHONE = re.compile(r"\+\d[\d\- ]{7,}")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_ADDRESSISH = re.compile(
    r"(?i)\b\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Lane|Way|Street|Road|Avenue|Drive)\b"
)
_PATIENT_LEVEL = (
    re.compile(r"\bper[- ]patient\b", re.I),
    re.compile(r"\bpatient[- ]level\b", re.I),
    re.compile(r"\b(mrn|nhs number|patient id)\b", re.I),
    re.compile(r"\bindividual patient\b", re.I),
)


class SensitiveDataError(ValueError):
    code = SENSITIVE_INGRESS_ERROR


class PatientLevelError(ValueError):
    code = PATIENT_LEVEL_ERROR


class OutOfScopeError(ValueError):
    code = "out_of_scope"


def is_generated_internal_id(value: str) -> bool:
    token = value.strip()
    return bool(_UUID_HEX.fullmatch(token) or _UUID_HYPHEN.fullmatch(token) or _SHA256.fullmatch(token))


def is_patient_level_request(value: str) -> bool:
    if any(pattern.search(value) for pattern in _PATIENT_LEVEL):
        return True
    # Same labeled-field detector used by app.core.prohibited_text / RFP PHI screen.
    return screen_text(value).detected


def is_credible_clause_number(number: str) -> bool:
    return bool(re.fullmatch(r"[1-9]\d?", number))


def is_already_redacted_metadata(value: str) -> bool:
    """True for field labels and already-redacted billing placeholders, not raw bank data."""
    stripped = value.strip()
    if not stripped or stripped == REDACTED:
        return True
    if stripped.lower() in _FIELD_LABELS:
        return True
    return bool(_REDACTED_BILLING_LINE.fullmatch(stripped))


def redact_billing_blocks(value: str) -> str:
    """Replace each billing block through the next real clause, not the next digit-period."""
    pieces: list[str] = []
    cursor = 0
    for opener in _BILLING_OPEN.finditer(value):
        if opener.start() < cursor:
            continue
        pieces.append(value[cursor : opener.start()])
        closer = None
        for heading in CLAUSE_HEADING.finditer(value, opener.end()):
            if heading.group("title").lower() in _BILLING_TITLES:
                continue
            closer = heading
            break
        end = closer.start() if closer else len(value)
        number = opener.group("number")
        prefix = f"{number}. " if number else ""
        pieces.append(f"{prefix}Billing details {REDACTED}.\n")
        cursor = end
    pieces.append(value[cursor:])
    return "".join(pieces)


def iter_numbered_clauses(text: str) -> list[tuple[str, str, str]]:
    matches = list(CLAUSE_HEADING.finditer(text))
    clauses: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        number = match.group("number")
        title = match.group("title")
        body = " ".join(text[match.start() : end].split())
        if "." in body:
            body = body.split(".", 1)[1].strip()
        clauses.append((number, title.lower().replace(" ", "_"), body))
    return clauses


def sanitize_contract_text(value: str) -> str:
    redacted = redact_billing_blocks(value)
    redacted = _BILLING_CONTACT.sub(REDACTED, redacted)
    redacted = _BANK_LABEL.sub(REDACTED, redacted)
    redacted = _EMAIL.sub(REDACTED, redacted)
    redacted = _PHONE.sub(REDACTED, redacted)
    redacted = _ADDRESSISH.sub(REDACTED, redacted)
    return redacted


def contains_bank_or_contact(value: str) -> bool:
    if not value or is_generated_internal_id(value):
        return False
    if is_already_redacted_metadata(value):
        return False
    return sanitize_contract_text(value) != value


def reject_patient_level(question: str) -> None:
    if is_patient_level_request(question):
        raise PatientLevelError(PATIENT_LEVEL_ERROR)


def reject_out_of_scope(question: str) -> None:
    """Reject jailbreak, personal, and identifier probes before generation.

    Support-agent canned DPA/BAA answers (action=answer) stay in scope so Task 4
    can still interpret supplier-contract questions. Casual redirects and blocks
    do not.
    """
    try:
        from app.agent.guardrails.input_scope import screen_question
    except ImportError:
        return
    decision = screen_question(question)
    if decision.action in {"block", "redirect"}:
        raise OutOfScopeError("out_of_scope")


def _walk(value: Any, visitor) -> None:
    if isinstance(value, str):
        visitor(value)
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        _walk(dataclasses.asdict(value), visitor)
        return
    if isinstance(value, dict):
        for item in value.values():
            _walk(item, visitor)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _walk(item, visitor)


def assert_clean_mapping(payload: Any) -> None:
    def check(text: str) -> None:
        if is_patient_level_request(text):
            raise PatientLevelError(PATIENT_LEVEL_ERROR)
        if contains_bank_or_contact(text):
            raise SensitiveDataError(SENSITIVE_INGRESS_ERROR)

    _walk(payload, check)
