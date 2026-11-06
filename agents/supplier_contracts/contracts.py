"""Extract sanitized terms from authored PDFs. Caps come from clauses, not supplier IDs."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from agents.supplier_contracts.constants import US_CPI
from agents.supplier_contracts.identity import CONTRACTS_ID
from agents.supplier_contracts.pdf import extract_pages, pdf_sha256
from agents.supplier_contracts.privacy import iter_numbered_clauses, sanitize_contract_text
from agents.supplier_contracts.registry import require_supplier
from agents.supplier_contracts.types import ContractsRequest, ContractsResult, TermCitation
EXPIRY_DAYS = re.compile(r"expires (\d+) days after the HealthCore data-load date", re.I)
NOTICE_DAYS = re.compile(r"(\d+) days' notice before expiry", re.I)
PERCENT_CAP = re.compile(r"capped at (\d+(?:\.\d+)?) percent", re.I)
CPI_CAP = re.compile(r"US Consumer Price Index", re.I)
FIXED_PRICE = re.compile(r"fixed for the full term", re.I)
EXIT_UNSPECIFIED = re.compile(r"averaging period is not specified", re.I)
SIGNED_BAA_CLAUSE = re.compile(r"signed BAA is annexed", re.I)
SIGNED_BAA_ANNEX = re.compile(r"Signed Business Associate Agreement", re.I)
MISSING_DPA = re.compile(r"includes no DPA", re.I)
NOT_PATIENT = re.compile(r"does not process patient data", re.I)
ANNUAL_VALUE = re.compile(
    r"estimated annual value of this agreement is (\d+(?:\.\d+)?)\s*(USD|GBP)",
    re.I,
)


def _citations(path: Path) -> tuple[str, str, tuple[TermCitation, ...]]:
    digest = pdf_sha256(path)
    pages = extract_pages(path)
    found: list[TermCitation] = []
    sanitized_pages: list[str] = []
    for page_number, raw in enumerate(pages, start=1):
        sanitized = sanitize_contract_text(raw)
        sanitized_pages.append(sanitized)
        for number, field, body in iter_numbered_clauses(sanitized):
            found.append(
                TermCitation(
                    field=field,
                    value=body,
                    clause=number,
                    page=page_number,
                    pdf_sha256=digest,
                    confidence="high",
                    status="present",
                )
            )
    return digest, "\n".join(sanitized_pages), tuple(found)


def load_sanitized_terms(pdf_path: Path) -> tuple[TermCitation, ...]:
    return _citations(pdf_path)[2]


def _term(terms: tuple[TermCitation, ...], *fields: str) -> TermCitation | None:
    wanted = {field.lower() for field in fields}
    for item in terms:
        if item.field in wanted:
            return item
    return None


def _int_from(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    if match is None:
        return None
    return int(match.group(1))


def _cap_from_text(text: str) -> tuple[str | None, Decimal | None]:
    if FIXED_PRICE.search(text):
        return "fixed", Decimal("0")
    if CPI_CAP.search(text):
        return "cpi", US_CPI
    percent = PERCENT_CAP.search(text)
    if percent:
        return "percent", Decimal(percent.group(1)) / Decimal("100")
    return None, None


def evaluate_revision_cap(
    cap_kind: str | None,
    cap_ratio: Decimal | None,
    previous: Decimal,
    proposed: Decimal,
) -> tuple[bool | None, Decimal | None, Decimal | None]:
    """Compare exact Decimal values. CPI 18 * 1.029 stays 18.522, not 18.52."""
    if cap_kind is None or cap_ratio is None:
        return None, None, None
    if cap_kind == "fixed":
        return proposed == previous, Decimal("0"), previous
    cap_price = previous * (Decimal("1") + cap_ratio)
    return proposed <= cap_price, cap_ratio, cap_price


def _dpa_from_text(full_text: str, processes_patient_data: bool) -> tuple[bool, str]:
    # Signed status is evidenced by clause 6 plus the annex page, never by supplier id.
    if SIGNED_BAA_CLAUSE.search(full_text) and SIGNED_BAA_ANNEX.search(full_text):
        return False, "signed_baa"
    if MISSING_DPA.search(full_text):
        return True, "missing_dpa"
    if NOT_PATIENT.search(full_text):
        return False, "not_applicable"
    if processes_patient_data:
        return True, "uncertain"
    return False, "uncertain"


def run_contracts(
    request: ContractsRequest,
    *,
    pdf_path: Path | None,
    load_date: date,
    previous_price: Decimal | None = None,
    proposed_price: Decimal | None = None,
) -> ContractsResult:
    supplier = require_supplier(request.supplier_id)
    if not supplier.has_contract or pdf_path is None or not pdf_path.exists():
        return ContractsResult(
            supplier_id=supplier.supplier_id,
            contract_id=None,
            missing_contract=True,
            terms=(),
            increase_allowed=None,
            cap_ratio=None,
            cap_price=None,
            missing_dpa=bool(supplier.processes_patient_data),
            processes_patient_data=supplier.processes_patient_data,
            dpa_status="missing_contract",
            exit_penalty_uncertain=False,
            expiry_offset_days=None,
            notice_days=None,
            pdf_sha256=None,
            actor_id=CONTRACTS_ID,
            estimated_annual_uncertain=True,
        )
    digest, full_text, terms = _citations(pdf_path)
    term_text = " ".join(item.value for item in terms) + "\n" + full_text
    revision = _term(terms, "price_revision")
    cap_kind, cap_ratio = _cap_from_text(revision.value if revision else "")
    allowed = cap_ratio_out = cap_price = None
    if previous_price is not None and proposed_price is not None:
        if revision is None or cap_kind is None:
            allowed = None
            terms = terms + (
                TermCitation(
                    field="price_revision",
                    value="price revision clause was not extracted",
                    clause="",
                    page=0,
                    pdf_sha256=digest,
                    confidence="uncertain",
                    status="missing",
                ),
            )
        else:
            allowed, cap_ratio_out, cap_price = evaluate_revision_cap(
                cap_kind, cap_ratio, previous_price, proposed_price
            )
    missing_dpa, dpa_status = _dpa_from_text(term_text, supplier.processes_patient_data)
    expiry_term = _term(terms, "term")
    notice_term = _term(terms, "non-renewal_notice")
    expiry_offset_days = _int_from(EXPIRY_DAYS, expiry_term.value if expiry_term else "")
    notice_days = _int_from(NOTICE_DAYS, notice_term.value if notice_term else "")
    exit_term = _term(terms, "exit")
    exit_uncertain = bool(exit_term and EXIT_UNSPECIFIED.search(exit_term.value))
    annual_term = _term(terms, "estimated_annual_value")
    annual_match = ANNUAL_VALUE.search(annual_term.value if annual_term else "")
    if annual_match:
        estimated_annual_value = Decimal(annual_match.group(1))
        estimated_annual_currency = annual_match.group(2).upper()
        estimated_annual_uncertain = False
    else:
        estimated_annual_value = None
        estimated_annual_currency = None
        estimated_annual_uncertain = True
    return ContractsResult(
        supplier_id=supplier.supplier_id,
        contract_id=supplier.contract_id,
        missing_contract=False,
        terms=terms,
        increase_allowed=allowed,
        cap_ratio=cap_ratio_out if cap_ratio_out is not None else cap_ratio,
        cap_price=cap_price,
        missing_dpa=missing_dpa,
        processes_patient_data=supplier.processes_patient_data,
        dpa_status=dpa_status,
        exit_penalty_uncertain=exit_uncertain,
        expiry_offset_days=expiry_offset_days,
        notice_days=notice_days,
        pdf_sha256=digest,
        actor_id=CONTRACTS_ID,
        estimated_annual_value=estimated_annual_value,
        estimated_annual_currency=estimated_annual_currency,
        estimated_annual_uncertain=estimated_annual_uncertain,
    )


def schedule_dates(expiry_offset_days: int, notice_days: int, load_date: date) -> dict[str, date]:
    expiry = load_date + timedelta(days=expiry_offset_days)
    notice_deadline = expiry - timedelta(days=notice_days)
    return {"expiry": expiry, "notice_deadline": notice_deadline}
