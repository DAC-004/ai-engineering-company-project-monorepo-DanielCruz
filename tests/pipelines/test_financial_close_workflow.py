"""Review, outbox uniqueness, jobs, and named-identity workflow. No live broker."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from agents.financial_close.agent import run_close
from agents.financial_close.calendar import FrozenClock
from agents.financial_close.distribution import distribute_approved, notify_claire_quarantine
from agents.financial_close.identity import (
    CLAIRE_EMAIL,
    DISTRIBUTION_EMAILS,
    TOM_EMAIL,
    ActorIdentity,
    ActorRejected,
    named_tom_from_actor,
    trusted_named_person,
)
from agents.financial_close.review import ReviewError, approve_draft, recover_rejected_successor, reject_draft
from agents.financial_close.runtime import CloseRuntime, reset_runtime_for_tests
from agents.financial_close.schedule import should_run, tick
from agents.financial_close.seed import write_fixtures
from agents.financial_close.store import StaleDraftError


def _tom(**overrides) -> ActorIdentity:
    payload = dict(
        user_id=uuid4().hex,
        role="supervisor",
        department_id="revenue_cycle",
        email=TOM_EMAIL,
        is_active=True,
        is_admin=False,
        can_approve=True,
    )
    payload.update(overrides)
    return ActorIdentity(**payload)


def _transport(messages):
    system = messages[0]["content"]
    if "planner" in system:
        return json.dumps({"tools": ["ingest_and_normalize", "convert_gbp_usd"]})
    return json.dumps({"hypotheses": {}, "summary": []})


def _runtime(tmp_path, *, transport=_transport) -> CloseRuntime:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    return CloseRuntime(
        raw=raw,
        process=tmp_path / "proc",
        as_of=date(2026, 11, 6),
        transport=transport,
        clock=FrozenClock(datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)),
    )


def test_named_reader_requires_active_role_and_department() -> None:
    assert trusted_named_person(_tom()) == "tom.callahan"
    assert trusted_named_person(_tom(is_active=False)) is None
    assert trusted_named_person(_tom(role="employee", can_approve=False)) is None
    assert trusted_named_person(_tom(department_id="compliance")) is None
    try:
        named_tom_from_actor(_tom(is_admin=True, role="admin", department_id="technology"))
        raise AssertionError("admin must not substitute Tom")
    except ActorRejected:
        pass


def test_distribute_approved_refuses_unapproved_draft(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)
    try:
        distribute_approved(runtime, draft)
        raise AssertionError("unapproved draft must not distribute")
    except Exception as exc:
        assert "unapproved" in str(exc)


def test_outbox_notice_keys_are_unique_and_cover_all_quarantine_ids(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)
    entry_ids = tuple(
        item["entry_id"] for item in draft["report"]["missing_or_uncertain"] if item.get("entry_id")
    )
    notify_claire_quarantine(runtime, draft["period"], int(draft["version"]), entry_ids)
    notify_claire_quarantine(runtime, draft["period"], int(draft["version"]), entry_ids)
    privacy = [row for row in runtime.store.list_outbox() if row["kind"] == "privacy_quarantine"]
    assert privacy
    keys = [row["notice_key"] for row in privacy]
    assert len(keys) == len(set(keys))
    payloads = {
        json.loads(row["payload_json"])["entry_id"] if isinstance(row["payload_json"], str) else row["payload"]["entry_id"]
        for row in privacy
    }
    assert payloads == set(entry_ids)


def test_seven_recipients_only_after_approved_persisted_version(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)
    updated = approve_draft(
        runtime,
        _tom(),
        draft_id=draft["draft_id"],
        version=int(draft["version"]),
        content_sha256=draft["content_sha256"],
        approval_nonce=draft["approval_nonce"],
    )
    reports = [row for row in runtime.store.list_outbox() if row["kind"] == "approved_report"]
    assert {row["recipient_email"] for row in reports} == set(DISTRIBUTION_EMAILS)
    assert len(reports) == 7
    persisted = runtime.store.get_draft(updated["draft_id"])
    assert persisted["state"] == "approved"


def test_reject_creates_revised_report_and_invalidates_nonce(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)
    old_nonce = draft["approval_nonce"]
    revised = reject_draft(
        runtime,
        _tom(),
        draft_id=draft["draft_id"],
        version=int(draft["version"]),
        content_sha256=draft["content_sha256"],
        approval_nonce=old_nonce,
        comments="Please emphasize the 7 percent laboratory increase.",
    )
    stored = runtime.store.get_draft(draft["draft_id"])
    assert stored["state"] == "rejected"
    assert stored["approval_nonce"] != old_nonce
    assert revised["draft_id"] != draft["draft_id"]
    assert revised["parent_version"] == draft["version"]
    assert "7" in (revised["report"].get("reviewer_guidance") or "")
    try:
        approve_draft(
            runtime,
            _tom(),
            draft_id=draft["draft_id"],
            version=int(draft["version"]),
            content_sha256=draft["content_sha256"],
            approval_nonce=old_nonce,
        )
        raise AssertionError("old nonce must not approve")
    except StaleDraftError:
        pass
    try:
        reject_draft(
            runtime,
            _tom(),
            draft_id=draft["draft_id"],
            version=int(draft["version"]),
            content_sha256=draft["content_sha256"],
            approval_nonce=stored["approval_nonce"],
            comments="Follow up with Jordan Hale.",
        )
        raise AssertionError("unsafe comments must not revise")
    except ReviewError:
        pass


def test_job_survives_runtime_restart(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    reset_runtime_for_tests(runtime)
    now = datetime.now(timezone.utc).isoformat()
    job_id = uuid4().hex
    runtime.store.save_job(
        {
            "job_id": job_id,
            "actor_email": TOM_EMAIL,
            "state": "queued",
            "created_at": now,
            "updated_at": now,
            "result": {},
        }
    )
    from app.services.financial_close_service import execute_queued_job

    execute_queued_job(job_id)
    restarted = CloseRuntime(
        raw=runtime.raw,
        process=runtime.process,
        as_of=date(2026, 11, 6),
        transport=_transport,
    )
    job = restarted.store.get_job(job_id)
    assert job["state"] == "success"
    assert job["result"]["draft_id"]
    reset_runtime_for_tests(None)


def test_source_digest_change_allows_scheduled_rerun(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    run_close(runtime, catch_up=True)
    run, _, _ = should_run(runtime)
    assert run is False
    path = runtime.raw / "operations.csv"
    text = path.read_text(encoding="utf-8").replace("22.6", "21.6")
    path.write_text(text, encoding="utf-8")
    run, catch_up, period = should_run(runtime)
    assert run is True
    assert period == "2026-10"
    result = tick(runtime)
    assert result["ran"] is True
    _ = Decimal("390308")
    _ = CLAIRE_EMAIL


def test_job_replay_does_not_create_a_second_draft(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    reset_runtime_for_tests(runtime)
    now = datetime.now(timezone.utc).isoformat()
    job_id = uuid4().hex
    runtime.store.save_job(
        {
            "job_id": job_id,
            "actor_email": TOM_EMAIL,
            "state": "queued",
            "created_at": now,
            "updated_at": now,
            "result": {},
            "period": "2026-10",
        }
    )
    from app.services.financial_close_service import execute_queued_job

    first = execute_queued_job(job_id)
    second = execute_queued_job(job_id)
    assert first["draft_id"] == second["draft_id"]
    assert len(runtime.store.list_drafts("2026-10")) == 1
    reset_runtime_for_tests(None)


def test_approval_is_refused_after_source_digest_change(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)
    path = runtime.raw / "operations.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("22.6", "21.6"), encoding="utf-8")
    try:
        approve_draft(
            runtime,
            _tom(),
            draft_id=draft["draft_id"],
            version=int(draft["version"]),
            content_sha256=draft["content_sha256"],
            approval_nonce=draft["approval_nonce"],
        )
        raise AssertionError("stale source must not remain approvable")
    except StaleDraftError:
        pass


def test_rejected_successor_is_recoverable(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)

    def updater(current: dict) -> dict:
        current["state"] = "rejected"
        current["comments"] = "Please emphasize the 7 percent laboratory increase."
        current["approval_nonce"] = "b" * 32
        return current

    runtime.store.cas_update_draft(
        draft["draft_id"],
        expected_nonce=draft["approval_nonce"],
        expected_version=int(draft["version"]),
        expected_hash=draft["content_sha256"],
        updater=updater,
    )
    first = recover_rejected_successor(runtime, _tom(), draft["draft_id"])
    second = recover_rejected_successor(runtime, _tom(), draft["draft_id"])
    assert first["parent_version"] == draft["version"]
    assert first["draft_id"] == second["draft_id"]
    assert first["state"] == "awaiting_tom"


def test_parallel_due_ticks_create_one_draft_and_unique_versions(tmp_path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from unittest.mock import patch

    from agents.financial_close import schedule

    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    process = tmp_path / "proc"
    clock = FrozenClock(datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc))
    instances = [
        CloseRuntime(raw=raw, process=process, as_of=date(2026, 11, 6), transport=_transport, clock=clock)
        for _ in range(2)
    ]
    barrier = threading.Barrier(2)
    original = schedule.should_run

    def synchronized(runtime):
        answer = original(runtime)
        barrier.wait(timeout=10)
        return answer

    with patch.object(schedule, "should_run", side_effect=synchronized), ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(schedule.tick, instances))
    drafts = instances[0].store.list_drafts("2026-10")
    awaiting = [row for row in drafts if row["state"] == "awaiting_tom"]
    assert len(awaiting) == 1
    assert len({row["version"] for row in drafts}) == len(drafts)


def test_active_same_owner_job_cannot_reenter(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    job_id = uuid4().hex
    runtime.store.save_job(
        {
            "job_id": job_id,
            "actor_email": TOM_EMAIL,
            "state": "queued",
            "created_at": now,
            "updated_at": now,
            "period": "2026-10",
            "result": {},
        }
    )
    first, _ = runtime.store.claim_job(job_id, owner="same-delivery-owner")
    second_runtime = CloseRuntime(
        raw=runtime.raw,
        process=runtime.process,
        as_of=date(2026, 11, 6),
        transport=_transport,
    )
    second, _ = second_runtime.store.claim_job(job_id, owner="same-delivery-owner")
    assert first == "claimed"
    assert second == "busy"


def test_distribute_approved_rejects_forged_unsaved_object(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    draft = run_close(runtime, catch_up=True)
    forged = dict(draft)
    forged["state"] = "approved"
    try:
        distribute_approved(runtime, forged)
        raise AssertionError("forged approved object must not distribute")
    except Exception as exc:
        assert "unapproved" in str(exc) or "unknown" in str(exc)
