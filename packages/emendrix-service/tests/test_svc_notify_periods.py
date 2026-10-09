"""Digests fall due at the configured local hour, across both clock changes."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from emendrix_service.notify.periods import (
    Period,
    daily_due,
    heartbeat_due,
    previous_month,
    weekly_due,
)

BRUSSELS = ZoneInfo("Europe/Brussels")


def at(text: str) -> datetime:
    """A Brussels wall-clock time as the UTC instant a clock would report."""
    return datetime.fromisoformat(text).replace(tzinfo=BRUSSELS).astimezone(UTC)


def test_svc_notify_daily_falls_due_at_seven_local() -> None:
    assert daily_due(at("2026-10-14T06:59"), BRUSSELS, 7) is None
    due = daily_due(at("2026-10-14T07:00"), BRUSSELS, 7)
    assert due == Period(
        kind="daily", key="2026-10-14", boundary=datetime(2026, 10, 14, 7, tzinfo=BRUSSELS)
    )
    assert due.boundary.astimezone(UTC) == datetime(2026, 10, 14, 5, tzinfo=UTC)
    late = daily_due(at("2026-10-14T23:59"), BRUSSELS, 7)
    assert late is not None and late.key == "2026-10-14"


def test_svc_notify_weekly_falls_due_on_monday_and_keeps_its_iso_week() -> None:
    assert weekly_due(at("2026-10-12T06:59"), BRUSSELS, 7) is None
    monday = weekly_due(at("2026-10-12T07:00"), BRUSSELS, 7)
    assert monday is not None and monday.key == "2026-W42"
    assert monday.boundary == datetime(2026, 10, 12, 7, tzinfo=BRUSSELS)
    # Later in the week the same period stands, so a missed Monday is caught up once.
    assert weekly_due(at("2026-10-15T12:00"), BRUSSELS, 7) == monday


def test_svc_notify_iso_week_53() -> None:
    due = weekly_due(at("2027-01-01T09:00"), BRUSSELS, 7)
    assert due is not None and due.key == "2026-W53"
    assert due.boundary == datetime(2026, 12, 28, 7, tzinfo=BRUSSELS)


def test_svc_notify_the_march_clock_change_keeps_seven_local() -> None:
    # Clocks go forward on Sunday 2026-03-29; the Monday after is 07:00 CEST, 05:00 UTC.
    assert weekly_due(datetime(2026, 3, 30, 4, 59, tzinfo=UTC), BRUSSELS, 7) is None
    due = weekly_due(datetime(2026, 3, 30, 5, 0, tzinfo=UTC), BRUSSELS, 7)
    assert due is not None and due.key == "2026-W14"
    before = daily_due(datetime(2026, 3, 28, 6, 0, tzinfo=UTC), BRUSSELS, 7)
    assert before is not None and before.boundary.astimezone(UTC).hour == 6


def test_svc_notify_the_october_clock_change_keeps_seven_local() -> None:
    # Clocks go back on Sunday 2026-10-25; the Monday after is 07:00 CET, 06:00 UTC.
    assert weekly_due(datetime(2026, 10, 26, 5, 59, tzinfo=UTC), BRUSSELS, 7) is None
    due = weekly_due(datetime(2026, 10, 26, 6, 0, tzinfo=UTC), BRUSSELS, 7)
    assert due is not None and due.key == "2026-W44"
    assert daily_due(datetime(2026, 10, 25, 5, 59, tzinfo=UTC), BRUSSELS, 7) is None
    assert daily_due(datetime(2026, 10, 25, 6, 0, tzinfo=UTC), BRUSSELS, 7) is not None


def test_svc_notify_the_monthly_note_falls_due_on_the_first_monday() -> None:
    assert heartbeat_due(at("2026-11-01T12:00"), BRUSSELS, 7) is None
    assert heartbeat_due(at("2026-11-02T06:59"), BRUSSELS, 7) is None
    due = heartbeat_due(at("2026-11-02T07:00"), BRUSSELS, 7)
    assert due == Period(
        kind="heartbeat", key="2026-11", boundary=datetime(2026, 11, 2, 7, tzinfo=BRUSSELS)
    )
    start, end = previous_month(due, BRUSSELS)
    assert (start, end) == (
        datetime(2026, 10, 1, tzinfo=BRUSSELS),
        datetime(2026, 11, 1, tzinfo=BRUSSELS),
    )
    assert heartbeat_due(at("2026-11-02T23:59"), BRUSSELS, 7) is not None
    assert heartbeat_due(at("2026-11-03T07:00"), BRUSSELS, 7) is None
    # A month that starts on a Monday has its note that day.
    assert heartbeat_due(at("2027-03-01T07:00"), BRUSSELS, 7) is not None
    january = heartbeat_due(at("2027-01-04T07:00"), BRUSSELS, 7)
    assert january is not None
    assert previous_month(january, BRUSSELS)[0] == datetime(2026, 12, 1, tzinfo=BRUSSELS)
