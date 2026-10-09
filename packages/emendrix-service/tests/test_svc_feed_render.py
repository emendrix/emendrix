"""The personal feed's entries and its Atom bytes, built from values a test writes by hand."""

from __future__ import annotations

import uuid
from datetime import date
from xml.etree.ElementTree import fromstring

from emendrix_service import DISCLAIMER
from emendrix_service.db.enums import ItemKind
from emendrix_service.feed.logic import event_dated, feed_entries
from emendrix_service.feed.model import FeedChange, FeedHead
from emendrix_service.feed.render import atom
from emendrix_service.notify.compose import FALLBACK
from emendrix_service.notify.facts import ChangeFacts, EventFacts, ItemFacts, StoredSentence
from tests.conftest import NOW, SITE_URL

NS = "{http://www.w3.org/2005/Atom}"
WATCHLIST = uuid.UUID("00000000-0000-4000-8000-000000000001")
TOKEN = "secret-token-AAAAAAAAAA"
FEED_URL = f"{SITE_URL}/u/feed/{TOKEN}.xml"
HEAD = FeedHead(watchlist_id=WATCHLIST, name="Flat rules", created_at=NOW)
QUOTED = "Tenants shall keep the stairwell clear at all times."


def event(version: str, *, detected: date, in_force: tuple[date, ...] = ()) -> EventFacts:
    return EventFacts(
        event_key=f"toy/house-rules@{version}",
        corpus="toy",
        act_key="house-rules",
        from_version="v1",
        to_version=version,
        detected_on=detected,
        in_force=in_force,
        url=f"{SITE_URL}/acts/house-rules/{version}/",
    )


def change(at: str, version: str, **extra: object) -> ChangeFacts:
    return ChangeFacts.model_validate(
        {
            "event_key": f"toy/house-rules@{version}",
            "location": at,
            "change_type": "MODIFIED",
            "anchor": f"{version}-{at.lower().replace(' ', '-')}",
            **extra,
        }
    )


def item(location: str | None) -> ItemFacts:
    return ItemFacts(
        item_id=uuid.uuid4(),
        watchlist_id=WATCHLIST,
        kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
        corpus="toy",
        act_key="house-rules",
        location=location,
    )


V2 = event("v2", detected=date(2026, 8, 1), in_force=(date(2026, 7, 1), date(2026, 9, 1)))
V3 = event("v3", detected=date(2026, 10, 10))
CHANGES = (
    FeedChange(change=change("AR 2", "v2"), event=V2, act_label="House Rules"),
    FeedChange(
        change=change(
            "AR 4",
            "v3",
            sentences=[{"text": QUOTED, "fallback": True}],
            dates_added=[date(2027, 1, 1)],
        ),
        event=V3,
        act_label="House Rules",
    ),
    FeedChange(change=change("AR 10", "v3"), event=V3, act_label="House Rules"),
    FeedChange(
        change=change("AR 2", "v3", sentences=[StoredSentence(text="Bins move.").model_dump()]),
        event=V3,
        act_label="House Rules",
    ),
)


def test_svc_feed_entries_are_the_matched_changes_newest_event_first() -> None:
    entries = feed_entries(CHANGES, (item("AR 2"), item("AR 4")), site_url=SITE_URL)
    assert [entry.link for entry in entries] == [
        f"{SITE_URL}/acts/house-rules/v3/#v3-ar-2",
        f"{SITE_URL}/acts/house-rules/v3/#v3-ar-4",
        f"{SITE_URL}/acts/house-rules/v2/#v2-ar-2",
    ]
    assert entries[0].title == "House Rules: Article 2 modified"
    assert entries[2].updated == event_dated(V2) == date(2026, 9, 1)
    assert entries[0].updated == date(2026, 10, 10)
    assert (
        "Date alert." in entries[1].content and "a date in the text changed" in entries[1].content
    )
    assert FALLBACK in entries[1].content and QUOTED not in entries[1].content
    assert "Why: you watch House Rules Article 2" in entries[0].content
    assert all(entry.content.endswith(DISCLAIMER) for entry in entries)
    assert len(feed_entries(CHANGES, (item(None),), site_url=SITE_URL, limit=2)) == 2
    assert feed_entries(CHANGES, (), site_url=SITE_URL) == ()


def test_svc_feed_atom_is_well_formed_and_carries_the_disclaimer() -> None:
    entries = feed_entries(CHANGES, (item(None),), site_url=SITE_URL)
    body = atom(HEAD, entries, site_url=SITE_URL, feed_url=FEED_URL)
    assert body == atom(HEAD, entries, site_url=SITE_URL, feed_url=FEED_URL)
    assert body.startswith(b"<?xml version='1.0' encoding='utf-8'?>\n<feed xmlns=")
    root = fromstring(body)
    assert root.tag == f"{NS}feed"
    assert root.findtext(f"{NS}id") == f"{SITE_URL}/u/feed/{WATCHLIST}.xml"
    assert TOKEN not in (root.findtext(f"{NS}id") or "")
    assert root.findtext(f"{NS}subtitle") == DISCLAIMER
    assert root.findtext(f"{NS}updated") == "2026-10-10T00:00:00Z"
    assert root.find(f"{NS}link[@rel='self']").get("href") == FEED_URL  # type: ignore[union-attr]
    found = root.findall(f"{NS}entry")
    assert len(found) == 4
    for element, entry in zip(found, entries, strict=True):
        assert element.findtext(f"{NS}id") == entry.link
        assert element.find(f"{NS}link").get("href") == entry.link  # type: ignore[union-attr]
        content = element.find(f"{NS}content")
        assert content is not None and content.get("type") == "text"
        assert (content.text or "").endswith(DISCLAIMER)
    assert QUOTED.encode() not in body


def test_svc_feed_an_empty_feed_is_dated_by_its_watchlist() -> None:
    root = fromstring(atom(HEAD, (), site_url=SITE_URL, feed_url=FEED_URL))
    assert root.findtext(f"{NS}updated") == f"{NOW.date().isoformat()}T00:00:00Z"
    assert root.findall(f"{NS}entry") == []
