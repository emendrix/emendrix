"""One event's dates and counts, in the line that sits under its heading.

Split out of `act_event.py` on 2026-09-03, when the gate clause was rewritten for a reader and
that module crossed the size cap. The seam is the one the module already had: everything here
is a statement about the committed document's own fields, the two clocks and the seven counts,
and none of it knows what a change block looks like or where the evidence lives.

One line, three surfaces. The card on an act's timeline, the event's own page and an
instrument's page all print it through the shared header in `act_event`, so an event cannot
state its counts one way in a list and another way on the page a reader opens.

The words are the reader's, the numbers are the document's. `unexplained` and `quoted` are
counted by the citation gate and are named after it in the committed Markdown; here they are
said as what they mean, because a reader arriving at an event page has never heard of a gate.
Nothing below this page moves with the rewording: the changelog keeps its own names.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.output.counts import EntryCounts
from emendrix.site_.clocks import event_date
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.untouched import (
    TEXTLESS_CLAUSE,
    UNTOUCHED_SENTENCE,
    all_textless,
    untouched,
)

__all__ = ["event_facts"]

_ALL_CHECKED = "every change carries an explanation that passed its citation check"
"""The all-clear, as a sentence rather than as a pair of zeros. Two zeros beside two nouns read
as a counter that failed and say nothing about what the run actually found."""

_DIFF_ONLY = "the explain stage did not run for this event, so it carries the structural facts only"


def _checked(counts: EntryCounts) -> str:
    """What the citation check left behind, leading with the changes that carry no explanation.

    Each clause is printed only where it happened, the larger fact first: a change with no
    explanation at all, then a sentence the gate wrote verbatim because the explanation it
    replaced could not be traced to the provision it described.
    """
    stated: list[str] = []
    if counts.unexplained:
        stated.append(f"{count(counts.unexplained, 'change')} without an explanation")
    if counts.quoted:
        stated.append(
            f"{count(counts.quoted, 'sentence')} quoting the provision verbatim where an "
            "explanation failed its citation check"
        )
    return "; ".join(stated) if stated else _ALL_CHECKED


def event_facts(entry: ChangelogEntry) -> list[Html]:
    """The dates and the counts, all of them read off the document, none of them recomputed.

    An event that touched nothing states the finding as a sentence instead of the count line:
    "0 provisions touched" with three more zeros and a clause about explanations reads like a
    counter that failed, where the sentence says what the comparison found. An event with rows
    and no text in any of them replaces the three-way split alone, for the same reason and with
    nothing else dropped: the touched count, the disputed count and the gate clause all stay.

    The split prints unconditionally otherwise, `0 with no text` included. Every count on this
    line is printed whether or not it happened, and a line that changed shape between two
    events is a line a reader has to read twice.

    The dates line carries what the heading above it did not. The heading names one clock and
    one date, so repeating that clause here would print the same fact twice on one screen and
    invite a reader to look for the difference between them. Nothing is dropped: an event with
    no in-force date says so, an event carrying several lists them all, and the clock the
    heading did not name is always here.
    """
    counts = entry.counts
    headed = event_date(entry)
    rest = []
    if not entry.in_force:
        rest.append("in force not stated")
    elif len(entry.in_force) > 1:
        rest.append("in force " + ", ".join(value.isoformat() for value in entry.in_force))
    if headed.in_force:
        rest.append(f"detected {entry.detected_on.isoformat()}")
    dates = Html(f'<p class="facts">{escape(" · ".join(rest))}</p>')
    if untouched(entry):
        return [dates, Html(f'<p class="facts">{escape(UNTOUCHED_SENTENCE)}</p>')]
    gate = _DIFF_ONLY if entry.diff_only else _checked(counts)
    split = (
        escape(TEXTLESS_CLAUSE)
        if all_textless(entry)
        else (
            f"{counts.substantive} substantive, {counts.date_only} date-only, "
            f"{counts.textless} with no text"
        )
    )
    return [
        dates,
        Html(
            f'<p class="facts">{escape(count(counts.touched, "provision"))} touched — '
            f"{split}, <strong>{counts.disputed} disputed</strong> · {escape(gate)}</p>"
        ),
    ]
