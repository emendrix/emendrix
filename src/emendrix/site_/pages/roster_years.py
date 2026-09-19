"""A roster grouped by year: a jump list of its years, and every year but the newest folded.

A roster that lists everything newest first grows by a year's worth of rows every year.
Measured on 2026-09-19 over the published changelogs, the amending-acts roster stood 47,338px
tall on a 390px screen with every row showing, and 9,299px with only the two newest years open.
Filtering would need script or state, and paging would move addresses, so the page stays whole
and shortens by structure: each year is a `<details>` whose summary is the year's heading and
count, the newest `OPEN_YEARS` open. Every row stays in the markup, so nothing is dropped, the
page works with script off, and the search box and the jump list both reach any row.

The helpers know nothing about amending acts beyond the noun they count, so a later roster
grouped by year can use them. The year ids (`y2026`) are addresses from the day they shipped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from emendrix.site_.markup import Html, count, escape

__all__ = ["OPEN_YEARS", "year_anchor", "year_jumps", "year_section"]

OPEN_YEARS: Final = 2
"""How many of the newest years are open when the page loads."""


def year_anchor(year: int) -> str:
    """`y2026`: an id must not start with a digit to be usable as a CSS selector."""
    return f"y{year}"


def year_jumps(counts: Mapping[int, int]) -> list[Html]:
    """The jump list: every year, newest first, with how many rows it holds; empty for none."""
    if not counts:
        return []
    items = "".join(
        f'<li><a href="#{year_anchor(year)}">{year}</a> <span class="small">{counts[year]}</span>'
        "</li>"
        for year in sorted(counts, reverse=True)
    )
    return [Html(f'<nav class="sectors years" aria-label="Years"><ul>{items}</ul></nav>')]


def year_section(year: int, rows: Sequence[Html], *, noun: str, open_: bool) -> list[Html]:
    """One year: its heading and count as the summary, its rows as a roster list."""
    opened = " open" if open_ else ""
    return [
        Html(f'<details class="year" id="{year_anchor(year)}"{opened}>'),
        Html(
            f'<summary><h2>{year} <span class="count">{escape(count(len(rows), noun))}</span>'
            "</h2></summary>"
        ),
        Html('<ul class="roster">'),
        *rows,
        Html("</ul>"),
        Html("</details>"),
    ]
