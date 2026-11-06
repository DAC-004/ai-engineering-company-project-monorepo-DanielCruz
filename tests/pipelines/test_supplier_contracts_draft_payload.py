"""Structured drafts stay off the answer text; notice/exit terms stay in briefs."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from agents.supplier_contracts.facts import FactBlock
from agents.supplier_contracts.interpret import write_from_facts
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.serialize import response_payload
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import SupervisorRequest


def _runtime(tmp_path: Path) -> ContractRuntime:
    return ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))


def test_draft_communication_returns_structured_draft_without_technical_answer_fields(tmp_path: Path) -> None:
    response = Supervisor(_runtime(tmp_path)).handle(
        SupervisorRequest(
            kind="draft_communication",
            question="Write a communication to the supplier.",
            supplier_id="HC-S01",
        )
    )
    assert response.blocked is False
    assert response.draft is not None
    assert response.draft["body"]
    assert response.draft["required"]
    assert response.draft["state"] == "pending"
    assert response.draft["draft_id"] not in response.answer
    assert "nonce=" not in response.answer
    payload = response_payload(response)
    draft = payload["draft"]
    assert draft["body"]
    assert "content_sha256" in draft
    assert "approval_nonce" in draft
    assert draft["draft_id"] not in payload["answer"]


def test_model_cannot_drop_exit_and_notice_terms_from_a_brief() -> None:
    blocks = (
        FactBlock("compliance_dpa_recorded", "compliance", "missing_dpa=False dpa_status=signed_baa."),
        FactBlock("approval_required", "approval", "Required approvers: marcus.reid."),
        FactBlock("source_exit_5", "source", "exit clause 5 page 1 sha256=abc"),
        FactBlock("price_change", "pricing", "ratio 0.0700 above_threshold=True."),
        FactBlock(
            "exit_penalty",
            "contract",
            "Exit clause 5 page 1: Early termination carries a penalty of two months of average billing.",
        ),
        FactBlock(
            "expiry_notice",
            "contract",
            "expiry 2027-01-05 notice_deadline 2026-11-21 notice_days=45.",
        ),
    )

    def fake_transport(messages: list[dict[str, str]]) -> str:
        return '{"fact_ids":["price_change"]}'

    written = write_from_facts(
        "Write a renegotiation brief with notice, exit, and sources.",
        blocks,
        transport=fake_transport,
    )
    assert "two months of average billing" in written
    assert "notice_deadline 2026-11-21" in written
    assert "missing_dpa=False" in written
