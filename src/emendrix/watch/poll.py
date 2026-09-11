"""`poll_once` — one window of the feed, against the watchlist and the state, out come events.

Deterministic and clock-free by construction: the window and the observation date are values
handed in from `watch/cli.py`. Given the same entries, the same state and the same version
inventory, this function returns the same events and the same next state, which is what makes
the crash-restart and overlapping-window tests honest rather than decorative.

## Exactly once, twice over

Two dedupe layers, because one is not enough:

1. **By entry identity** (`cellarId@updated`), which makes overlapping windows free and so lets
   the poller assume it died mid-run last time and simply re-scan.
2. **By what the entry resolved to** (`eu:32024R1689@02024R1689-20260727`), the layer that
   actually matters. CELLAR re-notified the AI Act's Digital Omnibus consolidation 46 times in
   one day, each time under a fresh entry id (measured 2026-08-05). Without this layer the
   watcher would announce the same amendment 46 times.

## What an entry becomes

For each watchlist hit the act's version inventory is consulted through `discover_versions`, the
seam's own method, so this module can be driven by any adapter and is stubbed in three lines in
the tests.

```
listed, in the language          →  AmendmentEvent(new_version, previous_version)
not listed at all                →  AmendmentEvent(ConsolidationPending)   … recorded, re-checked
listed, in other languages only  →  AmendmentEvent(EnglishUnavailable)     … recorded, re-checked
no version named by the feed     →  the newest version listed, then as above
```

Pending records are re-checked **before** the window is walked, so an act whose text has
arrived is reported even on a poll that finds nothing new in the feed. When one resolves it
emits a single ordinary version event and leaves the pending list: amended-then-consolidated is
reported exactly twice, never once and never on every poll in between.

A record that never resolves looks like a healthy poll in every other counter: the window is
read, the cursor advances and the run exits successfully. So the stats carry how many records
are still waiting once the poll is done and how old the oldest of them is, which is the only
number that separates a corpus with nothing new from one nothing new is reaching.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from emendrix.core import (
    ActId,
    ConsolidationPending,
    EnglishUnavailable,
    VersionDescriptor,
    VersionId,
)
from emendrix.eu.feed_atom import FeedEntry
from emendrix.watch.config import WatchedAct, WatchIndex, Watchlist
from emendrix.watch.events import (
    AmendmentEvent,
    PollResult,
    PollStats,
    PollWindow,
    VersionSource,
)
from emendrix.watch.state import (
    EmittedEvent,
    PendingConsolidation,
    SeenEntry,
    WatchState,
    prune,
)

__all__ = ["poll_once"]


class _Resolver:
    """Version lookups for one poll, memoised — a watchlist act appears in dozens of entries."""

    def __init__(self, versions: VersionSource, language: str) -> None:
        self._versions = versions
        self._language = language.upper()
        self._cache: dict[str, list[VersionDescriptor]] = {}

    def descriptors(self, act: ActId) -> list[VersionDescriptor]:
        found = self._cache.get(act.key)
        if found is None:
            found = self._versions.discover_versions(act)
            self._cache[act.key] = found
        return found

    def resolve(
        self, watched: WatchedAct, version: str | None, window: PollWindow, trigger: str
    ) -> AmendmentEvent:
        """One watchlist hit → the event it justifies, first-class state and all."""
        act = watched.act
        descriptors = self.descriptors(act)
        # Version inventories come oldest first, the OJ text included (`eu/cellar.py`), so the
        # last one is the newest — which is what an identifier naming the act itself implies.
        wanted = VersionId(version) if version is not None else _newest(descriptors)
        position = next((i for i, item in enumerate(descriptors) if item.version == wanted), None)
        if wanted is None or position is None:
            return _pending(act, wanted, window, trigger, _why_pending(wanted, descriptors))
        descriptor = descriptors[position]
        if not descriptor.has_language(self._language):
            return AmendmentEvent(
                act=act,
                target_version=wanted,
                trigger=trigger,
                observed_on=window.observed_on,
                unavailable=EnglishUnavailable(
                    act=act,
                    version=wanted,
                    requested_language=self._language,
                    available_languages=descriptor.languages,
                    observed_on=window.observed_on,
                    detail=f"the corpus offers {', '.join(descriptor.languages) or 'no language'}",
                ),
            )
        return AmendmentEvent(
            act=act,
            target_version=wanted,
            new_version=wanted,
            previous_version=descriptors[position - 1].version if position > 0 else None,
            version_date=descriptor.version_date,
            trigger=trigger,
            observed_on=window.observed_on,
        )


def _newest(descriptors: list[VersionDescriptor]) -> VersionId | None:
    return descriptors[-1].version if descriptors else None


def _why_pending(wanted: VersionId | None, descriptors: list[VersionDescriptor]) -> str:
    if wanted is None:
        return "the corpus lists no version of this act at all"
    return f"{wanted} is not among the {len(descriptors)} versions the corpus lists"


def _waiting_age(rows: Iterable[PendingConsolidation], *, on: date) -> int:
    """Days since the oldest of these rows was first seen, or 0 when there are none.

    `on` is the window's observation date, a value handed in at the CLI boundary, so nothing
    here reads a clock. A row first seen after `on` counts 0: an age is a duration, and a
    negative one would be a report about the caller rather than a fact about the corpus.
    """
    ages = [(on - row.first_seen).days for row in rows]
    return max((age for age in ages if age > 0), default=0)


def _pending(
    act: ActId,
    wanted: VersionId | None,
    window: PollWindow,
    trigger: str,
    detail: str,
) -> AmendmentEvent:
    """Amended, not consolidated yet — a value that persists and resolves once."""
    return AmendmentEvent(
        act=act,
        target_version=wanted,
        trigger=trigger,
        observed_on=window.observed_on,
        unavailable=ConsolidationPending(act=act, observed_on=window.observed_on, detail=detail),
    )


def _pending_row(
    event: AmendmentEvent,
    watched: WatchedAct,
    window: PollWindow,
    previous: PendingConsolidation | None,
) -> PendingConsolidation:
    """The state row for an event that has not resolved; keeps the original first-seen date.

    A poll can reach the same unresolved act twice — once from the pending list, once from an
    entry in the window — so `checks` counts *polls*, not visits: it advances only when the
    row was last checked on an earlier date.
    """
    unavailable = event.unavailable
    checked_before = previous is not None and previous.last_checked == window.observed_on
    return PendingConsolidation(
        act_key=str(event.act),
        celex=watched.celex,
        version=str(event.target_version) if event.target_version is not None else None,
        state=unavailable.state if unavailable is not None else "unknown",
        first_seen=previous.first_seen if previous is not None else window.observed_on,
        last_checked=window.observed_on,
        checks=previous.checks + (0 if checked_before else 1) if previous is not None else 1,
        detail=unavailable.detail if unavailable is not None else "",
    )


class _Poll:
    """One run's mutable bookkeeping, so `poll_once` reads as the two steps it is."""

    def __init__(self, state: WatchState, window: PollWindow, covered_to: datetime | None) -> None:
        self.window = window
        self.covered_to = covered_to
        self.seen = set(state.seen_ids)
        self.emitted = set(state.emitted_keys)
        self.seen_rows = list(state.seen)
        self.emitted_rows = list(state.emitted)
        self.events: list[AmendmentEvent] = []
        self.pending: dict[str, PendingConsolidation] = {}
        self.duplicates = 0
        self.matched = 0
        self.suppressed = 0
        self.resolved = 0

    def record(
        self,
        event: AmendmentEvent,
        watched: WatchedAct,
        previous: PendingConsolidation | None,
    ) -> None:
        """Emit unless it has been reported before, and keep the state rows in step."""
        if not event.ready:
            key = f"{event.act}@{event.target_version or 'latest'}"
            row = _pending_row(event, watched, self.window, previous or self.pending.get(key))
            self.pending[row.key] = row
        if event.key in self.emitted:
            self.suppressed += 1
            return
        self.emitted.add(event.key)
        self.emitted_rows.append(EmittedEvent(key=event.key, on=self.window.observed_on))
        self.events.append(event)
        if event.ready and previous is not None:
            self.resolved += 1

    def state(self) -> WatchState:
        # The cursor stops where the feed was actually read, which is the window end unless the
        # fetch was cut short. Advancing past unread notifications would lose them for good.
        cursor = self.window.end if self.covered_to is None else self.covered_to
        return prune(
            WatchState(
                last_window_end=max(cursor, self.window.start),
                seen=tuple(self.seen_rows),
                emitted=tuple(self.emitted_rows),
                pending=tuple(self.pending.values()),
            ),
            on=self.window.observed_on,
        )


