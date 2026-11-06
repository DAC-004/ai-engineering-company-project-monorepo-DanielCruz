"""Build the seven-section report from deterministic facts. Numbers never come from the model."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from agents.financial_close.constants import (
    CURRENCY_GBP,
    LINE_IDS,
    LINE_SPEC,
    METRIC_CLAIMS_ACTUAL,
    METRIC_CLAIMS_BUDGET,
    METRIC_DENIAL_ACTUAL,
    METRIC_DENIAL_BUDGET,
    PAYER_COMMERCIAL,
    PAYER_MEDICARE,
)
from agents.financial_close.money import display_percent
from agents.financial_close.privacy import ALLOWED_FIGURE_IDS, assert_clean_mapping
from agents.financial_close.tools import laboratory_support, operations_value, to_usd
from agents.financial_close.types import CloseFacts, LineFact

LAB_QUANTITY_CAVEAT = (
    "Unchanged quantity is a brief expectation, not observed budget quantity data"
)


def _money(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _amount_status(fact: LineFact) -> str:
    if fact.missing_actual:
        return "missing"
    if fact.incomplete:
        return "known_subtotal"
    return "complete"


def _line_payload(fact: LineFact) -> dict:
    return {
        "line_id": fact.line_id,
        "country": fact.country,
        "payer": fact.payer,
        "category": fact.category,
        "currency": fact.currency,
        "kind": fact.kind,
        "budget": _money(fact.budget),
        "verified_actual": _money(fact.verified_actual),
        "known_subtotal": _money(fact.verified_actual) if fact.incomplete and fact.verified_actual is not None else None,
        "amount_status": _amount_status(fact),
        "percent": str(fact.percent) if fact.percent is not None else None,
        "percent_display": display_percent(fact.percent) if fact.percent is not None else None,
        "amount_variance": _money(fact.amount_variance),
        "incomplete": fact.incomplete,
        "missing_actual": fact.missing_actual,
        "missing_budget": fact.missing_budget,
        "relevant": fact.relevant,
        "entry_ids": list(fact.verified_entry_ids),
        "budget_row_ids": list(fact.budget_row_ids),
        "source_refs": list(fact.source_refs),
        "issues": list(fact.issues),
    }


def _budget_complete(facts: CloseFacts) -> bool:
    return all(fact.budget is not None and not fact.missing_budget for fact in facts.lines.values()) and not any(
        row.uncertain or row.exclude_from_totals for row in facts.budget_rows
    )


def _usd_for_line(facts: CloseFacts, line_id: str, basis: str, amount: Decimal | None, currency: str) -> Decimal | None:
    if amount is None:
        return None
    if currency != CURRENCY_GBP:
        return to_usd(amount, currency)
    for item in facts.conversion_results:
        if item.line_id == line_id and item.basis == basis:
            return Decimal(item.usd_amount)
    return to_usd(amount, currency)


def _consolidated(facts: CloseFacts) -> dict:
    revenue_budget = Decimal("0")
    expense_budget = Decimal("0")
    known_revenue_actual = Decimal("0")
    known_expense_actual = Decimal("0")
    revenue_actual_complete = True
    expense_actual_complete = True
    for fact in facts.lines.values():
        budget_usd = _usd_for_line(facts, fact.line_id, "budget", fact.budget, fact.currency)
        actual_usd = _usd_for_line(facts, fact.line_id, "verified_actual", fact.verified_actual, fact.currency)
        if fact.kind == "revenue":
            if budget_usd is not None:
                revenue_budget += budget_usd
            if actual_usd is not None:
                known_revenue_actual += actual_usd
            if actual_usd is None or fact.incomplete:
                revenue_actual_complete = False
        else:
            if budget_usd is not None:
                expense_budget += budget_usd
            if actual_usd is not None:
                known_expense_actual += actual_usd
            if actual_usd is None or fact.incomplete:
                expense_actual_complete = False
    budget_complete = _budget_complete(facts)
    actual_complete = revenue_actual_complete and expense_actual_complete and not facts.incomplete
    result_budget = revenue_budget - expense_budget if budget_complete else None
    result_actual = known_revenue_actual - known_expense_actual if actual_complete else None
    return {
        "status": "complete" if actual_complete and budget_complete else "incomplete",
        "budget_status": "complete" if budget_complete else "incomplete",
        "actual_status": "complete" if actual_complete else "incomplete",
        "known_revenue_actual_usd": _money(known_revenue_actual),
        "known_expense_actual_usd": _money(known_expense_actual),
        "revenue_budget_usd": _money(revenue_budget) if budget_complete or revenue_budget != 0 else None,
        "expense_budget_usd": _money(expense_budget) if budget_complete or expense_budget != 0 else None,
        "result_actual_usd": _money(result_actual),
        "result_budget_usd": _money(result_budget),
        "complete": actual_complete and budget_complete,
        "known_actuals_are_subtotals": not actual_complete,
    }


def default_hypotheses(facts: CloseFacts) -> dict[str, str]:
    written: dict[str, str] = {}
    medicare = facts.lines["us_medicare_medicaid_revenue"]
    if medicare.relevant:
        claims_b = operations_value(facts, PAYER_MEDICARE, METRIC_CLAIMS_BUDGET)
        claims_a = operations_value(facts, PAYER_MEDICARE, METRIC_CLAIMS_ACTUAL)
        den_b = operations_value(facts, PAYER_MEDICARE, METRIC_DENIAL_BUDGET)
        den_a = operations_value(facts, PAYER_MEDICARE, METRIC_DENIAL_ACTUAL)
        if claims_b is not None and claims_a is not None and den_b is not None and den_a is not None:
            written["us_medicare_medicaid_revenue"] = (
                "Hypothesis: submitted claims were "
                f"{claims_b} in budget and {claims_a} actual, while the denial rate moved from "
                f"{den_b} to {den_a}. This is a data-backed hypothesis, not proved causality."
            )
        else:
            written["us_medicare_medicaid_revenue"] = (
                "Hypothesis unavailable: supporting operations metrics are missing or uncertain."
            )
    lab = facts.lines["us_laboratory"]
    if lab.relevant:
        support = laboratory_support(facts)
        if support is not None:
            written["us_laboratory"] = (
                "Hypothesis: observed ClearPath Labs unit price is "
                f"{support['observed_unit_price']} versus a budget-implied "
                f"{support['budget_implied_unit_price']} (unit-price variance "
                f"{support['unit_price_variance']}) from budget {support['budget']} and observed "
                f"quantity {support['observed_quantity']} tests; verified actual {support['verified_actual']} "
                f"is {support['increase']} above budget ({display_percent(Decimal(support['percent']))}). "
                f"{LAB_QUANTITY_CAVEAT}. "
                "This is a hypothesis, not proved causality."
            )
        else:
            written["us_laboratory"] = (
                "Hypothesis unavailable: laboratory supplier unit or quantity facts are missing."
            )
    return written


def _add_number(catalog: set[str], value: Decimal | int | str | None) -> None:
    if value is None:
        return
    text = str(value)
    catalog.add(text)
    if text.endswith(".0"):
        catalog.add(text[:-2])
    if "." in text:
        stripped = text.rstrip("0").rstrip(".")
        catalog.add(stripped)
    try:
        as_decimal = Decimal(text)
    except Exception:
        return
    catalog.add(str(as_decimal))
    if as_decimal == as_decimal.to_integral():
        catalog.add(str(int(as_decimal)))


def _period_tokens(facts: CloseFacts) -> set[str]:
    # Full YYYY-MM is consumed by the period matcher. Standalone year or month
    # must not enter the numeric catalog; month 10 would authorize percent 10.
    catalog = {facts.period}
    _add_number(catalog, facts.fx_rate)
    return catalog


def number_catalogs_by_line(facts: CloseFacts) -> dict[str, set[str]]:
    shared = _period_tokens(facts)
    by_line: dict[str, set[str]] = {}
    for line_id, fact in facts.lines.items():
        catalog = set(shared)
        _add_number(catalog, fact.budget)
        _add_number(catalog, fact.verified_actual)
        _add_number(catalog, fact.percent)
        _add_number(catalog, fact.amount_variance)
        if fact.percent is not None:
            # Keep the signed display (for example -10.0). Do not catalog the
            # absolute loss percentage; that would accept a reformatted 10.0%.
            display = display_percent(fact.percent).replace("%", "")
            _add_number(catalog, display)
        for item in facts.supplier_facts:
            if item.line_id == line_id:
                _add_number(catalog, item.unit_price)
                _add_number(catalog, item.quantity)
        for converted in facts.conversion_results:
            if converted.line_id == line_id:
                _add_number(catalog, converted.gbp_amount)
                _add_number(catalog, converted.usd_amount)
                _add_number(catalog, converted.rate)
        by_line[line_id] = catalog
    lab_support = laboratory_support(facts)
    if lab_support is not None:
        lab_catalog = by_line.setdefault("us_laboratory", set(shared))
        for key in (
            "observed_unit_price",
            "observed_quantity",
            "budget",
            "verified_actual",
            "budget_implied_unit_price",
            "unit_price_variance",
            "increase",
            "percent",
        ):
            _add_number(lab_catalog, lab_support.get(key))
    medicare_catalog = by_line.setdefault("us_medicare_medicaid_revenue", set(shared))
    for metric in (METRIC_CLAIMS_BUDGET, METRIC_CLAIMS_ACTUAL, METRIC_DENIAL_BUDGET, METRIC_DENIAL_ACTUAL):
        _add_number(medicare_catalog, operations_value(facts, PAYER_MEDICARE, metric))
    return by_line


def allowed_number_catalog(facts: CloseFacts) -> set[str]:
    catalog = set(_period_tokens(facts))
    for values in number_catalogs_by_line(facts).values():
        catalog |= values
    consolidated = _consolidated(facts)
    for value in consolidated.values():
        if isinstance(value, str):
            _add_number(catalog, value)
    return catalog


def known_reference_catalog(facts: CloseFacts) -> set[str]:
    refs: set[str] = {facts.digest, facts.fx_source}
    refs.update(facts.quarantined_entry_ids)
    refs.update(facts.unmapped_ingest_refs)
    refs.update(value for value in facts.file_hashes.values() if value != "missing")
    for fact in facts.lines.values():
        refs.update(fact.verified_entry_ids)
        refs.update(fact.source_refs)
        refs.update(fact.budget_row_ids)
    for row in facts.ledger_rows:
        if row.public_entry_id:
            refs.add(row.public_entry_id)
        refs.add(row.source_ref)
        refs.add(row.ingest_ref)
    for row in facts.budget_rows:
        refs.add(row.row_id)
        refs.add(row.ingest_ref)
    for row in facts.operations:
        refs.add(row.row_id)
        refs.add(row.ingest_ref)
    for item in facts.conversion_results:
        refs.update(item.source_refs)
    return {item for item in refs if item}


def evidence_sentences(facts: CloseFacts) -> dict[str, str]:
    """Short code-computed evidence the writer must copy exactly. No lab caveat here."""
    sentences: dict[str, str] = {}
    medicare = facts.lines["us_medicare_medicaid_revenue"]
    if medicare.relevant:
        claims_b = operations_value(facts, PAYER_MEDICARE, METRIC_CLAIMS_BUDGET)
        claims_a = operations_value(facts, PAYER_MEDICARE, METRIC_CLAIMS_ACTUAL)
        den_b = operations_value(facts, PAYER_MEDICARE, METRIC_DENIAL_BUDGET)
        den_a = operations_value(facts, PAYER_MEDICARE, METRIC_DENIAL_ACTUAL)
        if claims_b is not None and claims_a is not None and den_b is not None and den_a is not None:
            claims_clause = (
                f"Claims {_money(claims_a)} unchanged"
                if claims_a == claims_b
                else f"Claims actual {_money(claims_a)} from budget {_money(claims_b)}"
            )
            medicare_sentence = (
                f"{claims_clause}; denials {_money(den_b)} to {_money(den_a)}."
            )
            # Qualitative direction only. Signed amounts stay in tables, not writer prose.
            if medicare.verified_actual is not None and medicare.budget is not None:
                if medicare.verified_actual < medicare.budget:
                    direction = "Revenue below budget."
                elif medicare.verified_actual > medicare.budget:
                    direction = "Revenue above budget."
                else:
                    direction = "Revenue matches budget."
                medicare_sentence = f"{medicare_sentence} {direction}"
            sentences["us_medicare_medicaid_revenue"] = medicare_sentence
    lab = facts.lines["us_laboratory"]
    if lab.relevant:
        support = laboratory_support(facts)
        if support is not None:
            sentences["us_laboratory"] = (
                f"Observed {support['observed_unit_price']} vs budget-implied "
                f"{support['budget_implied_unit_price']}; qty {support['observed_quantity']}; "
                f"variance {support['unit_price_variance']}; increase {support['increase']}."
            )
    assert_clean_mapping(sentences)
    return sentences


def writer_projection(facts: CloseFacts) -> dict:
    relevant = [line_id for line_id, fact in facts.lines.items() if fact.relevant]
    payload = {
        "period": facts.period,
        "incomplete": facts.incomplete,
        "missing_lines": list(facts.missing_lines),
        "relevant": relevant,
        "evidence_sentence": evidence_sentences(facts),
    }
    assert_clean_mapping(payload)
    return payload


def _figure_hash(payload: dict) -> str:
    encoded = json.dumps({key: value for key, value in payload.items() if key != "hash"}, sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _ledger_contributors(facts: CloseFacts, line_id: str) -> list[dict]:
    rows = []
    for row in facts.ledger_rows:
        if row.line_id != line_id or row.uncertain or row.exclude_from_totals or row.amount is None:
            continue
        if not row.public_entry_id:
            continue
        from agents.financial_close.tools import line_actual

        rows.append(
            {
                "entry_id": row.public_entry_id,
                "value": str(line_actual(row)),
                "source_ref": row.source_ref,
            }
        )
    return rows


def _budget_contributors(facts: CloseFacts, line_id: str) -> list[dict]:
    rows = []
    for row in facts.budget_rows:
        if row.line_id != line_id or row.uncertain or row.exclude_from_totals or row.amount is None:
            continue
        rows.append(
            {
                "row_id": row.row_id,
                "value": str(row.amount),
                "ingest_ref": row.ingest_ref,
            }
        )
    return rows


def _line_ids_of_kind(kind: str) -> tuple[str, ...]:
    return tuple(line_id for line_id in LINE_IDS if LINE_SPEC[line_id][4] == kind)


def _source_figure_refs(*figure_ids: str) -> list[dict]:
    return [{"source_figure_id": figure_id} for figure_id in figure_ids]


def _line_source_figures(line_ids: tuple[str, ...], suffix: str) -> list[dict]:
    return [{"source_figure_id": f"{line_id}.{suffix}"} for line_id in line_ids]


def _actual_and_budget_refs(line_id: str) -> list[dict]:
    return _source_figure_refs(f"{line_id}.verified_actual", f"{line_id}.budget")


def build_figures(facts: CloseFacts) -> dict[str, dict]:
    figures: dict[str, dict] = {}
    for line_id, fact in facts.lines.items():
        ledger_rows = _ledger_contributors(facts, line_id)
        budget_rows = _budget_contributors(facts, line_id)
        verified = {
            "figure_id": f"{line_id}.verified_actual",
            "value": _money(fact.verified_actual),
            "currency": fact.currency,
            "formula": f"sum(verified {fact.kind} amounts for {line_id})",
            "contributing_rows": ledger_rows,
            "amount_status": _amount_status(fact),
        }
        verified["hash"] = _figure_hash(verified)
        budget = {
            "figure_id": f"{line_id}.budget",
            "value": _money(fact.budget),
            "currency": fact.currency,
            "formula": f"sum(budget amounts for {line_id})",
            "contributing_rows": budget_rows,
            "amount_status": "complete" if fact.budget is not None and not fact.missing_budget else "missing",
        }
        budget["hash"] = _figure_hash(budget)
        percent = {
            "figure_id": f"{line_id}.percent",
            "value": str(fact.percent) if fact.percent is not None else None,
            "formula": "(verified_actual - budget) / budget",
            "contributing_rows": _actual_and_budget_refs(line_id),
            "amount_status": "complete" if fact.percent is not None else "missing",
        }
        percent["hash"] = _figure_hash(percent)
        variance = {
            "figure_id": f"{line_id}.amount_variance",
            "value": _money(fact.amount_variance),
            "currency": fact.currency,
            "formula": "verified_actual - budget",
            "contributing_rows": _actual_and_budget_refs(line_id),
            "amount_status": "complete" if fact.amount_variance is not None else "missing",
        }
        variance["hash"] = _figure_hash(variance)
        known = {
            "figure_id": f"{line_id}.known_subtotal",
            "value": _money(fact.verified_actual),
            "currency": fact.currency,
            "formula": f"sum(verified amounts for {line_id}); not a complete total",
            "contributing_rows": ledger_rows,
            "amount_status": _amount_status(fact),
        }
        known["hash"] = _figure_hash(known)
        figures[f"{line_id}.verified_actual"] = verified
        figures[f"{line_id}.budget"] = budget
        figures[f"{line_id}.percent"] = percent
        figures[f"{line_id}.amount_variance"] = variance
        figures[f"{line_id}.known_subtotal"] = known
    consolidated = _consolidated(facts)
    revenue_ids = _line_ids_of_kind("revenue")
    expense_ids = _line_ids_of_kind("expense")
    # Child figure_id links carry native currency rows; consolidated values are USD at briefing FX.
    consolidated_sources = {
        "revenue_budget_usd": (
            "sum of the four revenue line budgets in native currency converted to USD at briefing FX",
            _line_source_figures(revenue_ids, "budget") + _source_figure_refs("fx.rate"),
        ),
        "expense_budget_usd": (
            "sum of the ten expense line budgets in native currency converted to USD at briefing FX",
            _line_source_figures(expense_ids, "budget") + _source_figure_refs("fx.rate"),
        ),
        "result_budget_usd": (
            "revenue_budget_usd - expense_budget_usd; GBP native amounts converted to USD at briefing FX",
            _source_figure_refs(
                "consolidated.revenue_budget_usd",
                "consolidated.expense_budget_usd",
                "fx.rate",
            ),
        ),
        "known_revenue_actual_usd": (
            "sum of verified revenue ledger actuals in native currency converted to USD at briefing FX; incomplete known subtotal",
            _line_source_figures(revenue_ids, "verified_actual") + _source_figure_refs("fx.rate"),
        ),
        "known_expense_actual_usd": (
            "sum of verified expense ledger actuals in native currency converted to USD at briefing FX; incomplete known subtotal",
            _line_source_figures(expense_ids, "verified_actual") + _source_figure_refs("fx.rate"),
        ),
    }
    for key, (formula, contributors) in consolidated_sources.items():
        figure_id = f"consolidated.{key}"
        payload = {
            "figure_id": figure_id,
            "value": consolidated.get(key),
            "currency": "USD",
            "formula": formula,
            "contributing_rows": contributors,
            "amount_status": consolidated["budget_status"] if "budget" in key else consolidated["actual_status"],
            "fx_source": facts.fx_source,
        }
        payload["hash"] = _figure_hash(payload)
        figures[figure_id] = payload
    fx = {
        "figure_id": "fx.rate",
        "value": facts.fx_rate,
        "formula": "briefing reference rate",
        "contributing_rows": [{"source": facts.fx_source}],
        "amount_status": "complete",
    }
    fx["hash"] = _figure_hash(fx)
    figures["fx.rate"] = fx
    ops_map = {
        "operations.medicare.claims_submitted_actual": (PAYER_MEDICARE, METRIC_CLAIMS_ACTUAL),
        "operations.medicare.claims_submitted_budget": (PAYER_MEDICARE, METRIC_CLAIMS_BUDGET),
        "operations.medicare.denial_rate_pct_actual": (PAYER_MEDICARE, METRIC_DENIAL_ACTUAL),
        "operations.medicare.denial_rate_pct_budget": (PAYER_MEDICARE, METRIC_DENIAL_BUDGET),
        "operations.commercial.claims_submitted_actual": (PAYER_COMMERCIAL, METRIC_CLAIMS_ACTUAL),
        "operations.commercial.claims_submitted_budget": (PAYER_COMMERCIAL, METRIC_CLAIMS_BUDGET),
        "operations.commercial.denial_rate_pct_actual": (PAYER_COMMERCIAL, METRIC_DENIAL_ACTUAL),
        "operations.commercial.denial_rate_pct_budget": (PAYER_COMMERCIAL, METRIC_DENIAL_BUDGET),
    }
    for figure_id, (payer, metric) in ops_map.items():
        value = operations_value(facts, payer, metric)
        rows = [
            {"ingest_ref": row.ingest_ref, "row_id": row.row_id, "value": str(row.value)}
            for row in facts.operations
            if row.payer == payer and row.metric == metric and not row.uncertain
        ]
        payload = {
            "figure_id": figure_id,
            "value": _money(value),
            "formula": f"operations {metric} for {payer}",
            "contributing_rows": rows,
            "amount_status": "complete" if value is not None else "missing",
        }
        payload["hash"] = _figure_hash(payload)
        figures[figure_id] = payload
    support = laboratory_support(facts)
    if support is not None:
        ledger_only = [{"source_refs": list(support.get("source_refs") or ())}]
        lab_actual_and_budget = _actual_and_budget_refs("us_laboratory")
        lab_map = {
            "us_laboratory.unit_price": (
                "observed_unit_price",
                "observed ClearPath Labs unit price",
                ledger_only,
            ),
            "us_laboratory.observed_quantity": (
                "observed_quantity",
                "sum of laboratory test quantities",
                ledger_only,
            ),
            "us_laboratory.budget_implied_unit_price": (
                "budget_implied_unit_price",
                "laboratory budget divided by observed quantity",
                lab_actual_and_budget,
            ),
            "us_laboratory.increase": (
                "increase",
                "verified laboratory actual minus budget",
                lab_actual_and_budget,
            ),
            "us_laboratory.unit_price_variance": (
                "unit_price_variance",
                "observed unit price minus budget-implied unit price",
                lab_actual_and_budget,
            ),
        }
        for figure_id, (key, formula, contributors) in lab_map.items():
            payload = {
                "figure_id": figure_id,
                "value": support.get(key),
                "formula": formula,
                "contributing_rows": contributors,
                "amount_status": "complete",
            }
            payload["hash"] = _figure_hash(payload)
            figures[figure_id] = payload
    return {key: value for key, value in figures.items() if key in ALLOWED_FIGURE_IDS}


def lookup_figure(report: dict, figure_id: str) -> dict:
    if figure_id not in ALLOWED_FIGURE_IDS:
        raise KeyError("unknown_figure")
    figures = report.get("figures") or {}
    payload = figures.get(figure_id)
    if not payload:
        raise KeyError("unknown_figure")
    return payload


def _safe_operations_row(row) -> dict:
    payload = {
        "ingest_ref": row.ingest_ref,
        "row_id": row.row_id,
        "uncertain": row.uncertain,
        "issues": list(row.issues),
    }
    if not row.uncertain and row.metric is not None and row.payer is not None:
        payload["payer"] = row.payer
        payload["metric"] = row.metric
        payload["value"] = str(row.value) if row.value is not None else None
    return payload


def _issue_entries(facts: CloseFacts) -> list[dict]:
    missing: list[dict] = []
    for filename in facts.missing_files:
        missing.append({"file": filename, "reason": "missing_source_file"})
    for line_id in facts.missing_lines:
        missing.append({"line_id": line_id, "reason": "missing_actual"})
    for entry_id in facts.quarantined_entry_ids:
        missing.append({"entry_id": entry_id, "reason": "uncertain_quarantined"})
    for ingest_ref in facts.unmapped_ingest_refs:
        missing.append({"ingest_ref": ingest_ref, "reason": "unknown_line"})
    for row in facts.ledger_rows:
        if row.issues and row.public_entry_id not in facts.quarantined_entry_ids:
            missing.append(
                {
                    "ingest_ref": row.ingest_ref,
                    "entry_id": row.public_entry_id,
                    "reason": "ledger_row_issue",
                    "issues": list(row.issues),
                }
            )
    for row in facts.budget_rows:
        if row.issues or row.uncertain:
            missing.append(
                {
                    "ingest_ref": row.ingest_ref,
                    "row_id": row.row_id,
                    "reason": "budget_row_issue",
                    "issues": list(row.issues),
                }
            )
    for row in facts.operations:
        if row.issues or row.uncertain:
            missing.append(
                {
                    "ingest_ref": row.ingest_ref,
                    "row_id": row.row_id,
                    "reason": "operations_row_issue",
                    "issues": list(row.issues),
                }
            )
    return missing


def build_report(
    facts: CloseFacts,
    *,
    hypotheses: dict[str, str] | None = None,
    summary_lines: list[str] | None = None,
    reviewer_guidance: str | None = None,
) -> dict:
    hypo = hypotheses or default_hypotheses(facts)
    for line_id, fact in facts.lines.items():
        if fact.relevant and line_id not in hypo:
            hypo[line_id] = (
                "Hypothesis unavailable: the model did not return a grounded explanation. "
                f"Verified actual {fact.verified_actual} versus budget {fact.budget}."
            )
    summary = summary_lines or [
        f"Close for {facts.period} is {'incomplete' if facts.incomplete else 'complete'}.",
        "Consolidated USD uses verified amounts only and does not treat missing software as zero.",
        "Medicare/Medicaid and US laboratory are the relevant deviations when those lines are complete.",
        "UK clinical software licences have no ledger entries.",
        "Uncertain ledger records are listed by entry_id only.",
    ]
    if len(summary) > 5:
        summary = summary[:5]
    report = {
        "period": facts.period,
        "load_date": facts.load_date,
        "catch_up": facts.catch_up,
        "incomplete": facts.incomplete,
        "facts_digest": facts.digest,
        "file_hashes": facts.file_hashes,
        "fx_rate": facts.fx_rate,
        "fx_source": facts.fx_source,
        "executive_summary": " ".join(summary),
        "consolidated_usd": _consolidated(facts),
        "revenue_by_country_payer": [
            _line_payload(fact) for fact in facts.lines.values() if fact.kind == "revenue"
        ],
        "expenses_by_country": [
            _line_payload(fact) for fact in facts.lines.values() if fact.kind != "revenue"
        ],
        "relevant_deviations": [
            {
                "line_id": line_id,
                "hypothesis": hypo[line_id],
                "percent": str(facts.lines[line_id].percent),
                "percent_display": display_percent(facts.lines[line_id].percent)
                if facts.lines[line_id].percent is not None
                else None,
                "amount_variance": _money(facts.lines[line_id].amount_variance),
                "budget": _money(facts.lines[line_id].budget),
                "verified_actual": _money(facts.lines[line_id].verified_actual),
                "entry_ids": list(facts.lines[line_id].verified_entry_ids),
                "source_refs": list(facts.lines[line_id].source_refs),
            }
            for line_id, fact in facts.lines.items()
            if fact.relevant
        ],
        "missing_or_uncertain": _issue_entries(facts),
        "operations": [_safe_operations_row(row) for row in facts.operations],
        "figures": build_figures(facts),
        "traceability": {
            "file_hashes": facts.file_hashes,
            "missing_files": list(facts.missing_files),
            "fx_source": facts.fx_source,
            "fx_rate": facts.fx_rate,
            "invoked_tools": list(facts.invoked_tools),
            "lines": {
                line_id: {
                    "figure_id": f"{line_id}.verified_actual",
                    "entry_ids": list(fact.verified_entry_ids),
                    "budget_row_ids": list(fact.budget_row_ids),
                    "source_refs": list(fact.source_refs),
                    "fx_source": facts.fx_source,
                    "amount_status": _amount_status(fact),
                }
                for line_id, fact in facts.lines.items()
            },
            "fx_conversions": [
                {
                    "line_id": item.line_id,
                    "basis": item.basis,
                    "usd_amount": item.usd_amount,
                    "source_refs": list(item.source_refs),
                }
                for item in facts.conversion_results
            ],
            "operations": [
                {
                    "ingest_ref": row.ingest_ref,
                    "row_id": row.row_id,
                    "issues": list(row.issues),
                    **(
                        {"metric": row.metric, "payer": row.payer}
                        if row.metric is not None and row.payer is not None and not row.uncertain
                        else {}
                    ),
                }
                for row in facts.operations
            ],
        },
        "reviewer_guidance": reviewer_guidance,
    }
    assert_clean_mapping(report)
    return report
