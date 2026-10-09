"""Which backup copies are kept: seven daily and four weekly, across month and year boundaries."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from emendrix_service.ops.retain import backup_name, dated, keep, prunable


def every_day(start: date, days: int) -> list[str]:
    return [backup_name(start + timedelta(days=offset)) for offset in range(days)]


def days_of(names: set[str] | list[str]) -> list[date]:
    found = [dated(name) for name in names]
    return sorted(day for day in found if day is not None)


def test_svc_ops_retain_names_round_trip() -> None:
    assert backup_name(date(2026, 1, 5)) == "emendrix-app-20260105.dump.age"
    assert dated("emendrix-app-20260105.dump.age") == date(2026, 1, 5)
    for foreign in (
        "emendrix-app-20261305.dump.age",
        "emendrix-app-20260105.dump.age.part",
        "emendrix-app-2026015.dump.age",
        "notes.txt",
        "emendrix-app-20260105.dump",
    ):
        assert dated(foreign) is None


@pytest.mark.parametrize(
    ("today", "daily", "weekly"),
    [
        # A Wednesday in mid-month: the last seven days, and the Mondays of four earlier weeks.
        (
            date(2026, 10, 14),
            [date(2026, 10, 8) + timedelta(days=n) for n in range(7)],
            [date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28), date(2026, 10, 5)],
        ),
        # A Sunday across a year boundary: the oldest weekly copy is 34 days old.
        (
            date(2026, 1, 4),
            [date(2025, 12, 29) + timedelta(days=n) for n in range(7)],
            [date(2025, 12, 1), date(2025, 12, 8), date(2025, 12, 15), date(2025, 12, 22)],
        ),
        # A Monday on the first of a month: today opens a week of its own.
        (
            date(2026, 6, 1),
            [date(2026, 5, 26) + timedelta(days=n) for n in range(7)],
            [date(2026, 5, 4), date(2026, 5, 11), date(2026, 5, 18), date(2026, 5, 25)],
        ),
    ],
)
def test_svc_ops_retain_keeps_seven_daily_and_four_weekly(
    today: date, daily: list[date], weekly: list[date]
) -> None:
    names = every_day(today - timedelta(days=90), 91)
    kept = keep(names, today)
    assert days_of(kept) == sorted(set(daily) | set(weekly))
    assert (today - min(days_of(kept))).days <= 35
    assert set(prunable(names, today)) == set(names) - kept


def test_svc_ops_retain_a_missing_monday_keeps_the_earliest_of_its_week() -> None:
    today = date(2026, 10, 14)
    names = [
        backup_name(date(2026, 9, 16)),
        backup_name(date(2026, 9, 18)),
        backup_name(date(2026, 9, 7)),
    ]
    assert keep(names, today) == {backup_name(date(2026, 9, 16))}
    assert prunable(names, today) == [
        backup_name(date(2026, 9, 7)),
        backup_name(date(2026, 9, 18)),
    ]


def test_svc_ops_retain_never_prunes_a_foreign_name_or_a_future_copy() -> None:
    today = date(2026, 10, 14)
    names = ["README", "emendrix-app-20261014.dump.age.part", backup_name(date(2026, 10, 20))]
    assert prunable(names, today) == []
    assert keep(names, today) == {backup_name(date(2026, 10, 20))}


def test_svc_ops_retain_nothing_older_than_35_days_survives_any_day_of_a_year() -> None:
    start = date(2025, 11, 1)
    for offset in range(400):
        today = start + timedelta(days=offset)
        names = every_day(today - timedelta(days=60), 61)
        oldest = min(days_of(keep(names, today)))
        assert (today - oldest).days <= 35, today
        assert backup_name(today) in keep(names, today)


def test_svc_ops_retain_prunes_a_partial_upload_of_an_earlier_day() -> None:
    today = date(2026, 10, 14)
    stale = backup_name(date(2026, 10, 13)) + ".part"
    fresh = backup_name(today) + ".part"
    assert prunable([stale, fresh, "notes.part"], today) == [stale]
