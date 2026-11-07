"""Estimated annual-value clauses come from PDF provenance, not the registry."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from agents.supplier_contracts.approvals import (
    annual_evidence_from_contract,
    annual_usd_from_contract,
    create_draft,
    required_approvers,
)
from agents.supplier_contracts.constants import GBP_USD, SANDRA_ANNUAL_USD
from agents.supplier_contracts.contracts import run_contracts
from agents.supplier_contracts.identity import SANDRA
from agents.supplier_contracts.pdf import write_pdf
from agents.supplier_contracts.registry import require_supplier
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.seed import BAA_ANNEX, BILLING_BODIES
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import ContractsRequest, SupervisorRequest

LOAD_DATE = date(2026, 11, 6)
EXPECTED = {
    "HC-S01": (Decimal("537600"), "USD"),
    "HC-S03": (Decimal("540000"), "USD"),
    "HC-S06": (Decimal("121800"), "GBP"),
    "HC-S07": (Decimal("210600"), "USD"),
}


def _runtime(tmp_path: Path) -> ContractRuntime:
    runtime = ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=LOAD_DATE)
    runtime.ensure_seeded()
    return runtime


def _contracts(runtime: ContractRuntime, supplier_id: str):
    record = require_supplier(supplier_id)
    return run_contracts(
        ContractsRequest(supplier_id=supplier_id, question="annual value", contract_id=record.contract_id),
        pdf_path=runtime.pdf_path(record.contract_id),
        load_date=LOAD_DATE,
    )


def test_pdf_clauses_carry_numbered_annual_values_with_citations(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    for supplier_id, (amount, currency) in EXPECTED.items():
        result = _contracts(runtime, supplier_id)
        assert result.estimated_annual_uncertain is False
        assert result.estimated_annual_value == amount
        assert result.estimated_annual_currency == currency
        term = next(item for item in result.terms if item.field == "estimated_annual_value")
        assert term.clause == "8"
        assert term.page >= 1
        assert term.pdf_sha256
        assert format(amount, "f") in term.value
        assert currency in term.value


def test_sandra_threshold_uses_extracted_pdf_figure(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    s01 = annual_usd_from_contract(_contracts(runtime, "HC-S01"))
    s03 = annual_usd_from_contract(_contracts(runtime, "HC-S03"))
    s06 = annual_usd_from_contract(_contracts(runtime, "HC-S06"))
    s07 = annual_usd_from_contract(_contracts(runtime, "HC-S07"))
    assert s01 == Decimal("537600")
    assert s03 == Decimal("540000")
    assert s06 == Decimal("121800") * GBP_USD
    assert s07 == Decimal("210600")
    assert s01 > SANDRA_ANNUAL_USD
    assert s03 > SANDRA_ANNUAL_USD
    assert s06 < SANDRA_ANNUAL_USD
    assert s07 < SANDRA_ANNUAL_USD
    assert SANDRA in required_approvers("HC-S01", s01, annual_evidenced=True)
    assert SANDRA in required_approvers("HC-S03", s03, annual_evidenced=True)
    assert SANDRA not in required_approvers("HC-S06", s06, annual_evidenced=True)
    assert SANDRA not in required_approvers("HC-S07", s07, annual_evidenced=True)


def _write_s07(path: Path, annual_line: str | None) -> None:
    lines = [
        "CT-HC-04 LinguaCare Interpreting medical interpreting agreement.",
        "1. Parties. HealthCore and LinguaCare Interpreting.",
        "2. Term. This agreement expires 28 days after the HealthCore data-load date.",
        "3. Non-renewal notice. Either party must give 15 days' notice before expiry.",
        "4. Price revision. The unit price is fixed for the full term.",
        "5. Exit. There is no penalty for ending this agreement.",
        "6. Data protection. A signed BAA is annexed to this contract.",
        "7. Governing language. English.",
    ]
    if annual_line is not None:
        lines.append(annual_line)
    write_pdf(
        path,
        [
            lines,
            [BILLING_BODIES["CT-HC-04"], "10. Notices. Formal notices use the addresses in clause 9."],
            list(BAA_ANNEX),
        ],
    )


def test_missing_annual_clause_does_not_use_registry_or_drop_sandra(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _write_s07(runtime.pdf_dir / "CT-HC-04.pdf", None)
    result = _contracts(runtime, "HC-S07")
    usd, evidenced = annual_evidence_from_contract(result)
    assert result.estimated_annual_uncertain is True
    assert result.estimated_annual_value is None
    assert usd is None
    assert evidenced is False
    assert SANDRA in required_approvers("HC-S07", usd, annual_evidenced=evidenced)
    draft = create_draft(
        runtime.store,
        supplier_id="HC-S07",
        kind="draft_communication",
        body="internal",
        annual_usd=usd,
        annual_evidenced=evidenced,
    )
    assert SANDRA in draft["required"]
    assert draft["state"] == "pending"


def test_altered_annual_clause_does_not_use_registry_or_drop_sandra(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    _write_s07(
        runtime.pdf_dir / "CT-HC-04.pdf",
        "8. Estimated annual value. The estimated annual value is recorded in an annex that is not attached.",
    )
    result = _contracts(runtime, "HC-S07")
    usd, evidenced = annual_evidence_from_contract(result)
    assert result.estimated_annual_uncertain is True
    assert result.estimated_annual_value is None
    assert usd is None
    assert evidenced is False
    assert SANDRA in required_approvers("HC-S07", None, annual_evidenced=False)
    assert SANDRA not in required_approvers("HC-S07", Decimal("210600"), annual_evidenced=True)


def test_missing_contract_still_returns_informational_answer(tmp_path: Path) -> None:
    response = Supervisor(_runtime(tmp_path)).handle(
        SupervisorRequest(
            kind="question",
            question="What alternatives exist in the same country and category?",
            supplier_id="HC-S02",
        )
    )
    assert response.blocked is False
    assert response.draft is None
    assert "HC-S01" in response.answer or "quote_only" in response.answer
