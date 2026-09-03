"""One act, whole: every amendment seen for it, newest first, each linking to its evidence.

This is the page the rest of the site exists to point at. It assembles three things and
renders one summary card per event through `act_event`:

- the header, which identifies the act well enough to check it against the official source;
- the index, which is the answer to "has anything ever touched Article 13?" and links each
  coordinate straight into the event page holding its newest change, so it works with
  JavaScript switched off;
- the timeline, newest first, because the question a reader arrives with is what changed
  recently. A card states the event's facts and links to the event's own page, which is where
  the per-change blocks and the verbatim text live: an act with a long history was shipping
  megabytes of collapsed evidence on this one page, and a timeline a phone can hold serves
  the same reader better than a fold it cannot.

Every card still carries `id="{entry.key}"`, because that fragment is the permalink every
feed entry was published under and an address published once never stops resolving.

Anchors are computed once here, in `render_act`, and handed to the index, so a link in the
sidebar and the block it lands on cannot disagree with the event page, which computes the
same tuple through the same one function.

A watched act with no amendments gets a page that says so. Silence and "nothing happened" are
different claims, and only one of them is true here.
"""

from __future__ import annotations

from emendrix.core import ChangeType, ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amenders
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_dated
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.act_event import render_event_summary
from emendrix.site_.pages.prose import pill
from emendrix.site_.seo import act_json_ld
from emendrix.site_.urls import act_href, entry_anchors, event_href, up

__all__ = ["render_act"]

_QUIET = (
    "No amendments to this act have been seen since watching began. A quiet act is a real answer."
)

_DEPTH = 2
"""`acts/<slug>/index.html`: every internal link on this page climbs two directories first.

A literal, because the page's own path is `act_href(act.slug)` and that is not known until
`render_act` has an act. It is the same number as `depth_of(act_href(slug))` for any slug, and
`test_urls.py` pins the two equal.
"""


def _event_link(act: ActSite, entry: ChangelogEntry) -> str:
    """Where one event's own page is, from any link on this act's page.

    Computed in one place because three parts of the page link there, the timeline card, the
    amendments list and the provision index, and three independent constructions is how one
    of them drifts from `_DEPTH`.
    """
    return up(_DEPTH) + event_href(act.slug, entry.key)


def _provisions(act: ActSite, anchors: tuple[tuple[str, ...], ...]) -> list[Html]:
    """Every provision this act's watched history touched, in document order.

    Sorted by `ProvisionLocation.sort_key` rather than by the canonical string, so `AR 10`
    follows `AR 9` and `AN II` follows `AN I`. The link goes to the newest change of that
    location, on the event page holding it: entries arrive newest first, so the first target
    seen is the one to keep.
    """
    locations: dict[str, ProvisionLocation] = {}
    href_of: dict[str, str] = {}
    kinds: dict[str, list[ChangeType]] = {}
    for entry, row in zip(act.entries, anchors, strict=True):
        target = _event_link(act, entry)
        for emitted, anchor in zip(entry.changes, row, strict=True):
            key = emitted.change.location.canonical
            if key not in locations:
                locations[key] = emitted.change.location
                href_of[key] = f"{target}#{anchor}"
            seen = kinds.setdefault(key, [])
            if emitted.change.change_type not in seen:
                seen.append(emitted.change.change_type)
    lines = [Html("<h2>Touched provisions</h2>"), Html("<ul>")]
    for location in sorted(locations.values(), key=lambda item: item.sort_key):
        key = location.canonical
        pills = join((pill(kind) for kind in kinds[key]), " ")
        lines.append(
            Html(f'<li><a href="{escape(href_of[key])}">{escape(location.human)}</a> {pills}</li>')
        )
    lines.append(Html("</ul>"))
    return lines


def _sidebar(act: ActSite, anchors: tuple[tuple[str, ...], ...]) -> Html:
    """The index: provisions and events, each a plain link into an event page. No script.

    The lists sit inside a `<details open>` so a narrow screen can fold the whole index away
    with the browser's own control, which needs no JavaScript. The element carrying the class
    is on the outside, because that is the one the layout makes sticky on a wide screen.
    """
    lines = [
        Html('<aside class="sidebar">'),
        Html("<details open><summary>Index of this act</summary>"),
        *_provisions(act, anchors),
        Html("<h2>Amendments</h2>"),
        Html("<ul>"),
    ]
    lines.extend(
        Html(
            f'<li><a href="{escape(_event_link(act, entry))}">'
            f"{escape(str(entry.from_version))} → "
            f'{escape(str(entry.to_version))}</a> <span class="small muted">'
            f"{event_dated(entry).isoformat()}</span></li>"
        )
        for entry in act.entries
    )
    lines.extend((Html("</ul>"), Html("</details>"), Html("</aside>")))
    return join(lines, "\n")


