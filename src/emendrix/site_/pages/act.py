"""One act, whole: every amendment seen for it, newest first, each linking to its evidence.

This is the page the rest of the site exists to point at. It assembles four things and
renders one summary card per event through `act_event`:

- the header, which identifies the act well enough to check it against the official source;
- the index, which is the answer to "has anything ever touched Article 13?" and links each
  coordinate to that provision's own page, its whole history in one place, so it works with
  JavaScript switched off;
- the timeline, newest first, because the question a reader arrives with is what changed
  recently. A card (`pages/version_card.py`) names the version, what made it and its tally,
  and its heading links the version's own page, which is where
  the per-change blocks and the verbatim text live: an act with a long history was shipping
  megabytes of collapsed evidence on this one page, and a timeline a phone can hold serves
  the same reader better than a fold it cannot;
- the list of dates the amended text names, under the timeline, which `act_dates` renders and
  which is the one place on the site that reads this act's dates as a set rather than one
  change at a time. It states facts about text and never a schedule, which is why the words
  around it live in that module beside the list they qualify.

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

from emendrix.site_.amending import amenders
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.history import dates_named
from emendrix.site_.identity import masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.act_dates import dates_section
from emendrix.site_.pages.act_index import ACT_DEPTH, event_link, sidebar
from emendrix.site_.pages.version_card import version_card
from emendrix.site_.seo import act_json_ld
from emendrix.site_.tags import LIST_HELP_WORDS, tags_help
from emendrix.site_.trail import act_trail
from emendrix.site_.urls import act_href, domain_anchor, up

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

_VERSIONS = "Versions, newest first"
"""The timeline's heading, so the page reads as an act, then its versions, then each version."""

_RELATED = 6
"""How many neighbours the related line names before it stops and links the group instead."""

_DEPTH = ACT_DEPTH
"""Where the act page sits, the one number this module and its index share."""


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

    The H1 is the act's headline, the long form where the watchlist gives one, in a masthead
    whose caption says the page is an act and names its domain, which is the only kind the
    inputs carry: `ActSite` has no per-act legal type, and printing one would be inventing it.
    The short label then opens the facts line so it stays on the page beside the key. The official
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
    caption = escape(f"Act · {act.domain}" if act.domain else "Act")
    header = masthead("act", act_trail(act), _DEPTH, caption, escape(act.headline))
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
    if act.entries:
        timeline.extend(
            (
                Html(f'<h2 class="section">{escape(_VERSIONS)}</h2>'),
                tags_help(up(_DEPTH), LIST_HELP_WORDS),
            )
        )
    for entry in act.entries:
        timeline.extend(
            version_card(
                entry,
                event_link(act, entry),
                amenders(site.amending, entry),
                level=2,
                root=up(_DEPTH),
                coded=site.version_dates.get((entry.act, entry.to_version)),
            )
        )
    if not act.entries:
        timeline.append(Html(f'<p class="none">{escape(_quiet_words(act, site))}</p>'))
    timeline.append(Html("</section>"))
    # A quiet act gets no index and no two-column layout: the index would be two headings
    # over two empty lists, and the grid reserves its first column for exactly that index.
    mentions = dates_named(act)
    columns = (
        (
            Html('<div class="layout">'),
            sidebar(act, mentions, site.amending),
            *timeline,
            *dates_section(act, mentions, up(_DEPTH)),
            Html("</div>"),
        )
        if act.entries
        else tuple(timeline)
    )
    body = join((*_header(act, site), *columns), "\n")
    # The title names the act the way a person types it and says what the page holds; the
    # short label rides along in brackets so a search for the initialism still reads right.
    named = f"{act.headline} ({act.label})" if act.headline != act.label else act.label
    title = f"{named}: every version and what changed — emendrix"
    description = (
        f"Every version emendrix has recorded for {act.headline}. Each event's own page carries "
        "the provision text before and after each change."
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=act_href(act.slug),
        chrome=site.chrome,
        section="acts/",
        # The act's own feed leads, because a reader subscribing from this page is asking for
        # this act; the global one follows so the offer is never only the narrow one.
        feeds=((feed_path(act), feed_title(act)), (feed_path(None), feed_title(None))),
        structured=(
            act_json_ld(site, act, title=title, description=description) if site.site_url else None
        ),
    )
