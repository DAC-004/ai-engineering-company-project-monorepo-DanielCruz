"""Derived figures must identify their producing records, not generic line lists."""
from datetime import date

import pytest

from agents.financial_close.seed import write_fixtures
from agents.financial_close.serialize import build_report, default_hypotheses
from agents.financial_close.tools import CalculationToolbox, ALLOWED_TOOLS

REVENUE={'us_commercial_revenue','us_medicare_medicaid_revenue','uk_private_revenue','uk_nhs_revenue'}
EXPENSE={'us_consumables','us_laboratory','us_interpreting','us_payroll','us_rent','uk_consumables','uk_laboratory','uk_payroll','uk_rent','uk_software'}

def _fixture(tmp_path):
    raw=tmp_path/'raw';write_fixtures(raw,date(2026,11,6))
    facts=CalculationToolbox(raw_dir=raw,load_date=date(2026,11,6),catch_up=True).invoke(list(ALLOWED_TOOLS))
    return facts,build_report(facts,hypotheses=default_hypotheses(facts))

def _source_roots(facts,report,figure_id):
    aliases={}
    for row in facts.ledger_rows:
        if not row.uncertain and not row.exclude_from_totals and row.public_entry_id:
            aliases[row.public_entry_id]=row.public_entry_id
            aliases[row.source_ref]=row.public_entry_id
    for row in [*facts.budget_rows,*facts.operations]:
        if not row.uncertain and not row.exclude_from_totals:
            aliases[row.row_id]=row.row_id
    figures=report['figures']
    def resolve(current,ancestors):
        assert current not in ancestors,'traceability contains a cycle'
        assert current in figures,'traceability references an unknown figure'
        result=set()
        def walk(node):
            if isinstance(node,list):
                for child in node:walk(child)
            elif isinstance(node,dict):
                for key,value in node.items():
                    if key in {'figure_id','source_figure_id'} and isinstance(value,str):
                        result.update(resolve(value,ancestors|{current}))
                    elif key in {'figure_ids','source_figure_ids'} and isinstance(value,list):
                        for ref in value:result.update(resolve(ref,ancestors|{current}))
                    elif key in {'entry_id','public_entry_id','row_id','source_ref'} and isinstance(value,str):
                        if value in aliases:result.add(aliases[value])
                    elif key in {'entry_ids','budget_row_ids','source_refs'} and isinstance(value,list):
                        result.update(aliases[ref] for ref in value if ref in aliases)
                    elif isinstance(value,(list,dict)):
                        walk(value)
        walk(figures[current].get('contributing_rows',[]))
        return result
    return resolve(figure_id,set())

@pytest.mark.parametrize('figure_id,line_ids,basis',[
    ('consolidated.revenue_budget_usd',REVENUE,'budget'),
    ('consolidated.expense_budget_usd',EXPENSE,'budget'),
    ('consolidated.result_budget_usd',REVENUE|EXPENSE,'budget'),
    ('consolidated.known_revenue_actual_usd',REVENUE,'actual'),
    ('consolidated.known_expense_actual_usd',EXPENSE,'actual'),
])
def test_consolidated_figure_resolves_only_its_producing_sources(tmp_path,figure_id,line_ids,basis):
    facts,report=_fixture(tmp_path)
    expected={ref for line in line_ids for ref in (facts.lines[line].budget_row_ids if basis=='budget' else facts.lines[line].verified_entry_ids)}
    assert expected
    assert _source_roots(facts,report,figure_id)==expected
    assert report['figures'][figure_id]['fx_source']==facts.fx_source

@pytest.mark.parametrize('figure_id',[
    'us_laboratory.percent','us_laboratory.amount_variance',
    'us_laboratory.budget_implied_unit_price','us_laboratory.increase',
])
def test_laboratory_derived_figures_resolve_both_ledger_and_budget(tmp_path,figure_id):
    facts,report=_fixture(tmp_path)
    line=facts.lines['us_laboratory']
    expected=set(line.verified_entry_ids)|set(line.budget_row_ids)
    assert _source_roots(facts,report,figure_id)==expected
