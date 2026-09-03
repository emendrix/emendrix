"""The size of a change as the page prints it: the figure, its sentence, and its decade.

Nothing here is about a diff. `test_diffview.py` asserts that the counts are the rendered
comparison's own; this module asserts what the site does with them, which is print a number,
say what the number counts, and give an index item a weight. The one thing it must never do is
turn either into a word about how much the change matters, and the last test pins that.
"""

from __future__ import annotations

import pytest

from emendrix.site_.diffview import Rendered
from emendrix.site_.magnitude import LINE_TITLE, TITLE, magnitude_html, weight_class
from emendrix.site_.markup import Html
from emendrix.site_.style import STYLE
from emendrix.site_.worddiff import Granularity


def _block(inserted: int, deleted: int, granularity: Granularity | None = "word") -> Rendered:
    return Rendered(
        html=Html("<p></p>"), inserted=inserted, deleted=deleted, granularity=granularity
    )


@pytest.mark.parametrize(
    ("moved", "expected"),
    [
        (0, "mag-1"),
        (99, "mag-1"),
        (100, "mag-2"),
        (999, "mag-2"),
        (1_000, "mag-3"),
        (9_999, "mag-3"),
        (10_000, "mag-4"),
        (4_100_000, "mag-4"),
    ],
)
def test_the_weight_class_is_the_decade_of_characters_both_sides_moved(
    moved: int, expected: str
) -> None:
    """Decades, at their boundaries, over the two sides together.

    The corpus spans an apostrophe to an annex of four million characters, so the buckets are
    decades: a linear scale over that range puts every ordinary provision in one of them.
    """
    assert weight_class(_block(moved, 0)) == expected
    assert weight_class(_block(0, moved)) == expected
    assert weight_class(_block(moved - moved // 2, moved // 2)) == expected


def test_every_class_the_function_can_return_is_styled_by_the_sheet() -> None:
    """A class the sheet does not know is an item that quietly weighs like every other."""
    for decade in range(1, 5):
        assert f".touched .mag-{decade} a {{ font-weight:" in STYLE


def test_the_figure_carries_a_thousands_separator_and_the_minus_sign() -> None:
    """`+1,204 −318`: grouped so a five-figure count is readable, and U+2212 for the minus.

    The hyphen is the character a coordinate slug uses and the two halves are one figure, so
    the sign is the typographic minus and the sheet keeps the pair off a line break.
    """
    rendered = magnitude_html(_block(1_204, 318))
    assert ">+1,204 −318</span>" in rendered
    assert "-318" not in rendered


def test_a_change_that_moved_nothing_says_so_in_one_mark() -> None:
    """Reachable where a unit carries no text at all, which is a real class in the corpus."""
    assert ">±0</span>" in magnitude_html(_block(0, 0, None))


def test_the_title_says_what_was_counted_and_the_line_case_says_it_differently() -> None:
    """The unit changes with the comparison, so the sentence does too, rather than silently.

    A one-sided change names no granularity and gets the same sentence as a word comparison:
    it is phrased over the texts a change carries, which is one of them there.
    """
    assert f'title="{TITLE}"' in magnitude_html(_block(12, 4))
    assert f'title="{TITLE}"' in magnitude_html(_block(12, 0, None))
    assert f'title="{LINE_TITLE}"' in magnitude_html(_block(12, 4, "line"))
    assert "line by line" in LINE_TITLE and "line by line" not in TITLE


def test_the_count_is_never_turned_into_a_word_about_importance() -> None:
    """The constraint the module exists under, asserted over everything it can emit.

    A count of characters is not a reading of legal weight, and the moment a class name or a
    title says `minor` or `substantive` the site is making a claim nobody measured.
    """
    emitted = "".join(
        (TITLE, LINE_TITLE, *(magnitude_html(_block(n, n)) for n in (0, 1, 500, 50_000)))
    )
    for judgement in ("minor", "major", "significant", "substantive", "typographic", "trivial"):
        assert judgement not in emitted.casefold()
