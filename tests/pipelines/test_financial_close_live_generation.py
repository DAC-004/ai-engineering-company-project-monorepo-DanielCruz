"""Separate live writer evidence. Skipped unless FINANCIAL_CLOSE_LIVE_GENERATION=1."""

from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal

import pytest

from agents.financial_close.agent import run_close
from agents.financial_close.generation import configured_transport, parse_plan_payload, parse_write_payload
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.seed import write_fixtures
from agents.financial_close.serialize import (
    allowed_number_catalog,
    evidence_sentences,
    known_reference_catalog,
    number_catalogs_by_line,
)
from agents.financial_close.tools import build_facts

pytestmark = pytest.mark.skipif(
    os.environ.get("FINANCIAL_CLOSE_LIVE_GENERATION", "").strip() not in {"1", "true", "yes"},
    reason="live generation is isolated from the default suite",
)


def test_live_configured_transport_parses_plan_fx_and_both_hypotheses(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=configured_transport,
    )
    draft = run_close(runtime, catch_up=True)
    assert draft["write_source"] == "model"
    assert draft["deterministic_fallback"] is False
    parsed_plan = parse_plan_payload(draft["plan_raw"] or "")
    assert parsed_plan == list(draft["model_selected_tools"])
    assert "convert_gbp_usd" in parsed_plan
    assert "actual_versus_budget" in parsed_plan
    conversions = draft["tool_results"]["convert_gbp_usd"]
    assert conversions
    private = next(
        item
        for item in conversions
        if item["line_id"] == "uk_private_revenue" and item["basis"] == "verified_actual"
    )
    assert Decimal(private["usd_amount"]) == Decimal("344170")
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    evidence = evidence_sentences(facts)
    accepted, summary = parse_write_payload(
        draft["write_raw"] or "",
        {"us_medicare_medicaid_revenue", "us_laboratory"},
        allowed_number_catalog(facts),
        number_catalogs_by_line(facts),
        known_reference_catalog(facts),
        evidence,
    )
    assert set(accepted) == {"us_medicare_medicaid_revenue", "us_laboratory"}
    assert summary
    assert accepted == draft["model_hypotheses"]
    rendered = {item["line_id"]: item["hypothesis"] for item in draft["report"]["relevant_deviations"]}
    assert accepted["us_medicare_medicaid_revenue"] in rendered["us_medicare_medicaid_revenue"]
    assert accepted["us_laboratory"] in rendered["us_laboratory"]
    assert evidence["us_medicare_medicaid_revenue"] in accepted["us_medicare_medicaid_revenue"]
    assert "Hypothesis (not proved causality):" in accepted["us_medicare_medicaid_revenue"]
    assert evidence["us_laboratory"] in accepted["us_laboratory"]
    assert "Hypothesis (not proved causality):" in accepted["us_laboratory"]
    assert "22.6" in accepted["us_medicare_medicaid_revenue"]
    assert "19.26" in accepted["us_laboratory"]
    assert "18" in accepted["us_laboratory"]
    assert "987654321" not in json.dumps(draft["report"])
    assert "Jordan Hale" not in json.dumps(draft["report"])
