"""The fixed clock stands still until moved, and only ever forward."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from emendrix_service.clock import FixedClock, SystemClock
from tests.conftest import NOW


def test_svc_the_fixed_clock_moves_only_when_told(clock: FixedClock) -> None:
    assert clock.now() == NOW
    assert clock.monotonic() == 0.0
    clock.advance(timedelta(minutes=31))
    assert clock.now() == NOW + timedelta(minutes=31)
    assert clock.monotonic() == 31 * 60.0


def test_svc_the_fixed_clock_answers_in_utc() -> None:
    brussels = timezone(timedelta(hours=2))
    clock = FixedClock(datetime(2026, 10, 12, 7, 0, tzinfo=brussels))
    assert clock.now() == NOW
    assert clock.now().tzinfo is UTC


def test_svc_the_fixed_clock_refuses_a_naive_instant_and_going_back() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 10, 12, 5, 0))
    with pytest.raises(ValueError, match="forward"):
        FixedClock(NOW).advance(timedelta(seconds=-1))


def test_svc_the_system_clock_is_aware() -> None:
    assert SystemClock().now().tzinfo is UTC
