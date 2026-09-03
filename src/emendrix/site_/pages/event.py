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
from emendrix.site_.instruments import amended_by
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pages.act_event import render_event
from emendrix.site_.seo import event_json_ld
from emendrix.site_.titles import event_title
from emendrix.site_.untouched import UNTOUCHED_CARD, untouched
from emendrix.site_.urls import act_href, amendment_href, entry_anchors, event_href, up

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


def _instruments(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> list[Html]:
    """Where each named instrument's own page is, and which other watched acts it also moved.

    One line per instrument, under the facts about the act: an event of a consolidation that
    folded several is several lines rather than one, because "also amended" is a different set
    for each of them. The act this page belongs to is left out of that set, it being the page
    the reader is already on.

    The inversion is computed here rather than carried in the inputs, for the reason every
    other derived list on this site is: `SiteInputs` holds what was read off disk, and a
    renderer is a pure function of it.
    """
    found = amended_by(site)
    lines: list[Html] = []
    for instrument in amenders(site.amending, entry):
        facts = [
            Html(
                f'<a href="{escape(up(_DEPTH) + amendment_href(instrument.key))}">'
                f"Everything {escape(instrument.short)} amended</a>"
            )
        ]
        others: dict[str, ActSite] = {
            other.act.key: other
            for other, _ in found.get(instrument.key, ())
            if other.act != act.act
        }
        if others:
            named = [
                Html(
                    f'<a href="{escape(up(_DEPTH) + act_href(other.slug))}">'
                    f"{escape(other.label)}</a>"
                )
                for other in others.values()
            ]
            facts.append(Html(f"also amended {join(named, ', ')}"))
        lines.append(Html(f'<p class="facts">{join(facts, " · ")}</p>'))
    return lines


def _pager(act: ActSite, entry: ChangelogEntry) -> list[Html]:
    """The events either side of this one in the act's own history, each named by its date.

    The act's timeline runs newest first, so the *previous* event in reading order is the
    older one and `rel="next"` points at the newer. Nothing on the page says "previous" or
    "next" in words for that reason: each link carries the date it goes to, with the clock
    that date answers to, so the direction is read rather than deduced. An event at either end
    of the history is simply missing that half.
    """
    keys = [other.key for other in act.entries]
    if entry.key not in keys:
        return []
    at = keys.index(entry.key)
    older = act.entries[at + 1] if at + 1 < len(act.entries) else None
    newer = act.entries[at - 1] if at > 0 else None
    links: list[Html] = []
    if older is not None:
        links.append(
            Html(
                f'<a rel="prev" href="../{escape(older.key)}/">'
                f"← {escape(event_date(older).words)}</a>"
            )
        )
    if newer is not None:
        links.append(
            Html(
                f'<a rel="next" href="../{escape(newer.key)}/">'
                f"{escape(event_date(newer).words)} →</a>"
            )
        )
    if not links:
        return []
    return [
        Html('<nav class="pager" aria-label="Events of this act">'),
        *links,
        Html("</nav>"),
    ]


def render_event_page(site: SiteInputs, act: ActSite, entry: ChangelogEntry) -> Html:
    """One event's complete page. Deterministic: same inputs, same bytes, no clock, no network."""
    anchors = entry_anchors(
        entry.key, [emitted.change.location.canonical for emitted in entry.changes]
    )
    acts = amenders(site.amending, entry)
    body = join(
        (
            *_header(act),
            *_instruments(site, act, entry),
            *render_event(entry, anchors, acts),
            *_pager(act, entry),
        ),
        "\n",
    )
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
