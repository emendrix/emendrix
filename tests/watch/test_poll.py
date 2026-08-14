"""`poll_once`: idempotent under overlap, resumable after a crash, resolving exactly once.

The version inventory is stubbed, because what is under test is the bookkeeping, which is
where the production bugs of a poller live. One test runs against the real pinned feed window
so the bookkeeping is exercised on real duplication rather than on a convenient shape.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from emendrix.core import (
    ActId,
    ConsolidationPending,
    EnglishUnavailable,
    VersionDescriptor,
    VersionId,
)
from emendrix.eu.feed import fetch_notifications
from emendrix.eu.feed_atom import FeedEntry, FeedIdentifier
from emendrix.eu.http import CellarHttp
from emendrix.watch.config import WatchedAct, Watchlist
from emendrix.watch.events import PollResult, PollWindow
from emendrix.watch.poll import poll_once
from emendrix.watch.state import WatchState
from eu_pins import AI_ACT, AI_ACT_V1, AI_ACT_V2, FEED_WINDOW, MDR

TODAY = date(2026, 8, 6)
WINDOW = PollWindow(
    start=datetime(2026, 8, 5, 0, 0), end=datetime(2026, 8, 6, 0, 0), observed_on=TODAY
)
NEXT_WINDOW = PollWindow(
    start=datetime(2026, 8, 6, 0, 0), end=datetime(2026, 8, 7, 0, 0), observed_on=date(2026, 8, 7)
)

WATCHLIST = Watchlist(acts=(WatchedAct(celex=AI_ACT, name="AI Act"),))


class Versions:
    """The whole of the corpus, as the poller needs to see it: `discover_versions`."""

    def __init__(self, table: dict[str, list[VersionDescriptor]]) -> None:
        self.table = table
        self.calls = 0

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]:
        self.calls += 1
        return self.table.get(act.key, [])


def inventory(*versions: tuple[str, tuple[str, ...]], act: str = AI_ACT) -> Versions:
    """Version descriptors, oldest first, exactly as `eu/cellar.py` orders them."""
    identity = ActId(corpus="eu", key=act)
    return Versions(
        {
            act: [
                VersionDescriptor(
                    act=identity,
                    version=VersionId(name),
                    version_date=date(2026, 7, 27),
                    languages=languages,
                )
                for name, languages in versions
            ]
        }
    )


AVAILABLE = ((AI_ACT, ("ENG",)), (AI_ACT_V1, ("DEU", "FRA")), (AI_ACT_V2, ("ENG", "DEU")))
"""The AI Act as it really stands: three versions, the middle one with no English."""


def entry(identifier: str, scheme: str = "celex", *, at: str = "t1") -> FeedEntry:
    return FeedEntry(
        entry_id=f"cellar:{identifier}@{at}",
        cellar_id=f"cellar:{identifier}",
        updated_raw=at,
        notification_type="update",
        identifiers=(FeedIdentifier(scheme=scheme, value=identifier),),
    )


def poll(
    entries: tuple[FeedEntry, ...],
    versions: Versions,
    *,
    state: WatchState | None = None,
    window: PollWindow = WINDOW,
    watchlist: Watchlist = WATCHLIST,
) -> PollResult:
    return poll_once(
        entries=entries,
        watchlist=watchlist,
        state=state if state is not None else WatchState(),
        window=window,
        versions=versions,
    )


# ---------------------------------------------------------------- the happy path


def test_a_new_consolidated_version_becomes_one_event() -> None:
    result = poll((entry(AI_ACT_V2),), inventory(*AVAILABLE))
    (event,) = result.events
    assert event.ready is True
    assert (event.new_version, event.previous_version) == (AI_ACT_V2, AI_ACT_V1)
    assert event.version_date == date(2026, 7, 27)
    assert event.trigger == f"celex:{AI_ACT_V2}"
    assert result.state.last_window_end == WINDOW.end


def test_an_identifier_naming_the_act_resolves_to_its_newest_version() -> None:
    """The work record was touched and the feed did not say which version. Ask the corpus."""
    (event,) = poll((entry(AI_ACT),), inventory(*AVAILABLE)).events
    assert event.new_version == AI_ACT_V2


def test_the_first_consolidation_has_no_previous_version() -> None:
    (event,) = poll((entry(AI_ACT_V2),), inventory((AI_ACT_V2, ("ENG",)))).events
    assert (event.new_version, event.previous_version) == (AI_ACT_V2, None)


# ------------------------------------------------------------ first-class states


def test_an_amendment_with_no_consolidation_yet_is_a_pending_event_not_an_error() -> None:
    """The consolidated text lags the act that amended it, so waiting is the answer, not an
    error; `core/states.py` carries the measured lag behind `ConsolidationPending`."""
    result = poll((entry(AI_ACT_V2),), inventory((AI_ACT, ("ENG",))))
    (event,) = result.events
    assert event.ready is False
    assert isinstance(event.unavailable, ConsolidationPending)
    assert event.unavailable.observed_on == TODAY
    assert "not among the 1 versions" in event.unavailable.detail
    (waiting,) = result.state.pending
    assert (waiting.celex, waiting.version, waiting.checks) == (AI_ACT, AI_ACT_V2, 1)


def test_a_version_without_english_is_its_own_state() -> None:
    """`02024R1689-20240712` exists in eleven languages and not this one."""
    result = poll((entry(AI_ACT_V1),), inventory(*AVAILABLE))
    (event,) = result.events
    assert isinstance(event.unavailable, EnglishUnavailable)
    assert event.unavailable.available_languages == ("DEU", "FRA")
    assert result.state.pending[0].state == "english_unavailable"


# ------------------------------------------------------------------ exactly once


def test_a_pending_consolidation_resolves_on_a_later_poll_and_only_once() -> None:
    """The whole consolidation lag, in three polls: notified, still waiting, resolved once.

    `core/states.py` carries the measured lag behind `ConsolidationPending`.
    """
    first = poll((entry(AI_ACT_V2),), inventory((AI_ACT, ("ENG",))))
    assert [event.ready for event in first.events] == [False]

    # Still nothing built. Re-checked, re-recorded, not re-announced.
    second = poll((), inventory((AI_ACT, ("ENG",))), state=first.state, window=NEXT_WINDOW)
    assert second.events == ()
    assert second.stats.pending_checked == 1
    assert second.state.pending[0].checks == 2
    assert second.state.pending[0].first_seen == TODAY

    # The text appears, with no feed entry at all, because the pending list is checked first.
    third = poll((), inventory(*AVAILABLE), state=second.state, window=NEXT_WINDOW)
    (event,) = third.events
    assert (event.ready, event.new_version) == (True, AI_ACT_V2)
    assert third.stats.pending_resolved == 1
    assert third.state.pending == ()

    # And never again, however many times the feed re-announces it.
    fourth = poll((entry(AI_ACT_V2, at="t9"),), inventory(*AVAILABLE), state=third.state)
    assert fourth.events == ()
    assert fourth.stats.suppressed == 1


def test_the_same_work_notified_many_times_becomes_one_event() -> None:
    """CELLAR re-notified this consolidation 46 times on 2026-08-05, under fresh entry ids."""
    entries = tuple(entry(AI_ACT_V2, at=f"t{index}") for index in range(20))
    result = poll(entries, inventory(*AVAILABLE))
    assert len(result.events) == 1
    assert (result.stats.matched, result.stats.suppressed) == (20, 19)


def test_overlapping_windows_emit_nothing_twice() -> None:
    """Windows overlap on purpose; dedupe by entry id is what makes that free."""
    entries = (entry(AI_ACT_V2), entry(AI_ACT_V2, at="t2"))
    first = poll(entries, inventory(*AVAILABLE))
    second = poll(entries, inventory(*AVAILABLE), state=first.state, window=NEXT_WINDOW)
    assert second.events == ()
    assert second.stats.duplicates == 2
    assert second.stats.matched == 0


def test_a_run_that_died_before_saving_repeats_itself_exactly() -> None:
    """Assume the process died mid-run: the same input state and window give the same events."""
    entries = (entry(AI_ACT_V2), entry("32026R1913"))
    first = poll(entries, inventory(*AVAILABLE))
    again = poll(entries, inventory(*AVAILABLE))
    assert first.events == again.events
    assert first.state == again.state


# ------------------------------------------------------------------ the firehose


def test_a_window_with_no_hits_still_advances_the_cursor() -> None:
    """Otherwise the next run re-scans the same window forever."""
    result = poll((entry("32026R1913"), entry("62024CO0821_INF")), inventory(*AVAILABLE))
    assert result.events == ()
    assert result.stats.matched == 0
    assert result.state.last_window_end == WINDOW.end
    assert len(result.state.seen) == 2


def test_a_truncated_window_stops_the_cursor_where_the_feed_stopped() -> None:
    """~3,000 notifications a day overrun `MAX_PAGES` in eleven; the default window is fourteen.

    Advancing to the window end would step over every notification on the pages nobody fetched,
    and they are never offered again. So the caller says how far it got and the cursor stops.
    """
    covered = datetime(2026, 8, 5, 14, 30)
    result = poll_once(
        entries=(entry(AI_ACT_V2),),
        watchlist=WATCHLIST,
        state=WatchState(),
        window=WINDOW,
        versions=inventory(*AVAILABLE),
        covered_to=covered,
    )
    assert result.state.last_window_end == covered
    assert result.stats.truncated is True
    assert len(result.events) == 1  # what *was* read is still reported


def test_a_truncated_window_never_moves_the_cursor_backwards() -> None:
    """A fetch that returned nothing datable covers nothing, and re-reads the same window."""
    result = poll_once(
        entries=(),
        watchlist=WATCHLIST,
        state=WatchState(),
        window=WINDOW,
        versions=inventory(*AVAILABLE),
        covered_to=WINDOW.start - timedelta(days=3),
    )
    assert result.state.last_window_end == WINDOW.start


def test_an_empty_window_advances_the_cursor_and_costs_nothing() -> None:
    versions = inventory(*AVAILABLE)
    result = poll((), versions)
    assert (result.events, result.stats.entries) == ((), 0)
    assert result.state.last_window_end == WINDOW.end
    assert versions.calls == 0


def test_an_act_not_on_the_watchlist_is_never_looked_up() -> None:
    """The filter is string work; the network is only reached for a hit."""
    versions = inventory(*AVAILABLE, act=MDR)
    result = poll((entry("02017R0745-20260801"),), versions, watchlist=WATCHLIST)
    assert (result.events, versions.calls) == ((), 0)


def test_the_version_inventory_is_fetched_once_per_act_per_poll() -> None:
    entries = tuple(entry(AI_ACT_V2, at=f"t{index}") for index in range(10))
    versions = inventory(*AVAILABLE)
    poll(entries, versions)
    assert versions.calls == 1


def test_dropping_an_act_from_the_watchlist_stops_tracking_it() -> None:
    first = poll((entry(AI_ACT_V2),), inventory((AI_ACT, ("ENG",))))
    assert first.state.pending
    emptied = poll((), inventory(*AVAILABLE), state=first.state, watchlist=Watchlist())
    assert (emptied.events, emptied.state.pending) == ((), ())


def test_the_real_pinned_window_yields_exactly_one_event(http: CellarHttp) -> None:
    """46 real notifications, 4 of them the AI Act, one event, end to end on real bytes."""
    feed = fetch_notifications(http, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    result = poll(feed.entries, inventory(*AVAILABLE))
    (event,) = result.events
    assert (event.new_version, event.previous_version) == (AI_ACT_V2, AI_ACT_V1)
    assert result.stats.entries == len(feed.entries)
    assert result.stats.matched == 4


@pytest.mark.parametrize("scheme", ["celex", "consolidation"])
def test_both_identifier_forms_of_one_version_reach_the_same_event(scheme: str) -> None:
    value = AI_ACT_V2 if scheme == "celex" else "2024R1689/20260727"
    (event,) = poll((entry(value, scheme),), inventory(*AVAILABLE)).events
    assert event.new_version == AI_ACT_V2
