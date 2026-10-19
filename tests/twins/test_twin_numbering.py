"""The numbering-only test: renumbering alone is masked, any other difference is kept.

The substantive cases are differences found between twin pairs of acts written as variants of
each other: a seat, a trade-defence term, a class of addressee, a date. Each must keep a pair
apart however few words it is.
"""

from __future__ import annotations

import pytest

from emendrix.twins.numbering import numbering_only, without_numbering

RENUMBERED = (
    (
        "Article 20 Parts and components 1. Any person who makes available an item referred to "
        "in Article 26 shall comply with point (a) of paragraph 2.",
        "Article 19 Parts and components 1. Any person who makes available an item referred to "
        "in Article 25 shall comply with point (b) of paragraph 3.",
    ),
    (
        "Documents required pursuant to Articles 38 and 39, in accordance with Article 39(3).",
        "Documents required pursuant to Articles 34 and 35, in accordance with Article 35(3).",
    ),
    (
        "Measures adopted pursuant to Articles 95 to 98 and Article 4a.",
        "Measures adopted pursuant to Articles 90 to 93 and Article 4b.",
    ),
    (
        "ANNEX IV EU DECLARATION referred to in Chapter II, Section 2.2 of Part A: (iv) the name",
        "ANNEX V EU DECLARATION referred to in Chapter III, Section 2.3 of Part B: (v) the name",
    ),
)

SUBSTANTIVE = (
    (
        "Article 7 Seat The Authority shall have its seat in Frankfurt am Main.",
        "Article 7 Seat The Authority shall have its seat in Paris.",
    ),
    (
        "Article 3 An imported product is dumped where its price is lower.",
        "Article 3 An imported product is subsidised where its price is lower.",
    ),
    (
        "Article 1 This Regulation applies to financial institutions.",
        "Article 1 This Regulation applies to financial market participants.",
    ),
    (
        "Article 113 It shall apply from 26 May 2021.",
        "Article 106 It shall apply from 26 May 2022.",
    ),
    (
        "Article 52 Manufacturers of class I devices.",
        "Article 48 Manufacturers of class II devices.",
    ),
    (
        "Article 4 as referred to in Regulation (EU) 2017/745.",
        "Article 4 as referred to in Regulation (EU) 2017/746.",
    ),
    ("Article 4 referred to in Articles 38 and 39.", "Article 4 referred to in Articles 38 to 39."),
    (
        "Article 14 in accordance with Article 10(11), and",
        "Article 14 in accordance with Article 10(11) and",
    ),
)


@pytest.mark.parametrize(("a", "b"), RENUMBERED)
def test_texts_differing_in_numbering_alone_are_numbering_only(a: str, b: str) -> None:
    assert numbering_only(a, b)
    assert numbering_only(b, a)


@pytest.mark.parametrize(("a", "b"), SUBSTANTIVE)
def test_any_other_difference_keeps_the_texts_apart(a: str, b: str) -> None:
    assert not numbering_only(a, b)


def test_equal_texts_are_never_numbering_only() -> None:
    text = "Article 12 Implant card"
    assert not numbering_only(text, text)
    assert not numbering_only(text, " Article  12 Implant card ")


def test_a_number_outside_a_numbering_position_is_kept() -> None:
    assert without_numbering("Article 20(3) by 26 May 2021 at EUR 1000") == (
        "Article # by 26 May 2021 at EUR 1000"
    )
    assert without_numbering("in (2021) and (100)") == "in (2021) and (#)"
    assert without_numbering("the device(s) of (EU) origin, point (aa) and (i)") == (
        "the device(s) of (EU) origin, point (#) and (#)"
    )
