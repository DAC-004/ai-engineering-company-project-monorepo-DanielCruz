"""Independent interrupted-approval delivery contract in owned SQLite storage."""
from datetime import date
import json
import sqlite3
from uuid import uuid4

from agents.financial_close.agent import run_close
from agents.financial_close.identity import ActorIdentity, DISTRIBUTION_EMAILS, TOM_EMAIL
from agents.financial_close.review import approve_draft
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.seed import write_fixtures


def test_interrupted_distribution_can_retry_same_approval_without_partial_delivery(tmp_path):
    raw=tmp_path/'raw'
    write_fixtures(raw,date(2026,11,6))
    def transport(messages):
        return json.dumps({'tools':['ingest_and_normalize']} if 'planner' in messages[0]['content'] else {'hypotheses':{},'summary':[]})
    runtime=CloseRuntime(raw=raw,process=tmp_path/'process',as_of=date(2026,11,6),transport=transport)
    draft=run_close(runtime,catch_up=True)
    actor=ActorIdentity(user_id=uuid4().hex,role='supervisor',department_id='revenue_cycle',email=TOM_EMAIL,is_active=True,is_admin=False,can_approve=True)
    request=dict(draft_id=draft['draft_id'],version=draft['version'],content_sha256=draft['content_sha256'],approval_nonce=draft['approval_nonce'])
    # This fault applies to the real durable insert boundary, including bulk
    # inserts, rather than mocking an implementation-specific helper method.
    with sqlite3.connect(runtime.store.path) as connection:
        connection.executescript("""
        CREATE TRIGGER task5_test_interrupt_fourth_report
        BEFORE INSERT ON outbox
        WHEN NEW.kind='approved_report'
          AND (SELECT COUNT(*) FROM outbox WHERE kind='approved_report')=3
        BEGIN
          SELECT RAISE(ABORT,'synthetic_distribution_interruption');
        END;
        """)
    interrupted=False
    try:
        approve_draft(runtime,actor,**request)
    except Exception:
        interrupted=True
    finally:
        with sqlite3.connect(runtime.store.path) as connection:
            connection.execute('DROP TRIGGER task5_test_interrupt_fourth_report')
    assert interrupted, 'the synthetic durable-write fault must be exercised'
    # Either the first attempt rolled back approval, or replay resumes its
    # already-approved version. The original request must remain recoverable.
    approved=approve_draft(runtime,actor,**request)
    assert approved['state']=='approved'
    reports=[row for row in runtime.store.list_outbox() if row['kind']=='approved_report']
    assert len(reports)==7
    assert {row['recipient_email'] for row in reports}==set(DISTRIBUTION_EMAILS)
    assert len({row['notice_key'] for row in reports})==7
    for row in reports:
        payload=json.loads(row['payload_json'])
        assert payload['draft_id']==draft['draft_id']
        assert payload['content_sha256']==draft['content_sha256']
