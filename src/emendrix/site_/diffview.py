"""The evidence inside an expanded change: before and after, compared or stacked.

The unified view merges both texts into one block, so it is explicitly a comparison
rendering; the stacked blocks are the verbatim stored text, whitespace and all. Both are
`pre-wrap`, and the unified one is so deliberately: stored text carries a line break at
every block boundary the source opened, and a view that collapsed them would hand the
reader one wall of prose where the document had a title, a subtitle and numbered
paragraphs. Below `SIMILARITY_FLOOR` the unified view is mostly markup and the page stacks
instead, saying so.

**A long enough run of *unchanged* text is replaced by a count of what it hid**, because a page
nobody can open is not a more honest rendering of the text than a page that says how much of it
is unchanged. Three conditions are what keep that honest, and they are the conditions under
which it is allowed. Only *unchanged* runs are ever elided, so nothing the diff reported as a
change is hidden. Every elision is marked and carries the exact count of what it replaced, which
is the project's standing rule for truncation in output. And the threshold sits far above any
ordinary provision, so what collapses is the tens of thousands of unchanged units that only
appear in tables.

Every text on this page came out of a legal document, so all of it goes through `escape`,
including the runs the diff decided were unchanged.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import Change
from emendrix.output import ChangelogEntry
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.worddiff import (
    SIMILARITY_FLOOR,
    Comparison,
    Granularity,
    compare,
)

__all__ = ["render_texts"]

_NO_TEXT = (
    "No text on either side: this unit was named by a signal that carries no text, and only "
    "the structural diff carries any."
)
"""The changelog's own sentence for a unit no text-carrying signal saw, word for word.

Two renderings of one fact must not describe it differently, so this matches
`output.markdown`'s line rather than paraphrasing it.
"""


def _verbatim(label: str, text: str, extra_class: str = "") -> Html:
    """One stored text, labelled, whitespace intact. `pre-wrap` does the wrapping."""
    suffix = f" {extra_class}" if extra_class else ""
    return Html(
        f'<p class="lbl">{escape(label)}</p><pre class="verbatim{suffix}">{escape(text)}</pre>'
    )


CONTEXT: Final[dict[Granularity, int]] = {"word": 40, "line": 3}
"""How much unchanged text to keep either side of a change, in the granularity's own unit.

A diff view exists to show what changed, and rendering the unchanged remainder in full is not
neutral. Measured over the committed corpus on 2026-08-13, doing so makes one act's page 64MB,
because CLP's Annex VI is two million characters that appear, all but identical, in thirty
transitions. Three lines is enough to place a changed row in a table; forty words is roughly a
sentence either side, which is enough to place a changed phrase in a provision.
"""

ELIDE_ABOVE: Final[dict[Granularity, int]] = {"word": 400, "line": 20}
"""How long an unchanged run must be before it is worth replacing with a count.

Deliberately far above `CONTEXT` rather than just above it. The pages this exists to fix
carry unchanged runs of tens of thousands of units; a provision that reads normally carries
runs of tens. Hiding the second kind would make every ordinary page worse to read in order
to fix two extraordinary ones, so the threshold is set where no ordinary provision reaches
it: the committed golden's MDR page has a run of 87 unchanged words and is rendered whole.
"""


def _kept(text: str, granularity: Granularity) -> Html:
    """An unchanged run: whole if short, else its two ends with the middle counted out."""
    context = CONTEXT[granularity]
    units = text.split("\n") if granularity == "line" else text.split(" ")
    if len(units) <= ELIDE_ABOVE[granularity]:
        return escape(text)
    joiner = "\n" if granularity == "line" else " "
    hidden = len(units) - 2 * context
    noun = "lines" if granularity == "line" else "words"
    return join(
        (
            escape(joiner.join(units[:context])),
            Html(f'<span class="elided">… {hidden:,} unchanged {noun} …</span>'),
            escape(joiner.join(units[-context:])),
        ),
        joiner,
    )


def _unified(comparison: Comparison, entry: ChangelogEntry) -> Html:
    """One block carrying both texts, with what went and what arrived marked.

    Each span is followed by the separator the diff recorded for it rather than by a blanket
    space, so a provision keeps the line structure the source document gave it. The block is
    `pre-wrap` for that reason: a paragraph would collapse every one of those breaks.
    """
    spans = comparison.spans
    parts: list[Html] = []
    for index, span in enumerate(spans):
        if span.kind == "equal":
            parts.append(_kept(span.text, comparison.granularity))
        elif span.kind == "deleted":
            parts.append(Html(f"<del>{escape(span.text)}</del>"))
        else:
            parts.append(Html(f"<ins>{escape(span.text)}</ins>"))
        # Not after the last span: a text that ended in a newline would otherwise render a
        # trailing blank line inside the block.
        if index < len(spans) - 1:
            parts.append(escape(span.sep))
    label = Html(
        f'<p class="lbl"><code>{escape(str(entry.from_version))}</code> → '
        f"<code>{escape(str(entry.to_version))}</code></p>"
    )
    # Said, not left to be inferred. At line granularity a whole row is marked because one
    # cell in it moved, and a reader who assumed word granularity would read the untouched
    # cells as changed too.
    if comparison.granularity == "line":
        label = join(
            (
                label,
                Html(
                    '<p class="none">compared line by line: this provision is too large to '
                    "compare word by word, so a marked line is a line that changed somewhere"
                    "</p>"
                ),
            ),
            "\n",
        )
    return join((label, Html(f'<p class="diff">{join(parts, "")}</p>')), "\n")


def render_texts(change: Change, entry: ChangelogEntry) -> Html:
    """Whatever evidence the change carries, in the most legible honest form."""
    before, after = change.before, change.after
    if before is not None and after is not None:
        # One comparison, used for both questions: whether the unified view is worth showing
        # and what it contains. Asking them separately built the matcher twice.
        comparison = compare(before, after)
        if comparison.ratio >= SIMILARITY_FLOOR:
            return _unified(comparison, entry)
        note = Html(
            '<p class="none">texts differ too much for an inline diff; shown separately</p>'
        )
        return join(
            (
                note,
                _verbatim(f"before ({entry.from_version})", before),
                _verbatim(f"after ({entry.to_version})", after),
            ),
            "\n",
        )
    if after is not None:
        return _verbatim(f"inserted text ({entry.to_version})", after, "ins")
    if before is not None:
        return _verbatim(f"deleted text ({entry.from_version})", before, "del")
    return Html(f'<p class="none">{escape(_NO_TEXT)}</p>')
