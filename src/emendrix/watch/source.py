"""One poll of the notification feed, end to end — the WATCH stage as a callable seam.

Two commands need this and they must not drift: `emendrix watch --once`, which polls and
prints, and `emendrix run --once`, whose graph polls and then diffs what came back. So the
sequence (read the persisted state, fetch the window, resolve entries against the watchlist,
write the state back) lives here once, and both composition roots call it.

It is deliberately the *whole* poll including persistence. A source that fetched but did not
save would let a crash between the poll and the diff re-notify the same amendment forever, and
a source that saved somewhere else would give the two commands two different cursors over one
feed. Idempotence is a property of the pair, so the pair stays together.

`FeedWatchSource.poll` satisfies `graph.WatchSource` structurally, and nothing in `graph/`
imports this module: the composition root hands one over, and the loop runs just as well over a
test double that answers from a list.

**No clock read.** The window arrives as a value. `window_start` computes where a window
*would* begin from the flags and the persisted cursor, and even that takes `end` as an argument:
`watch/cli.py` and `graph/cli.py` are the two places allowed to ask what day it is.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.feed import DEFAULT_CHANNEL, FeedResult, fetch_notifications
from emendrix.watch.config import Watchlist
from emendrix.watch.events import PollResult, PollWindow
from emendrix.watch.poll import poll_once
from emendrix.watch.state import StateLoad, WatchState, load_state, save_state

__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "OVERLAP",
    "FeedWatchSource",
    "covered_to",
    "window_start",
]

DEFAULT_LOOKBACK_DAYS: Final = 14
"""First run, no state: long enough to cover the ≈10-day consolidation lag."""

OVERLAP: Final = timedelta(hours=1)
"""Deliberate re-scan of the end of the last window. Dedupe makes it free; a crash makes it
necessary."""

Notice = Callable[[str], None]
"""Where a source reports something the operator should know. Not a logger — a callback, so the
two commands print in their own voice and the seam stays free of an output convention."""


def window_start(since: datetime | None, cursor: datetime | None, end: datetime) -> datetime:
    """Where this window begins: the flag, else the cursor less the overlap, else a fortnight."""
    if since is not None:
        return since
    if cursor is not None:
        return min(cursor - OVERLAP, end)
    return end - timedelta(days=DEFAULT_LOOKBACK_DAYS)


def covered_to(feed: FeedResult, window: PollWindow) -> datetime | None:
    """How far the feed was actually read — `None` when that is the whole window.

    A window wider than `MAX_PAGES` pages of 1,000 is not exotic: the ≈3,000-a-day
    `ingestion` channel overruns it in eleven days, and the no-state default window is
    fourteen. So truncation is a normal outcome and it must not move the cursor past unread
    entries.

    Entries arrive in ascending `<updated>` order, within a page and across pages, verified
    2026-08-06 over the four pages of 2026-08-05 (3,823 entries, strictly ascending, each page's
    first stamp after the previous page's last). So the last entry read is the high-water mark.
    Its timestamp is the server's own zone, the same zone the window bounds are read in, so the
    offset is dropped rather than converted.
    """
    if not feed.truncated:
        return None
    stamps = [entry.updated for entry in feed.entries if entry.updated is not None]
    if not stamps:
        return window.start  # nothing datable came back: cover nothing, retry the window
    return max(max(stamps).replace(tzinfo=None), window.start)


class FeedWatchSource:
    """The notification feed, the watchlist and the seen-state, as one `poll(window)` call."""

    def __init__(
        self,
        adapter: EuCorpusAdapter,
        *,
        watchlist: Watchlist,
        state_path: Path,
        channel: str = DEFAULT_CHANNEL,
        notice: Notice | None = None,
    ) -> None:
        self.adapter = adapter
        self.watchlist = watchlist
        self.state_path = state_path
        self.channel = channel
        self.notice: Notice = notice if notice is not None else _silent
        self._loaded: StateLoad | None = None

    def state(self) -> WatchState:
        """The persisted state, read from disk **once** per source and then carried.

        Reading it twice is not idempotent and the reason is a real one: `load_state` moves an
        unusable file aside as it reports it (`watch/state.py`), so a second read of a corrupt
        file finds a clean slate and the operator never hears that anything was lost. One read,
        one report, and `poll` replaces the memo with what it saved.
        """
        if self._loaded is None:
            self._loaded = load_state(self.state_path)
            if self._loaded.recovered:
                self.notice(f"state recovered: {self._loaded.detail}")
        return self._loaded.state

    def window(self, *, since: datetime | None, until: datetime, observed_on: date) -> PollWindow:
        """The next window, from the flags and whatever cursor the last poll left behind."""
        return PollWindow(
            start=window_start(since, self.state().last_window_end, until),
            end=until,
            observed_on=observed_on,
        )

    def poll(self, window: PollWindow) -> PollResult:
        """One window: read the state, fetch, resolve, persist. The `WatchSource` seam."""
        state = self.state()
        feed = fetch_notifications(
            self.adapter.client.http, start=window.start, end=window.end, channel=self.channel
        )
        covered = covered_to(feed, window)
        if covered is not None:
            self.notice(
                f"window truncated at {feed.pages} pages: read up to {covered.isoformat()} of "
                f"{window.end.isoformat()}; the cursor stops there and the next poll resumes it"
            )
        result = poll_once(
            entries=feed.entries,
            watchlist=self.watchlist,
            state=state,
            window=window,
            versions=self.adapter,
            covered_to=covered,
        )
        save_state(self.state_path, result.state)
        # What is on disk is now what this poll produced, so a `--loop` caller's next window
        # resumes from it without re-reading a file only this process has written.
        self._loaded = StateLoad(state=result.state, existed=True)
        return result


def _silent(message: str) -> None:
    """The default notice sink: a library that prints without being asked is a nuisance."""
