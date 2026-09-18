"""The act page's index: the provisions its history touched and the versions it has had.

Split from `act.py` on 2026-09-18, when that page's header grew a masthead and the module had
no room left under the size cap. The seam is between what a reader navigates by, this sidebar,
and what the page says about the act, its header and its timeline, which stay there. Nothing
here knows how a card or a header looks; both halves share only where the act page sits.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from emendrix.core import Change, ChangeType
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct, amenders, by_words
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, unattributed
from emendrix.site_.clocks import event_date, time_html
from emendrix.site_.history import DateMention
from emendrix.site_.inputs import ActSite
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.act_dates import ANCHOR, LINK
from emendrix.site_.pages.prose import title_span
from emendrix.site_.tags import kind_tag
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

    Computed in one place because two parts of the page link there, the timeline card and the
    index's versions list, and two independent constructions is how one of them drifts from
    `ACT_DEPTH`.
    """
    return up(ACT_DEPTH) + event_href(act.slug, entry.key)


def _provisions(act: ActSite) -> list[Html]:
    """Every provision this act's watched history touched, in document order.

    Sorted by `ProvisionLocation.sort_key` rather than by the canonical string, so `AR 10`
    follows `AR 9` and `AN II` follows `AN I`. The link goes to that coordinate's own page,
    which is its whole history newest first; it pointed at the newest change on the event page
    holding it until those pages existed, and the anchor was standing in for the history the
    index has always been asking about.

    Each row carries the provision's title from its newest change, the one its history page's
    heading reads, where the title says more than the coordinate. The sheet cuts it to fit; the
    markup carries it whole.
    """
    newest: dict[str, Change] = {}
    kinds: dict[str, list[ChangeType]] = {}
    for entry in act.entries:
        for emitted in entry.changes:
            key = emitted.change.location.canonical
            newest.setdefault(key, emitted.change)
            seen = kinds.setdefault(key, [])
            if emitted.change.change_type not in seen:
                seen.append(emitted.change.change_type)
    lines = [Html("<h2>Touched provisions</h2>"), Html("<ul>")]
    for change in sorted(newest.values(), key=lambda item: item.location.sort_key):
        key = change.location.canonical
        tags = join((kind_tag(kind) for kind in kinds[key]), " ")
        href = escape(up(ACT_DEPTH) + provision_href(act.slug, key))
        lines.append(
            Html(
                f'<li><a href="{href}">{escape(change.location.human)}</a> {tags}'
                f"{title_span(change)}</li>"
            )
        )
    lines.append(Html("</ul>"))
    return lines


def _version(act: ActSite, entry: ChangelogEntry, known: Mapping[str, AmendingAct]) -> Html:
    """One version in the index: its date, the clock's word where it is not in force, its maker.

    Lean on purpose, because an act can have hundreds of versions and every byte here is paid
    once per version: the date as its page's heading says it, and the amending act by its short
    name, with no identifier. `detected` is written out because the clock is part of a version's
    name, and a bare detection date would read as the day the law moved. A version that names
    no maker says so where the corpus says so, and says nothing where it was never asked.
    """
    dated = event_date(entry)
    words = time_html(dated.on) if dated.in_force else Html(f"detected {time_html(dated.on)}")
    made = by_words(amenders(known, entry)) or (UNATTRIBUTED_LABEL if unattributed(entry) else "")
    maker = Html(f' <span class="small">{escape(made)}</span>') if made else Html("")
    return Html(f'<li><a href="{escape(event_link(act, entry))}">{words}</a>{maker}</li>')


def sidebar(
    act: ActSite, mentions: tuple[DateMention, ...], known: Mapping[str, AmendingAct]
) -> Html:
    """The index: provisions and versions, each a plain link to its own page. No script.

    The lists sit inside a `<details open>` so a narrow screen can fold the whole index away
    with the browser's own control, which needs no JavaScript. The element carrying the class
    is on the outside, because that is the one the layout makes sticky on a wide screen.
    `known` is the site's amending acts, which name each version's maker.

    The dates section is a link rather than a list: it is one section with one heading, and
    the index carries it only when the page has one, so the link cannot point at nothing.
    """
    lines = [
        Html('<aside class="sidebar">'),
        Html("<details open><summary>Index of this act</summary>"),
        *_provisions(act),
        Html("<h2>Versions</h2>"),
        Html('<ul class="versions">'),
        *(_version(act, entry, known) for entry in act.entries),
        Html("</ul>"),
    ]
    if mentions:
        lines.append(Html(f'<p class="small"><a href="#{ANCHOR}">{escape(LINK)}</a></p>'))
    lines.extend((Html("</details>"), Html("</aside>")))
    return join(lines, "\n")
