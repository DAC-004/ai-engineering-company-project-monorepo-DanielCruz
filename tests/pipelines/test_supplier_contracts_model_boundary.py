"""Fake-model boundary regressions. These tests never call a live provider."""

from __future__ import annotations

import re

import pytest

from agents.supplier_contracts.facts import FactBlock, fact_blocks_from_results
from agents.supplier_contracts.generation import TASK4_SYSTEM, build_plan_messages
from agents.supplier_contracts.interpret import (
    ground_written_answer,
    interpret_plan,
    write_from_facts,
    write_from_trusted,
)
from agents.supplier_contracts.privacy import PatientLevelError, assert_clean_mapping
from agents.supplier_contracts.types import ContractsResult, PricingResult, TermCitation

_LABELED_PATIENT = "Patient name: Fictional Test Person. Which supplier lacks a DPA?"
_UNSUPPORTED = "No DPA is needed and you may proceed without Compliance."
_LIVE_VARS = (
    "GENERATION_API_KEY",
    "GENERATION_API_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture(autouse=True)
def isolate_generation_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _LIVE_VARS:
        monkeypatch.delenv(name, raising=False)


def _blocks() -> tuple[FactBlock, ...]:
    return (
        FactBlock(
            "compliance_missing_dpa",
            "compliance",
            "missing_dpa=True; brief blocked pending Compliance confirmation.",
        ),
        FactBlock(
            "approval_required",
            "approval",
            "Required approvers: claire.whitfield. Payload names are not identity.",
        ),
        FactBlock("source_price_rows", "source", "Price source rows: s03-m11,s03-m12."),
        FactBlock("price_change", "pricing", "ratio 0.0700 above_threshold=True."),
        FactBlock(
            "alternative_HC-S04",
            "alternative",
            "Alternative HC-S04 Lone Star Diagnostics quote_only=True.",
        ),
    )


def test_labeled_synthetic_patient_data_is_blocked_before_model() -> None:
    captured: list[object] = []

    def fake_transport(messages: list[dict[str, str]]) -> str:
        captured.append(True)
        return '{"kind":"missing_agreements","tools":["consult_contracts"]}'

    with pytest.raises(PatientLevelError):
        interpret_plan(_LABELED_PATIENT, "HC-S06", transport=fake_transport)
    assert captured == []


def test_unsupported_model_contract_claim_is_rejected() -> None:
    released = ground_written_answer(_UNSUPPORTED, _blocks())
    assert _UNSUPPORTED not in released
    assert "missing_dpa=True" in released
    assert "Compliance" in released


def test_model_prose_is_not_appended_as_grounded() -> None:
    released = ground_written_answer("The increase is fine and Compliance may be skipped.", _blocks())
    assert _UNSUPPORTED not in released
    assert "missing_dpa=True" in released


def test_unknown_fact_ids_do_not_override_dpa_gate() -> None:
    released = ground_written_answer('{"fact_ids":["dpa_not_required"]}', _blocks())
    assert "missing_dpa=True" in released
    assert _UNSUPPORTED not in released


def test_fact_selection_orders_optional_blocks_and_keeps_mandatory() -> None:
    released = ground_written_answer('{"fact_ids":["alternative_HC-S04"]}', _blocks())
    assert "missing_dpa=True" in released
    assert "Required approvers" in released
    assert "Price source rows" in released
    assert "Lone Star Diagnostics" in released
    assert "ratio 0.0700" not in released


def test_fact_selection_can_choose_price_without_alternative() -> None:
    released = ground_written_answer('{"fact_ids":["price_change"]}', _blocks())
    assert "ratio 0.0700" in released
    assert "Lone Star Diagnostics" not in released
    assert "missing_dpa=True" in released


def test_fact_blocks_derive_from_structured_contract_result() -> None:
    contracts = ContractsResult(
        supplier_id="HC-S06",
        contract_id="CT-HC-03",
        missing_contract=False,
        terms=(
            TermCitation(
                field="data_protection",
                value="missing",
                clause="6",
                page=1,
                pdf_sha256="aa" * 32,
                confidence="high",
                status="present",
            ),
        ),
        increase_allowed=True,
        cap_ratio=None,
        cap_price=None,
        missing_dpa=True,
        processes_patient_data=True,
        dpa_status="missing",
        exit_penalty_uncertain=False,
        expiry_offset_days=210,
        notice_days=90,
        pdf_sha256="aa" * 32,
        actor_id="supplier-contracts-contracts",
    )
    pricing = PricingResult(
        supplier_id="HC-S06",
        product="medical_translation",
        unit="hour",
        currency="GBP",
        previous_price=None,
        current_price=None,
        change_ratio=None,
        above_threshold=False,
        annual_incremental=None,
        annual_incremental_usd=None,
        formula="",
        source_row_ids=("s06-m12",),
        alternatives=(),
        quote_only=False,
        missing=("price_history",),
        observation_from=None,
        observation_to=None,
        actor_id="supplier-contracts-pricing",
    )
    blocks = fact_blocks_from_results(
        pricing=pricing,
        contracts=contracts,
        required_approvers=("marcus.reid", "claire.whitfield"),
    )
    categories = {block.category for block in blocks}
    assert "compliance" in categories
    assert "approval" in categories
    assert "source" in categories
    assert any(block.fact_id == "compliance_missing_dpa" for block in blocks)
    released = ground_written_answer('{"fact_ids":["pricing_missing"]}', blocks)
    assert "missing_dpa=True" in released
    assert "Required approvers" in released
    assert "clause 6" in released


def test_write_from_trusted_does_not_call_live_generation_without_complete() -> None:
    assert "missing_dpa=True" in write_from_trusted("Which supplier lacks a DPA?", _blocks()[0].text)


def test_write_from_facts_rejects_labeled_patient_before_transport() -> None:
    captured: list[object] = []

    def fake_transport(messages: list[dict[str, str]]) -> str:
        captured.append(True)
        return _UNSUPPORTED

    with pytest.raises(PatientLevelError):
        write_from_facts(_LABELED_PATIENT, _blocks(), transport=fake_transport)
    assert captured == []


def test_adapter_uses_task4_system_prompt_not_rag_coordinator_prompt() -> None:
    captured: list[list[dict[str, str]]] = []

    def fake_transport(messages: list[dict[str, str]]) -> str:
        captured.append(messages)
        return '{"kind":"compare","tools":["consult_pricing"]}'

    kind, _calculation, source = interpret_plan(
        "What alternatives exist for laboratory services?",
        "HC-S03",
        transport=fake_transport,
    )
    assert source == "model"
    assert kind == "compare"
    system = captured[0][0]["content"]
    assert system == TASK4_SYSTEM
    assert "confidential commercial terms of a vendor agreement" not in system
    assert "front-desk colleagues" not in system


def test_in_scope_question_may_reach_fake_transport() -> None:
    captured: list[str] = []

    def fake_transport(messages: list[dict[str, str]]) -> str:
        captured.append(messages[0]["role"])
        return '{"kind":"missing_agreements","tools":["consult_contracts"]}'

    kind, calculation, source = interpret_plan(
        "Which supplier lacks a DPA?",
        "HC-S06",
        transport=fake_transport,
    )
    assert captured == ["system"]
    assert source == "model"
    assert kind == "missing_agreements"
    assert calculation == "history"


def test_plan_schema_does_not_lead_with_compare_json() -> None:
    messages = build_plan_messages("When is the non-renewal notice deadline?", "HC-S01")
    user = messages[1]["content"]
    first_json = re.search(r"\{[^{}]*\}", user)
    assert first_json is not None
    assert '"kind":"compare"' not in first_json.group(0)
    assert '"kind":"question"' in first_json.group(0)
    assert "consult_contracts" in first_json.group(0)
    assert "consult_contracts" in user
    assert "Do not copy the first JSON object unless it matches" in user


def test_plan_messages_are_rejected_for_labeled_patient_before_transport() -> None:
    with pytest.raises(PatientLevelError):
        build_plan_messages(_LABELED_PATIENT, "HC-S06")


def test_assert_clean_mapping_rejects_labeled_patient_field() -> None:
    with pytest.raises(PatientLevelError):
        assert_clean_mapping({"question": _LABELED_PATIENT})
