"""How much of a provision moved, in characters, and the weight that gives it in an index.

A change block has always said what kind of change it was; since 2026-09-03 it also says how
big it was, as the characters the comparison on that page marked inserted and the characters it
marked deleted. The number is taken from that comparison and never from a second one, so the
figure beside a block and the marks inside it cannot disagree, and the most expensive call the
site build makes is not made twice.

**It is a count of characters and not a reading of legal weight**, and the site says so
wherever it prints one. The title on every count states what was counted, the label beside the
totals says `characters`, and nothing here turns a number into a word like minor, typographic
or substantive. Two characters can move a deadline by sixteen months, and two thousand can
renumber a list. The site's own `substantive` / `date-only` split is a different fact, computed
in the pipeline from what the change did rather than from how much of it there is.

The class names are decades and say only that: under a hundred characters, under a thousand,
under ten thousand, and above. Decades because that is the span the corpus covers, from a
single apostrophe to an annex of two million characters, and a linear scale over that range
would put every ordinary provision in one bucket. The index spends weight on them and no
colour: colour is spent on diffs, disputes and links, and a heavier link is still a link.

The unit follows the comparison. Above `worddiff.LINE_TOKEN_CEILING` two texts are compared
line by line, so a line one word of which moved is counted whole, and the title says that
rather than leaving a reader to assume words.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.diffview import Rendered
from emendrix.site_.markup import Html, escape

__all__ = ["magnitude_html", "weight_class"]

TITLE: Final = "characters inserted and deleted between the stored texts this change carries"
"""What the count is, on every count the site prints, whatever branch the evidence took.

Phrased over the texts a change *carries* rather than over two of them, because a change with
text on one side has one and the count is then that text whole; the sentence stays true of an
insertion, of a deletion and of a unit no text-carrying signal saw.
"""

LINE_TITLE: Final = (
    "characters in the lines that changed, compared line by line because the texts are too "
    "large to compare word by word"
)
"""Said rather than left to be inferred, for the reason the diff block itself says it.

At line granularity a whole line counts because one word in it moved, so a one-word change in a
table can read as thousands of characters. Silently switching units would make the two numbers
on one page mean different things without saying so.
"""

_NOTHING: Final = "±0"
"""Both sides zero: nothing was inserted and nothing deleted, in one mark rather than `+0 -0`.

Reachable only where the change carries no text at all on either side, a unit named by a signal
that carries none. Two identical texts would also read this way and the diff does not emit them.
"""

_DECADES: Final[tuple[tuple[int, str], ...]] = ((100, "mag-1"), (1_000, "mag-2"), (10_000, "mag-3"))
"""Each decade's ceiling and its class. Anything at or above the last one is `mag-4`."""


def magnitude_html(rendered: Rendered) -> Html:
    """`+1,204 −318`, with the sentence saying what those characters are.

    The minus is U+2212 rather than a hyphen, the two halves being one figure and the hyphen
    being the character a coordinate uses; `white-space: nowrap` in the sheet keeps them on one
    line, since `+1,204` alone on the end of a row would read as the whole count.
    """
    title = LINE_TITLE if rendered.granularity == "line" else TITLE
    moved = (
        _NOTHING
        if not rendered.inserted and not rendered.deleted
        else f"+{rendered.inserted:,} −{rendered.deleted:,}"
    )
    return Html(f'<span class="mag" title="{escape(title)}">{escape(moved)}</span>')


def weight_class(rendered: Rendered) -> str:
    """Which decade of characters this change moved, as the class an index item carries.

    Over both sides together: a provision half of which was rewritten moved twice as much text
    as one half of which was deleted, and the index is a map of where the text moved.
    """
    moved = rendered.inserted + rendered.deleted
    for ceiling, name in _DECADES:
        if moved < ceiling:
            return name
    return "mag-4"
