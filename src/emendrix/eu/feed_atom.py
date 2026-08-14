"""Reading the Atom the notification endpoint sends, which is not what Atom promises.

The transport half lives in `eu/feed.py`; this is the vocabulary and the parser, split for the
same reason `eu/notices.py` is split from `eu/cellar.py`: fetching a thing and understanding it
are two jobs. Everything below was read off a live response on **2026-08-06** and is pinned in
`tests/fixtures/eu/notification_ingestion_20260805T1000_20260805T1005_p1.atom.xml`.

**The standard Atom fields ship unrendered Velocity template variables.** Every entry literally
contains `<title>$item.title</title>`, `<link href="$item.cellarUri"/>` and an `<id>` of
`${item.cellarUri}_2026-08-05T10:03:48.434+02:00`. A generic Atom library reads that as a title
and a link and is confidently wrong, which is why `feedparser` is banned package-wide
(`tests/test_architecture.py`). Only the `notifEntry:` namespace is real, plus `<updated>`,
the one Atom field the server does render, so an entry's identity is `cellarId@updated`.

**Identifiers are percent-encoded, scheme-prefixed, and several per entry.** One entry carries
`consolidation:2024R1689%2F20260727`, `celex:02024R1689-20260727` and
`eli:reg:2024:1689:2026-07-27` side by side under `notifEntry:identifiers`; a single
`<notifEntry:identifier>` child of `<entry>` is not the shape the server sends, confirmed
against the live feed on 2026-08-05. They are decoded and kept verbatim; reading them is
`eu/identifiers.py`'s job, never a local regex.

That entry is the AI Act's Digital Omnibus consolidation, on the `ingestion` channel, on
2026-08-05: twelve days after the OJ publication and one after the consolidated text was
built, which is the consolidation lag the watcher is built around. So `ingestion` is the
channel that carries consolidations of watchlist acts, confirmed 2026-08-06. The same work is
re-notified every few minutes for hours (that one produced 46 entries in a day), which is why
the poller dedupes on what an entry *resolved to* and not only on entry identity.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # types only; parsing goes through `eu/xml_.py`
from datetime import datetime
from typing import Final
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field

from emendrix.eu.xml_ import fromstring

__all__ = ["FeedEntry", "FeedIdentifier", "FeedPage", "parse_feed"]

_ATOM: Final = "{http://www.w3.org/2005/Atom}"
_ENTRY: Final = "{http://publications.europa.eu/atom/notificationEntry}"
_REQ: Final = "{http://publications.europa.eu/atom/notificationRequest}"

_READABLE_SCHEMES: Final = frozenset({"celex", "consolidation"})
"""The identifier families `eu/identifiers.py` can read. The rest ride along unparsed."""


class FeedIdentifier(BaseModel):
    """One `notifEntry:identifier`, split at its scheme and percent-decoded.

    Kept as strings on purpose: this module reports what the feed said, and deciding whether
    `2024R1689/20260727` names a watched act is `eu/identifiers.py`'s job.
    """

    model_config = ConfigDict(frozen=True)

    scheme: str = ""
    value: str

    @classmethod
    def parse(cls, raw: str) -> FeedIdentifier:
        scheme, _, rest = raw.strip().partition(":")
        if not rest:
            return cls(value=unquote(raw.strip()))
        return cls(scheme=scheme.lower(), value=unquote(rest))

    @property
    def readable(self) -> bool:
        """True if this is a family the EU identifier grammar knows how to read."""
        return self.scheme in _READABLE_SCHEMES

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}" if self.scheme else self.value


class FeedEntry(BaseModel):
    """One notification, reduced to the fields the server actually renders."""

    model_config = ConfigDict(frozen=True)

    entry_id: str = Field(description="`cellarId@updated` — the poller's dedupe key.")
    cellar_id: str
    updated_raw: str = ""
    updated: datetime | None = None
    notification_type: str = ""
    wemi_class: str = ""
    identifiers: tuple[FeedIdentifier, ...] = ()
    classes: tuple[str, ...] = ()

    @property
    def readable_identifiers(self) -> tuple[FeedIdentifier, ...]:
        return tuple(item for item in self.identifiers if item.readable)


class FeedPage(BaseModel):
    """One page of the feed, plus the server's own statement about continuation."""

    model_config = ConfigDict(frozen=True)

    page: int = 1
    more_entries: bool = False
    entries: tuple[FeedEntry, ...] = ()
    skipped: int = Field(default=0, description="Entries with no cellarId: unusable, counted.")
    without_identifiers: int = Field(
        default=0, description="Entries the server sent with no identifier at all. Kept."
    )


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _parse_timestamp(raw: str) -> datetime | None:
    """`<updated>` is the one Atom field that is real. An unreadable one is not fatal."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _children(element: ET.Element, path: str) -> tuple[str, ...]:
    """The non-empty text of every child on a path, in document order."""
    return tuple(value for value in (_text(child) for child in element.iterfind(path)) if value)


def _parse_entry(element: ET.Element) -> FeedEntry | None:
    """One `<entry>` → a `FeedEntry`, or `None` when it carries no identity at all."""
    cellar_id = _text(element.find(f"{_ENTRY}cellarId"))
    if not cellar_id:
        return None
    updated_raw = _text(element.find(f"{_ATOM}updated"))
    identifiers = tuple(
        FeedIdentifier.parse(value)
        for value in _children(element, f"{_ENTRY}identifiers/{_ENTRY}identifier")
    )
    classes = _children(element, f"{_ENTRY}classes/{_ENTRY}class")
    return FeedEntry(
        entry_id=f"{cellar_id}@{updated_raw}" if updated_raw else cellar_id,
        cellar_id=cellar_id,
        updated_raw=updated_raw,
        updated=_parse_timestamp(updated_raw),
        notification_type=_text(element.find(f"{_ENTRY}type")),
        wemi_class=_text(element.find(f"{_ENTRY}wemiClass")),
        identifiers=identifiers,
        classes=classes,
    )


def parse_feed(body: bytes) -> FeedPage:
    """Atom bytes → the entries, the page number and whether the server has more.

    An entry the server sent incomplete is counted and skipped, never raised on: the feed is a
    firehose and one malformed record in three thousand must not lose the other 2,999.
    """
    root = fromstring(body)
    entries: list[FeedEntry] = []
    skipped = 0
    without_identifiers = 0
    for element in root.iterfind(f"{_ATOM}entry"):
        entry = _parse_entry(element)
        if entry is None:
            skipped += 1
            continue
        if not entry.identifiers:
            without_identifiers += 1
        entries.append(entry)
    page_text = _text(root.find(f"{_REQ}page"))
    return FeedPage(
        page=int(page_text) if page_text.isdigit() else 1,
        more_entries=_text(root.find(f"{_REQ}moreEntries")).lower() == "true",
        entries=tuple(entries),
        skipped=skipped,
        without_identifiers=without_identifiers,
    )
