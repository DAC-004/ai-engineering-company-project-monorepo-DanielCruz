"""Reminders and overdue routing use injectable calendar settings, not invented holidays."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from agents.onboarding_orchestrator.calendar import (
    CalendarPolicy,
    FrozenClock,
    evaluate_stage_timing,
    reminder_datetime,
    stage_deadline_datetime,
)
from agents.onboarding_orchestrator.deadline_sweep import (
    SWEEP_INTERVAL_ENV,
    SWEEP_TASK_NAME,
    OwnedDeadlineScheduler,
    celery_beat_schedule,
)
from tests.pipelines.onboarding_helpers import make_runtime, start_three


def test_injected_timezone_is_honored_including_dst() -> None:
    chicago = CalendarPolicy(timezone_name="America/Chicago", cutoff_hour=17)
    winter = stage_deadline_datetime("2026-11-09", 1, chicago)
    assert winter.tzinfo is not None
    assert winter.utcoffset() is not None
    assert winter.utcoffset().total_seconds() == -6 * 3600
    summer = stage_deadline_datetime("2026-06-01", 1, chicago)
    assert summer.utcoffset() is not None
    assert summer.utcoffset().total_seconds() == -5 * 3600
    try:
        stage_deadline_datetime("2026-11-09", 1, CalendarPolicy(timezone_name="Not/AZone"))
        raise AssertionError("unsupported timezone must be rejected")
    except ValueError as error:
        assert "unsupported_timezone" in str(error)


def test_calendar_policy_is_explicit_and_stage_one_uses_day_two(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    assert runtime.calendar.start_date_counts_as_day == 1
    assert runtime.calendar.holidays == ()
    assert runtime.calendar.cutoff_hour is None
    assert runtime.calendar.timezone_name == "UTC"
    deadline = stage_deadline_datetime("2026-11-09", 1, runtime.calendar)
    # 2026-11-09 is Monday. Day 2 with start_date_counts_as_day=1 is Tuesday.
    assert deadline.date().isoformat() == "2026-11-10"


def test_reminder_then_ordinary_overdue_escalates_to_manager(tmp_path) -> None:
    start = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    runtime = make_runtime(tmp_path, now=start)
    start_three(runtime, start.date())
    runtime.clock = FrozenClock(datetime(2026, 11, 10, 0, 30, tzinfo=timezone.utc))
    notices = runtime.process_deadlines("onb-austin")
    assert any(item["kind"] == "reminder" and item["recipient"] == "hire" for item in notices)
    runtime.process_deadlines("onb-austin")
    assert sum(1 for item in runtime.store.read()["notices"] if item["kind"] == "reminder") == 1
    runtime.clock = FrozenClock(datetime(2026, 11, 11, 1, 0, tzinfo=timezone.utc))
    later = runtime.process_deadlines("onb-austin")
    assert any(item["kind"] == "escalation" and item["recipient"] == "manager" for item in later)


def test_overdue_compliance_notifies_diane_without_bypass(tmp_path) -> None:
    from tests.pipelines.onboarding_helpers import ACTORS, complete_paperwork, submit_answers

    start = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    runtime = make_runtime(tmp_path, now=start)
    record = complete_paperwork(runtime, start_three(runtime, start.date())["onb-austin"])
    for _ in range(2):
        record = submit_answers(runtime, record, ACTORS["hire_austin"])
    assert record["current_stage"] == 4
    runtime.clock = FrozenClock(datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc))
    notices = runtime.process_deadlines("onb-austin")
    assert any(item["recipient"] == "diane" and item["template"] == "compliance_overdue_no_bypass" for item in notices)
    assert record["pending_kind"] in {"check", "compliance_approval"}
    assert runtime.current("onb-austin")["compliance_approved"] is False
    assert runtime.calendar == CalendarPolicy(
        timezone_name="UTC",
        start_date_counts_as_day=1,
        holidays=(),
        cutoff_hour=None,
        reminder_hours_before=24,
    )


def test_reminder_is_exactly_24_utc_hours_across_chicago_fallback() -> None:
    policy = CalendarPolicy(
        timezone_name="America/Chicago",
        cutoff_hour=0,
        reminder_hours_before=24,
    )
    deadline = stage_deadline_datetime("2026-10-30", 1, policy)
    assert deadline.date().isoformat() == "2026-11-02"
    reminder = reminder_datetime(deadline, policy)
    elapsed_utc_hours = (
        deadline.astimezone(timezone.utc) - reminder.astimezone(timezone.utc)
    ).total_seconds() / 3600
    assert elapsed_utc_hours == 24
    wall = deadline.replace(tzinfo=None) - timedelta(hours=24)
    wall_elapsed = (
        deadline.astimezone(timezone.utc)
        - wall.replace(tzinfo=ZoneInfo("America/Chicago")).astimezone(timezone.utc)
    ).total_seconds() / 3600
    assert wall_elapsed == 25
    too_early = evaluate_stage_timing(
        "2026-10-30",
        1,
        datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc),
        policy,
        reminder_already_sent=False,
        escalation_already_sent=False,
    )
    assert too_early.reminder_due is False
    due = evaluate_stage_timing(
        "2026-10-30",
        1,
        datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc),
        policy,
        reminder_already_sent=False,
        escalation_already_sent=False,
    )
    assert due.reminder_due is True


def test_owned_deadline_sweep_needs_no_http_and_writes_internal_outbox(tmp_path, monkeypatch) -> None:
    import urllib.request

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("http_not_authorized")),
    )
    start = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    runtime = make_runtime(tmp_path, now=start)
    start_three(runtime, start.date())
    runtime.clock = FrozenClock(datetime(2026, 11, 10, 0, 30, tzinfo=timezone.utc))
    assert celery_beat_schedule({SWEEP_INTERVAL_ENV: ""}) == {}
    configured = celery_beat_schedule({SWEEP_INTERVAL_ENV: "15"})
    assert configured["onboarding-deadline-sweep"]["task"] == SWEEP_TASK_NAME
    assert configured["onboarding-deadline-sweep"]["schedule"] == 15
    sleeps: list[float] = []
    scheduler = OwnedDeadlineScheduler(
        runtime.process_all_deadlines,
        interval_seconds=15,
        sleeper=sleeps.append,
    )
    emitted = scheduler.run_cycles(2)
    assert sleeps == [15]
    assert emitted
    assert all(item["channel"] == "internal_outbox" for item in emitted)
    outbox = runtime.outbox.lines()
    assert outbox
    assert all(item["channel"] == "internal_outbox" for item in outbox)
    assert "smtp" not in runtime.paths.outbox.read_text(encoding="utf-8").lower()
    assert "mailto" not in runtime.paths.outbox.read_text(encoding="utf-8").lower()
    disabled = OwnedDeadlineScheduler(runtime.process_all_deadlines, interval_seconds=0)
    assert disabled.enabled() is False
    assert disabled.run_once() == []