def _header(act: ActSite, site: SiteInputs) -> list[Html]:
    """The act's name, its official title, the facts that identify it, and where to go next.

    Each link renders only when there is something for it to point at: a feed exists only
    under a configured site URL, and only the composition root knows whether this corpus has
    an official page. A dead link is worse than a missing one, and a line holding no link at
    all is not rendered, so an act with neither keeps a header of three elements.

    The feed's own module says where a feed lives, rather than this page spelling the path a
    second time: the two agreeing today is not the same as their being unable to disagree.

    The H1 is the act's headline, the long form where the watchlist gives one, and the short
    label then opens the facts line so it stays on the page beside the key. The official
    title is rendered whole. The cut at `output.markdown.TITLE_CAP` belongs to a changelog
    heading and to the acts index, where the title is one item in a list; this is the one
    page whose job is to be the act, and the words a title carries past its first hundred
    characters are the ones a reader searched for. It is rendered only when a recorded event
    carried one that says more than either name already does: repeating a label under itself
    would dress a name somebody chose as the title the legislation publishes for itself.

    The identifying facts and the two things a reader can do are separate lines, because they
    are answers to different questions: what this act is called elsewhere, and where to read
    it or subscribe to it. Joined into one chain of separators, the feed sat between a domain
    and a date and read like another fact about the legislation.

    The dated fact names its clock, like every dated line on the site. The header once said
    "reflects the consolidated version of" over whichever date the newest event carried,
    which dressed a detection date as a fact about the official text. An act whose every
    event names no amending act has no amendment to date, and the header says that instead
    of falling silent over a timeline the reader can see is not empty.
    """
    title = act.entries[0].title if act.entries else act.label
    facts: list[Html] = []
    if act.headline != act.label:
        facts.append(escape(act.label))
    facts.append(Html(f"<code>{escape(act.act.key)}</code>"))
    if act.domain:
        facts.append(escape(act.domain))
    dated = act.dated
    if dated is not None:
        facts.append(escape(f"newest amendment {dated.words}"))
    elif act.entries:
        facts.append(escape("recorded events name no amending act"))
    links: list[Html] = []
    if site.site_url:
        href = escape(up(_DEPTH) + feed_path(act))
        links.append(Html(f'<a href="{href}">Atom feed</a>'))
    if act.eurlex_url:
        links.append(Html(f'<a class="nowrap" href="{escape(act.eurlex_url)}">on EUR-Lex</a>'))
    header = [Html(f"<h1>{escape(act.headline)}</h1>")]
    if title != act.headline and title != act.label:
        header.append(Html(f'<p class="official">{escape(title)}</p>'))
    header.append(Html(f'<p class="facts">{join(facts, " · ")}</p>'))
    if links:
        header.append(Html(f'<p class="links">{join(links, " · ")}</p>'))
    return header


def render_act(site: SiteInputs, act: ActSite) -> Html:
    """One act's complete page. Deterministic: same inputs, same bytes, no clock, no network."""
    anchors = tuple(
        entry_anchors(entry.key, [emitted.change.location.canonical for emitted in entry.changes])
        for entry in act.entries
    )
    timeline: list[Html] = [Html('<section class="timeline">')]
    for entry in act.entries:
        timeline.extend(
            render_event_summary(entry, _event_link(act, entry), amenders(site.amending, entry))
        )
    if not act.entries:
        timeline.append(Html(f'<p class="none">{escape(_QUIET)}</p>'))
    timeline.append(Html("</section>"))
    # A quiet act gets no index and no two-column layout: the index would be two headings
    # over two empty lists, and the grid reserves its first column for exactly that index.
    columns = (
        (Html('<div class="layout">'), _sidebar(act, anchors), *timeline, Html("</div>"))
        if act.entries
        else tuple(timeline)
    )
    body = join((*_header(act, site), *columns), "\n")
    # The title names the act the way a person types it and says what the page holds; the
    # short label rides along in brackets so a search for the initialism still reads right.
    named = f"{act.headline} ({act.label})" if act.headline != act.label else act.label
    title = f"{named}: every amendment — emendrix"
    description = (
        f"Every amendment emendrix has seen for {act.headline}. Each event's own page carries "
        "the provision text before and after each change."
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=act_href(act.slug),
        chrome=site.chrome,
        # The act's own feed leads, because a reader subscribing from this page is asking for
        # this act; the global one follows so the offer is never only the narrow one.
        feeds=((feed_path(act), feed_title(act)), (feed_path(None), feed_title(None))),
        structured=(
            act_json_ld(site, act, title=title, description=description) if site.site_url else None
        ),
    )
