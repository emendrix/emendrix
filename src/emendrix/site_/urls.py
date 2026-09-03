"""Where things live on the site, and nothing else.

Both halves of every URL are canonical identifiers: the act slug is the corpus's own key
made filesystem-safe (`output.json_out.slug`, the same function that names the changelog
directories), and the anchor is the event's entry key plus the canonical location string.
Canonical in, stable out: an anchor published once never changes, which is what lets feeds
and search results point at one specific change.

The entry key rather than the amending act's identifier, because no stage of the loop
resolves the amending act (an event names the consolidation it produced, and a change's
amending acts can be empty), while the entry key is always present and unique per event.
The same key also names the event's own page as a directory segment under its act, so an
event has one identifier however it is addressed: as a page, or as the fragment its card on
the act page answers to.

An amending instrument is addressed the same way, under `amendments/`: its own key, made
safe by the same function, and never a year-and-number reading of it.

A provision is addressed under its own act, by the slug of its canonical location string. Its
pages and the act's event pages are siblings in one directory, so the two vocabularies must
never mint one path twice; `shared_path` is what a caller asks before writing either.

Pages reference each other relatively (`up(depth)`), so the tree works from `file://`, from
a subpath, and from the site root alike.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from emendrix.output.json_out import slug

__all__ = [
    "act_href",
    "amendment_href",
    "amendments_href",
    "change_anchor",
    "depth_of",
    "entry_anchors",
    "event_href",
    "location_slug",
    "provision_href",
    "shared_path",
    "up",
]

_SEPARATORS: Final = re.compile(r"\s+")
_DROPPED: Final = re.compile(r"[()]")


def location_slug(canonical: str) -> str:
    """`AR 5 PA 1 ALN 1 PTA (bb)` becomes `ar-5-pa-1-aln-1-pta-bb`.

    Lowercase, spaces to hyphens, parentheses dropped. The segmentation survives the rewrite,
    because segments are space-separated and no segment value contains a hyphen, so every
    hyphen in the result is a segment boundary.

    The parentheses do not survive, and that is the one way two distinct canonical strings can
    slug alike: `AR 5 PTA (bb)` and `AR 5 PTA bb` both give `ar-5-pta-bb`. It takes a lettered
    point written without its parentheses, which nothing writes. The Formex reader builds every
    `PTA` and `PTI` value parenthesised and every `PO` value bare (`eu/formex/locations.py`),
    and no location in the committed corpus is the bare-valued twin of a parenthesised one. A
    slug alphabet of `[a-z0-9.-]` cannot carry the distinction without an escape, and an escape
    would be a published URL scheme paying for a form the vocabulary has never produced. So it
    is written down here rather than engineered away, and `test_urls.py` pins the behaviour.
    """
    return _DROPPED.sub("", _SEPARATORS.sub("-", canonical.strip())).lower()


def change_anchor(entry_key: str, canonical: str, occurrence: int = 1) -> str:
    """The stable fragment for one change: entry key, location, and a disambiguator.

    `occurrence` counts repeats of one location within one entry (two changes can land on
    the same coordinate); the first occurrence carries no suffix so the common case stays
    short.

    The suffix shares its alphabet with the slug, so one entry holding both a location
    repeated n times and a second location whose canonical string is that one followed by a
    bare `n` would mint the same fragment twice. That needs a trailing valueless numeric
    segment, which no observed location code carries; the counters are computed identically
    everywhere anchors are produced, so a repeat would be visible as a duplicated fragment
    rather than as two pages disagreeing.

    `location_slug` carries a second such case of its own, in dropped parentheses. Neither is
    reachable from a change location, which is always a top-level unit (`AR 5`, `AN III`) and
    carries no point segment at all.
    """
    if occurrence < 1:
        raise ValueError(f"occurrence counts from 1, got {occurrence}")
    suffix = "" if occurrence == 1 else f"-{occurrence}"
    return f"{entry_key}-{location_slug(canonical)}{suffix}"


def entry_anchors(entry_key: str, canonicals: Iterable[str]) -> tuple[str, ...]:
    """Every anchor of one event, one per change, in the order the entry carries them.

    The occurrence counter is the only part of the anchor scheme a caller could get subtly
    wrong, and a page, a feed and a search result that count it differently point at
    fragments no page holds. So it is counted here, once: pass one entry's change locations
    in entry order and read the anchors back positionally.
    """
    seen: dict[str, int] = {}
    anchors: list[str] = []
    for canonical in canonicals:
        seen[canonical] = seen.get(canonical, 0) + 1
        anchors.append(change_anchor(entry_key, canonical, seen[canonical]))
    return tuple(anchors)


def act_href(act_slug: str) -> str:
    """One act's page, relative to the site root."""
    return f"acts/{act_slug}/"


