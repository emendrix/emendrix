"""Atom, for readers who want the site to come to them.

One feed per act plus one global feed, assembled as strings rather than through an XML library,
for the same reason the pages are: two builds of one repository state have to produce identical
bytes, and a serialiser free to reorder attributes or pick its own quoting is diff noise in an
artifact people subscribe to. Every interpolated value goes through `markup.escape`, which is
HTML escaping and is also valid XML escaping for a text node and for a quoted attribute value.

An Atom entry's `<id>` is a promise: reissue it and every reader is notified again. So the id is
the address the event is published at, `{site_url}/acts/{slug}/#{entry.key}`, and the site base is
the one part of it that can move. Everything else is pinned: the entry key is the version the
event produced, fixed the moment the corpus publishes that consolidation, so the id is stable
across rebuilds, across re-runs of the loop, and across a change to anything else on the page,
including the day the site grew a page per event, when the act page kept its card at that fragment
and a fresh id would have renotified every subscriber about events none of them missed. Moving the
base reissues every entry in every feed in a single poll, so `--site-url` carries a promise of its
own: it is not changed without the page at `/feeds/` saying that it changed and when.

A `tag:` URI is the other conventional answer and is not used. It would hold an id across a base
move, but it cannot be pasted into a browser, and adopting one would itself reissue every entry
once, which is the whole cost it exists to save.

`<link rel="alternate">` is a different promise, where the entry's content actually is, and that
one moves with the content: it names the event's own page, which carries the verbatim text the
act page no longer does. An id identifies and a link locates, and both are minted in this module
so the two can be read side by side rather than trusted to agree.

An entry is dated by `event_dated`: the in-force date the changes carry, or failing that the
date the event was detected, rendered as midnight UTC of that day. The corpus dates an amendment
to the day and no finer, so a time of day would be invented precision, and it must never be a
clock read, because a rebuild an hour later would restamp every entry and re-notify every reader
about nothing.

A feed's links are absolute by definition, so a feed cannot be written without knowing where the
site will live. That is a build configuration fact rather than a state of the corpus, so
`render_feed` refuses rather than inventing a base; the builder asks `site.site_url` first and
writes no feed files without one, and the feeds page (`pages/feeds_page.py`) then says so in
words.
"""

from __future__ import annotations

from datetime import date

from emendrix import DISCLAIMER
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amenders
from emendrix.site_.attribution import UNATTRIBUTED_FEED_LEAD, unattributed
from emendrix.site_.clocks import event_dated
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.titles import event_words
from emendrix.site_.untouched import (
    TEXTLESS_CLAUSE,
    UNTOUCHED_SENTENCE,
    all_textless,
    untouched,
)
from emendrix.site_.urls import act_href, event_href

__all__ = ["feed_path", "feed_title", "render_feed"]

_MIDNIGHT = "T00:00:00Z"
"""What a date becomes in a feed. The corpus dates events to the day; this invents no more."""

_GLOBAL_PATH = "feeds/all.xml"


def feed_path(act: ActSite | None) -> str:
    """Where one feed lives, relative to the site root. `None` is the global feed."""
    return _GLOBAL_PATH if act is None else f"feeds/{act.slug}.xml"


def feed_title(act: ActSite | None) -> str:
    """One feed's title, unescaped. `None` is the feed of every watched act.

    The document itself and the pages that advertise it read this one function, so a feed
    reader offered a subscription and the document it then fetches cannot be named differently.
    """
    return "emendrix — all watched acts" if act is None else f"emendrix — {act.label}"


def _stamp(value: date) -> str:
    """A date as an Atom timestamp: midnight UTC of the day the corpus named."""
    return f"{value.isoformat()}{_MIDNIGHT}"


