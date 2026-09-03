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

from emendrix.site_.amending import resolve
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_date
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.instruments import Amended, amended_by
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.urls import amendment_href, amendments_href, depth_of, up

__all__ = ["render_amendments_index"]

_PATH = amendments_href()
_DEPTH = depth_of(_PATH)
"""`amendments/index.html`: every internal link on this page climbs one directory first."""

_EMPTY = (
    "No committed event names an amending instrument yet. Every event the site has seen was "
    "observed by the text comparison alone."
)


def _row(site: SiteInputs, key: str, amended: Amended) -> Html:
    """One instrument: the name it is known by, its identifier, and what it has done.

    Two lines like the acts index's rows, and for the same reason: the name reads down the
    column and the facts sit under it. The dated words carry their own clock, the one every
    dated line on the site is built from, so a detection date can never be printed as an
    in-force one.
    """
    instrument = resolve(site.amending, key)
    acts = {act.act.key for act, _ in amended}
    dated = event_date(amended[0][1])
    sub = [escape(count(len(acts), "watched act")), escape(dated.words)]
    return Html(
        f'<li><a href="{escape(up(_DEPTH) + amendment_href(key))}">'
        f"{escape(instrument.short)}</a> "
        f'<span class="ident"><code class="id">{escape(key)}</code></span> '
        f'<span class="sub">{join(sub, " · ")}</span></li>'
    )


def render_amendments_index(site: SiteInputs) -> Html:
    """The instruments roster. Deterministic: same inputs, same bytes, no clock, no network."""
    found = amended_by(site)
    years: dict[int, list[Html]] = {}
    for key, amended in found.items():
        years.setdefault(event_date(amended[0][1]).on.year, []).append(_row(site, key, amended))
    events = sum(len(amended) for amended in found.values())
    lines = [
        Html("<h1>Amending instruments</h1>"),
        Html(
            f'<p class="lede muted">{escape(count(len(found), "instrument"))} named by a '
            f"committed event, between them {escape(count(events, 'amendment event'))} on the "
            f"watched acts. Newest first by the newest event each one produced.</p>"
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
        title="Amending instruments — emendrix",
        description=(
            "Every instrument a committed event names as having amended a watched act, newest "
            "first, with how many acts each one moved and when."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )
