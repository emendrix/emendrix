"""The forward list on Dates ahead: its rows, and the headings they are gathered under.

Split from `pages.dates` along the seam between the list and the page around it. This module
knows what one row says and how rows are grouped; `pages.dates` knows which blocks the page has
and in what order they come. A row is also what the folded window of passed dates prints, so the
row lives here and the page imports it.

The list is gathered by sector first and by year second, because the reader it serves arrives
asking what their own sector's texts name. A sector is `sectors.sector_of`, the grouping the
acts roster uses, and sectors come in `sectors.sector_key` order, so the two pages cannot
disagree about where an act sits or which sector comes first. The rows themselves are the same
sentences in the same date order; only the headings above them are new.
"""

from __future__ import annotations

from datetime import date
from itertools import groupby
from typing import Final

from emendrix.output import ChangelogEntry
from emendrix.site_.clocks import event_date
from emendrix.site_.history import MOVED, CrossActMention
from emendrix.site_.inputs import ActSite
from emendrix.site_.markup import Html, escape
from emendrix.site_.sectors import sector_key, sector_of
from emendrix.site_.urls import act_href, domain_anchor, event_href, provision_href

__all__ = [
    "FAR_YEARS",
    "QUALIFIER",
    "RANGE_ANCHOR",
    "by_sector",
    "event_link",
    "row",
    "sector_anchor",
    "sector_nav",
]


def event_link(entry: ChangelogEntry, anchor: str, act: ActSite, root: str) -> Html:
    """The dated words of the event that moved a date, linked to the change block that did it.

    The anchor is the one the event page publishes for that change, carried on the mention
    rather than recomputed, so a row lands on the block a reader can check the date in.
    """
    href = root + event_href(act.slug, entry.key)
    return Html(f'<a href="{escape(href)}#{escape(anchor)}">{escape(event_date(entry).words)}</a>')


def row(one: CrossActMention, root: str) -> Html:
    """One mention: the date, the direction, the provision, the act and the event that moved it.

    Every row is a sentence in the record's own voice, and both of its coordinates are links, so
    it can be checked against the verbatim text in two clicks: the provision link opens that
    coordinate's whole history and the event link opens the change block that moved the date.
    """
    act = one.act
    mention = one.mention
    provision = root + provision_href(act.slug, mention.location.canonical)
    superseded = Html("")
    if one.superseded_by is not None:
        later = event_link(one.superseded_by.entry, one.superseded_by.anchor, act, root)
        superseded = Html(
            f'<span class="muted">; a later amendment {later} removed it from that '
            f"provision's text</span>"
        )
    return Html(
        f'<li><span class="on">{escape(mention.on.isoformat())}</span> '
        f"{escape(MOVED[mention.added])} "
        f'<a href="{escape(provision)}">{escape(mention.location.human)}</a> of '
        f'<a href="{escape(root + act_href(act.slug))}">{escape(act.label)}</a>, by the '
        f"amendment {event_link(mention.entry, mention.anchor, act, root)}{superseded}</li>"
    )


FAR_YEARS: Final = 100
"""How far past the build year a reading may fall before its year heading is qualified.

A year more than a century out is not a plausible date on its face for a text in force now, so
it is shown exactly as the source's date markup read it and its heading says so, linking the
panel sentence that states the range the markup produced. Nothing is clipped or moved: the row
stays under its own year, because a reading that looks wrong is still what was measured.
"""

QUALIFIER: Final = "as the source's date markup reads it"
"""The words a far year heading carries, so the heading is not taken for a claim about that year."""

RANGE_ANCHOR: Final = "date-range"
"""The id of the panel sentence giving the range of readings, which every qualifier links."""


def sector_anchor(sector: str) -> str:
    """The id a sector's heading carries on this page, prefixed so it never collides with the
    bare anchors the acts roster owns for the same sectors."""
    return f"dates-{domain_anchor(sector)}"


def _by_sector(
    mentions: tuple[CrossActMention, ...],
) -> list[tuple[str, list[CrossActMention]]]:
    """The mentions by sector, sectors in `sector_key` order, dates in the order they arrived.

    `sorted` is stable, so the date order the mentions came in survives inside each sector.
    """
    ordered = sorted(mentions, key=lambda one: sector_key(sector_of(one.act)))
    return [
        (sector, list(group))
        for sector, group in groupby(ordered, key=lambda one: sector_of(one.act))
    ]


def sector_nav(mentions: tuple[CrossActMention, ...]) -> Html:
    """The jump list: every sector with a row in the forward list, and how many rows it has."""
    items = "".join(
        f'<li><a href="#{escape(sector_anchor(sector))}">{escape(sector)}</a> '
        f'<span class="small">{len(rows)}</span></li>'
        for sector, rows in _by_sector(mentions)
    )
    return Html(f'<nav class="sectors" aria-label="Sectors on this page"><ul>{items}</ul></nav>')


def _year_heading(year: int, built: date) -> Html:
    """A year's heading, qualified only when the reading is too far out to take at face value."""
    if year <= built.year + FAR_YEARS:
        return Html(f"<h4>{escape(str(year))}</h4>")
    return Html(
        f'<h4>{escape(str(year))} <span class="small"><a href="#{RANGE_ANCHOR}">'
        f"{escape(QUALIFIER)}</a></span></h4>"
    )


def by_sector(mentions: tuple[CrossActMention, ...], root: str, built: date) -> list[Html]:
    """The forward list, one heading per sector with rows, then one per year present in it.

    No buckets and no folding of the far end: a reading four centuries out gets its own heading
    and is visible, which is what "publish numbers as measured" means for a date the source's
    own markup produced. Past `FAR_YEARS` the heading says whose reading it is.
    """
    lines: list[Html] = []
    for sector, group in _by_sector(mentions):
        lines.append(Html(f'<h3 id="{escape(sector_anchor(sector))}">{escape(sector)}</h3>'))
        for year, rows in groupby(group, key=lambda one: one.mention.on.year):
            lines.extend((_year_heading(year, built), Html("<ul>")))
            lines.extend(row(one, root) for one in rows)
            lines.append(Html("</ul>"))
    return lines
