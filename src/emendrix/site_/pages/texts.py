"""One change's evidence, rendered once per build and shown wherever it belongs.

The before-and-after block of a change is the most expensive markup the site produces. It is a
word or line diff over two stored provision texts, and one committed change carries 4.1 million
characters of them; `diffview.py` records the act page that reached 64 MB before unchanged runs
were elided. Until a provision had a page of its own, that cost was paid once per change,
because one change appeared on exactly one page.

It appears on two now: its event's page and its provision's. So the block is computed here, per
entry, and handed to whichever pages show it, rather than each page calling `render_texts` for
itself. `build.act_pages` makes one dictionary of these tuples for an act and hands out slices
of it, which is what keeps the tree's cost linear in changes rather than in pages showing them.

The tuple is positional: the block at index `i` is the evidence of `entry.changes[i]`, the same
index `entry_anchors` counts occurrences over, so nothing has to be matched up by coordinate.
`RenderedText` is a model rather than a bare `Html` because the measurement of how much of a
provision moved belongs beside the rendering that measured it, and a tuple of strings has
nowhere to put it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.output import ChangelogEntry
from emendrix.site_.diffview import render_texts
from emendrix.site_.markup import Html

__all__ = ["RenderedText", "text_blocks"]


class RenderedText(BaseModel):
    """One change's before-and-after block, ready for a page."""

    model_config = ConfigDict(frozen=True)

    html: Html = Field(description="The evidence as markup, escaped by the renderer that made it.")


def text_blocks(entry: ChangelogEntry) -> tuple[RenderedText, ...]:
    """Every change of one entry as its evidence block, in the entry's own order.

    Called once per entry per build. A page never calls `render_texts` itself, which is the
    property that stops one diff being computed twice now that two page kinds show it.
    """
    return tuple(
        RenderedText(html=render_texts(emitted.change, entry)) for emitted in entry.changes
    )
