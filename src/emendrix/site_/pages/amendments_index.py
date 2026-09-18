"""Every instrument that has amended a watched act, newest first, grouped by year.

The roster the acts index is for acts. A reader who arrives with an instrument in mind, a
directive named in a trade press headline or a regulation a colleague mentioned, lands here and
finds it by name, by number or by its identifier; a reader who arrives with nothing gets a
readable record of what has been happening and when.

Only instruments a committed event names are listed. A short name the watchlist declares for an
instrument nothing has yet been attributed to buys no row, because a row would promise a page
about work the corpus has not recorded.

The year headings are a fact of each instrument's newest event date and not a claim about when
the instrument was adopted, which the site does not know. They exist because three hundred rows
in one list have no rhythm, and each is the year of the row under it, so nothing is grouped by
anything a reader cannot read off the row itself.
"""

from __future__ import annotations

from emendrix.output.markdown import short_title
from emendrix.site_.amending import resolve
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_date, time_html
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import page_masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.instruments import Amended, amended_by
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.trail import AMENDING_ROSTER
from emendrix.site_.urls import act_href, amendment_href, amendments_href, depth_of, up

__all__ = ["render_amendments_index"]

_PATH = amendments_href()
_DEPTH = depth_of(_PATH)
"""`amendments/index.html`: every internal link on this page climbs one directory first."""

_EMPTY = (
    "No committed event names an amending instrument yet. Every event the site has seen was "
    "observed by the text comparison alone."
)


_NAMED_ACTS = 3
"""How many changed acts a row names before it counts the rest."""


def _changed(amended: Amended) -> Html:
    """`Changed A, B and C`: the watched acts this instrument moved, each linking its page.

    Distinct acts in the order of their newest event here, at most `_NAMED_ACTS` of them and
    the rest counted, because one instrument can move a dozen acts and a row is a row. The act
    names are what give a row its sector's scent, which is why this roster is not grouped by
    sector: an amending act that changed acts in two sectors would be listed twice.
    """
    acts: dict[str, ActSite] = {}
    for act, _ in amended:
        acts.setdefault(act.act.key, act)
    links = [
        Html(f'<a href="{escape(up(_DEPTH) + act_href(act.slug))}">{escape(act.label)}</a>')
        for act in list(acts.values())[:_NAMED_ACTS]
    ]
    rest = len(acts) - len(links)
    if rest:
        links.append(Html(f"{rest} more"))
    joined = links[0] if len(links) == 1 else Html(f"{join(links[:-1], ', ')} and {links[-1]}")
    return Html(f"Changed {joined}")


def _row(site: SiteInputs, key: str, amended: Amended) -> Html:
    """One amending act: its name and identifier, what it is about, and what it changed when.

    The subject is the recorded official title, cut by `short_title` with its visible marker,
    because it is what says what the instrument was for, and a short name such as a number
    says nothing about that. The dated words carry their own clock, the one every dated line
    on the site is built from, so a detection date can never be printed as an in-force one.
    """
    instrument = resolve(site.amending, key)
    dated = event_date(amended[0][1])
    subject = (
        Html(f' <span class="sub">{escape(short_title(instrument.title))}</span>')
        if instrument.title
        else Html("")
    )
    return Html(
        f'<li><a href="{escape(up(_DEPTH) + amendment_href(key))}">'
        f"{escape(instrument.short)}</a> "
        f'<span class="ident"><code class="id">{escape(key)}</code></span>{subject} '
        f'<span class="facts">{_changed(amended)} · {dated.clock} {time_html(dated.on)}</span>'
        f"</li>"
    )


def render_amendments_index(site: SiteInputs) -> Html:
    """The instruments roster. Deterministic: same inputs, same bytes, no clock, no network."""
    found = amended_by(site)
    years: dict[int, list[Html]] = {}
    for key, amended in found.items():
        years.setdefault(event_date(amended[0][1]).on.year, []).append(_row(site, key, amended))
    events = sum(len(amended) for amended in found.values())
    lines = [
        *page_masthead("index", "Index", AMENDING_ROSTER, _PATH),
        Html(
            f'<p class="lede muted">{escape(count(len(found), "amending act"))} named by a '
            f"recorded version, between them {escape(count(events, 'version'))} of the watched "
            f"acts. Newest first, by the newest version each one made.</p>"
        ),
    ]
    if not found:
        lines.append(Html(f'<p class="none">{escape(_EMPTY)}</p>'))
    for year in sorted(years, reverse=True):
        lines.append(Html(f"<h2>{year}</h2>"))
        lines.append(Html('<ul class="roster">'))
        lines.extend(years[year])
        lines.append(Html("</ul>"))
    return page(
        title=f"{AMENDING_ROSTER} — emendrix",
        description=(
            "Every instrument a committed event names as having amended a watched act, newest "
            "first, with how many acts each one moved and when."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        section=_PATH,
        feeds=((feed_path(None), feed_title(None)),),
    )
