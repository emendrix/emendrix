"""Every watched act, grouped, with the one fact that decides where a reader goes next.

The roster page. It answers "is this act watched at all?" and "has anything happened to it?",
and it is the whole navigation for a reader without JavaScript, so it lists everything rather
than the recent slice the home page shows.

Grouping is `sectors.groups`, the one place that decides which sector an act sits in and in
what order sectors come, so this roster and the feeds page cannot disagree about either. Each
sector's heading carries the id an act page's neighbours line links to, so a reader following
"all 12" from one act lands on the sector rather than at the top of the roster. A jump list of
the sectors opens the page, each with its count, because forty rows under nine headings is a
scroll a reader who knows their sector should not have to make.

The page also says what the roster covers, in two places for two reasons. The lede says what
kinds of act are on it, counted from words the composition root chose, because "67 acts" says
nothing about whether the one a reader came for could be here at all. The paragraph under it
is `pitch.SCOPE`, and it is printed only while the kinds say it is true: it claims no Directive
is watched, and the day one is, the sentence would be the site being wrong about itself.

An act with no events says so in words. A row that simply had no date would read as a rendering
bug; "No amendment recorded" is the actual state, and it is a real answer. It says what the
record holds rather than what anyone has looked for: the site has no "last checked" date and
`emendrix backfill` writes historical transitions, so nothing here is a claim about time. An
act whose every recorded event names no amending act is a third state and gets its own words,
because "No amendment recorded" would deny events the act's own page shows.

A row leads with the name a reader knows the act by, with the label and the key beside it one
step down in size and colour: an identifier a reader pastes into EUR-Lex belongs on the page
that lists the acts and not only on each act's own, but it is not the thing the row is about.
Under the name, the official title, cut visibly, then the dated words.

A row's date names its clock, in the words every version card uses: "in force" is the corpus's
own answer, "detected" is the day emendrix first saw the event. The rule is the one
`clocks.event_date` states; this page once broke it by printing whichever date existed under
"last amended", so a backfill's run day read as an amendment a reader had missed.
"""

from __future__ import annotations

from emendrix.output.markdown import short_title
from emendrix.site_.amending import amenders, by_words
from emendrix.site_.attribution import unattributed
from emendrix.site_.chrome import page
from emendrix.site_.clocks import time_html
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import page_masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pitch import SCOPE, scope_holds
from emendrix.site_.sectors import groups
from emendrix.site_.trail import ACTS_ROSTER
from emendrix.site_.urls import act_href, depth_of, domain_anchor, up

__all__ = ["render_acts_index"]

_PATH = "acts/"
_DEPTH = depth_of(_PATH)
"""`acts/index.html`: every internal link on this page climbs one directory first."""

_QUIET = "No amendment recorded"

_UNATTRIBUTED_ONLY = "Events recorded, none names an amending act"
"""The row's date fact when every recorded event names no amending act. Not `_QUIET`, because
events were seen; not a date, because dating an "amended" fact by one of them would claim an
amendment the pipeline did not find."""


def _kinds_clause(kinds: tuple[tuple[str, int], ...]) -> str:
    """What the roster is made of, as a clause hanging off the count of acts.

    The words and the counts are the composition root's; this page prints them and never
    learns what a kind is. One kind is stated as a property of the whole roster rather than as
    a count repeating the one before it, and a roster of one act is stated as the one act it
    is. With no kinds at all, which is a build with no watchlist, there is nothing to say and
    the clause is empty rather than a guess.
    """
    if not kinds:
        return ""
    if len(kinds) == 1:
        name, number = kinds[0]
        return f", all of them {name}s" if number > 1 else f", a {name}"
    parts = [count(number, name) for name, number in kinds]
    return ", " + " and ".join((", ".join(parts[:-1]), parts[-1]))


