"""One act, whole: every amendment seen for it, newest first, with the evidence attached.

This is the page the rest of the site exists to point at. It assembles three things and
renders one event card through `act_event`:

- the header, which identifies the act well enough to check it against the official source;
- the index, which is the answer to "has anything ever touched Article 13?" and is pure
  anchors, so it works with JavaScript switched off;
- the timeline, newest first, because the question a reader arrives with is what changed
  recently.

Anchors are computed once here, in `render_act`, and handed to both the index and the cards,
so a link in the sidebar and the block it lands on cannot disagree.

A watched act with no amendments gets a page that says so. Silence and "nothing happened" are
different claims, and only one of them is true here.

Where any change on the page carries a disagreement, the timeline opens with one sentence
saying what a disagreement is and that the tool does not resolve it. It belongs here rather
than on the card, because a reader needs it once before the first one and never again; a page
whose sources all agree does not get it at all, since an explanation of something not present
reads as a warning about it.
"""

from __future__ import annotations

from emendrix.core import ChangeType, ProvisionLocation
from emendrix.output.markdown import short_title
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_dated
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.act_event import pill, render_event
from emendrix.site_.seo import act_json_ld
from emendrix.site_.urls import act_href, entry_anchors, up

__all__ = ["render_act"]

_QUIET = (
    "No amendments to this act have been seen since watching began. A quiet act is a real answer."
)

_THREE_SOURCES = (
    "Emendrix checks every change against three independent sources. Where they disagree it "
    "says so rather than picking a winner."
)
"""Said once above the timeline, and only on a page that has a disagreement on it."""

_DEPTH = 2
"""`acts/<slug>/index.html`: every internal link on this page climbs two directories first.

A literal, because the page's own path is `act_href(act.slug)` and that is not known until
`render_act` has an act. It is the same number as `depth_of(act_href(slug))` for any slug, and
`test_urls.py` pins the two equal.
"""


def _provisions(act: ActSite, anchors: tuple[tuple[str, ...], ...]) -> list[Html]:
    """Every provision this act's watched history touched, in document order.

    Sorted by `ProvisionLocation.sort_key` rather than by the canonical string, so `AR 10`
    follows `AR 9` and `AN II` follows `AN I`. The link goes to the newest change of that
    location: entries arrive newest first, so the first anchor seen is the one to keep.
    """
    locations: dict[str, ProvisionLocation] = {}
    anchor_of: dict[str, str] = {}
    kinds: dict[str, list[ChangeType]] = {}
    for entry, row in zip(act.entries, anchors, strict=True):
        for emitted, anchor in zip(entry.changes, row, strict=True):
            key = emitted.change.location.canonical
            if key not in locations:
                locations[key] = emitted.change.location
                anchor_of[key] = anchor
            seen = kinds.setdefault(key, [])
            if emitted.change.change_type not in seen:
                seen.append(emitted.change.change_type)
    lines = [Html("<h2>Touched provisions</h2>"), Html("<ul>")]
    for location in sorted(locations.values(), key=lambda item: item.sort_key):
        key = location.canonical
        pills = join((pill(kind) for kind in kinds[key]), " ")
        lines.append(
            Html(
                f'<li><a href="#{escape(anchor_of[key])}">{escape(location.human)}</a> {pills}</li>'
            )
        )
    lines.append(Html("</ul>"))
    return lines


def _sidebar(act: ActSite, anchors: tuple[tuple[str, ...], ...]) -> Html:
    """The index: provisions and events, both pure anchors into this page. No script.

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
            f'<li><a href="#{escape(entry.key)}">{escape(str(entry.from_version))} → '
            f'{escape(str(entry.to_version))}</a> <span class="small muted">'
            f"{event_dated(entry).isoformat()}</span></li>"
        )
        for entry in act.entries
    )
    lines.extend((Html("</ul>"), Html("</details>"), Html("</aside>")))
    return join(lines, "\n")


def _three_sources(act: ActSite) -> list[Html]:
    """The explainer, once, when this act's history holds at least one disagreement."""
    disagrees = any(emitted.change.disputed for entry in act.entries for emitted in entry.changes)
    return [Html(f'<p class="small muted">{escape(_THREE_SOURCES)}</p>')] if disagrees else []


def _header(act: ActSite, site: SiteInputs) -> list[Html]:
    """The act's name, its official title, and the facts that identify it elsewhere.

    Each link renders only when there is something for it to point at: a feed exists only
    under a configured site URL, and only the composition root knows whether this corpus has
    an official page. A dead link is worse than a missing one.

    The feed's own module says where a feed lives, rather than this page spelling the path a
    second time: the two agreeing today is not the same as their being unable to disagree.

    The official title is rendered only when a recorded event carried one that says more than
    the watchlist label already does. Repeating the label under itself would dress a name
    somebody chose as the title the legislation publishes for itself.

    The dated fact names its clock, like every dated line on the site. The header once said
    "reflects the consolidated version of" over whichever date the newest event carried,
    which dressed a detection date as a fact about the official text. An act whose every
    event names no amending act has no amendment to date, and the header says that instead
    of falling silent over a timeline the reader can see is not empty.
    """
    title = short_title(act.entries[0].title) if act.entries else act.label
    facts = [Html(f"<code>{escape(act.act.key)}</code>")]
    if act.domain:
        facts.append(escape(act.domain))
    if site.site_url:
        href = escape(up(_DEPTH) + feed_path(act))
        facts.append(Html(f'<a href="{href}">Atom feed</a>'))
    if act.eurlex_url:
        facts.append(Html(f'<a href="{escape(act.eurlex_url)}">on EUR-Lex</a>'))
    dated = act.dated
    if dated is not None:
        facts.append(escape(f"newest amendment {dated.words}"))
    elif act.entries:
        facts.append(escape("recorded events name no amending act"))
    header = [Html(f"<h1>{escape(act.label)}</h1>")]
    if title != act.label:
        header.append(Html(f'<p class="official">{escape(title)}</p>'))
    header.append(Html(f'<p class="facts">{join(facts, " · ")}</p>'))
    return header


def render_act(site: SiteInputs, act: ActSite) -> Html:
    """One act's complete page. Deterministic: same inputs, same bytes, no clock, no network."""
    anchors = tuple(
        entry_anchors(entry.key, [emitted.change.location.canonical for emitted in entry.changes])
        for entry in act.entries
    )
    timeline: list[Html] = [Html('<section class="timeline">'), *_three_sources(act)]
    for entry, row in zip(act.entries, anchors, strict=True):
        timeline.extend(render_event(entry, row))
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
    title = f"{act.label} — emendrix"
    description = (
        f"Every amendment emendrix has seen for {act.label}, with the provision text "
        "before and after each change."
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
