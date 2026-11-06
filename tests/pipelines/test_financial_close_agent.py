"""Agent planning, writer grounding, missing sources, and production transport default."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from agents.financial_close.agent import run_close
from agents.financial_close.generation import configured_transport, parse_plan_payload
from agents.financial_close.identity import ActorIdentity, TOM_EMAIL
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.seed import write_fixtures
from agents.financial_close.generation import text_is_grounded
from agents.financial_close.serialize import known_reference_catalog, lookup_figure
from agents.financial_close.tools import CalculationToolbox, build_facts


def _tom() -> ActorIdentity:
    return ActorIdentity(
        user_id=uuid4().hex,
        role="supervisor",
        department_id="revenue_cycle",
        email=TOM_EMAIL,
        is_active=True,
        is_admin=False,
        can_approve=True,
    )


def _transport(calls: list) -> object:
    def run(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        system = messages[0]["content"]
        if "planner" in system:
            return json.dumps(
                {
                    "tools": [
                        "ingest_and_normalize",
                        "aggregate_lines",
                        "actual_versus_budget",
                        "convert_gbp_usd",
                    ]
                }
            )
        user = messages[1]["content"] if len(messages) > 1 else ""
        marker = "Facts (data): "
        evidence = {}
        if marker in user:
            evidence = json.loads(user.split(marker, 1)[1]).get("evidence_sentence") or {}
        medicare = evidence.get("us_medicare_medicaid_revenue", "")
        lab_evidence = evidence.get("us_laboratory", "")
        return json.dumps(
            {
                "hypotheses": {
                    "us_medicare_medicaid_revenue": {
                        "evidence": medicare,
                        "hypothesis": "Higher denials reduced collections this closing period.",
                    },
                    "us_laboratory": {
                        "evidence": lab_evidence,
                        "hypothesis": "Higher supplier unit price increased expense.",
                    },
                },
                "summary": "Close for 2026-10 remains incomplete.",
            }
        )

    return run


def test_production_runtime_defaults_to_configured_transport(tmp_path) -> None:
    runtime = CloseRuntime(raw=tmp_path / "raw", process=tmp_path / "proc")
    assert runtime.transport is configured_transport


def test_mocked_plan_invokes_allowlisted_tools_and_writer(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    calls: list = []
    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=_transport(calls),
    )
    draft = run_close(runtime, catch_up=True)
    assert len(calls) == 2
    assert "planner" in calls[0][0]["content"]
    assert "writer" in calls[1][0]["content"]
    projection = calls[1][1]["content"]
    assert "4000" in projection
    assert "22.6" in projection
    assert "14.0" in projection
    assert "19.26" in projection
    assert "1.26" in projection
    assert "unchanged" in projection
    assert "Revenue below budget." in projection
    assert "budget-implied" in projection
    assert "evidence_sentence" in projection
    assert "-52000" not in projection
    assert "-10.0%" not in projection
    assert draft["write_source"] == "model"
    assert "us_laboratory" in draft["model_hypotheses"]
    assert "convert_gbp_usd" in parse_plan_payload(draft["plan_raw"] or "")
    assert "convert_gbp_usd" in draft["model_selected_tools"]
    assert "ingest_and_normalize" in draft["tools"]
    assert draft["deterministic_fallback"] is False
    medicare_item = next(
        item for item in draft["report"]["relevant_deviations"] if item["line_id"] == "us_medicare_medicaid_revenue"
    )
    assert "Hypothesis (not proved causality):" in medicare_item["hypothesis"]
    assert "Higher denials reduced collections this closing period." in medicare_item["hypothesis"]
    assert "Revenue below budget." in medicare_item["hypothesis"]
    lab = next(item for item in draft["report"]["relevant_deviations"] if item["line_id"] == "us_laboratory")
    assert "19.26" in lab["hypothesis"]
    assert "Hypothesis (not proved causality):" in lab["hypothesis"]
    assert "Higher supplier unit price increased expense." in lab["hypothesis"]
    assert "brief expectation" in lab["hypothesis"]
    assert "not observed budget quantity" in lab["hypothesis"]
    assert "987654321" not in json.dumps(draft["report"])


def test_missing_ledger_is_uncertain_and_does_not_write_finance_files(tmp_path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    calls: list = []
    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=_transport(calls),
    )
    draft = run_close(runtime, catch_up=True)
    assert not (raw / "ledger.csv").exists()
    assert not (raw / "budget.csv").exists()
    reasons = {item.get("reason") for item in draft["report"]["missing_or_uncertain"]}
    assert "missing_source_file" in reasons
    assert draft["report"]["incomplete"] is True
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    assert facts.file_hashes["ledger.csv"] == "missing"
    assert facts.lines["us_laboratory"].verified_actual is None


def test_invented_writer_amount_is_not_persisted(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))

    def bad_transport(messages: list[dict[str, str]]) -> str:
        if "planner" in messages[0]["content"]:
            return json.dumps({"tools": ["ingest_and_normalize"]})
        return json.dumps(
            {"hypotheses": {"us_laboratory": "Hypothesis: costs changed by 987654321 USD."}, "summary": []}
        )

    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=bad_transport,
    )
    draft = run_close(runtime, catch_up=True)
    blob = json.dumps(draft["report"])
    assert "987654321" not in blob
    lab = next(item for item in draft["report"]["relevant_deviations"] if item["line_id"] == "us_laboratory")
    assert "19.26" in lab["hypothesis"]
    assert lab["verified_actual"] == "48150"


def test_us_lab_support_uses_budget_implied_unit_not_invented_quantity(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    from agents.financial_close.tools import laboratory_support

    support = laboratory_support(facts)
    assert support is not None
    assert support["observed_unit_price"] == "19.26"
    assert support["observed_quantity"] == "2500"
    assert Decimal(support["budget_implied_unit_price"]) == Decimal("18")
    assert Decimal(support["unit_price_variance"]) == Decimal("1.26")
    assert support["increase"] == "3150"
    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=_transport([]),
    )
    draft = run_close(runtime, catch_up=True)
    hypothesis = next(
        item["hypothesis"] for item in draft["report"]["relevant_deviations"] if item["line_id"] == "us_laboratory"
    )
    assert "brief expectation" in hypothesis
    assert "not observed budget quantity" in hypothesis


def test_exact_figure_lookup_returns_rows_and_rejects_suffix(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=_transport([]),
    )
    draft = run_close(runtime, catch_up=True)
    payload = lookup_figure(draft["report"], "us_laboratory.verified_actual")
    assert payload["value"] == "48150"
    assert payload["contributing_rows"]
    assert payload["formula"]
    assert payload["hash"]
    try:
        lookup_figure(draft["report"], "us_laboratory.verified_actual.extra")
        raise AssertionError("suffix must be rejected")
    except KeyError:
        pass
    lab_unit = lookup_figure(draft["report"], "us_laboratory.unit_price")
    assert lab_unit["value"] == "19.26"
    quantity = lookup_figure(draft["report"], "us_laboratory.observed_quantity")
    assert quantity["value"] == "2500"
    implied = lookup_figure(draft["report"], "us_laboratory.budget_implied_unit_price")
    assert Decimal(implied["value"]) == Decimal("18")
    variance = lookup_figure(draft["report"], "us_laboratory.unit_price_variance")
    assert Decimal(variance["value"]) == Decimal("1.26")
    increase = lookup_figure(draft["report"], "us_laboratory.increase")
    assert increase["value"] == "3150"
    commercial = lookup_figure(draft["report"], "operations.commercial.claims_submitted_actual")
    assert commercial["value"] == "6400"
    _ = _tom()


def test_empty_writer_payload_is_not_model_write_source(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))

    def transport(messages: list[dict[str, str]]) -> str:
        if "planner" in messages[0]["content"]:
            return json.dumps(
                {
                    "tools": [
                        "ingest_and_normalize",
                        "actual_versus_budget",
                        "convert_gbp_usd",
                    ]
                }
            )
        return json.dumps({"hypotheses": {}, "summary": []})

    runtime = CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=transport,
    )
    draft = run_close(runtime, catch_up=True)
    assert draft["write_source"] == "deterministic_fallback"
    assert draft["model_hypotheses"] == {}
    assert draft["tool_results"]["convert_gbp_usd"]
