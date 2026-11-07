"""Current Task 5 source-requirement counterexamples."""
from datetime import date
from agents.financial_close.seed import write_fixtures
from agents.financial_close.tools import build_facts
from agents.financial_close.serialize import build_report

def test_review_summary_does_not_invent_missing_software_when_ledger_file_absent(tmp_path):
    write_fixtures(tmp_path,date(2026,11,6))
    (tmp_path/'ledger.csv').unlink()
    facts=build_facts(raw_dir=tmp_path,load_date=date(2026,11,6),catch_up=False)
    summary=build_report(facts)['executive_summary']
    assert 'ledger.csv' in summary
    assert 'Medicare/Medicaid and US laboratory are the relevant deviations' not in summary

def test_review_all_three_feature_schedules_survive_financial_close_enable(tmp_path):
    import os,sys,subprocess,json
    env=dict(os.environ,CELERY_TASK_ALWAYS_EAGER='1',ONBOARDING_DEADLINE_SWEEP_INTERVAL_SECONDS='60',SUPPLIER_CONTRACTS_ALERT_INTERVAL_SECONDS='60',FINANCIAL_CLOSE_BEAT_SECONDS='60')
    code='import json;from app.celery_app import celery_app;print(json.dumps({"schedule":list(celery_app.conf.beat_schedule),"imports":list(celery_app.conf.imports)}))'
    completed=subprocess.run([sys.executable,'-B','-c',code],cwd=tmp_path,env=env,capture_output=True,text=True,check=True)
    got=json.loads(completed.stdout.strip())
    assert {'onboarding-deadline-sweep','supplier-contract-alerts','financial-close-sweep'} <= set(got['schedule'])
    assert {'app.onboarding_tasks','app.tasks_supplier_contracts','app.tasks_financial_close'} <= set(got['imports'])



def test_review_tom_receives_each_draft_before_distribution_and_replay_is_idempotent(tmp_path):
    import json
    from agents.financial_close.runtime import CloseRuntime
    from agents.financial_close.agent import run_close
    from agents.financial_close.review import reject_draft
    from agents.financial_close.identity import ActorIdentity,TOM_EMAIL
    write_fixtures(tmp_path/'raw',date(2026,11,6))
    runtime=CloseRuntime(raw=tmp_path/'raw',process=tmp_path/'process',as_of=date(2026,11,6),transport=None)
    draft=run_close(runtime)
    assert run_close(runtime)['draft_id']==draft['draft_id']
    notices=runtime.store.list_outbox()
    reviews=[n for n in notices if n['kind']=='review_request']
    assert len(reviews)==1 and reviews[0]['recipient_email']==TOM_EMAIL
    assert json.loads(reviews[0]['payload_json'])=={'draft_id':draft['draft_id'],'content_sha256':draft['content_sha256']}
    assert not any(n['kind']=='approved_report' for n in notices)
    actor=ActorIdentity(user_id='fixture-tom',role='supervisor',department_id='revenue_cycle',email=TOM_EMAIL,can_approve=True)
    revised=reject_draft(runtime,actor,draft_id=draft['draft_id'],version=draft['version'],content_sha256=draft['content_sha256'],approval_nonce=draft['approval_nonce'],comments='Please emphasize the laboratory price increase.')
    reviews=[n for n in runtime.store.list_outbox() if n['kind']=='review_request']
    assert [n['version'] for n in reviews]==[1,2]
    assert all(n['recipient_email']==TOM_EMAIL for n in reviews)
    assert json.loads(reviews[1]['payload_json'])['draft_id']==revised['draft_id']

def test_review_notice_failure_rolls_back_new_draft(tmp_path,monkeypatch):
    import pytest
    from agents.financial_close.runtime import CloseRuntime
    from agents.financial_close.agent import run_close
    write_fixtures(tmp_path/'raw',date(2026,11,6))
    runtime=CloseRuntime(raw=tmp_path/'raw',process=tmp_path/'process',as_of=date(2026,11,6),transport=None)
    def fail(conn,item):raise RuntimeError('synthetic_notice_failure')
    monkeypatch.setattr(runtime.store,'_insert_outbox',fail)
    with pytest.raises(RuntimeError,match='synthetic_notice_failure'):run_close(runtime)
    assert runtime.store.list_drafts()==[] and runtime.store.list_outbox()==[]
