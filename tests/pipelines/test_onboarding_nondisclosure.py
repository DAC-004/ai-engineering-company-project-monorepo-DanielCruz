"""Sensitive hire data is rejected at ingress and absent from logs and messages."""

from __future__ import annotations

import pytest

from agents.onboarding_orchestrator.sensitive import (
    DETERMINISTIC_DECISION_NONCE,
    SensitiveDataError,
    contains_sensitive_text,
    scan_mapping,
)
from tests.pipelines.onboarding_helpers import ACTORS, make_runtime, start_three

SYNTHETIC_NI = "QQ123456C"
SYNTHETIC_NI_GROUPED = "QQ 12 34 56 C"
SYNTHETIC_IBAN = "GB82WEST12345698765432"
SYNTHETIC_SORT_ACCOUNT = "20-00-00 12345678"


def test_background_outcome_and_salary_are_rejected_and_not_logged(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    austin = start_three(runtime)["onb-austin"]
    with pytest.raises(SensitiveDataError):
        runtime.apply_event(
            austin["onboarding_id"],
            {
                "type": "people_receipt",
                "documents_received": True,
                "background_check_completed": True,
                "background_check_outcome": "cleared",
                "decision_nonce": austin["decision_nonce"],
            },
            ACTORS["people"],
        )
    with pytest.raises(SensitiveDataError):
        runtime.apply_event(
            austin["onboarding_id"],
            {
                "type": "people_receipt",
                "documents_received": True,
                "background_check_completed": True,
                "comment": "salary is 120000",
                "decision_nonce": austin["decision_nonce"],
            },
            ACTORS["people"],
        )
    text = runtime.paths.audit.read_text(encoding="utf-8")
    store = runtime.paths.store.read_text(encoding="utf-8")
    assert "cleared" not in text
    assert "120000" not in text
    assert "background_check_outcome" not in text
    assert "salary" not in store.lower()
    assert runtime.current("onb-austin")["background_check_completed"] is False
    assert all(item["actor_type"] == "automated_process" for item in runtime.audit.lines())


def test_only_background_completion_flag_is_persisted(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    austin = start_three(runtime)["onb-austin"]
    updated = runtime.apply_event(
        austin["onboarding_id"],
        {
            "type": "people_receipt",
            "documents_received": True,
            "background_check_completed": True,
            "decision_nonce": austin["decision_nonce"],
        },
        ACTORS["people"],
    )
    assert updated["background_check_completed"] is True
    assert "background_check_outcome" not in updated
    assert "ssn" not in updated
    dumped = runtime.paths.store.read_text(encoding="utf-8").lower()
    assert "ssn" not in dumped
    assert "iban" not in dumped
    assert "passport" not in dumped


def test_unlabeled_ssn_format_is_rejected_from_questions_and_text(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    assert contains_sensitive_text("123-45-6789") is True
    with pytest.raises(SensitiveDataError):
        runtime.ask(
            "onb-austin",
            "Please store 123-45-6789 with my paperwork",
            ACTORS["hire_austin"]["user_id"],
        )
    dumped = runtime.paths.store.read_text(encoding="utf-8")
    assert "123-45-6789" not in dumped
    audit = runtime.paths.audit.read_text(encoding="utf-8")
    assert "123-45-6789" not in audit


def test_deterministic_generated_nonce_is_not_classified_as_bank() -> None:
    assert len(DETERMINISTIC_DECISION_NONCE) == 32
    assert DETERMINISTIC_DECISION_NONCE.startswith("ab12")
    assert contains_sensitive_text(DETERMINISTIC_DECISION_NONCE) is False
    scan_mapping(
        {
            "decision_nonce": DETERMINISTIC_DECISION_NONCE,
            "onboarding_id": "onb-austin",
            "status": "waiting_human",
        }
    )
    assert contains_sensitive_text(SYNTHETIC_IBAN) is True
    assert contains_sensitive_text(f"{DETERMINISTIC_DECISION_NONCE} {SYNTHETIC_NI}") is True
    with pytest.raises(SensitiveDataError):
        scan_mapping({"comment": SYNTHETIC_IBAN})


def test_unlabeled_ni_and_bank_formats_are_rejected_from_checkpoint_and_logs(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    runtime.store.upsert_onboarding(
        {**runtime.current("onb-austin"), "decision_nonce": DETERMINISTIC_DECISION_NONCE}
    )
    assert contains_sensitive_text(SYNTHETIC_NI) is True
    assert contains_sensitive_text(SYNTHETIC_NI_GROUPED) is True
    assert contains_sensitive_text(SYNTHETIC_IBAN) is True
    assert contains_sensitive_text(SYNTHETIC_SORT_ACCOUNT) is True
    with pytest.raises(SensitiveDataError):
        runtime.ask(
            "onb-austin",
            f"Please store {SYNTHETIC_NI} with my paperwork",
            ACTORS["hire_austin"]["user_id"],
        )
    with pytest.raises(SensitiveDataError):
        runtime.ask(
            "onb-austin",
            f"Payroll destination {SYNTHETIC_IBAN}",
            ACTORS["hire_austin"]["user_id"],
        )
    with pytest.raises(SensitiveDataError):
        runtime.ask(
            "onb-austin",
            f"Use {SYNTHETIC_SORT_ACCOUNT} for the transfer",
            ACTORS["hire_austin"]["user_id"],
        )
    store = runtime.paths.store.read_text(encoding="utf-8")
    audit = runtime.paths.audit.read_text(encoding="utf-8")
    checkpoint = runtime.paths.checkpoint.read_bytes()
    for token in (SYNTHETIC_NI, SYNTHETIC_IBAN, SYNTHETIC_SORT_ACCOUNT):
        assert token not in store
        assert token not in audit
        assert token.encode("ascii") not in checkpoint
    assert DETERMINISTIC_DECISION_NONCE == runtime.current("onb-austin")["decision_nonce"]



def test_unlabeled_fictional_passport_and_bank_identifiers_are_excluded() -> None:
    import pytest
    from agents.onboarding_orchestrator.sensitive import SensitiveDataError, scan_mapping

    for value in ["ZZ0000000", "00000000", "000000000"]:
        with pytest.raises(SensitiveDataError):
            scan_mapping({"comment": f"Do not retain this fictional identifier {value}"})
