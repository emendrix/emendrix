"""The CELLAR notification feed, parsed the only way it can honestly be parsed.

This is the WATCH stage's eyes: the endpoint, the window and the pagination loop. Reading what
comes back is `eu/feed_atom.py`'s job, and the trap that makes it a job of its own is documented
there. Everything below was measured against the live endpoint on **2026-08-06**.

## The endpoint

```
GET /webapi/notification/{channel}?startDate=…&endDate=…&type=UPDATE&wemiClasses=work&page=N
Accept: application/atom+xml
```

- **The channel segment is mandatory**: `/webapi/notification/` and `/webapi/notification`
  both answer `404` (verified 2026-08-06). Channels: `ingestion`, `nal`, `sparql-load`,
  `ontology`.
- **`page` is the pagination parameter**, 1-based, 1000 entries per page, verified 2026-08-06:
  `…&page=2` on a 1,253-entry window returns the remaining 253. The feed also announces its
  own continuation in `<notifReq:page>` / `<notifReq:moreEntries>`, which is what the loop
  below follows. No page-size parameter exists: `pageSize`, `size`, `limit`, `itemsPerPage`,
  `perPage`, `maxResults`, `count` and `rows` are all ignored.
- **Entries arrive in ascending `<updated>` order**, within a page and across pages, checked
  2026-08-06 over the four pages of 2026-08-05 (3,823 entries, strictly ascending, each page's
  first stamp later than the previous page's last). That is what makes a truncated fetch
  resumable: the last entry read is a high-water mark, and `watch/cli.py` stops the cursor
  there rather than at a window end it never reached.
- **The window is half-open and takes a time.** `startDate=2026-07-01&endDate=2026-07-01`
  returns zero entries, `…&endDate=2026-07-02` returns 3,088. Both bounds accept
  `YYYY-MM-DDTHH:MM:SS`, which is how a fixture pins five real minutes of the firehose rather
  than a day of it. Times are read in the server's own zone (it echoes `+02:00`); windows here
  are naive and deliberately overlap, because dedupe, not arithmetic, is what makes the poller
  idempotent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eu.feed_atom import FeedEntry, parse_feed
from emendrix.eu.http import CellarHttp

__all__ = [
    "ACCEPT_ATOM",
    "CHANNELS",
    "DEFAULT_CHANNEL",
    "MAX_PAGES",
    "PAGE_SIZE",
    "FeedResult",
    "feed_url",
    "fetch_notifications",
]

ACCEPT_ATOM: Final = "application/atom+xml"

CHANNELS: Final = ("ingestion", "nal", "sparql-load", "ontology")
"""The four channel segments the endpoint accepts. Anything else is a 404."""

DEFAULT_CHANNEL: Final = "ingestion"
"""The channel that carries consolidations — confirmed on the AI Act, 2026-08-06."""

PAGE_SIZE: Final = 1000
"""Entries per page, fixed by the server. Recorded for the reader, never sent."""

MAX_PAGES: Final = 32
"""A stop for a server that keeps saying `moreEntries`. 32 pages ≈ 32,000 entries ≈ 10 days."""

WINDOW_FORMAT: Final = "%Y-%m-%dT%H:%M:%S"


class FeedResult(BaseModel):
    """Every entry in a window, and what it cost to say so."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[FeedEntry, ...] = ()
    pages: int = 0
    skipped: int = 0
    without_identifiers: int = 0
    truncated: bool = Field(
        default=False, description="True if `MAX_PAGES` stopped a feed still offering more."
    )


def feed_url(
    channel: str,
    start: datetime,
    end: datetime,
    *,
    page: int = 1,
    notification_type: str = "UPDATE",
    wemi_classes: str = "work",
) -> str:
    """The request path for one page. Byte-stable, because it is also a cache key."""
    if channel not in CHANNELS:
        raise ValueError(f"unknown notification channel {channel!r}; expected one of {CHANNELS}")
    query = (
        f"startDate={quote(start.strftime(WINDOW_FORMAT))}"
        f"&endDate={quote(end.strftime(WINDOW_FORMAT))}"
        f"&type={quote(notification_type)}"
        f"&wemiClasses={quote(wemi_classes)}"
        f"&page={page}"
    )
    return f"/webapi/notification/{channel}?{query}"


def fetch_notifications(
    http: CellarHttp,
    *,
    start: datetime,
    end: datetime,
    channel: str = DEFAULT_CHANNEL,
    notification_type: str = "UPDATE",
    wemi_classes: str = "work",
    max_pages: int = MAX_PAGES,
) -> FeedResult:
    """Every notification in `[start, end)`, following the server's own `moreEntries` flag.

    Goes through `eu.http`, so it goes through the disk cache and a fixture-backed run makes
    no network call at all. A page the server refuses is an error, not a state: the corpus has
    said nothing about any act, and pretending a window was empty would silently lose
    amendments.
    """
    entries: list[FeedEntry] = []
    skipped = 0
    without_identifiers = 0
    pages = 0
    more = True
    while more and pages < max_pages:
        url = feed_url(
            channel,
            start,
            end,
            page=pages + 1,
            notification_type=notification_type,
            wemi_classes=wemi_classes,
        )
        response = http.get(url, accept=ACCEPT_ATOM, accept_language=None)
        if not response.ok:
            raise LookupError(
                f"notification feed answered HTTP {response.status_code} for {response.url}: "
                f"{response.text(200)!r}"
            )
        page = parse_feed(response.body)
        pages += 1
        entries.extend(page.entries)
        skipped += page.skipped
        without_identifiers += page.without_identifiers
        more = page.more_entries and bool(page.entries)
    return FeedResult(
        entries=tuple(entries),
        pages=pages,
        skipped=skipped,
        without_identifiers=without_identifiers,
        truncated=more,
    )
