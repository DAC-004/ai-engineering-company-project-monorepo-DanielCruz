"""Independent Task 5 briefing contracts. Pure tools; no app/model/broker."""
import csv
from datetime import date
from decimal import Decimal

import pytest

from agents.financial_close.ingest import ingest_ledger
from agents.financial_close.money import is_relevant, percentage_deviation
from agents.financial_close.seed import write_fixtures
from agents.financial_close.tools import build_facts


def _read(path):
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def _write(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path):
    raw = tmp_path/'raw'
    write_fixtures(raw, load_date=date(2026, 11, 6))
    return raw


def test_briefing_raw_actuals_are_exact(tmp_path):
    raw = _fixture(tmp_path)
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    expected = {
        'us_commercial_revenue':'1120000', 'us_medicare_medicaid_revenue':'468000',
        'uk_private_revenue':'271000', 'uk_nhs_revenue':'75000',
        'us_consumables':'46816', 'us_laboratory':'48150', 'us_interpreting':'17550',
        'us_payroll':'1060000', 'us_rent':'180000', 'uk_consumables':'9450',
        'uk_laboratory':'10353', 'uk_payroll':'209000', 'uk_rent':'52000',
    }
    assert all(facts.lines[key].raw_actual == Decimal(value) for key, value in expected.items())


def test_missing_software_is_not_zero_or_negative_hundred_percent(tmp_path):
    facts = build_facts(raw_dir=_fixture(tmp_path), load_date=date(2026, 11, 6), catch_up=True)
    line = facts.lines['uk_software']
    assert line.verified_actual is None
    assert line.percent is None
    assert line.missing_actual and line.incomplete


def test_quarantined_expense_is_not_a_verified_total(tmp_path):
    facts = build_facts(raw_dir=_fixture(tmp_path), load_date=date(2026, 11, 6), catch_up=True)
    rent = facts.lines['us_rent']
    assert rent.verified_actual == Decimal('179000')
    assert rent.incomplete and rent.percent is None
    assert len(facts.quarantined_entry_ids) == 1


def test_exact_required_deviations_without_rounding_false_positives(tmp_path):
    facts = build_facts(raw_dir=_fixture(tmp_path), load_date=date(2026, 11, 6), catch_up=True)
    assert {key for key, value in facts.lines.items() if value.relevant} == {'us_medicare_medicaid_revenue', 'us_laboratory'}
    assert facts.lines['us_medicare_medicaid_revenue'].percent == Decimal('-0.1')
    assert facts.lines['us_laboratory'].percent == Decimal('0.07')


@pytest.mark.parametrize('actual,budget,expected', [('105','100',True),('95','100',True),('104.999','100',False),('95.001','100',False)])
def test_inclusive_favorable_and_unfavorable_threshold(actual, budget, expected):
    assert is_relevant(percentage_deviation(Decimal(actual), Decimal(budget))) is expected


def test_zero_budget_has_no_invented_percentage():
    assert percentage_deviation(Decimal('100'), Decimal('0')) is None


@pytest.mark.parametrize('load,period', [(date(2027,1,6),'2026-12'),(date(2024,3,1),'2024-02')])
def test_generated_period_tracks_load_date_and_valid_calendar(tmp_path, load, period):
    write_fixtures(tmp_path, load_date=load)
    _, rows = _read(tmp_path/'ledger.csv')
    assert all(date.fromisoformat(row['date']).strftime('%Y-%m') == period for row in rows)
    assert all(row['entry_id'].startswith('LED-'+period.replace('-','')+'-') for row in rows)
    for filename in ['budget.csv','operations.csv']:
        _, rows = _read(tmp_path/filename)
        assert rows and all(row['month'] == period for row in rows)


