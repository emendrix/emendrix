"""The act page's index: the provisions its history touched and the versions it has had.

Split from `act.py` on 2026-09-18, when that page's header grew a masthead and the module had
no room left under the size cap. The seam is between what a reader navigates by, this sidebar,
and what the page says about the act, its header and its timeline, which stay there. Nothing
here knows how a card or a header looks; both halves share only where the act page sits.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import ChangeType, ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.clocks import event_dated
from emendrix.site_.history import DateMention
from emendrix.site_.inputs import ActSite
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.act_dates import ANCHOR, LINK
from emendrix.site_.pages.prose import pill
from emendrix.site_.urls import event_href, provision_href, up

__all__ = ["ACT_DEPTH", "event_link", "sidebar"]

ACT_DEPTH: Final = 2
"""`acts/<slug>/index.html`: every internal link on this page climbs two directories first.

A literal, because the page's own path is `act_href(act.slug)` and that is not known until
`render_act` has an act. It is the same number as `depth_of(act_href(slug))` for any slug, and
`test_urls.py` pins the two equal.
"""


def event_link(act: ActSite, entry: ChangelogEntry) -> str:
    """Where one event's own page is, from any link on this act's page.

    Computed in one place because three parts of the page link there, the timeline card, the
    amendments list and the provision index, and three independent constructions is how one
    of them drifts from `ACT_DEPTH`.
    """
    return up(ACT_DEPTH) + event_href(act.slug, entry.key)


def _provisions(act: ActSite) -> list[Html]:
    """Every provision this act's watched history touched, in document order.

    Sorted by `ProvisionLocation.sort_key` rather than by the canonical string, so `AR 10`
    follows `AR 9` and `AN II` follows `AN I`. The link goes to that coordinate's own page,
    which is its whole history newest first; it pointed at the newest change on the event page
    holding it until those pages existed, and the anchor was standing in for the history the
    index has always been asking about.
    """
    locations: dict[str, ProvisionLocation] = {}
    kinds: dict[str, list[ChangeType]] = {}
    for entry in act.entries:
        for emitted in entry.changes:
            key = emitted.change.location.canonical
            locations.setdefault(key, emitted.change.location)
            seen = kinds.setdefault(key, [])
            if emitted.change.change_type not in seen:
                seen.append(emitted.change.change_type)
    lines = [Html("<h2>Touched provisions</h2>"), Html("<ul>")]
    for location in sorted(locations.values(), key=lambda item: item.sort_key):
        key = location.canonical
        pills = join((pill(kind) for kind in kinds[key]), " ")
        href = escape(up(ACT_DEPTH) + provision_href(act.slug, key))
        lines.append(Html(f'<li><a href="{href}">{escape(location.human)}</a> {pills}</li>'))
    lines.append(Html("</ul>"))
    return lines


def sidebar(act: ActSite, mentions: tuple[DateMention, ...]) -> Html:
    """The index: provisions and events, each a plain link into an event page. No script.

    The lists sit inside a `<details open>` so a narrow screen can fold the whole index away
    with the browser's own control, which needs no JavaScript. The element carrying the class
    is on the outside, because that is the one the layout makes sticky on a wide screen.

    The dates section is a link rather than a list: it is one section with one heading, and
    the index carries it only when the page has one, so the link cannot point at nothing.
    """
    lines = [
        Html('<aside class="sidebar">'),
        Html("<details open><summary>Index of this act</summary>"),
        *_provisions(act),
        Html("<h2>Amendments</h2>"),
        Html("<ul>"),
    ]
    lines.extend(
        Html(
            f'<li><a href="{escape(event_link(act, entry))}">'
            f"{escape(str(entry.from_version))} → "
            f'{escape(str(entry.to_version))}</a> <span class="small muted">'
            f"{event_dated(entry).isoformat()}</span></li>"
        )
        for entry in act.entries
    )
    lines.append(Html("</ul>"))
    if mentions:
        lines.append(Html(f'<p class="small"><a href="#{ANCHOR}">{escape(LINK)}</a></p>'))
    lines.extend((Html("</details>"), Html("</aside>")))
    return join(lines, "\n")
