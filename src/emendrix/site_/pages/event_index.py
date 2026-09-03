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
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.pages.prose import pill

__all__ = ["INDEX_ABOVE", "touched"]

INDEX_ABOVE = 6
"""How many changes an event needs before its page opens with a list of them.

Below six the headings are on one screen and a list of them is a second copy of what the
reader can already see; the MDR postponement in the golden has nine, the AI Act's Digital
Omnibus event 45. Zero is under the line too, so an untouched event never opens with an
empty list. It is the one threshold: the column, the count line and the way back to the top
all key off it, so a page can never carry half of that set.
"""


def touched(entry: ChangelogEntry, anchors: tuple[str, ...]) -> list[Html]:
    """The in-page index: one link per change block, in the order the page carries them.

    `anchors` is the page's own fragment per change, handed in rather than recomputed, so the
    index and the blocks point at the same ids by construction. The pill is the same call the
    block's heading makes, so the two can never disagree about a change's kind.

    The count opens the list because at the width where it stands as a column beside the
    changes it needs a label of its own: a bare column of coordinates says what it holds only
    to a reader who has already read the page it maps.

    It counts the blocks below, which is what the list has an entry for, and so says `change`
    rather than `provision`: a coordinate one event touched twice is two blocks and one
    provision, and the event's own facts line already states how many provisions were touched.
    Two numbers on one page under one noun would be read as one of them being wrong.
    """
    lines = [
        Html('<nav class="touched" aria-label="Provisions in this event">'),
        Html(
            f'<p class="small muted">{escape(count(len(entry.changes), "change"))} '
            f"in this event</p>"
        ),
        Html("<ol>"),
    ]
    for emitted, anchor in zip(entry.changes, anchors, strict=True):
        change = emitted.change
        lines.append(
            Html(
                f'<li><a href="#{escape(anchor)}">{escape(change.location.human)}</a> '
                f"{pill(change.change_type, disputed=change.disputed)}</li>"
            )
        )
    lines.extend((Html("</ol>"), Html("</nav>")))
    return lines
