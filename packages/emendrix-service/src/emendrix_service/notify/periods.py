"""When a digest falls due, in the configured zone's wall-clock time, and what period it covers.

A period has a key (`2026-10-12`, `2026-W42`, `2026-10`) and a boundary, the local instant it
fell due. A digest is due from its boundary to the end of its day or week, so a run that missed
the hour still sends the period's one email later in it; the boundary, not the run's own time,
bounds which matches it carries, so a late run sends what an on-time one would have.

Every boundary is built as a wall-clock time in the zone (`datetime(..., tzinfo=zone)`), which is
what keeps 07:00 at 07:00 across the March and October clock changes: the UTC instant moves by an
hour and the local hour does not.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Period",
    "PeriodKind",
    "daily_due",
    "heartbeat_due",
    "local",
    "previous_month",
    "weekly_due",
]

PeriodKind = Literal["daily", "weekly", "heartbeat"]


class Period(BaseModel):
    """One period whose email is due."""

    model_config = ConfigDict(frozen=True)

    kind: PeriodKind = Field(description="Which email the period is for.")
    key: str = Field(description="The period's key; with the kind it is sent at most once.")
    boundary: datetime = Field(description="The local instant it fell due, timezone-aware.")


def local(now: datetime, zone: ZoneInfo) -> datetime:
    """`now` on the zone's wall clock."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("a period is computed from a timezone-aware instant")
    return now.astimezone(zone)


def _before(now: datetime, boundary: datetime) -> bool:
    # Compared in UTC: two datetimes sharing one zone object compare on the wall clock.
    return now.astimezone(UTC) < boundary.astimezone(UTC)


def _at(day: date, hour: int, zone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=zone)


def daily_due(now: datetime, zone: ZoneInfo, hour: int) -> Period | None:
    """Today's daily period, once the local time has reached `hour`."""
    today = local(now, zone).date()
    boundary = _at(today, hour, zone)
    if _before(now, boundary):
        return None
    return Period(kind="daily", key=today.isoformat(), boundary=boundary)


def weekly_due(now: datetime, zone: ZoneInfo, hour: int) -> Period | None:
    """This ISO week's period, once its Monday has reached `hour` local time."""
    today = local(now, zone).date()
    monday = today - timedelta(days=today.weekday())
    boundary = _at(monday, hour, zone)
    if _before(now, boundary):
        return None
    year, week, _ = monday.isocalendar()
    return Period(kind="weekly", key=f"{year}-W{week:02d}", boundary=boundary)


def heartbeat_due(now: datetime, zone: ZoneInfo, hour: int) -> Period | None:
    """This month's "still watching" period, on its first Monday from `hour` to midnight.

    Unlike a digest it is not caught up later in the month: a note is worth sending on the day
    it is expected, and a watchlist that turns it on mid-month waits for the next first Monday.
    """
    today = local(now, zone).date()
    first = today.replace(day=1)
    first_monday = first + timedelta(days=(7 - first.weekday()) % 7)
    boundary = _at(first_monday, hour, zone)
    if today != first_monday or _before(now, boundary):
        return None
    return Period(kind="heartbeat", key=f"{today.year}-{today.month:02d}", boundary=boundary)


def previous_month(period: Period, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The local start of the month before `period`'s and the start of `period`'s own month."""
    month_start = local(period.boundary, zone).date().replace(day=1)
    before = (month_start - timedelta(days=1)).replace(day=1)
    return _at(before, 0, zone), _at(month_start, 0, zone)
