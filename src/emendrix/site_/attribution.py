"""Naming the events no amending act is named for, without claiming what caused them.

Some committed events record a version pair whose corroboration window turned up no amending
act at all: the corpus's modification metadata annotated nothing in the window and there was
no amending act whose instructions could be read, so only the structural comparison observed
the difference. The commonest shape is the act as published in the Official Journal against
its own first consolidation, where no amending act can exist yet (`eu/modmeta.py` records the
measurement); such a difference is typically the publisher correcting its own text. The site
does not say so, because the pipeline did not establish it: the fact it has is that no
amending act is named, and that is the only claim any page makes.

The classification is derived here, at build time, from the committed document's own fields.
It is deliberately not a pipeline concept: the emitted schema does not carry it, and this
module must not grow into one that re-runs corroboration. The day the vocabulary gains a
first-class state for it, this predicate becomes a read of that field and every renderer
stays put, because all of them ask this one function.

What the classification changes, and where:

- the front page leaves these events out of its newest-first list and says how many;
- the acts index never answers its date fact with one of them, and its lede counts them
  apart from the amendment events;
- the act page keeps every one, in place, labelled;
- the feeds keep every one, with the label leading the summary.

Nothing is dropped anywhere: the question is what to call these events and where to rank
them, never whether to keep them.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import Signal
from emendrix.output import ChangelogEntry

__all__ = ["UNATTRIBUTED_FEED_LEAD", "UNATTRIBUTED_LABEL", "UNATTRIBUTED_NOTE", "unattributed"]

UNATTRIBUTED_LABEL: Final = "no amending act named"
"""The badge text, and the only phrase any surface uses for the class. Never a cause word
like "corrigendum": the pipeline established that no act is named, not what happened."""

UNATTRIBUTED_NOTE: Final = (
    "No amending act is named for this event: the EU's own amendment metadata annotated "
    "nothing in this window and there were no amending-act instructions to read, so only the "
    "text comparison observed it. That is a fact about the corpus's records for the window, "
    "not a doubt about the text shown below."
)
"""The full sentence for the act page, once per qualifying event, in a first-time reader's
words for the same reason `dispute.py` writes its own: "unattributed" on a page carrying a
not-legal-advice disclaimer would read as a claim about the law."""

UNATTRIBUTED_FEED_LEAD: Final = "No amending act is named for this event."
"""The clause an Atom summary leads with. The entry itself is kept whole: its id, link and
date do not move, because a reworded summary is not a new event."""


def unattributed(entry: ChangelogEntry) -> bool:
    """True when no signal named an amending act for this event. Four checks, all structural.

    `corroboration` must be present: a diff-only entry never corroborated anything, so there
    is no window to have named an act, and it stays out of the class. Both non-diff signals
    must have come back unavailable, which is how a window naming no amending act serialises
    (`eu/signals.py` builds both reports off the window's own amending-act list). And the
    document's two consequences are checked rather than assumed: no change names an amending
    act, and no in-force date was stamped, both of which can only come from an available
    metadata signal (`corroborate/merge.py`) but are asserted here against the committed
    bytes, because this module answers from the document, not from what the pipeline is
    currently known to imply about it.

    One ambiguity is accepted and named: a version pair the corpus never dated also ships
    both signals unavailable, distinguishable only by the free-text notes, which this project
    does not parse to drive logic. No committed entry is in that state (verified 2026-08-31
    over the 369 committed events; the 26 with both signals unavailable are exactly the 26
    whose window named no amending act), and a pipeline-level state is the fix if one ever
    is, not a note parser here.
    """
    report = entry.corroboration
    if report is None:
        return False
    non_diff = [units for units in report.signals if units.signal is not Signal.STRUCTURAL_DIFF]
    if not non_diff or any(units.available for units in non_diff):
        return False
    if any(emitted.change.amending_acts for emitted in entry.changes):
        return False
    return not entry.in_force
