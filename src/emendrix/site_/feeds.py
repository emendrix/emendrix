"""Atom, for readers who want the site to come to them.

One feed per act plus one global feed, assembled as strings rather than through an XML library,
for the same reason the pages are: two builds of one repository state have to produce identical
bytes, and a serialiser free to reorder attributes or pick its own quoting is diff noise in an
artifact people subscribe to. Every interpolated value goes through `markup.escape`, which is
HTML escaping and is also valid XML escaping for a text node and for a quoted attribute value.

An Atom entry's `<id>` is a promise: reissue it and every reader is notified again. So the id is
the permalink of the event on this site, `{site_url}/acts/{slug}/#{entry.key}`. The entry key is
the version the event produced, fixed the moment the corpus publishes that consolidation, so the
id is stable across rebuilds, across re-runs of the loop, and across a change to anything else
on the page. A `tag:` URI is the other conventional answer and is rejected deliberately: it
needs a tagging authority, meaning a domain plus a date on which the operator held it, and
nothing here knows either, while the permalink is just as stable and a reader can paste it.

An entry is dated by `event_dated`: the in-force date the changes carry, or failing that the
date the event was detected, rendered as midnight UTC of that day. The corpus dates an amendment
to the day and no finer, so a time of day would be invented precision, and it must never be a
clock read, because a rebuild an hour later would restamp every entry and re-notify every reader
about nothing.

A feed's links are absolute by definition, so a feed cannot be written without knowing where the
site will live. That is a build configuration fact rather than a state of the corpus, so
`render_feed` refuses rather than inventing a base; the builder asks `site.site_url` first and
writes no feed files without one, and `render_feeds_page` then says so in words.
"""

from __future__ import annotations

from datetime import date

from emendrix import DISCLAIMER
from emendrix.output import ChangelogEntry
from emendrix.site_.attribution import UNATTRIBUTED_FEED_LEAD, unattributed
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_dated
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.urls import act_href, depth_of, up

__all__ = ["feed_path", "feed_title", "render_feed", "render_feeds_page"]

_PATH = "feeds/"
_DEPTH = depth_of(_PATH)
"""Where the feeds page lives and, derived from it, how far its internal links climb first.

The feed XML files are addressed absolutely and are unaffected: this pair is `render_feeds_page`'s
alone.
"""

_MIDNIGHT = "T00:00:00Z"
"""What a date becomes in a feed. The corpus dates events to the day; this invents no more."""

_GLOBAL_PATH = "feeds/all.xml"

_UNCONFIGURED = (
    "Feeds are not published for this build because no site URL was configured. A feed's "
    "links have to be absolute, and a guessed address would be worse than none."
)


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
    """The event's own place on this site: the act page, at the event's anchor."""
    return f"{site.site_url}/{act_href(act.slug)}#{entry.key}"


def _summary(entry: ChangelogEntry) -> str:
    """The counts as the document records them, the in-force dates, and the disclaimer.

    Every number is read off `entry.counts`, which the emit stage computed; nothing here
    recounts anything. A disputed change is counted in the open, in the same sentence as the
    rest, because a feed that quietly reported only the undisputed ones would be the one
    place on this site where a disagreement disappears. An event no amending act is named
    for keeps its entry whole and says so first, for the same reason: the feed carries every
    event, worded as what it is.
    """
    counts = entry.counts
    in_force = ", ".join(value.isoformat() for value in entry.in_force) or "not stated"
    lead = f"{UNATTRIBUTED_FEED_LEAD} " if unattributed(entry) else ""
    return (
        f"{lead}{count(counts.touched, 'provision')} touched: {counts.substantive} substantive, "
        f"{counts.date_only} date-only, {counts.disputed} disputed. "
        f"In force {in_force}. {DISCLAIMER}"
    )


def _entry_xml(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> str:
    """One amendment event as one Atom entry, id and link both the permalink."""
    link = escape(_permalink(site, act, entry))
    title = escape(f"{act.label}: {entry.from_version} → {entry.to_version}")
    return join(
        (
            Html("<entry>"),
            Html(f"<title>{title}</title>"),
            Html(f"<id>{link}</id>"),
            Html(f'<link rel="alternate" href="{link}"/>'),
            Html(f"<updated>{_stamp(event_dated(entry))}</updated>"),
            Html(f"<summary>{escape(_summary(entry))}</summary>"),
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


def _feed_list(site: SiteInputs) -> list[Html]:
    """The global feed and one line per act, each pointing at a file the builder writes.

    Every watched act is listed, including one nothing has happened to yet: its feed is an
    empty feed, which is the same real answer its page gives, and a link on the act page that
    resolved to nothing would be worse.
    """
    root = up(_DEPTH)
    lines = [
        Html("<ul>"),
        Html(
            f'<li><a href="{escape(root + _GLOBAL_PATH)}">All watched acts</a> '
            f'<span class="muted">every amendment event this site records</span></li>'
        ),
    ]
    lines.extend(
        Html(
            f'<li><a href="{escape(root + feed_path(act))}">{escape(act.label)}</a> '
            f'<span class="muted">{escape(act.act.key)}</span></li>'
        )
        for act in site.acts
    )
    lines.append(Html("</ul>"))
    return lines


def render_feeds_page(site: SiteInputs) -> Html:
    """The short page that lists the feeds. Same inputs, same bytes, no clock, no network."""
    lines = [
        Html("<h1>Feeds</h1>"),
        Html(
            '<p class="lede">One Atom feed per watched act, plus one carrying every act. An '
            "entry appears when an amendment event is recorded, is identified by the permanent "
            "link to that event, and is never reissued.</p>"
        ),
    ]
    if site.site_url:
        lines.extend(_feed_list(site))
    else:
        lines.append(Html(f'<p class="none">{escape(_UNCONFIGURED)}</p>'))
    return page(
        title="Feeds — emendrix",
        description=(
            "Atom feeds of the amendment events emendrix records: one per watched act, plus a "
            "global feed."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )
