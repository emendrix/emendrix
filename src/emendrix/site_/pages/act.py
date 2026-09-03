"""One act, whole: every amendment seen for it, newest first, each linking to its evidence.

This is the page the rest of the site exists to point at. It assembles three things and
renders one summary card per event through `act_event`:

- the header, which identifies the act well enough to check it against the official source;
- the index, which is the answer to "has anything ever touched Article 13?" and links each
  coordinate to that provision's own page, its whole history in one place, so it works with
  JavaScript switched off;
- the timeline, newest first, because the question a reader arrives with is what changed
  recently. A card states the event's facts and links to the event's own page, which is where
  the per-change blocks and the verbatim text live: an act with a long history was shipping
  megabytes of collapsed evidence on this one page, and a timeline a phone can hold serves
  the same reader better than a fold it cannot.

Every card still carries `id="{entry.key}"`, because that fragment is the permalink every
feed entry was published under and an address published once never stops resolving.

A watched act with no amendments gets a page that says so. Silence and "nothing happened" are
different claims, and only one of them is true here. Such a page is not empty of facts: it
carries the act's identifiers, the address of its text as published, its feed, and the other
acts the watchlist puts in its group, which is everything the record holds about an act nothing
has yet happened to. What it never carries is a date, because the site has none: when an act
was last checked lives in the poller's own state file and reaches no committed artifact.
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
from emendrix.site_.urls import act_href, domain_anchor, event_href, provision_href, up

__all__ = ["render_act"]

_QUIET = (
    "No amendment event is recorded for this act: the changelog this site is built from holds "
    "no transition between two versions of it."
)
"""What an empty timeline means, said as a fact about the record rather than about time.

It carries no date, because the site has none to carry: the day an act was last checked lives
in the poller's own state file, never in the changelog repository, and nothing under `site_/`
reads a clock. "Since watching began" went with it on 2026-09-03, for a second reason:
`emendrix backfill` writes historical transitions, so an empty timeline is a statement about
what has been recorded and not about when watching started.
"""

_QUIET_PUBLISHED = "Its text as published is on EUR-Lex"
_QUIET_FEED = "the feed above will carry the first event the day one is recorded"
"""The two things a reader can still do here, each said only where it can be done: a build with
no site URL mints no feed, and an act outside a corpus with published documents has no link."""

_QUIET_TAIL = "A quiet act is a real answer."

_RELATED = 6
"""How many neighbours the related line names before it stops and links the group instead."""

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
        href = escape(up(_DEPTH) + provision_href(act.slug, key))
        lines.append(Html(f'<li><a href="{href}">{escape(location.human)}</a> {pills}</li>'))
    lines.append(Html("</ul>"))
    return lines


def _sidebar(act: ActSite) -> Html:
    """The index: provisions and events, each a plain link into an event page. No script.

    The lists sit inside a `<details open>` so a narrow screen can fold the whole index away
    with the browser's own control, which needs no JavaScript. The element carrying the class
    is on the outside, because that is the one the layout makes sticky on a wide screen.
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
            f'<li><a href="{escape(_event_link(act, entry))}">'
            f"{escape(str(entry.from_version))} → "
            f'{escape(str(entry.to_version))}</a> <span class="small muted">'
            f"{event_dated(entry).isoformat()}</span></li>"
        )
        for entry in act.entries
    )
    lines.extend((Html("</ul>"), Html("</details>"), Html("</aside>")))
    return join(lines, "\n")


def _quiet_words(act: ActSite, site: SiteInputs) -> str:
    """What a page with an empty timeline says, built from the facts this build actually has.

    Three sentences at most: what the record holds, what a reader can do about it, and the
    site's own answer to the question. The middle one is assembled from parts because each of
    its halves depends on something the build may not have been given, and a sentence naming a
    feed that was never written or a document that has no address would be the page making up
    an offer, which is the one thing a page about silence must not do.
    """
    offers = [_QUIET_PUBLISHED] if act.published_url else []
    if site.site_url:
        offers.append(_QUIET_FEED)
    middle = f"{', and '.join(offers)}. " if offers else ""
    return f"{_QUIET} {middle[:1].upper() + middle[1:]}{_QUIET_TAIL}"


def _related(site: SiteInputs, act: ActSite) -> list[Html]:
    """The other watched acts in this act's domain, and the roster group they all sit in.

    A domain is the watchlist's own label, so this line infers nothing: it says which other
    acts an operator put in the same group, which is the question a reader who came here for
    one act asks next. An act alone in its domain gets no line, because a list of no
    neighbours introduced by "also watched" is a heading over nothing.

    The order is `collect_site`'s, which is the acts index's order too, so the two agree
    without a second sort. Past `_RELATED` names the line stops and links the group's own
    heading on the roster instead: a domain of forty acts is a page of its own, and this is a
    line at the foot of a header.
    """
    if not act.domain:
        return []
    group = [item for item in site.acts if item.domain == act.domain]
    others = [item for item in group if item.act != act.act]
    if not others:
        return []
    links = [
        Html(f'<a href="{escape(up(_DEPTH) + act_href(item.slug))}">{escape(item.label)}</a>')
        for item in others[:_RELATED]
    ]
    if len(others) > _RELATED:
        href = escape(f"{up(_DEPTH)}acts/#{domain_anchor(act.domain)}")
        links.append(Html(f'<a href="{href}">all {escape(str(len(group)))} →</a>'))
    return [
        Html(f'<p class="related">Also watched in {escape(act.domain)}: {join(links, " · ")}</p>')
    ]


def _header(act: ActSite, site: SiteInputs) -> list[Html]:
    """The act's name, its official title, the facts that identify it, and where to go next.

    Each link renders only when there is something for it to point at: a feed exists only
    under a configured site URL, and only the composition root knows whether this corpus has
    an official page. A dead link is worse than a missing one, and a line holding no link at
    all is not rendered, so an act with neither keeps a header of three elements.

    The official document is named under one of two labels, never both, because the newest
    consolidated version and the act as it was published are two documents. The consolidated
    one leads where an event resolved it, and the act as published stands in where none did,
    which is the only one an act nothing has happened to can have. The neighbours line closes
    the header, after the links, because it is about the roster rather than about this act.

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
    elif act.published_url:
        links.append(
            Html(
                f'<a href="{escape(act.published_url)}">as published, '
                f'<span class="nowrap">on EUR-Lex</span></a>'
            )
        )
    header = [Html(f"<h1>{escape(act.headline)}</h1>")]
    if title != act.headline and title != act.label:
        header.append(Html(f'<p class="official">{escape(title)}</p>'))
    header.append(Html(f'<p class="facts">{join(facts, " · ")}</p>'))
    if links:
        header.append(Html(f'<p class="links">{join(links, " · ")}</p>'))
    header.extend(_related(site, act))
    return header


def render_act(site: SiteInputs, act: ActSite) -> Html:
    """One act's complete page. Deterministic: same inputs, same bytes, no clock, no network."""
    timeline: list[Html] = [Html('<section class="timeline">')]
    for entry in act.entries:
        timeline.extend(
            render_event_summary(entry, _event_link(act, entry), amenders(site.amending, entry))
        )
    if not act.entries:
        timeline.append(Html(f'<p class="none">{escape(_quiet_words(act, site))}</p>'))
    timeline.append(Html("</section>"))
    # A quiet act gets no index and no two-column layout: the index would be two headings
    # over two empty lists, and the grid reserves its first column for exactly that index.
    columns = (
        (Html('<div class="layout">'), _sidebar(act), *timeline, Html("</div>"))
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
