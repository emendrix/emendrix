"""The personal feed as Atom bytes, built with ElementTree and nothing read from outside.

The feed's `<id>` is the feed's address with the secret token replaced by the watchlist's id, so
replacing the token keeps the id and a reader's history survives it; the `self` link is the
address actually fetched. Each entry's `<id>` and `<link>` are the change's own address on its
event page, the id the public provision feeds give the same change, so a reader following both
sees one item, not two. The disclaimer is the feed's subtitle and ends every entry's content.

The namespace below is a name, not an address: nothing fetches it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Final
from xml.etree.ElementTree import Element, SubElement, tostring

from emendrix_service import DISCLAIMER
from emendrix_service.feed.model import FeedEntry, FeedHead

__all__ = ["ATOM", "atom", "feed_id", "feed_title"]

ATOM: Final = "http://www.w3.org/2005/Atom"


def _stamp(value: date) -> str:
    """Midnight UTC of the day, as the public feeds stamp an entry."""
    return f"{value.isoformat()}T00:00:00Z"


def feed_id(site_url: str, head: FeedHead) -> str:
    """The feed's lasting id: its address with the watchlist's id where the token stands."""
    return f"{site_url}/u/feed/{head.watchlist_id}.xml"


def feed_title(head: FeedHead) -> str:
    """`Emendrix watchlist: <name>`."""
    return f"Emendrix watchlist: {head.name}"


def _text(parent: Element, tag: str, value: str, **attributes: str) -> Element:
    element = SubElement(parent, tag, attributes)
    element.text = value
    return element


def atom(head: FeedHead, entries: Sequence[FeedEntry], *, site_url: str, feed_url: str) -> bytes:
    """The feed document, UTF-8, entries in the order given, ending in a newline."""
    feed = Element("feed", {"xmlns": ATOM})
    _text(feed, "title", feed_title(head))
    _text(feed, "subtitle", DISCLAIMER)
    _text(feed, "id", feed_id(site_url, head))
    SubElement(feed, "link", {"rel": "self", "href": feed_url})
    SubElement(feed, "link", {"rel": "alternate", "href": f"{site_url}/account/"})
    updated = max((entry.updated for entry in entries), default=head.created_at.date())
    _text(feed, "updated", _stamp(updated))
    author = SubElement(feed, "author")
    _text(author, "name", "emendrix")
    for entry in entries:
        element = SubElement(feed, "entry")
        _text(element, "title", entry.title)
        _text(element, "id", entry.link)
        SubElement(element, "link", {"rel": "alternate", "href": entry.link})
        _text(element, "updated", _stamp(entry.updated))
        _text(element, "content", entry.content, type="text")
    document: bytes = tostring(feed, encoding="utf-8", xml_declaration=True)
    return document + b"\n"
