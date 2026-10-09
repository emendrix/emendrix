"""Which changes the personal feed shows, and in what words: the email's rules, applied live.

The feed matches a watchlist's items against recent changes when it is fetched, so an item
added today shows changes recorded before it, which the email (matched once, when an event is
announced) never sends. Each entry repeats the lines the email gives the same change, built by
`notify.compose` and `notify.render`, so no provision text reaches the feed: a sentence the
citation gate wrote as a quotation is replaced by a pointer to the page, as in the email.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Final

from emendrix_service import DISCLAIMER
from emendrix_service.feed.model import FeedChange, FeedEntry
from emendrix_service.notify.compose import change_line, location_order
from emendrix_service.notify.facts import EventFacts, ItemFacts
from emendrix_service.notify.matching import best, is_date_alert, match, phrase
from emendrix_service.notify.render import text_lines

__all__ = ["ENTRY_LIMIT", "event_dated", "feed_entries"]

ENTRY_LIMIT: Final = 100


def event_dated(event: EventFacts) -> date:
    """When an event took effect: its latest in-force date, else the day it was detected.

    The public feeds date an entry by the same rule, so the two agree on every shared id.
    """
    return max(event.in_force) if event.in_force else event.detected_on


def _entry(found: FeedChange, items: Sequence[ItemFacts], *, site_url: str) -> FeedEntry | None:
    change, event, label = found.change, found.event, found.act_label
    hit = best(match(change, items))
    if hit is None:
        return None
    item = next(item for item in items if item.item_id == hit.item_id)
    line = change_line(change, event, label, phrase(hit, item, change, label))
    if item.date_alerts and is_date_alert(change):
        line = line.model_copy(update={"date_alert": True})
    content = "\n".join((*text_lines(line, site_url=site_url), "", DISCLAIMER))
    return FeedEntry(
        link=line.link,
        title=f"{label}: {line.location} {line.change_type}",
        updated=event_dated(event),
        content=content,
    )


def feed_entries(
    changes: Sequence[FeedChange],
    items: Sequence[ItemFacts],
    *,
    site_url: str,
    limit: int = ENTRY_LIMIT,
) -> tuple[FeedEntry, ...]:
    """The newest `limit` changes any of `items` matches, newest event first.

    Within an event, changes follow the location order the email uses.
    """
    by_location = sorted(
        changes, key=lambda c: (location_order(c.change.location), c.change.occurrence)
    )
    ordered = sorted(
        by_location,
        key=lambda c: (event_dated(c.event), c.event.detected_on, c.event.event_key),
        reverse=True,
    )
    entries: list[FeedEntry] = []
    for found in ordered:
        act = (found.event.corpus, found.event.act_key)
        watching = [item for item in items if (item.corpus, item.act_key) == act]
        entry = _entry(found, watching, site_url=site_url) if watching else None
        if entry is not None:
            entries.append(entry)
            if len(entries) >= limit:
                break
    return tuple(entries)
