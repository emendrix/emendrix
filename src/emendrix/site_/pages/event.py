"""One amendment event, whole, on its own address: the evidence the act page points at.

The act page decided this event belongs in the history and gave it a summary card; this is
where a reader who followed that card, a search result or a feed's `<link rel="alternate">`
actually lands. `act_event.render_event` renders the whole body, so this module supplies only
what a page needs beyond its body: enough of the act's identity to know where the reader is,
the shell, and the breadcrumb.

The header names the act and links back to its timeline rather than repeating the act page's
own header: the event's own date is this page's second-level heading, with the version pair
below it, both rendered by the shared card opening, and the act's full identity lives one link
up where it has always been.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amenders, by_words
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_date
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pages.act_event import render_event
from emendrix.site_.seo import event_json_ld
from emendrix.site_.titles import event_title
from emendrix.site_.untouched import UNTOUCHED_CARD, untouched
from emendrix.site_.urls import act_href, entry_anchors, event_href, up

__all__ = ["render_event_page"]

_DEPTH = 3
"""`acts/<slug>/<key>/index.html`: every internal link on this page climbs three directories.

A literal for the reason `pages/act.py` carries one: the page's own path needs an act and an
entry to exist, and it is the same number as `depth_of(event_href(slug, key))` for any pair,
which `test_urls.py` pins.
"""


def _header(act: ActSite) -> list[Html]:
    """Which act this event belongs to, and the way back to its timeline.

    The H1 is the act's headline and the short label opens the facts line when the two
    differ, mirroring the act page, so a reader who knows the act by its initialism still
    sees it. The facts are the act page's identifying ones, minus what only makes sense over
    a whole history: no feed link (the head advertises both feeds already, and the timeline is
    where a reader decides to subscribe) and no "newest amendment" line, which is a fact about
    the act rather than about this event.
    """
    facts: list[Html] = []
    if act.headline != act.label:
        facts.append(escape(act.label))
    facts.extend(
        (
            Html(f"<code>{escape(act.act.key)}</code>"),
            Html(
                f'<a href="{escape(up(_DEPTH) + act_href(act.slug))}">every event for this act</a>'
            ),
        )
    )
    if act.eurlex_url:
        facts.append(Html(f'<a class="nowrap" href="{escape(act.eurlex_url)}">on EUR-Lex</a>'))
    return [
        Html(f"<h1>{escape(act.headline)}</h1>"),
        Html(f'<p class="facts">{join(facts, " · ")}</p>'),
    ]


def render_event_page(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> Html:
    """One event's complete page. Deterministic: same inputs, same bytes, no clock, no network."""
    anchors = entry_anchors(
        entry.key, [emitted.change.location.canonical for emitted in entry.changes]
    )
    acts = amenders(site.amending, entry)
    body = join((*_header(act), *render_event(entry, anchors, acts)), "\n")
    # The title says what a reader learns by opening the page: the count, the instrument that
    # made the change and the date with its clock. It is composed in `titles` because the feed
    # entry says the same thing and the two may not drift. The description says it again under
    # the act's long form, which is what a snippet is read under, and names the version the
    # text below was read from; the version pair itself is under the H2 the body opens with.
    dated = event_date(entry)
    counted = (
        UNTOUCHED_CARD
        if untouched(entry)
        else f"{count(entry.counts.touched, 'provision')} changed"
    )
    named = by_words(acts)
    title = event_title(site, act, entry)
    description = (
        f"{act.headline}: {counted}{' ' + named if named else ''}, {dated.words}. Every changed "
        f"provision, with the verbatim text before and after, from consolidated version "
        f"{entry.to_version}."
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=event_href(act.slug, entry.key),
        chrome=site.chrome,
        # The act's own feed leads, for the reason the act page gives: a reader subscribing
        # from an event of this act is asking for this act.
        feeds=((feed_path(act), feed_title(act)), (feed_path(None), feed_title(None))),
        structured=(
            event_json_ld(site, act, entry, title=title, description=description)
            if site.site_url
            else None
        ),
    )
