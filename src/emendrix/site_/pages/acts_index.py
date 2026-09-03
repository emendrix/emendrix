"""Every watched act, grouped, with the one fact that decides where a reader goes next.

The roster page. It answers "is this act watched at all?" and "has anything happened to it?",
and it is the whole navigation for a reader without JavaScript, so it lists everything rather
than the recent slice the home page shows.

Grouping comes from the watchlist's `domain` field and nowhere else. Nothing here infers a
subject area from an act's title or its identifier: an operator who has not said which group an
act belongs in gets `Other`, which is honest, while a guess would be a claim this project has
no evidence for. `Other` sorts last for the same reason it exists, that it is the absence of an
answer rather than a group.

An act with no events says so in words. A row that simply had no date would read as a rendering
bug; "no amendments seen" is the actual state, and it is a real answer. An act whose every
recorded event names no amending act is a third state and gets its own words, because "no
amendments seen" would deny events the act's own page shows.

A row is two lines: the name a reader knows the act by, with the label and the key beside it,
then the official title and the dated words. The key joined the row on 2026-09-03, one step
down in size and colour, because an identifier a reader pastes into EUR-Lex should be on the
page that lists the acts and not only on each act's own.

A row's date names its clock, in the words the event cards already use: "in force" is the
corpus's own answer, "detected" is the day emendrix first saw the event. The rule is the one
`home.py` states for its cards; this page once broke it by printing whichever date existed
under "last amended", so a backfill's run day read as an amendment a reader had missed.
"""

from __future__ import annotations

from emendrix.output.markdown import short_title
from emendrix.site_.amending import amenders, by_words
from emendrix.site_.attribution import unattributed
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.urls import act_href, depth_of, up

__all__ = ["render_acts_index"]

_PATH = "acts/"
_DEPTH = depth_of(_PATH)
"""`acts/index.html`: every internal link on this page climbs one directory first."""

_UNGROUPED = "Other"
"""Where an act with no declared domain lands, and the group that always sorts last."""

_QUIET = "no amendments seen"

_UNATTRIBUTED_ONLY = "events recorded, none names an amending act"
"""The row's date fact when every recorded event names no amending act. Not `_QUIET`, because
events were seen; not a date, because dating an "amended" fact by one of them would claim an
amendment the pipeline did not find."""


def _groups(site: SiteInputs) -> list[tuple[str, list[ActSite]]]:
    """The acts by domain, groups alphabetical with the ungrouped bucket last.

    Insertion order inside a group is `collect_site`'s, which is already sorted by label, so
    the whole page is a total order over one repository state and two builds agree by
    construction.
    """
    grouped: dict[str, list[ActSite]] = {}
    for act in site.acts:
        grouped.setdefault(act.domain or _UNGROUPED, []).append(act)
    return sorted(
        grouped.items(), key=lambda item: (item[0] == _UNGROUPED, item[0].casefold(), item[0])
    )


def _row(site: SiteInputs, act: ActSite) -> Html:
    """One act on two lines: what it is called, then what it is and when it last moved.

    The link carries the headline, and the identifiers follow it on the same line: the short
    label when it differs, so a reader scanning for an initialism still finds the row, and the
    key, which was not on this page at all before 2026-09-03. The key is what a reader checks
    a row against and what they paste into EUR-Lex, so it belongs on every row, set one step
    down rather than left to the act's own page.

    The second line carries what the official text calls the act and when it last moved. A
    chain of five facts on one line reads as a column of separators; two lines let the eye run
    down the names. Which of the three parts sit on which line is the stylesheet's decision,
    so the markup keeps a literal space between them: with no stylesheet at all the row still
    reads as words rather than as one run.

    The official title stays cut here: this is a list, and a whole official title per row is a
    wall of text. The instrument that made the newest amendment is named beside its date for
    the opposite reason: it is the fact a reader scanning the roster for one act is looking
    for, and one short name is a name rather than a wall.
    """
    identity: list[Html] = []
    if act.headline != act.label:
        identity.append(escape(act.label))
    identity.append(Html(f'<code class="id">{escape(act.act.key)}</code>'))
    dated = act.dated
    newest = act.newest_amendment
    if dated is not None and newest is not None:
        named = by_words(amenders(site.amending, newest))
        last = f"{dated.words} {named}" if named else dated.words
    elif act.entries:
        last = _UNATTRIBUTED_ONLY
    else:
        last = _QUIET
    sub = [escape(short_title(act.entries[0].title))] if act.entries else []
    sub.append(escape(last))
    return Html(
        f'<li><a href="{escape(up(_DEPTH) + act_href(act.slug))}">{escape(act.headline)}</a> '
        f'<span class="ident">{join(identity, " · ")}</span> '
        f'<span class="sub">{join(sub, " · ")}</span></li>'
    )


def render_acts_index(site: SiteInputs) -> Html:
    """The roster page. Deterministic: same inputs, same bytes, no clock, no network.

    The lede counts the events no amending act is named for apart from the amendment events,
    and prints both numbers even when either is zero: one figure covering both would call
    every recorded event an amendment, which is the claim the split exists to stop.
    """
    events = sum(len(act.entries) for act in site.acts)
    unnamed = sum(1 for act in site.acts for entry in act.entries if unattributed(entry))
    lines = [
        Html("<h1>All watched acts</h1>"),
        Html(
            f'<p class="lede muted">{escape(count(len(site.acts), "act"))} watched, '
            f"{escape(count(events - unnamed, 'amendment event'))} recorded, plus "
            f"{escape(count(unnamed, 'event'))} naming no amending act. Grouping comes from "
            f"the watchlist; nothing here is inferred.</p>"
        ),
    ]
    for domain, acts in _groups(site):
        lines.append(Html(f"<h2>{escape(domain)}</h2>"))
        lines.append(Html('<ul class="roster">'))
        lines.extend(_row(site, act) for act in acts)
        lines.append(Html("</ul>"))
    return page(
        title="All watched acts — emendrix",
        description=(
            "Every act emendrix watches, grouped by the domain the watchlist declares, with "
            "when each one's newest amendment came into force or was detected."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )
