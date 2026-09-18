"""The page that lists the feeds: one per watched act, by sector, plus the one carrying every act.

Split from `feeds.py` on 2026-09-18, when the list grew sector headings. The seam is between
the Atom documents, which that module writes and whose ids are a public promise, and this HTML
page, which only says where they are. Nothing here mints an address: every link is
`feeds.feed_path`, the same function the builder writes the files under.

The acts are grouped by `sectors.groups`, the grouping the acts roster uses, so an act sits
under the same sector heading on both pages. The note about the one time every entry was
reissued follows the list: it is owed to a reader who was handed every entry twice, and it is
not what a reader arriving to subscribe came for.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import page_masthead
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.sectors import groups
from emendrix.site_.urls import depth_of, up

__all__ = ["render_feeds_page"]

_PATH: Final = "feeds/"
_DEPTH: Final = depth_of(_PATH)
"""`feeds/index.html`: every internal link on this page climbs one directory first."""

_UNCONFIGURED: Final = (
    "Feeds are not published for this build because no site URL was configured. A feed's "
    "links have to be absolute, and a guessed address would be worse than none."
)

_LEDE: Final = (
    "One Atom feed per watched act, plus one carrying every act. Atom is a format feed readers "
    "subscribe to. An entry appears when an amendment event is recorded and is identified by "
    "the permanent link to that event."
)

_REISSUE: Final = (
    "Moving this site to its own domain on 2026-09-05 changed those permanent links and "
    "reissued every entry once, so a reader subscribed before that date saw every entry a "
    "second time. Nothing else reissues an entry."
)
"""Published copy about the durability of the ids: the day they moved and what it cost."""


def _feed_list(site: SiteInputs) -> list[Html]:
    """The global feed, then one line per act under its sector, each a file the builder writes.

    Every watched act is listed, including one nothing has happened to yet: its feed is an
    empty feed, which is the same real answer its page gives, and a link on the act page that
    resolved to nothing would be worse.
    """
    root = up(_DEPTH)
    lines = [
        Html(
            f'<ul><li><a href="{escape(root + feed_path(None))}">All watched acts</a> '
            f'<span class="muted">every amendment event this site records</span></li></ul>'
        )
    ]
    for sector, acts in groups(site.acts):
        lines.append(Html(f"<h2>{escape(sector)}</h2>"))
        lines.append(Html("<ul>"))
        lines.extend(
            Html(
                f'<li><a href="{escape(root + feed_path(act))}">{escape(act.label)}</a> '
                f'<span class="muted">{escape(act.act.key)}</span></li>'
            )
            for act in acts
        )
        lines.append(Html("</ul>"))
    return lines


def render_feeds_page(site: SiteInputs) -> Html:
    """The short page that lists the feeds. Same inputs, same bytes, no clock, no network."""
    lines = [
        *page_masthead("prose", "About this site", "Feeds", _PATH),
        Html(f'<p class="lede">{escape(_LEDE)}</p>'),
    ]
    if site.site_url:
        lines.extend(_feed_list(site))
    else:
        lines.append(Html(f'<p class="none">{escape(_UNCONFIGURED)}</p>'))
    lines.append(Html(f'<p class="small muted">{escape(_REISSUE)}</p>'))
    return page(
        title="Feeds — emendrix",
        description=(
            "Atom feeds of the amendment events emendrix records: one per watched act, plus a "
            "global feed."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        section=_PATH,
        feeds=((feed_path(None), feed_title(None)),),
    )
