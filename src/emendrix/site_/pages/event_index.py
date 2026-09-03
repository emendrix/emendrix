"""The list of provisions an event's page opens with, and the count of blocks it appears above.

Split out of `act_event` on 2026-09-03, when the index gained a label and the page around it
gained a column to put the index in. The seam is the one the markup already draws: the index is
a map of the page rather than part of it, it is the only thing on an event page that reads the
whole entry at once, and it is what has to change when the map learns to say more about a block
than that the block exists.

Two decisions carry it:

- **It is a table of contents, not a set of coordinates.** A coordinate an event touched twice
  is listed twice, once per block, each link on the anchor that block carries. Sorting or
  folding the list would make it a different claim from the page below it.
- **It is a wrapping row until there is room for a column.** Forty-five provisions cost a few
  lines of height in a row and a screen of scrolling in a column, so the row is what a phone
  gets; the stylesheet turns it into the sticky column at the width the act page's own index
  becomes one, and the count line is the label the column needs when it stands on its own.
- **It is a map of where the text moved, not only of what moved.** Each item carries the
  characters that change inserted and deleted, and its decade of those characters as a class the
  sheet sets a weight from, so a page of forty-five changes shows at a glance which few of them
  are most of the text. It is a size and never a judgement; `site_/magnitude.py` says so.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.magnitude import magnitude_html, weight_class
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.pages.prose import pill
from emendrix.site_.pages.texts import RenderedText

__all__ = ["INDEX_ABOVE", "touched"]

INDEX_ABOVE = 6
"""How many changes an event needs before its page opens with a list of them.

Below six the headings are on one screen and a list of them is a second copy of what the
reader can already see; the MDR postponement in the golden has nine, the AI Act's Digital
Omnibus event 45. Zero is under the line too, so an untouched event never opens with an
empty list. It is the one threshold: the column, the count line and the way back to the top
all key off it, so a page can never carry half of that set.
"""


def touched(
    entry: ChangelogEntry, anchors: tuple[str, ...], texts: tuple[RenderedText, ...]
) -> list[Html]:
    """The in-page index: one link per change block, in the order the page carries them.

    `anchors` is the page's own fragment per change, handed in rather than recomputed, so the
    index and the blocks point at the same ids by construction. `texts` arrives the same way
    and for the same reason: the pill, the count and the weight beside a link are all the same
    values the block itself prints, so the map and the page cannot disagree about a change.

    The count opens the list because at the width where it stands as a column beside the
    changes it needs a label of its own: a bare column of coordinates says what it holds only
    to a reader who has already read the page it maps.

    It counts the blocks below, which is what the list has an entry for, and so says `change`
    rather than `provision`: a coordinate one event touched twice is two blocks and one
    provision, and the event's own facts line already states how many provisions were touched.
    Two numbers on one page under one noun would be read as one of them being wrong.

    The characters follow the count, summed over the same blocks, so the label says how much
    text this event moved as well as in how many places. It is the sum of exactly what the
    page below prints, never a second measurement of anything.
    """
    inserted = sum(text.inserted for text in texts)
    deleted = sum(text.deleted for text in texts)
    lines = [
        Html('<nav class="touched" aria-label="Provisions in this event">'),
        Html(
            f'<p class="small muted">{escape(count(len(entry.changes), "change"))} '
            f"in this event · {escape(f'+{inserted:,} −{deleted:,}')} characters</p>"
        ),
        Html("<ol>"),
    ]
    for emitted, anchor, text in zip(entry.changes, anchors, texts, strict=True):
        change = emitted.change
        lines.append(
            Html(
                f'<li class="{escape(weight_class(text))}">'
                f'<a href="#{escape(anchor)}">{escape(change.location.human)}</a> '
                f"{pill(change.change_type, disputed=change.disputed)} "
                f"{magnitude_html(text)}</li>"
            )
        )
    lines.extend((Html("</ol>"), Html("</nav>")))
    return lines
