"""Briefing questions through the supervisor without a live provider."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import SupervisorRequest


def _runtime(tmp_path: Path) -> ContractRuntime:
    return ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))


def test_alternatives_question_returns_quote_without_hidden_kind(tmp_path: Path) -> None:
    response = Supervisor(_runtime(tmp_path)).handle(
        SupervisorRequest(
            kind="question",
            question="What alternatives exist in the same country and category?",
            supplier_id="HC-S03",
        )
    )
    assert response.blocked is False
    assert "HC-S04" in response.answer
    assert "Lone Star Diagnostics" in response.answer
    assert "quote_only=True" in response.answer
    assert "availability_assumed=False" in response.answer


def test_notice_question_returns_dated_deadline(tmp_path: Path) -> None:
    response = Supervisor(_runtime(tmp_path)).handle(
        SupervisorRequest(
            kind="question",
            question="When is the non-renewal notice deadline?",
            supplier_id="HC-S03",
        )
    )
    assert "notice_deadline" in response.answer
    assert "expiry" in response.answer


def test_compare_plan_with_contracts_tool_still_loads_notice_terms(tmp_path: Path) -> None:
    def fake_transport(messages: list[dict[str, str]]) -> str:
        text = messages[-1]["content"]
        if "specialist catalog" in text or "Catalog ids" in text:
            return '{"fact_ids":["expiry_notice"]}'
        return '{"kind":"compare","tools":["consult_pricing","consult_contracts"]}'

    supervisor = Supervisor(_runtime(tmp_path), transport=fake_transport)
    response = supervisor.handle(
        SupervisorRequest(
            kind="question",
            question="When is the non-renewal notice deadline?",
            supplier_id="HC-S03",
        )
    )
    assert supervisor.last_plan_source == "model"
    assert supervisor.last_plan_kind == "compare"
    assert "consult_contracts" in supervisor.last_plan_tools
    assert supervisor.last_contracts_consulted is True
    assert response.contracts is not None
    assert "notice_deadline" in response.answer


def test_misclassified_compare_notice_still_consults_contracts(tmp_path: Path) -> None:
    def fake_transport(messages: list[dict[str, str]]) -> str:
        text = messages[-1]["content"]
        if "specialist catalog" in text or "Catalog ids" in text:
            return '{"fact_ids":["expiry_notice"]}'
        return '{"kind":"compare","tools":["consult_pricing"]}'

    supervisor = Supervisor(_runtime(tmp_path), transport=fake_transport)
    response = supervisor.handle(
        SupervisorRequest(
            kind="question",
            question="When is the non-renewal notice deadline?",
            supplier_id="HC-S03",
        )
    )
    assert supervisor.last_plan_kind == "compare"
    assert supervisor.last_contracts_consulted is True
    assert response.contracts is not None
    assert "notice_deadline" in response.answer
    assert "expiry" in response.answer


def test_compare_only_alternatives_still_skip_contract_pdf(tmp_path: Path) -> None:
    def fake_transport(messages: list[dict[str, str]]) -> str:
        text = messages[-1]["content"]
        if "specialist catalog" in text or "Catalog ids" in text:
            return '{"fact_ids":["alternative_HC-S04"]}'
        return '{"kind":"compare","tools":["consult_pricing"]}'

    supervisor = Supervisor(_runtime(tmp_path), transport=fake_transport)
    response = supervisor.handle(
        SupervisorRequest(
            kind="question",
            question="What alternatives exist in the same country and category?",
            supplier_id="HC-S03",
        )
    )
    assert supervisor.last_plan_kind == "compare"
    assert supervisor.last_contracts_consulted is False
    assert response.contracts is None
    assert "HC-S04" in response.answer


def test_brief_contains_notice_exit_penalty_and_citations(tmp_path: Path) -> None:
    response = Supervisor(_runtime(tmp_path)).handle(
        SupervisorRequest(
            kind="question",
            question="Write a renegotiation brief with notice, exit, and sources.",
            supplier_id="HC-S03",
        )
    )
    assert response.blocked is False
    assert "notice_deadline" in response.answer
    assert "Exit clause 5" in response.answer
    assert "two months of average billing" in response.answer
    assert "averaging period is not specified" in response.answer
    assert "sha256=" in response.answer
    assert "540000" in response.answer
    assert response.required_approvers
