"""The counts a reader is shown first, derived from one emitted delta.

Split off `json_out.py` on 2026-09-05, when the split of the touched units became three ways
and that module crossed the size cap. The seam is the one it already had: everything here is a
question asked of the changes, at the unit of change, and none of it knows what a document
looks like or where one is written. `json_out` holds the document and asks this once.

Nothing here reads a clock, a network or a corpus, and nothing re-derives a verdict another
stage reached: the gate's flags and the signals' disagreement arrive on the changes and are
counted as they are.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, ChangeType
from emendrix.graph.report import EmittedChange, EmittedDelta, EmittedSentence

__all__ = ["EntryCounts", "counts_of"]


class EntryCounts(BaseModel):
    """The counts a reader is shown first, at the unit of change.

    `substantive`, `date_only` and `textless` split the touched units three ways, and every
    touched unit falls in exactly one of them: a unit whose every change is `DEFERRED` moved a
    date and nothing else, a unit whose every change carries no text on either side was named
    by a signal that carries none, and what is left is a unit whose text moved. The split is
    the one the Markdown header prints and the site's count line repeats, and it is computed,
    never asserted.

    The identity `touched == substantive + date_only + textless` holds of counts this module
    derives and is asserted over them. It is deliberately not a validator: a document published
    under schema `1.0` reads back with `textless` at 0 and the wider `substantive` of its own
    run, which satisfies the identity while answering the older question.
    """

    model_config = ConfigDict(frozen=True)

    touched: int = Field(default=0, ge=0, description="Top-level units this event touched.")
    substantive: int = Field(
        default=0, ge=0, description="Touched units that are neither date-only nor textless."
    )
    date_only: int = Field(default=0, ge=0, description="Units whose every change is DEFERRED.")
    textless: int = Field(
        default=0, ge=0, description="Units whose every change carries no text on either side."
    )
    disputed: int = Field(default=0, ge=0, description="Changes the signals disagree about.")
    quoted: int = Field(
        default=0, ge=0, description="Sentences the citation gate wrote as verbatim quotations."
    )
    unexplained: int = Field(
        default=0, ge=0, description="Changes that ship with no prose at all, and say why."
    )


def _sentences(change: EmittedChange) -> tuple[EmittedSentence, ...]:
    note = change.applicability_note
    return change.sentences if note is None else (*change.sentences, note)


def _buckets(units: Iterable[list[Change]]) -> tuple[int, int]:
    """The date-only and textless unit counts, each unit falling in at most one of them.

    Both questions are asked of the whole unit rather than of one change under it, mirroring
    each other: a unit is date-only when its every change is `DEFERRED` and textless when its
    every change carries no text, so a unit mixing either with anything else is substantive,
    which is the honest answer for a unit some of whose text the diff did read.

    They are counted in one pass, and date-only wins, so the two can never both claim a unit
    and leave `substantive` short. Nothing in the corpus produces one: a `DEFERRED` change
    carries the date it deferred, and the signals that name a unit the diff missed only ever
    claim inserted, modified or deleted. The order is what makes that a property rather than
    an assumption, and a date that moved is the more specific finding of the two.
    """
    date_only = textless = 0
    for group in units:
        if all(change.change_type is ChangeType.DEFERRED for change in group):
            date_only += 1
        elif all(change.textless for change in group):
            textless += 1
    return date_only, textless


def counts_of(delta: EmittedDelta, *, diff_only: bool) -> EntryCounts:
    """Every count on one entry, from the changes it holds. The one computation `of` makes."""
    units: dict[str, list[Change]] = {}
    for emitted in delta.changes:
        units.setdefault(emitted.change.unit.canonical, []).append(emitted.change)
    date_only, textless = _buckets(units.values())
    quoted = sum(
        1 for emitted in delta.changes for sentence in _sentences(emitted) if sentence.fallback
    )
    return EntryCounts(
        touched=len(units),
        substantive=len(units) - date_only - textless,
        date_only=date_only,
        textless=textless,
        disputed=sum(1 for emitted in delta.changes if emitted.change.disputed),
        # In diff-only mode nothing was asked of a model, so nothing is missing: reporting
        # 45 "unexplained" changes there would be a defect count for a stage that never ran.
        quoted=0 if diff_only else quoted,
        unexplained=0 if diff_only else sum(1 for e in delta.changes if not e.sentences),
    )