def poll_once(
    *,
    entries: tuple[FeedEntry, ...],
    watchlist: Watchlist,
    state: WatchState,
    window: PollWindow,
    versions: VersionSource,
    language: str = "ENG",
    covered_to: datetime | None = None,
) -> PollResult:
    """One poll: re-check what was pending, walk the window, advance the cursor.

    The cursor advances whether or not anything matched — a window that held no watchlist hit
    is a *result*, and re-scanning it forever is the failure mode this guards against.

    `covered_to` is the one thing that holds it back: when the feed could not be read to the end
    of the window (`FeedResult.truncated`, see `eu/feed.py`), the caller passes how far it got
    and the cursor stops there instead. The next poll resumes from that point rather than
    stepping over notifications nobody has looked at — the *other* way this kind of program
    quietly loses an amendment.
    """
    index = WatchIndex(watchlist)
    resolver = _Resolver(versions, language)
    by_celex = {entry.celex: entry for entry in watchlist.acts}
    run = _Poll(state, window, covered_to)

    # 1 — what was already waiting. Checked first, so an act whose text has arrived is
    #     reported even in a window the feed says nothing about.
    for waiting in state.pending:
        watched = by_celex.get(waiting.celex)
        if watched is None:  # dropped from the watchlist between polls: stop tracking it
            continue
        event = resolver.resolve(watched, waiting.version, window, f"pending:{waiting.key}")
        run.record(event, watched, waiting)

    # 2 — the window itself.
    for entry in entries:
        if entry.entry_id in run.seen:
            run.duplicates += 1
            continue
        run.seen.add(entry.entry_id)
        run.seen_rows.append(SeenEntry(entry_id=entry.entry_id, on=window.observed_on))
        hit = index.match_entry(entry)
        if hit is None:
            continue
        run.matched += 1
        # Resolving again is nearly free — the version inventory is memoised — and the two
        # dedupe layers make it harmless: the event is suppressed and the pending row merges.
        event = resolver.resolve(hit.watched, hit.version, window, hit.identifier)
        run.record(event, hit.watched, None)

    # The waiting counts are about the state this poll persists, not the one it started from:
    # `pending_checked` is what it looked at, `pending_waiting` what is still stuck after it did.
    persisted = run.state()
    return PollResult(
        events=tuple(run.events),
        state=persisted,
        stats=PollStats(
            entries=len(entries),
            duplicates=run.duplicates,
            matched=run.matched,
            suppressed=run.suppressed,
            pending_checked=len(state.pending),
            pending_resolved=run.resolved,
            pending_waiting=len(persisted.pending),
            pending_oldest_days=_waiting_age(persisted.pending, on=window.observed_on),
            truncated=covered_to is not None,
        ),
    )
