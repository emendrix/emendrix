"""The one place the service reads a clock, and the fixed clock every test runs on.

Everything that depends on the time (a link's expiry, a session's slide, a digest falling due, a
retry's schedule, a rate-limit window) is handed a `Clock` rather than asking the system, so a
test can stand at any instant and step forward without sleeping. `SystemClock` holds the only
wall-clock and monotonic reads in the member; the architecture test keeps it that way.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol

__all__ = ["Clock", "FixedClock", "SystemClock"]


class Clock(Protocol):
    """Where the time comes from."""

    def now(self) -> datetime:
        """The current instant, timezone-aware, in UTC."""
        ...

    def monotonic(self) -> float:
        """Seconds on a clock that never steps backwards, for measuring intervals only."""
        ...


class SystemClock:
    """The process's own clocks."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class FixedClock:
    """A clock that stands still until it is told to move, for tests."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("a FixedClock needs a timezone-aware instant")
        self._at = at.astimezone(UTC)
        self._elapsed = 0.0

    def now(self) -> datetime:
        return self._at

    def monotonic(self) -> float:
        return self._elapsed

    def advance(self, by: timedelta) -> None:
        """Move both clocks forward by `by`. A clock that went backwards would not be monotonic."""
        if by < timedelta(0):
            raise ValueError("a clock only moves forward")
        self._at += by
        self._elapsed += by.total_seconds()
