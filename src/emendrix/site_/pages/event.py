"""One version, whole, on its own address: the evidence the act page points at.

The act page lists this version as a card; this is where a reader who followed that card, a
search result or a feed's `<link rel="alternate">` actually lands. The page is composed of four
parts, each of which lives in its own module: the masthead that says what kind of page this is
and names the version (`identity`), the version's own subject, facts and tally
(`pages/version_masthead.py`), on a long page the line that stays pinned while it scrolls
(`pages/context_bar.py`), and its changes (`pages/act_event.render_event`). The evidence
blocks arrive from the builder rather than being rendered here, because this act's provision
pages show the same blocks and a diff is expensive enough to be worth computing once.

The act's full identity lives one link up, which the trail and the caption both point at.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amenders, by_words
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_date, version_heading
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pages.act_event import render_event
from emendrix.site_.pages.context_bar import context_bar
from emendrix.site_.pages.texts import RenderedText
from emendrix.site_.pages.version_masthead import pager, version_masthead
from emendrix.site_.seo import event_json_ld
from emendrix.site_.titles import event_title
from emendrix.site_.trail import version_trail
from emendrix.site_.untouched import (
    UNTOUCHED_CARD,
    all_textless,
    textless_words,
    untouched,
)
from emendrix.site_.urls import act_href, entry_anchors, event_href, up

__all__ = ["render_event_page"]

_DEPTH = 3
"""`acts/<slug>/<key>/index.html`: every internal link on this page climbs three directories.

A literal for the reason `pages/act.py` carries one: the page's own path needs an act and an
entry to exist, and it is the same number as `depth_of(event_href(slug, key))` for any pair,
which `test_urls.py` pins.
"""


def _header(act: ActSite, entry: ChangelogEntry) -> list[Html]:
    """The trail, the caption naming the page a version of its act, and the version's own H1.

    The H1 is the version's name, its date with its clock, and never the act's heading, which
    is one link up: a version page that carried its act's H1 could not be told from the act
    page by its heading.
    """
    act_page = escape(up(_DEPTH) + act_href(act.slug))
    caption = Html(f'Version · <a href="{act_page}">{escape(act.label)}</a>')
    return masthead("version", version_trail(act, entry), _DEPTH, caption, version_heading(entry))


def render_event_page(
    site: SiteInputs, act: ActSite, entry: ChangelogEntry, texts: tuple[RenderedText, ...]
) -> Html:
    """One event's complete page. Deterministic: same inputs, same bytes, no clock, no network.

    `texts` is the entry's evidence blocks, one per change in the entry's own order, computed
    once by the builder because the provision pages of this act show the same blocks.
    """
    anchors = entry_anchors(
        entry.key, [emitted.change.location.canonical for emitted in entry.changes]
    )
    acts = amenders(site.amending, entry)
    body = join(
        (
            *_header(act, entry),
            *version_masthead(site, act, entry, acts, anchors=anchors),
            *context_bar(act, entry, _DEPTH),
            *render_event(entry, anchors, texts, site.changelogs_url),
            *pager(act, entry, top=False),
        ),
        "\n",
    )
    # The title says what a reader learns by opening the page: the count, the instrument that
    # made the change and the date with its clock. It is composed in `titles` because the feed
    # entry says the same thing and the two may not drift. The description says it again under
    # the act's long form, which is what a snippet is read under, and names the version the
    # text below was read from.
    # It also says what the page holds, so a page with no text on it does not promise any.
    dated = event_date(entry)
    if untouched(entry):
        counted = UNTOUCHED_CARD
    elif all_textless(entry):
        counted = textless_words(entry)
    else:
        counted = f"{count(entry.counts.touched, 'provision')} changed"
    named = by_words(acts)
    title = event_title(site, act, entry)
    holds = (
        "Each provision, with the source that named it"
        if all_textless(entry)
        else "Every changed provision, with the verbatim text before and after"
    )
    description = (
        f"{act.headline}: {counted}{' ' + named if named else ''}, {dated.words}. {holds}, "
        f"from consolidated version {entry.to_version}."
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=event_href(act.slug, entry.key),
        chrome=site.chrome,
        section="acts/",
        # The act's own feed leads, for the reason the act page gives: a reader subscribing
        # from an event of this act is asking for this act.
        feeds=((feed_path(act), feed_title(act)), (feed_path(None), feed_title(None))),
        structured=(
            event_json_ld(site, act, entry, title=title, description=description)
            if site.site_url
            else None
        ),
    )
