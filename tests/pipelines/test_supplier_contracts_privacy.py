"""Privacy regressions. Canary values must not appear in assertion messages."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from agents.supplier_contracts.privacy import (
    assert_clean_mapping,
    contains_bank_or_contact,
    is_already_redacted_metadata,
    is_credible_clause_number,
    iter_numbered_clauses,
    sanitize_contract_text,
)
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.serialize import response_payload
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import SupervisorRequest

# Index 5 is a wrapped bank-account number published as a fake clause id.
_CANARIES = (
    "GB82WEST12345698765432",
    "morgan.ellis@clearpathlabs.invalid",
    "Morgan Ellis",
    "Reese Dalton",
    "Samira Cole",
    "44556677",
    "00019991",
    "12345678",
    "Avery Quinn",
    "reese.dalton@medsupply.invalid",
    "samira.cole@thamespath.invalid",
    "avery.quinn@linguacare.invalid",
    "+1-555-0148",
    "+1-555-0172",
    "14 Harbor Lane",
    "9 Copper Road",
)


def _assert_canaries_absent(blob: str) -> None:
    leaked = [index for index, item in enumerate(_CANARIES) if item in blob]
    assert leaked == [], "sensitive canary leaked"


def test_wrapped_account_line_is_not_a_clause_and_preserves_notices() -> None:
    wrapped = (
        "8. Billing. LinguaCare Interpreting Treasury, 55 Congress Avenue, Austin. Account\n"
        "44556677. Billing contact: Avery Quinn, 8 River Way,\n"
        "avery.quinn@linguacare.invalid, +1-555-0188.\n"
        "9. Notices. Formal notices use the addresses in clause 8."
    )
    cleaned = sanitize_contract_text(wrapped)
    _assert_canaries_absent(cleaned)
    assert "9. Notices" in cleaned
    clauses = iter_numbered_clauses(cleaned)
    numbers = [number for number, _field, _body in clauses]
    assert "9" in numbers
    assert all(is_credible_clause_number(number) for number in numbers)
    assert not any(len(number) > 2 for number in numbers)


def test_redacted_billing_metadata_is_idempotent() -> None:
    labels = ("billing", "notices", "non-renewal_notice", "8. Billing details [redacted-sensitive].")
    for label in labels:
        assert is_already_redacted_metadata(label)
        assert contains_bank_or_contact(label) is False
        assert sanitize_contract_text(label) == label


def test_s06_blocked_brief_from_generated_pdf_returns_public_payload(tmp_path: Path) -> None:
    runtime = ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))
    supervisor = Supervisor(runtime)
    response = supervisor.handle(
        SupervisorRequest(kind="brief", question="write a renegotiation brief", supplier_id="HC-S06")
    )
    assert response.blocked is True
    assert response.block_reason == "missing_dpa_blocks_brief_and_draft"
    payload = response_payload(response)
    assert_clean_mapping(payload)
    _assert_canaries_absent(json.dumps(payload))
    _assert_canaries_absent(response.answer)
    _assert_canaries_absent(" ".join(response.citations))
    claire = [row for row in response.alerts if row.get("kind") == "missing_dpa"]
    assert len(claire) == 1
    terms = (payload.get("contracts") or {}).get("terms") or []
    fields = [str(item.get("field", "")) for item in terms]
    assert "billing" in fields
    for item in terms:
        assert contains_bank_or_contact(str(item.get("field", ""))) is False
        assert contains_bank_or_contact(str(item.get("value", ""))) is False


def test_actual_pdf_clause_ids_citations_and_answers_omit_bank_canaries(tmp_path: Path) -> None:
    runtime = ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))
    supervisor = Supervisor(runtime)
    requests = (
        ("HC-S01", "evaluate_increase"),
        ("HC-S01", "brief"),
        ("HC-S03", "evaluate_increase"),
        ("HC-S07", "evaluate_increase"),
        ("HC-S07", "brief"),
    )
    for supplier_id, kind in requests:
        response = supervisor.handle(
            SupervisorRequest(kind=kind, question="evaluate increase and terms", supplier_id=supplier_id)
        )
        payload = response_payload(response)
        terms = (payload.get("contracts") or {}).get("terms") or []
        clause_ids = [str(item.get("clause", "")) for item in terms]
        invalid_count = sum(1 for clause_id in clause_ids if not is_credible_clause_number(clause_id))
        assert invalid_count == 0, "non-clause identifier published"
        assert "9" in clause_ids
        surfaces = [
            json.dumps(payload),
            response.answer,
            " ".join(response.citations),
            " ".join(clause_ids),
        ]
        for blob in surfaces:
            _assert_canaries_absent(blob)
        for citation in response.citations:
            assert re.search(r"\bclause [1-9]\d?\b", citation)
            assert not re.search(r"\bclause \d{3,}\b", citation)
        store_blob = (tmp_path / "process" / "projection.json").read_text(encoding="utf-8")
        audit_blob = (tmp_path / "process" / "audit.jsonl").read_text(encoding="utf-8")
        _assert_canaries_absent(store_blob)
        _assert_canaries_absent(audit_blob)
