"""Wording for an event whose comparison found no provision to report.

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

Like `attribution.py`, the classification is derived here at build time from the committed
document's own counts, is not a pipeline concept, and every renderer asks this one predicate
so no two surfaces can disagree about what the class is.
"""

from __future__ import annotations

from typing import Final

from emendrix.output import ChangelogEntry
from emendrix.site_.markup import count

__all__ = ["UNTOUCHED_CARD", "UNTOUCHED_SENTENCE", "untouched", "untouched_note"]

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