def _sectors(grouped: list[tuple[str, list[ActSite]]]) -> Html:
    """The jump list: every sector on the page, in the page's order, with how many acts it holds.

    Each link is the fragment the sector's heading carries, the address an act page's
    neighbours line already uses, so the list adds no address of its own.
    """
    items = "".join(
        f'<li><a href="#{escape(domain_anchor(domain))}">{escape(domain)}</a> '
        f'<span class="small">{len(acts)}</span></li>'
        for domain, acts in grouped
    )
    return Html(f'<nav class="sectors" aria-label="Sectors"><ul>{items}</ul></nav>')


def _row(site: SiteInputs, act: ActSite) -> Html:
    """One act: what it is called, then what the official text calls it and when it last moved.

    The link carries the headline, and the identifiers follow it on the same line, one step
    down: the short label when it differs, so a reader scanning for an initialism still finds
    the row, and the key, which is what a reader checks a row against and pastes into EUR-Lex.
    Which part sits on which line is the stylesheet's decision, so the markup keeps a literal
    space between them: with no stylesheet at all the row still reads as words.

    The official title stays cut, with its visible marker: this is a list, and a whole official
    title per row is a wall of text. The instrument that made the newest amendment is named
    beside its date for the opposite reason: it is the fact a reader scanning the roster for
    one act is looking for, and one short name is a name rather than a wall.
    """
    identity: list[Html] = []
    if act.headline != act.label:
        identity.append(escape(act.label))
    identity.append(Html(f'<code class="id">{escape(act.act.key)}</code>'))
    dated = act.dated
    newest = act.newest_amendment
    if dated is not None and newest is not None:
        named = by_words(amenders(site.amending, newest))
        last = Html(f"Newest amendment {dated.clock} {time_html(dated.on)}")
        if named:
            last = Html(f"{last} {escape(named)}")
    elif act.entries:
        last = escape(_UNATTRIBUTED_ONLY)
    else:
        last = escape(_QUIET)
    sub = (
        Html(f' <span class="sub">{escape(short_title(act.entries[0].title))}</span>')
        if act.entries
        else Html("")
    )
    return Html(
        f'<li><a href="{escape(up(_DEPTH) + act_href(act.slug))}">{escape(act.headline)}</a> '
        f'<span class="ident">{join(identity, " · ")}</span>{sub} '
        f'<span class="facts">{last}</span></li>'
    )


def render_acts_index(site: SiteInputs) -> Html:
    """The roster page. Deterministic: same inputs, same bytes, no clock, no network.

    The lede counts the versions naming no amending act apart from those naming one, and
    prints both numbers even when either is zero: one figure covering both would call every
    recorded version an amendment, which is the claim the split exists to stop.
    """
    events = sum(len(act.entries) for act in site.acts)
    unnamed = sum(1 for act in site.acts for entry in act.entries if unattributed(entry))
    lines = [
        *page_masthead("index", "Index", ACTS_ROSTER, _PATH),
        Html(
            f'<p class="lede muted">{escape(count(len(site.acts), "act"))} watched'
            f"{escape(_kinds_clause(site.kinds))}. "
            f"Versions recorded: {events - unnamed} naming an amending act, {unnamed} naming "
            f"none. Grouping comes from the watchlist; nothing here is inferred.</p>"
        ),
    ]
    if scope_holds(site.kinds):
        lines.append(Html(f"<p>{escape(SCOPE)}</p>"))
    grouped = groups(site.acts)
    if grouped:
        lines.append(_sectors(grouped))
    for domain, acts in grouped:
        lines.append(Html(f'<h2 id="{escape(domain_anchor(domain))}">{escape(domain)}</h2>'))
        lines.append(Html('<ul class="roster">'))
        lines.extend(_row(site, act) for act in acts)
        lines.append(Html("</ul>"))
    return page(
        title=f"{ACTS_ROSTER} — emendrix",
        description=(
            "Every act emendrix watches, grouped by the domain the watchlist declares, with "
            "when each one's newest amendment came into force or was detected."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        section=_PATH,
        feeds=((feed_path(None), feed_title(None)),),
    )