def _permalink(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """The `<id>`'s address: the act page, at the event's card. It follows the site base and
    moves only when that base moves, which reissues the entry to every subscriber."""
    return f"{site.site_url}/{act_href(act.slug)}#{entry.key}"


def _event_link(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """The `<link rel="alternate">`'s address: the event's own page, where the content is."""
    return f"{site.site_url}/{event_href(act.slug, entry.key)}"


def _summary(site: SiteInputs, entry: ChangelogEntry) -> str:
    """The counts as the document records them, the in-force dates, and the disclaimer.

    Every number is read off `entry.counts`, which the emit stage computed; nothing here
    recounts anything. A change where the sources differ is counted in the open, in the same
    sentence as the rest, because a feed that quietly reported only the others would be the
    one place on this site where a disagreement disappears. An event no amending act is named
    for keeps its entry whole and says so first, for the same reason: the feed carries every
    event, worded as what it is. An event that touched nothing states the finding as a
    sentence rather than a row of zeros: a subscriber told nothing changed has learned
    something, and the words say it was a finding rather than a failure. An event none of whose
    units carries any text says that in place of the three-way split alone, and keeps both its
    counts either side of it.

    The instruments are named by their numbers rather than by the short names the title
    already used: a summary is where a subscriber checks which instrument this was, and a
    number is what they check it against.
    """
    counts = entry.counts
    in_force = ", ".join(value.isoformat() for value in entry.in_force) or "not stated"
    lead = f"{UNATTRIBUTED_FEED_LEAD} " if unattributed(entry) else ""
    split = (
        TEXTLESS_CLAUSE
        if all_textless(entry)
        else f"{counts.substantive} substantive, {counts.date_only} date-only, "
        f"{counts.textless} with no text"
    )
    counted = (
        UNTOUCHED_SENTENCE
        if untouched(entry)
        else f"{count(counts.touched, 'provision')} touched: {split}, "
        f"{counts.disputed} where sources differ."
    )
    numbers = ", ".join(act.number or act.key for act in amenders(site.amending, entry))
    made_by = f" Amended by {numbers}." if numbers else ""
    return f"{lead}{counted}{made_by} In force {in_force}. {DISCLAIMER}"


def _entry_xml(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """One amendment event as one Atom entry. The id follows the site base; the link follows
    the content.

    The title is the event page's own, minus the site's name, composed in `titles` so a reader
    who meets the event in a feed reader and one who meets it in a search result read the same
    words. A reworded title is not a new event: at a fixed base the id does not move, and only
    a fresh id would renotify anyone.
    """
    ident = escape(_permalink(site, act, entry))
    link = escape(_event_link(site, act, entry))
    title = escape(event_words(site, act, entry))
    return join(
        (
            Html("<entry>"),
            Html(f"<title>{title}</title>"),
            Html(f"<id>{ident}</id>"),
            Html(f'<link rel="alternate" href="{link}"/>'),
            Html(f"<updated>{_stamp(event_dated(entry))}</updated>"),
            Html(f"<summary>{escape(_summary(site, entry))}</summary>"),
            Html("</entry>"),
        ),
        "\n",
    )


def _pairs(site: SiteInputs, act: ActSite | None) -> tuple[tuple[ActSite, ChangelogEntry], ...]:
    """The events this feed carries, newest first, each with the act it belongs to."""
    if act is None:
        return site.recent
    return tuple((act, entry) for entry in act.entries)


def render_feed(site: SiteInputs, act: ActSite | None) -> str:
    """One Atom document, newline-terminated. `None` is the feed of every watched act.

    Deterministic: the entry order is `SiteInputs.recent`'s total order or the act's own,
    every date arrives in the inputs, and nothing is read from the clock or the network.
    """
    if not site.site_url:
        raise ValueError(
            "a feed's links are absolute, so rendering one needs a site URL; "
            "check `site.site_url` before asking for a feed"
        )
    pairs = _pairs(site, act)
    self_url = escape(f"{site.site_url}/{feed_path(act)}")
    alternate = escape(
        f"{site.site_url}/" if act is None else f"{site.site_url}/{act_href(act.slug)}"
    )
    title = escape(feed_title(act))
    updated = max((event_dated(entry) for _, entry in pairs), default=site.generated_on)
    lines = [
        Html('<?xml version="1.0" encoding="utf-8"?>'),
        Html('<feed xmlns="http://www.w3.org/2005/Atom">'),
        Html(f"<title>{title}</title>"),
        Html(f"<id>{self_url}</id>"),
        Html(f'<link rel="self" href="{self_url}"/>'),
        Html(f'<link rel="alternate" href="{alternate}"/>'),
        Html(f"<updated>{_stamp(updated)}</updated>"),
        Html("<author><name>emendrix</name></author>"),
        *(Html(_entry_xml(site, owner, entry)) for owner, entry in pairs),
        Html("</feed>"),
        Html(""),
    ]
    return join(lines, "\n")
