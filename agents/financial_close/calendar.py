"""Third weekday in America/Chicago plus configurable holidays.

The briefing does not define a holiday calendar. Default is Monday–Friday.
Holidays are only those explicitly supplied; none are invented.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from agents.financial_close.constants import (
    AUSTIN_TZ,
    BUSINESS_DAY_ORDINAL,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
)


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
    timezone_name: str = AUSTIN_TZ
    weekend_days: tuple[int, ...] = (5, 6)
    holidays: tuple[str, ...] = ()
    due_hour: int = SCHEDULE_HOUR
    due_minute: int = SCHEDULE_MINUTE
    business_day_ordinal: int = BUSINESS_DAY_ORDINAL


def policy_from_env() -> CalendarPolicy:
    raw = os.environ.get("FINANCIAL_CLOSE_HOLIDAYS", "").strip()
    holidays = tuple(item.strip() for item in raw.split(",") if item.strip()) if raw else ()
    return CalendarPolicy(holidays=holidays)


def _holiday_set(policy: CalendarPolicy) -> set[date]:
    return {date.fromisoformat(item) for item in policy.holidays}


def is_business_day(day: date, policy: CalendarPolicy) -> bool:
    if day.weekday() in policy.weekend_days:
        return False
    return day not in _holiday_set(policy)


def nth_business_day(year: int, month: int, policy: CalendarPolicy) -> date:
    cursor = date(year, month, 1)
    seen = 0
    while cursor.month == month:
        if is_business_day(cursor, policy):
            seen += 1
            if seen == policy.business_day_ordinal:
                return cursor
        cursor += timedelta(days=1)
    raise ValueError("not_enough_business_days")


def closing_period_for_load_date(load_date: date) -> str:
    """Last full calendar month before the load date. Not a hardcoded October."""
    first = load_date.replace(day=1)
    prior = first - timedelta(days=1)
    return f"{prior.year:04d}-{prior.month:02d}"


def parse_period(period: str) -> tuple[int, int]:
    parsed = date.fromisoformat(f"{period}-01")
    canonical = f"{parsed.year:04d}-{parsed.month:02d}"
    if period != canonical:
        raise ValueError("invalid_period")
    return parsed.year, parsed.month


def period_to_year_month(period: str) -> tuple[int, int]:
    return parse_period(period)


def last_date_of_period(period: str) -> date:
    year, month = parse_period(period)
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def clamp_day_in_period(period: str, day: int) -> date:
    last = last_date_of_period(period)
    return date(last.year, last.month, min(max(day, 1), last.day))


def month_name(period: str) -> str:
    year, month = parse_period(period)
    return date(year, month, 1).strftime("%B")


def due_instant_for_period(period: str, policy: CalendarPolicy) -> datetime:
    year, month = period_to_year_month(period)
    if month == 12:
        due_month = date(year + 1, 1, 1)
    else:
        due_month = date(year, month + 1, 1)
    due_day = nth_business_day(due_month.year, due_month.month, policy)
    zone = ZoneInfo(policy.timezone_name)
    return datetime.combine(due_day, time(policy.due_hour, policy.due_minute), tzinfo=zone)


def austin_now(clock: Clock, policy: CalendarPolicy) -> datetime:
    instant = clock.now()
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(ZoneInfo(policy.timezone_name))
