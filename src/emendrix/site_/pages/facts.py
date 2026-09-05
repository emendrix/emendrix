"""One event's opening: the heading it is known by, its identity, its dates and its counts.

Split out of `act_event.py` on 2026-09-03, when the gate clause was rewritten for a reader and
that module crossed the size cap, and widened on 2026-09-05, when gathering the changes with
no text to show crossed it again and the opening came here to join the count line it ends on.
The seam is the one that module always had and is a real one: everything here is a statement
about the committed document's own fields, the two clocks and the seven counts, and none of it
knows what a change block looks like or where the evidence lives. What stays behind is the
changes and the order they come in.

One opening, three surfaces. The card on an act's timeline, the event's own page and an
instrument's page all print it, so an event cannot state its counts one way in a list and
another way on the page a reader opens.

The words are the reader's, the numbers are the document's. `unexplained` and `quoted` are
counted by the citation gate and are named after it in the committed Markdown; here they are
said as what they mean, because a reader arriving at an event page has never heard of a gate.
Nothing below this page moves with the rewording: the changelog keeps its own names.
"""

from __future__ import annotations

from collections import Counter

from emendrix.output import ChangelogEntry
from emendrix.output.counts import EntryCounts
from emendrix.site_.amending import AmendingAct, amending_lines
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, UNATTRIBUTED_NOTE, unattributed
from emendrix.site_.clocks import event_date
from emendrix.site_.dispute import SHAPE_WORDS, dispute_shape
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.untouched import (
    TEXTLESS_CLAUSE,
    UNTOUCHED_SENTENCE,
    all_textless,
    textless_note,
    untouched,
    untouched_note,
)

__all__ = ["event_facts", "event_header"]

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


def _shapes(entry: ChangelogEntry) -> str:
    """What the disputed count is a count of, one clause per shape, or nothing to say.

    The three are read off the same function the site's published rates are counted by, so a
    reader can add these up and get the number to their left, and the methodology table's rows
    say the same thing about the same corpus. They print unconditionally once there is a
    disagreement at all, zeroes included, for the reason the split beside them does: a line
    that changes shape between two events is a line a reader has to read twice.

    An event with nothing disputed gets no clause. There is no shape of a disagreement that
    did not happen, and `0 disputed (0, 0, 0)` would put three numbers on every count line on
    the site to say what one zero already says.
    """
    shapes = Counter(
        dispute_shape(emitted.change.signals)
        for emitted in entry.changes
        if emitted.change.disputed
    )
    if not shapes.total():
        return ""
    return " (" + ", ".join(f"{shapes[key]} {words}" for key, words in SHAPE_WORDS.items()) + ")"


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

    The disputed count is followed by what it is a count of, wherever it is not zero, because
    one number covered three findings a reader would weigh differently: a change whose words
    the comparison read and another source did not list, one with no text to show at all, and
    the outright contradiction about kind. Naming them takes nothing away, and the total they
    add up to is the one that has always been printed here.

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
            f"{split}, <strong>{counts.disputed} disputed</strong>"
            f"{escape(_shapes(entry))} · {escape(gate)}</p>"
        ),
    ]


def event_header(entry: ChangelogEntry, acts: tuple[AmendingAct, ...], *, full: bool) -> list[Html]:
    """The article's opening, shared by the card and the event page: id, date, versions, facts.

    The `id` is the fragment every feed entry's `<id>` was minted from, so both surfaces must
    keep answering to it forever. The heading is the date, because a reader arriving at a
    timeline is asking when; it names its clock through the one helper every dated line on the
    site reads, so a detection date can never be set as an in-force date. The version pair is
    what the event *is* and sits directly below in the mono face, an identifier to check against
    EUR-Lex rather than a name to scan a list by. Then the instrument that made it, where one is
    named, because that is what a reader knows the event by; `full` is the event's own page
    rather than the card, and is what lets the official titles through. The facts line carries
    both clocks, so the record of when this happened is whole whichever the heading named.
    """
    versions = f"<code>{escape(str(entry.from_version))} → {escape(str(entry.to_version))}</code>"
    # The bare pill, no colour modifier: the label is a fact about the corpus's records, and
    # the palette spends colour on diffs, disputes and links only (`style/tokens.py`).
    unnamed = unattributed(entry)
    marker = f' <span class="pill">{escape(UNATTRIBUTED_LABEL)}</span>' if unnamed else ""
    lines = [
        Html(f'<article class="event" id="{escape(entry.key)}">'),
        Html(f"<h2>{escape(event_date(entry).words)}{marker}</h2>"),
        Html(f'<p class="ident">{versions}</p>'),
        *amending_lines(acts, full=full),
        *event_facts(entry),
    ]
    if unnamed:
        lines.append(Html(f'<p class="small muted">{escape(UNATTRIBUTED_NOTE)}</p>'))
    if untouched(entry):
        lines.append(Html(f'<p class="small muted">{escape(untouched_note(entry))}</p>'))
    elif all_textless(entry):
        lines.append(Html(f'<p class="small muted">{escape(textless_note(entry))}</p>'))
    return lines
