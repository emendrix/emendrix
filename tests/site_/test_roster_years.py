"""A roster grouped by year: one jump link per year, each to its own folded section.

The helpers are page-agnostic, so they are asserted here on bare rows; the amending-acts
roster's own use of them is asserted with the rest of that page.
"""

from __future__ import annotations

import re

from emendrix.site_.markup import Html, join
from emendrix.site_.pages.roster_years import OPEN_YEARS, year_jumps, year_section
from emendrix.site_.style import STYLE


def test_no_year_gives_no_jump_list() -> None:
    assert year_jumps({}) == []


def test_one_year_is_one_link_to_its_own_section() -> None:
    nav = join(year_jumps({2026: 1}), "\n")
    assert nav == (
        '<nav class="sectors years" aria-label="Years"><ul>'
        '<li><a href="#y2026">2026</a> <span class="small">1</span></li></ul></nav>'
    )
    section = join(year_section(2026, [Html("<li>one</li>")], noun="row", open_=True), "\n")
    assert section == (
        '<details class="year" id="y2026" open>\n'
        '<summary><h2>2026 <span class="count">1 row</span></h2></summary>\n'
        '<ul class="roster">\n<li>one</li>\n</ul>\n</details>'
    )


def test_the_jump_list_runs_newest_first_and_counts_each_year() -> None:
    nav = join(year_jumps({2019: 4, 2026: 14, 2024: 2}), "")
    assert re.findall(r'href="#y(\d+)">\d+</a> <span class="small">(\d+)<', nav) == [
        ("2026", "14"),
        ("2024", "2"),
        ("2019", "4"),
    ]


def test_a_closed_year_keeps_every_row_in_the_markup() -> None:
    rows = [Html(f"<li>{n}</li>") for n in range(3)]
    section = join(year_section(2019, rows, noun="amending act", open_=False), "\n")
    assert section.startswith('<details class="year" id="y2019">\n')
    assert '<span class="count">3 amending acts</span>' in section
    assert section.count("<li>") == 3


def test_two_years_are_open() -> None:
    assert OPEN_YEARS == 2


def test_the_sheet_draws_the_disclosure_mark_with_empty_alternative_text() -> None:
    """The escape reaches the sheet as CSS's, not swallowed by Python's as an octal one."""
    assert 'details.year h2::before { content: "\\25B8"; content: "\\25B8" / "";' in STYLE
    assert "details.year > summary::-webkit-details-marker { display: none; }" in STYLE
