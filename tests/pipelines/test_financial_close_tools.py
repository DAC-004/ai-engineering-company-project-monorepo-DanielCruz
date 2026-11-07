"""Allowlisted tool results, including per-line GBP conversions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from agents.financial_close.seed import write_fixtures
from agents.financial_close.tools import CalculationToolbox, to_usd


def test_convert_gbp_usd_returns_per_line_actual_and_budget_with_source_refs(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    toolbox = CalculationToolbox(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    facts = toolbox.invoke(["convert_gbp_usd"])
    converted = toolbox.tool_results["convert_gbp_usd"]
    assert converted == [
        {
            "line_id": item["line_id"],
            "basis": item["basis"],
            "gbp_amount": item["gbp_amount"],
            "usd_amount": item["usd_amount"],
            "rate": item["rate"],
            "fx_source": item["fx_source"],
            "source_refs": item["source_refs"],
        }
        for item in converted
    ]
    private_actual = next(
        item
        for item in converted
        if item["line_id"] == "uk_private_revenue" and item["basis"] == "verified_actual"
    )
    assert private_actual["gbp_amount"] == "271000"
    assert Decimal(private_actual["usd_amount"]) == to_usd(Decimal("271000"), "GBP")
    assert Decimal(private_actual["usd_amount"]) == Decimal("344170")
    assert private_actual["source_refs"]
    private_budget = next(
        item for item in converted if item["line_id"] == "uk_private_revenue" and item["basis"] == "budget"
    )
    assert private_budget["gbp_amount"] == "260000"
    assert Decimal(private_budget["usd_amount"]) == Decimal("330200")
    software_budget = next(
        item for item in converted if item["line_id"] == "uk_software" and item["basis"] == "budget"
    )
    assert software_budget["gbp_amount"] == "8000"
    assert not any(
        item["line_id"] == "uk_software" and item["basis"] == "verified_actual" for item in converted
    )
    assert facts.conversion_results
    assert {item.line_id for item in facts.conversion_results} == {
        item["line_id"] for item in converted
    }
    assert toolbox.tool_results.get("select_relevant_deviations") in (
        None,
        ["us_medicare_medicaid_revenue", "us_laboratory"],
    )


def test_signed_amount_variance_is_none_when_incomplete_or_missing(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    toolbox = CalculationToolbox(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    facts = toolbox.invoke(["actual_versus_budget"])
    medicare = facts.lines["us_medicare_medicaid_revenue"]
    lab = facts.lines["us_laboratory"]
    rent = facts.lines["us_rent"]
    software = facts.lines["uk_software"]
    assert medicare.amount_variance == Decimal("-52000")
    assert lab.amount_variance == Decimal("3150")
    assert rent.amount_variance is None
    assert software.amount_variance is None
    payload = toolbox.tool_results["actual_versus_budget"]
    assert payload["us_medicare_medicaid_revenue"]["amount_variance"] == "-52000"
    assert payload["us_laboratory"]["percent_display"] == "7.0%"
    assert payload["us_rent"]["amount_variance"] is None
    from agents.financial_close.serialize import lookup_figure, build_report, default_hypotheses

    report = build_report(facts, hypotheses=default_hypotheses(facts))
    figure = lookup_figure(report, "us_medicare_medicaid_revenue.amount_variance")
    assert figure["value"] == "-52000"
    lab_figure = lookup_figure(report, "us_laboratory.amount_variance")
    assert lab_figure["value"] == "3150"


def test_convert_selected_before_ingest_keeps_fx_results(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    toolbox = CalculationToolbox(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    facts = toolbox.invoke(["convert_gbp_usd", "ingest_and_normalize"])
    assert toolbox.invoked.index("ingest_and_normalize") < toolbox.invoked.index("convert_gbp_usd")
    assert toolbox.invoked.count("ingest_and_normalize") == 1
    assert facts.conversion_results
    assert toolbox.tool_results["convert_gbp_usd"]
    assert facts.model_selected_tools == ("convert_gbp_usd", "ingest_and_normalize")
    assert facts.deterministic_fallback is False