def event_href(act_slug: str, entry_key: str) -> str:
    """One event's own page, nested under its act.

    Built on `act_href` rather than repeating the directory, because an event page always
    sits under its act's own directory and the two must not be able to drift. Both segments
    are canonical identifiers, the act's key and the version the event produced, so the same
    entry key names the event twice: as this page's directory, and as the fragment its card
    on the act page keeps for every address published before the page existed.
    """
    return f"{act_href(act_slug)}{entry_key}/"


def provision_href(act_slug: str, canonical: str) -> str:
    """One provision's history, under its act, by its own slug: `acts/32024R1689/ar-6/`.

    The slug of the canonical location string, never a human reading of it. `Annex XVII` and
    `Article 6` are what the page's title says and what a reader searches for, but a second
    vocabulary for one coordinate is a second thing to keep in step, and it collides: the
    corpus writes both `AN 4` and `AN IV` for annexes of different acts, and a human-form path
    would have to decide which numeral an act's annex answers to. The canonical string decides
    nothing, which is the property a published address needs.

    Built on `act_href` for the reason `event_href` is: a provision page always sits under its
    act's own directory, beside that act's event pages, and the two must not drift apart.
    """
    return f"{act_href(act_slug)}{location_slug(canonical)}/"


def shared_path(entry_keys: Iterable[str], canonicals: Iterable[str]) -> tuple[str, str] | None:
    """The first entry key and canonical location of one act that would name one directory.

    Under an act sit two kinds of page addressed by two vocabularies: an event by its entry
    key (`02024R1689-20260727`) and a provision by its location slug (`ar-6`, `an-xvii`, `an`).
    Nothing makes the two disjoint by construction, and a collision would write one page where
    the tree lists two, so the caller that assembles an act asks here first and refuses.

    Returns the shared path segment with the canonical string that produced it, or `None`.
    """
    keys = set(entry_keys)
    for canonical in canonicals:
        found = location_slug(canonical)
        if found in keys:
            return found, canonical
    return None


def amendments_href() -> str:
    """The roster of amending instruments, relative to the site root."""
    return "amendments/"


def amendment_href(key: str) -> str:
    """One amending instrument's page: every watched act it amended, under its own key.

    The key is the identity and the whole path segment, made filesystem-safe by the same
    function that names an act's directory, so an instrument is addressed by the string the
    corpus published and never by a reading of it. A year-and-number path would need this
    module to know what an identifier means, which is the one thing it may not know.
    """
    return f"{amendments_href()}{slug(key)}/"


def depth_of(path: str) -> int:
    """How many directories deep a site-root-relative path sits.

    The paths counted here are the ones the builder writes, so this counts separators rather
    than parsing: `""` and `"404.html"` both sit at the root, `"acts/"` is one down, and
    `"acts/<slug>/"` is two. Pairing it with `up` in one module is the point. A page's path and
    the prefix that climbs back from it are one fact, and computing them apart is how they drift.
    """
    return path.count("/")


def up(depth: int) -> str:
    """The prefix that climbs from a page at `depth` back to the site root."""
    return "../" * depth
