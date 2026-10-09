"""An event is judged once: history and backfills never alert, a fresh event does."""

from __future__ import annotations

from datetime import date, timedelta

from emendrix_service.notify.eligibility import FRESHNESS, Judgement, judge
from emendrix_service.notify.facts import EventFacts

LIVE = date(2026, 10, 1)


def event(detected_on: date, *in_force: date) -> EventFacts:
    return EventFacts(
        event_key="eu/32024R1689@v2",
        corpus="eu",
        act_key="32024R1689",
        from_version="v1",
        to_version="v2",
        detected_on=detected_on,
        in_force=in_force,
        url="https://example.org/acts/ai-act/v2/",
    )


def test_svc_notify_the_first_run_judges_everything_history() -> None:
    verdict = judge(event(date(2026, 10, 5)), live_since=LIVE, bootstrap=True)
    assert verdict == Judgement(eligible=False, reason="bootstrap")
    assert verdict.stored() == "bootstrap"


def test_svc_notify_an_event_detected_before_going_live_never_alerts() -> None:
    verdict = judge(event(date(2026, 9, 30)), live_since=LIVE, bootstrap=False)
    assert (verdict.eligible, verdict.reason) == (False, "before_live")
    assert judge(event(LIVE), live_since=LIVE, bootstrap=False).eligible


def test_svc_notify_stale_at_61_days_but_fresh_at_60() -> None:
    detected = date(2026, 10, 5)
    assert timedelta(days=60) == FRESHNESS
    fresh = judge(event(detected, detected - timedelta(days=60)), live_since=LIVE, bootstrap=False)
    assert fresh == Judgement(eligible=True, reason="fresh")
    stale = judge(event(detected, detected - timedelta(days=61)), live_since=LIVE, bootstrap=False)
    assert stale == Judgement(eligible=False, reason="stale_in_force", gap_days=61)
    assert stale.stored() == "stale_in_force:61"


def test_svc_notify_the_newest_in_force_date_decides() -> None:
    detected = date(2026, 10, 5)
    dates = (date(2020, 1, 1), detected - timedelta(days=10))
    assert judge(event(detected, *dates), live_since=LIVE, bootstrap=False).eligible


def test_svc_notify_an_event_with_no_in_force_date_is_fresh() -> None:
    verdict = judge(event(date(2026, 10, 5)), live_since=LIVE, bootstrap=False)
    assert verdict == Judgement(eligible=True, reason="fresh")
