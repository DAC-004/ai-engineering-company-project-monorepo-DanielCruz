"""Business-day helpers with explicit injectable policy.

Source specifies a 10-business-day target, stage day numbers, and a 24-hour
reminder. It does not specify holidays, timezone, cutoff hour, or whether the
start date counts as Day 1. Those stay on CalendarPolicy so tests inject them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agents.onboarding_orchestrator.state import STAGE_DEADLINE_DAY


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class FrozenClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


@dataclass(frozen=True)
class CalendarPolicy:
    """Fixture-settable calendar. Do not treat defaults as real HealthCore HR policy."""

    timezone_name: str = "UTC"
    start_date_counts_as_day: int = 1
    weekend_days: tuple[int, ...] = (5, 6)
    holidays: tuple[str, ...] = ()
    cutoff_hour: int | None = None
    reminder_hours_before: int = 24


@dataclass
class DeadlineStatus:
    stage: int
    deadline_at: datetime
    reminder_at: datetime
    hours_until_deadline: float
    reminder_due: bool
    overdue: bool


def _as_utc_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value[:10])


def _holiday_set(policy: CalendarPolicy) -> set[date]:
    return {date.fromisoformat(item) for item in policy.holidays}


def is_business_day(day: date, policy: CalendarPolicy) -> bool:
    if day.weekday() in policy.weekend_days:
        return False
    return day not in _holiday_set(policy)


def shift_business_days(start: date, delta: int, policy: CalendarPolicy) -> date:
    """Move `delta` business days. delta=0 returns start if it is a business day."""
    if delta == 0:
        cursor = start
        while not is_business_day(cursor, policy):
            cursor += timedelta(days=1)
        return cursor
    step = 1 if delta > 0 else -1
    remaining = abs(delta)
    cursor = start
    while remaining:
        cursor += timedelta(days=step)
        if is_business_day(cursor, policy):
            remaining -= 1
    return cursor


def zone_for_policy(policy: CalendarPolicy) -> ZoneInfo:
    """Honor the injected timezone, including DST. Reject unknown zone names."""
    try:
        return ZoneInfo(policy.timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unsupported_timezone:{policy.timezone_name}") from error
    except Exception as error:
        raise ValueError(f"unsupported_timezone:{policy.timezone_name}") from error


def _as_utc_instant(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def stage_deadline_datetime(
    start_date: date | datetime | str,
    stage: int,
    policy: CalendarPolicy,
) -> datetime:
    """Deadline for a stage day number. Day numbering follows start_date_counts_as_day."""
    start = _as_utc_date(start_date)
    target_day = STAGE_DEADLINE_DAY[stage]
    offset = target_day - policy.start_date_counts_as_day
    deadline_day = shift_business_days(start, offset, policy)
    hour = 23 if policy.cutoff_hour is None else policy.cutoff_hour
    minute = 59 if policy.cutoff_hour is None else 0
    zone = zone_for_policy(policy)
    return datetime.combine(deadline_day, time(hour, minute), tzinfo=zone)


def reminder_datetime(deadline_at: datetime, policy: CalendarPolicy) -> datetime:
    """Subtract reminder hours on the UTC instant, then convert back to the policy zone.

    Same-tzinfo wall subtraction skips DST (Chicago fallback makes 24 wall hours
    equal 25 UTC hours). Elapsed reminder time is 24 UTC hours.
    """
    zone = zone_for_policy(policy)
    deadline_utc = _as_utc_instant(deadline_at)
    reminder_utc = deadline_utc - timedelta(hours=policy.reminder_hours_before)
    return reminder_utc.astimezone(zone)


def evaluate_stage_timing(
    start_date: date | datetime | str,
    stage: int,
    now: datetime,
    policy: CalendarPolicy,
    *,
    reminder_already_sent: bool,
    escalation_already_sent: bool,
) -> DeadlineStatus:
    deadline_at = stage_deadline_datetime(start_date, stage, policy)
    reminder_at = reminder_datetime(deadline_at, policy)
    now_utc = _as_utc_instant(now)
    deadline_utc = _as_utc_instant(deadline_at)
    reminder_utc = _as_utc_instant(reminder_at)
    hours_until = (deadline_utc - now_utc).total_seconds() / 3600
    overdue = now_utc > deadline_utc and not escalation_already_sent
    reminder_due = (
        now_utc >= reminder_utc
        and now_utc <= deadline_utc
        and not reminder_already_sent
        and not escalation_already_sent
    )
    return DeadlineStatus(
        stage=stage,
        deadline_at=deadline_at,
        reminder_at=reminder_at,
        hours_until_deadline=hours_until,
        reminder_due=reminder_due,
        overdue=now_utc > deadline_utc,
    )
