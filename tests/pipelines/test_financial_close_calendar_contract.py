"""Independent source-bound schedule checks; weekdays are the documented default."""
from datetime import date, datetime, timezone

import pytest

from agents.financial_close.calendar import CalendarPolicy, FrozenClock, due_instant_for_period
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.schedule import should_run


@pytest.mark.parametrize('period,expected_utc',[
    ('2026-09',datetime(2026,10,5,11,0,tzinfo=timezone.utc)),
    ('2026-10',datetime(2026,11,4,12,0,tzinfo=timezone.utc)),
])
def test_third_weekday_is_six_austin_across_dst(period,expected_utc):
    due=due_instant_for_period(period,CalendarPolicy())
    assert due.hour==6 and due.minute==0
    assert str(due.tzinfo)=='America/Chicago'
    assert due.astimezone(timezone.utc)==expected_utc


def test_only_explicit_holiday_changes_third_business_day():
    ordinary=due_instant_for_period('2026-10',CalendarPolicy())
    configured=due_instant_for_period('2026-10',CalendarPolicy(holidays=('2026-11-02',)))
    assert ordinary.date()==date(2026,11,4)
    assert configured.date()==date(2026,11,5)


@pytest.mark.parametrize('instant,expected',[
    (datetime(2026,11,4,11,59,59,tzinfo=timezone.utc),False),
    (datetime(2026,11,4,12,0,0,tzinfo=timezone.utc),True),
])
def test_schedule_does_not_run_before_exact_due_instant(tmp_path,instant,expected):
    runtime=CloseRuntime(raw=tmp_path/'raw',process=tmp_path/'process',clock=FrozenClock(instant),transport=None)
    run,catch_up,period=should_run(runtime)
    assert run is expected
    assert catch_up is False
    assert period=='2026-10'


def test_later_day_is_explicit_catch_up(tmp_path):
    runtime=CloseRuntime(raw=tmp_path/'raw',process=tmp_path/'process',clock=FrozenClock(datetime(2026,11,6,12,tzinfo=timezone.utc)),transport=None)
    assert should_run(runtime)==(True,True,'2026-10')
