"""Schema extra=forbid without starting the API process."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.financial_close import FinancialCloseApproval


def test_approval_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        FinancialCloseApproval(
            draft_id="a" * 32,
            version=1,
            content_sha256="b" * 64,
            approval_nonce="c" * 32,
            decision="approve",
            comments=None,
            unexpected="Jordan Hale",  # type: ignore[call-arg]
        )


def test_public_draft_exposes_reviewer_and_source_lookup_fields(tmp_path) -> None:
    from datetime import date

    from agents.financial_close.agent import run_close
    from agents.financial_close.runtime import CloseRuntime
    from agents.financial_close.seed import write_fixtures
    from agents.financial_close.serialize import lookup_figure
    from app.services.financial_close_service import public_draft

    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    runtime = CloseRuntime(raw=raw, process=tmp_path / "proc", as_of=date(2026, 11, 6), transport=None)
    draft = run_close(runtime, catch_up=True)
    payload = public_draft(draft)
    consolidated = payload["consolidated_usd"]
    assert consolidated["revenue_budget_usd"]
    assert consolidated["expense_budget_usd"]
    assert consolidated["known_revenue_actual_usd"]
    assert consolidated["known_expense_actual_usd"]
    assert isinstance(consolidated["result_budget_usd"], str)
    assert Decimal(consolidated["result_budget_usd"]) == Decimal("390308")
    revenue = payload["revenue_by_country_payer"][0]
    assert revenue["country"]
    assert "payer" in revenue
    assert revenue["currency"]
    assert "percent_display" in revenue or revenue.get("percent") is not None
    lab = lookup_figure(draft["report"], "us_laboratory.unit_price")
    assert lab["value"] == "19.26"
    assert lab["hash"]
    assert lab["contributing_rows"]
    assert "reviewer_guidance" in payload
    assert "us_laboratory.unit_price" in payload["figure_ids"]


def test_approval_schema_rejects_untyped_decision() -> None:
    with pytest.raises(ValidationError):
        FinancialCloseApproval(
            draft_id="a" * 32,
            version=1,
            content_sha256="b" * 64,
            approval_nonce="c" * 32,
            decision="maybe",
        )
