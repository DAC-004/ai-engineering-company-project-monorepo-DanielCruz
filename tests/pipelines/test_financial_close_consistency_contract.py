"""Supplier supporting arithmetic must reconcile before a row is verified."""
import csv
from datetime import date
import re

import pytest

from agents.financial_close.seed import write_fixtures
from agents.financial_close.tools import build_facts, laboratory_support


@pytest.mark.parametrize('field',['unit_price','quantity'])
def test_supplier_price_times_quantity_mismatch_is_uncertain(tmp_path,field):
    raw=tmp_path/'raw'
    write_fixtures(raw,date(2026,11,6))
    path=raw/'ledger.csv'
    with path.open(newline='',encoding='utf-8') as source:
        reader=csv.DictReader(source);columns=reader.fieldnames;rows=list(reader)
    target=next(row for row in rows if row['country']=='United States' and row['category']=='laboratory')
    original_amount=target['amount']
    if field=='unit_price':
        target['description']=re.sub(r'unit_price=\d+(?:\.\d+)?','unit_price=20.00',target['description'])
    else:
        target['description']=re.sub(r'quantity=(\d+)',lambda match:'quantity='+str(int(match.group(1))+1),target['description'])
    assert target['amount']==original_amount
    with path.open('w',newline='',encoding='utf-8') as output:
        writer=csv.DictWriter(output,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    facts=build_facts(raw_dir=raw,load_date=date(2026,11,6),catch_up=True)
    affected=next(row for row in facts.ledger_rows if row.public_entry_id==target['entry_id'])
    assert affected.uncertain
    assert facts.lines['us_laboratory'].incomplete
    assert target['entry_id'] not in facts.lines['us_laboratory'].verified_entry_ids
    assert laboratory_support(facts) is None