def test_operations_change_invalidates_report_input_identity(tmp_path):
    raw = _fixture(tmp_path)
    before = build_facts(raw_dir=raw, load_date=date(2026,11,6), catch_up=True)
    path = raw/'operations.csv'
    fields, rows = _read(path)
    for row in rows:
        if row['metric'] == 'denial_rate_pct_actual' and row['payer'] == 'Medicare / Medicaid':
            row['value'] = '21.6'
    _write(path, fields, rows)
    after = build_facts(raw_dir=raw, load_date=date(2026,11,6), catch_up=True)
    assert before.digest != after.digest


def test_malformed_amount_is_retained_as_uncertain_row(tmp_path):
    raw = _fixture(tmp_path)
    path = raw/'ledger.csv'
    fields, rows = _read(path)
    target_id = rows[0]['entry_id']
    rows[0]['amount'] = 'invalid'
    _write(path, fields, rows)
    parsed = ingest_ledger(path, '2026-10')
    target = [row for row in parsed if row.public_entry_id == target_id]
    assert len(target) == 1
    assert target[0].uncertain and target[0].amount is None
    assert 'malformed_amount' in target[0].issues


def test_all_duplicate_id_occurrences_are_excluded(tmp_path):
    raw = _fixture(tmp_path)
    path = raw/'ledger.csv'
    fields, rows = _read(path)
    rows[1]['entry_id'] = rows[0]['entry_id']
    target_id = rows[0]['entry_id']
    _write(path, fields, rows)
    duplicates = [row for row in ingest_ledger(path,'2026-10') if row.public_entry_id == target_id]
    assert len(duplicates) == 2
    assert all(row.uncertain and row.exclude_from_totals for row in duplicates)


@pytest.mark.parametrize('column,value,issue', [('date','2026-10-2','invalid_date'),('currency','GBP','currency_country_mismatch'),('amount','-1','unexpected_sign')])
def test_inconsistent_rows_are_not_valid_financial_input(tmp_path, column, value, issue):
    raw = _fixture(tmp_path)
    path = raw/'ledger.csv'
    fields, rows = _read(path)
    rows[0][column] = value
    _write(path, fields, rows)
    target = ingest_ledger(path,'2026-10')[0]
    assert target.uncertain and issue in target.issues


def test_unsafe_source_reference_is_replaced_not_echoed(tmp_path):
    raw = _fixture(tmp_path)
    path = raw/'ledger.csv'
    fields, rows = _read(path)
    rows[0]['source_ref'] = 'patient confidential record'
    _write(path, fields, rows)
    target = ingest_ledger(path,'2026-10')[0]
    assert target.source_ref == 'ledger.csv:1'
    assert target.uncertain and 'invalid_source_ref' in target.issues


def test_canonical_report_retains_budget_and_real_source_lookup(tmp_path):
    from agents.financial_close.serialize import build_report, lookup_figure
    facts = build_facts(raw_dir=_fixture(tmp_path),load_date=date(2026,11,6),catch_up=True)
    report = build_report(facts)
    assert report['incomplete']
    assert report['consolidated_usd']['result_actual_usd'] is None
    assert Decimal(report['consolidated_usd']['result_budget_usd']) == Decimal('390308')
    assert all('raw_actual' not in row for row in report['expenses_by_country'])
    figure = lookup_figure(report,'us_laboratory.verified_actual')
    assert Decimal(figure['value']) == Decimal('48150')
    assert len(figure['contributing_rows']) == 2
    with pytest.raises(KeyError):
        lookup_figure(report,'us_laboratory.unsourced_suffix')


def test_uncertain_operation_produces_report_without_echoing_raw_metadata(tmp_path):
    import json
    from agents.financial_close.serialize import build_report
    raw = _fixture(tmp_path)
    path = raw/'operations.csv'
    fields, rows = _read(path)
    rows[0]['metric'] = 'unknown_metric_text'
    _write(path,fields,rows)
    report = build_report(build_facts(raw_dir=raw,load_date=date(2026,11,6),catch_up=True))
    assert report['incomplete']
    assert any(item.get('reason') == 'operations_row_issue' for item in report['missing_or_uncertain'])
    assert 'unknown_metric_text' not in json.dumps(report)
