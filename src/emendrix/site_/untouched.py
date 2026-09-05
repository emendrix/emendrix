"""Wording for the two kinds of event whose counts say less than a sentence does.

Both are findings rather than rendering accidents, both are derived at build time from the
committed document's own counts, and each is asked through one predicate so no two surfaces
can disagree about what the class is. The first is an event with nothing to report at all; the
second is an event with rows to report and no text in any of them.

A committed entry can carry a version pair and an empty change list: the corpus published the
two as distinct versions, and the structural comparison matched every top-level provision.
That is a real answer a reader tracking an act wants, not a rendering accident, so the event
is kept everywhere. What changes is only how it is said: "0 provisions" as a numeral reads
like a counter that failed, where a sentence states the finding.

Verified 2026-08-31 over the 369 committed events: exactly two are in this state, and both
are true no-ops. The MiFIR pair `02014R0600-20250117` to `02014R0600-20251123` was checked
against both source documents byte by byte; the only difference sits in the bibliographic
front matter, before the enacting terms, so the comparison is right to report nothing. The
scoping caveat in `untouched_note` exists for exactly that shape.

The second class is an event every touched unit of which carries no text on either side. Such
a unit was named by the corpus metadata or by an amending act's instructions, and the text
comparison, which is the only source carrying any text, never saw it. Printing that event's
three-way split gives `0 substantive, 0 date-only, 36 with no text`, which spends a line on two
zeros to say what one clause says. Nothing is hidden by the swap: the touched count, the
disputed count and the gate clause all stay, and every row is still on the page.

Like `attribution.py`, both classifications are derived here from the committed document and
are not pipeline concepts. Neither recomputes anything: `counts` is what the emit stage wrote,
so a page states what the document says and an old document is corrected where it is stored.
"""

from __future__ import annotations

from typing import Final

from emendrix.output import ChangelogEntry
from emendrix.site_.markup import count

__all__ = [
    "TEXTLESS_CLAUSE",
    "TEXTLESS_TAIL",
    "UNTOUCHED_CARD",
    "UNTOUCHED_SENTENCE",
    "all_textless",
    "textless_note",
    "textless_words",
    "untouched",
    "untouched_note",
]

UNTOUCHED_SENTENCE: Final = "No provisions differ between these two versions."
"""The finding as a sentence, for the act page's facts line and the feed summary."""

UNTOUCHED_CARD: Final = "no provisions differ"
"""The same finding as a card fragment, where the other cards say `3 provisions`."""


def untouched(entry: ChangelogEntry) -> bool:
    """True when the comparison produced no changes at all for this event.

    Read off the committed counts, never recomputed: `counts.touched` is the number of
    distinct units in the entry's change list, and corroboration appends every unit any other
    signal named, so a zero here means every signal with anything to say said nothing.
    """
    return entry.counts.touched == 0


def untouched_note(entry: ChangelogEntry) -> str:
    """The sentence under the facts line, saying what was compared and what the zero means.

    The unit count is the evidence that the comparison really walked the document rather than
    coming up empty. The last clause is the scoping caveat: the corpus did publish two
    distinct versions, so something distinguishes them, and whatever it is sits outside the
    provisions this site compares.
    """
    compared = count(entry.summary.unchanged_units, "top-level provision")
    return (
        f"The comparison read all {compared} and matched every one. The corpus still "
        "published the two as distinct versions, so whatever distinguishes them sits outside "
        "the provisions this site compares."
    )


TEXTLESS_CLAUSE: Final = "none with text to show"
"""The three-way split, for an event none of whose units carries any text.

It stands where `0 substantive, 0 date-only, 36 with no text` would, on the count line and in
the feed summary. The counts either side of it, touched and disputed, are printed as they
always were.
"""

TEXTLESS_TAIL: Final = "named with no text to show"
"""What follows the provision count on a card and in a title, where the others say `changed`.

`36 provisions named with no text to show by Digital Omnibus on AI` is the whole frame, and
the instrument clause is joined to it with a space, so the fragment ends in a form that reads
on into it.
"""


def all_textless(entry: ChangelogEntry) -> bool:
    """True when this event touched units and not one of them carries any text.

    Read off the committed counts and never recomputed, the rule this module holds throughout.
    An entry written under schema `1.0` reports no textless units, so it is never in the class
    until whatever rewrote it has said otherwise.
    """
    counts = entry.counts
    return counts.touched > 0 and counts.textless == counts.touched


def textless_words(entry: ChangelogEntry) -> str:
    """`36 provisions named with no text to show`, for a card, a `<title>` and a description."""
    return f"{count(entry.counts.touched, 'provision')} {TEXTLESS_TAIL}"


def textless_note(entry: ChangelogEntry) -> str:
    """The sentence under the facts line, naming what the rows are and what became of them.

    The point a reader needs is that the rows exist and that the one source carrying text is
    not among the sources that named them, which is why there is nothing to open. The closing
    clause is the same promise the disputed mark carries everywhere else on this site: a
    disagreement ships as one and is never dropped.
    """
    named = count(entry.counts.touched, "provision")
    return (
        f"All {named} were named by a source other than the text comparison, which is the "
        "only source that carries any text. Each ships with the source that named it and is "
        "marked disputed; none was dropped."
    )
