"""The two spellings CELLAR writes dates in, and what an unreadable one answers.

`eu/dates.py` holds the one parser for each spelling, and these cases cover both call sites of
each. The impossible-date rows are the point of the file: `2007-02-30` and `20070230` are
well-formed spellings of days that do not exist, and the contract is that they are `None`, a
coverage gap to count, rather than a `ValueError` out of an act's version inventory.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.eu.dates import compact_date, iso_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-07-27", date(2026, 7, 27)),
        ("2007/11/23", date(2007, 11, 23)),
        ("  2026-07-27  ", date(2026, 7, 27)),
        ("2007-02-30", None),
        ("2026-13-01", None),
        ("20260727", None),
        ("not a date", None),
        ("", None),
        (None, None),
    ],
)
def test_both_iso_spellings_parse_and_an_unreadable_one_is_absent(
    raw: str | None, expected: date | None
) -> None:
    assert iso_date(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20271202", date(2027, 12, 2)),
        ("  20271202  ", date(2027, 12, 2)),
        ("20070230", None),
        ("99999999", None),
        ("2027-12-02", None),
        ("2027120", None),
        ("not a date", None),
        ("", None),
        (None, None),
    ],
)
def test_the_compact_formex_spelling_parses_and_an_unreadable_one_is_absent(
    raw: str | None, expected: date | None
) -> None:
    assert compact_date(raw) == expected


def test_the_two_spellings_do_not_read_each_other() -> None:
    """The naming trap: Formex's attribute is called `ISO` and holds the compact spelling.

    Neither function is a superset of the other, so a call site that reached for the wrong one
    would answer `None` on every real value rather than quietly succeeding on some of them.
    """
    assert iso_date("20271202") is None
    assert compact_date("2027-12-02") is None
