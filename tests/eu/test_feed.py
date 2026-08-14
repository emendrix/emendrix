"""The notification feed, against five pinned minutes of the real firehose.

The fixture is an unedited response, Velocity garbage and all, so these assertions are about
what the Publications Office actually sends, not about what a document says it sends.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from emendrix.eu.cache import CachedResponse, cache_key, entry_for
from emendrix.eu.feed import ACCEPT_ATOM, CHANNELS, feed_url, fetch_notifications
from emendrix.eu.feed_atom import FeedIdentifier, parse_feed
from emendrix.eu.http import BASE_URL, CellarHttp
from eu_pins import (
    AI_ACT_V2,
    EMPTY_FEED_WINDOW,
    FEED_AI_ACT_ENTRIES,
    FEED_ENTRIES,
    FEED_WINDOW,
    OBSERVED_ON,
)


def page_bytes(http: CellarHttp, window: tuple[datetime, datetime] = FEED_WINDOW) -> bytes:
    """One pinned page, fetched through the ordinary path, so the fixture wiring is tested."""
    return http.get(feed_url("ingestion", *window), accept=ACCEPT_ATOM, accept_language=None).body


class PagedCache:
    """An offline cache serving crafted pages by page number, to drive the pagination loop.

    Keyed exactly as `eu/http.py` keys the real thing, so what it exercises is the loop, not a
    parallel implementation of the URL.
    """

    def __init__(self, pages: dict[int, bytes]) -> None:
        self.pages = {
            cache_key(
                "GET",
                f"{BASE_URL}{feed_url('ingestion', *FEED_WINDOW, page=number)}",
                ACCEPT_ATOM,
                None,
            ): body
            for number, body in pages.items()
        }

    @property
    def offline(self) -> bool:
        return True

    def get(self, key: str) -> CachedResponse | None:
        body = self.pages.get(key)
        if body is None:
            return None
        return CachedResponse(
            entry=entry_for(
                key=key,
                url="stub",
                accept=ACCEPT_ATOM,
                accept_language=None,
                status_code=200,
                content_type="text/xml",
                fetched_at=datetime(OBSERVED_ON.year, OBSERVED_ON.month, OBSERVED_ON.day),
                body=body,
                file=f"{key}.body",
            ),
            body=body,
        )

    def store(self, response: CachedResponse) -> None:
        return None


def test_the_window_is_a_stable_url() -> None:
    """The URL is also a cache key, so it has to be built the same way every time."""
    assert feed_url("ingestion", *FEED_WINDOW) == (
        "/webapi/notification/ingestion"
        "?startDate=2026-08-05T10%3A00%3A00&endDate=2026-08-05T10%3A05%3A00"
        "&type=UPDATE&wemiClasses=work&page=1"
    )


def test_an_unknown_channel_is_refused_before_the_request() -> None:
    """The channel segment is mandatory and closed: a wrong one is a 404, verified 2026-08-06."""
    assert "ingestion" in CHANNELS
    with pytest.raises(ValueError, match="unknown notification channel"):
        feed_url("everything", *FEED_WINDOW)


def test_the_pinned_window_parses_to_the_entries_it_has(http: CellarHttp) -> None:
    result = fetch_notifications(http, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    assert (result.pages, result.truncated) == (1, False)
    assert len(result.entries) == FEED_ENTRIES
    assert result.skipped == 0
    assert http.network_calls == 0


def test_the_velocity_garbage_never_reaches_a_field(http: CellarHttp) -> None:
    """`<title>$item.title</title>` and `<link href="$item.cellarUri"/>` are unrendered."""
    result = fetch_notifications(http, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    serialised = "".join(entry.model_dump_json() for entry in result.entries)
    assert "$item" not in serialised
    assert all(entry.cellar_id.startswith("cellar:") for entry in result.entries)
    assert all(entry.notification_type == "update" for entry in result.entries)


def test_identity_comes_from_the_two_fields_the_server_renders(http: CellarHttp) -> None:
    """`<id>` is `${item.cellarUri}_…`; identity is `cellarId@updated` instead."""
    result = fetch_notifications(http, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    entry = next(item for item in result.entries if AI_ACT_V2 in str(item.identifiers))
    assert entry.entry_id == f"{entry.cellar_id}@{entry.updated_raw}"
    assert entry.updated is not None
    assert entry.updated.isoformat().startswith("2026-08-05T10:")
    assert len({item.entry_id for item in result.entries}) == FEED_ENTRIES


def test_the_flagship_consolidation_is_in_there_under_three_identifiers(
    http: CellarHttp,
) -> None:
    """The AI Act's Digital Omnibus consolidation, notified 2026-08-05 on `ingestion`."""
    result = fetch_notifications(http, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    hits = [
        entry
        for entry in result.entries
        if any("2024R1689" in item.value for item in entry.identifiers)
    ]
    assert len(hits) == FEED_AI_ACT_ENTRIES
    full = next(entry for entry in hits if len(entry.identifiers) == 3)
    assert [str(item) for item in full.identifiers] == [
        "consolidation:2024R1689/20260727",
        f"celex:{AI_ACT_V2}",
        "eli:reg:2024:1689:2026-07-27",
    ]
    # `eli:` names the same work through a vocabulary this adapter does not fetch by.
    assert [item.scheme for item in full.readable_identifiers] == ["consolidation", "celex"]


def test_an_empty_window_is_an_answer(http: CellarHttp) -> None:
    """Nothing happened is a result, not a failure, and it still costs exactly one page."""
    result = fetch_notifications(http, start=EMPTY_FEED_WINDOW[0], end=EMPTY_FEED_WINDOW[1])
    assert (result.entries, result.pages, result.truncated) == ((), 1, False)


def test_an_entry_the_server_sends_incomplete_is_counted_not_raised(http: CellarHttp) -> None:
    """One malformed record in a firehose must not lose the other 2,999.

    The bytes are the pinned page with one entry's `cellarId` removed, the field an entry has no
    identity without, because the archive holds no such entry to point at.
    """
    body = page_bytes(http)
    damaged = body.replace(
        b"<notifEntry:cellarId>cellar:3fd8c302-908b-11f1-9262-01aa75ed71a1</notifEntry:cellarId>",
        b"",
        1,
    )
    assert damaged != body
    page = parse_feed(damaged)
    assert page.skipped == 1
    assert len(page.entries) == FEED_ENTRIES - 1


def test_an_entry_with_no_identifier_is_kept_and_counted() -> None:
    """A notification naming nothing this adapter reads is a coverage number, not a crash."""
    page = parse_feed(
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<feed xmlns="http://www.w3.org/2005/Atom"'
        b' xmlns:notifEntry="http://publications.europa.eu/atom/notificationEntry"'
        b' xmlns:notifReq="http://publications.europa.eu/atom/notificationRequest">'
        b"<notifReq:page>3</notifReq:page>"
        b"<notifReq:moreEntries>true</notifReq:moreEntries>"
        b"<entry><updated>2026-08-05T10:00:00.000+02:00</updated>"
        b"<notifEntry:cellarId>cellar:abc</notifEntry:cellarId>"
        b"<notifEntry:type>update</notifEntry:type></entry>"
        b"</feed>"
    )
    assert (page.page, page.more_entries) == (3, True)
    assert page.without_identifiers == 1
    assert page.entries[0].entry_id == "cellar:abc@2026-08-05T10:00:00.000+02:00"


def _more(body: bytes) -> bytes:
    """The pinned page, claiming a continuation. One flag, so the loop can be driven."""
    return body.replace(
        b"<notifReq:moreEntries>false</notifReq:moreEntries>",
        b"<notifReq:moreEntries>true</notifReq:moreEntries>",
    )


def test_pagination_follows_the_servers_own_more_entries_flag(http: CellarHttp) -> None:
    """`page` is 1-based and the feed announces its own continuation (probed 2026-08-06).

    Driven from the two pinned pages: the real 46-entry page with its `moreEntries` flipped,
    then the real empty page, which is the shape the server produces at the end of a window.
    """
    pages = {1: _more(page_bytes(http)), 2: page_bytes(http, EMPTY_FEED_WINDOW)}
    stub = CellarHttp(cache=PagedCache(pages))
    result = fetch_notifications(stub, start=FEED_WINDOW[0], end=FEED_WINDOW[1])
    assert (result.pages, len(result.entries), result.truncated) == (2, FEED_ENTRIES, False)
    assert stub.network_calls == 0


def test_pagination_stops_at_the_cap_and_says_so(http: CellarHttp) -> None:
    """A server that keeps saying `moreEntries` is bounded, and the result admits it."""
    page = _more(page_bytes(http))
    stub = CellarHttp(cache=PagedCache(dict.fromkeys(range(1, 10), page)))
    result = fetch_notifications(stub, start=FEED_WINDOW[0], end=FEED_WINDOW[1], max_pages=3)
    assert (result.pages, result.truncated) == (3, True)
    assert len(result.entries) == 3 * FEED_ENTRIES


def test_a_refusal_is_not_an_empty_window() -> None:
    """Nobody may read "the server said no" as "no act changed"."""
    empty = CellarHttp(cache=PagedCache({}))
    with pytest.raises(LookupError, match="no fixture"):
        fetch_notifications(empty, start=FEED_WINDOW[0], end=FEED_WINDOW[1])


def test_identifiers_are_percent_decoded_and_split_at_the_scheme() -> None:
    assert FeedIdentifier.parse("consolidation:2024R1689%2F20260727") == FeedIdentifier(
        scheme="consolidation", value="2024R1689/20260727"
    )
    assert FeedIdentifier.parse("ep:P9_OJQ%282024%2903-11").readable is False
    assert FeedIdentifier.parse("bare-value") == FeedIdentifier(value="bare-value")
