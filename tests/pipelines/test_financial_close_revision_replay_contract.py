from datetime import date
import sqlite3
import pytest
from agents.financial_close.agent import run_close
from agents.financial_close.identity import ActorIdentity, TOM_EMAIL
from agents.financial_close.review import approve_draft, reject_draft
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.seed import write_fixtures

@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("legacy_pointer", [False, True])
def test_reopened_replay_uses_latest_matching_revision(tmp_path, approved, legacy_pointer):
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    runtime = CloseRuntime(raw=raw, process=tmp_path / "process", as_of=date(2026, 11, 6), transport=None)
    actor = ActorIdentity(user_id="fixture-tom", role="supervisor", department_id="revenue_cycle", email=TOM_EMAIL, can_approve=True)
    first = run_close(runtime, catch_up=True)
    identity = {key: first[key] for key in ("draft_id", "version", "content_sha256", "approval_nonce")}
    second = reject_draft(runtime, actor, **identity, comments="Explain denials and supplier prices.")
    if approved:
        identity = {key: second[key] for key in ("draft_id", "version", "content_sha256", "approval_nonce")}
        second = approve_draft(runtime, actor, **identity)
    if legacy_pointer:
        with sqlite3.connect(runtime.store.path) as connection:
            connection.execute("UPDATE run_claims SET draft_id=?", (first["draft_id"],))
    reopened = CloseRuntime(raw=raw, process=tmp_path / "process", as_of=date(2026, 11, 6), transport=None)
    replay = run_close(reopened, catch_up=True)
    assert replay["draft_id"] == second["draft_id"]
    assert replay["version"] == 2
    assert replay["state"] == ("approved" if approved else "awaiting_tom")
    assert len(reopened.store.list_drafts()) == 2
    assert len([row for row in reopened.store.list_outbox() if row["kind"] == "approved_report"]) == (7 if approved else 0)
