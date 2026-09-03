"""One change's evidence, rendered once per build and shown wherever it belongs.

The before-and-after block of a change is the most expensive markup the site produces. It is a
word or line diff over two stored provision texts, and one committed change carries 4.1 million
characters of them; `diffview.py` records the act page that reached 64 MB before unchanged runs
were elided. Until a provision had a page of its own, that cost was paid once per change,
because one change appeared on exactly one page.

It appears on two now: its event's page and its provision's. So the block is computed here, per
entry, and handed to whichever pages show it, rather than each page calling `render_texts` for
itself. `build.act_pages` calls this once per entry and hands out slices of it, which is what
keeps the tree's cost linear in changes rather than in pages showing them.

The tuple is positional: the block at index `i` is the evidence of `entry.changes[i]`, the same
index `entry_anchors` counts occurrences over, so nothing has to be matched up by coordinate.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.diffview import Rendered, render_texts

__all__ = ["RenderedText", "text_blocks"]

RenderedText = Rendered
"""The renderer's own model, under the name the pages ask for it by.

One class with two names rather than two models: the block carries how many characters were
inserted and deleted as well as the markup, and that measurement belongs beside the comparison
that produced it, so the model is declared where `render_texts` builds it. A second model here
would be the same fields in a second place, free to drift from the first.
"""


def text_blocks(entry: ChangelogEntry) -> tuple[RenderedText, ...]:
    """Every change of one entry as its evidence block, in the entry's own order.

    Called once per entry per build. A page never calls `render_texts` itself, which is the
    property that stops one diff being computed twice now that two page kinds show it.
    """
    return tuple(render_texts(emitted.change, entry) for emitted in entry.changes)
