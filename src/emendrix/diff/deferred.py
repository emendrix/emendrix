"""Clock 2: the dates a change moved, and the one case where that is an answer.

`in_force` is clock 1 and comes from the corpus, not from here. `applies_from` is clock 2 and
is *prose*: attaching a date to a set of provisions has exceptions and conditions, so it is
read only where reading it is deterministic and reported `unknown` everywhere else. Many
unknowns is the correct outcome; nothing here infers, and no model is involved.

A change is `DEFERRED` when both of these hold:

1. **The only differences are inside dates that moved.** Every differing region of the two
   comparison forms consists solely of tokens that render one of the removed dates (old side)
   or one of the added dates (new side), and each region carries at least one token that
   cannot be anything but a date: a year, a month name, a fully written numeric date. Only the
   machine-readable `DATE ISO` values the parser extracted are used, and nothing here goes
   hunting for dates with a regex, which is exactly where false deferrals would come from. That
   second condition is what stops a renumbered cross-reference (`point 5` → `point 6`) from
   passing as a day that moved.
2. **Exactly one date was added**, so there is a single unambiguous new date to report.

Anything else is `MODIFIED` with `ApplicabilityUnknown` and the dates recorded as detail. The
AI Act's Article 113 is that case: four dates were added and its prose changed around them, so
the dates ride along and which one the article applies from is left to the explanation to quote.

Measured on the pinned fixtures on 2026-08-06: the MDR 2017-05-05 → 2020-04-24 transition
(Regulation (EU) 2020/561, the one-year postponement) yields six deferrals (`AR 1`, `AR 17`,
`AR 34`, `AR 113`, `AR 120`, `AN IX`) and three plain modifications. The AI Act transition
yields none.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from datetime import date
from typing import Final, NamedTuple

from pydantic import BaseModel, ConfigDict

from emendrix.core import (
    Applicability,
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    ProvisionNode,
)

__all__ = ["DateVerdict", "read_dates"]

_MONTHS: Final = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""English month names. v0.1 is English-only by scope cap."""

_PUNCTUATION: Final = ",;:.()[]{}'\"/-…«»\u2013—"
"""Trimmed off a token before it is tested. A token that is only punctuation never matches."""

_BEYOND_DATES_REASON: Final = (
    "the text changed beyond its dates, so no date that moved can be read as the application date"
)
"""Why clock 2 stays unknown when the differing regions carry more than date material.

Phrased as a statement about what this stage will read, never about what binds anyone. The
sibling reason in `api.py` sets the shape: a subject, a verb, and `application date` written
out. In particular the word `binding` stays out of these reasons: a reader of a legal document
meets it as an adjective first, so a sentence carrying it reads as a claim about legal force,
which nothing in this project may appear to make.
"""

_NOT_ONE_DATE_REASON: Final = (
    "{count} dates were added, so no single one can be read as the application date"
)
"""Why clock 2 stays unknown when the text differs only in dates but not exactly one was added.

`{count}` is how many dates were added, which is zero or two or more here and never one.
"""


class DateVerdict(BaseModel):
    """What the two versions of one unit say about clock 2."""

    model_config = ConfigDict(frozen=True)

    deferred: bool = False
    applies_from: Applicability = ApplicabilityUnknown()
    removed: tuple[date, ...] = ()
    added: tuple[date, ...] = ()


def read_dates(before: ProvisionNode, after: ProvisionNode) -> DateVerdict:
    """Read clock 2 off one changed unit. Pure, offline, and never inferential."""
    old = {mention.value for mention in before.dates}
    new = {mention.value for mention in after.dates}
    removed, added = tuple(sorted(old - new)), tuple(sorted(new - old))
    if not removed and not added:
        return DateVerdict(applies_from=ApplicabilityUnchanged())
    if not _differs_only_in_dates(before, after, removed, added):
        return DateVerdict(
            applies_from=ApplicabilityUnknown(reason=_BEYOND_DATES_REASON),
            removed=removed,
            added=added,
        )
    if len(added) != 1:
        return DateVerdict(
            applies_from=ApplicabilityUnknown(reason=_NOT_ONE_DATE_REASON.format(count=len(added))),
            removed=removed,
            added=added,
        )
    return DateVerdict(deferred=True, applies_from=added[0], removed=removed, added=added)


def _differs_only_in_dates(
    before: ProvisionNode,
    after: ProvisionNode,
    removed: tuple[date, ...],
    added: tuple[date, ...],
) -> bool:
    old_tokens, new_tokens = _tokens(removed), _tokens(added)
    old_words = str(before.comparison_text).split()
    new_words = str(after.comparison_text).split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if not _is_date_region(old_words[i1:i2], old_tokens):
            return False
        if not _is_date_region(new_words[j1:j2], new_tokens):
            return False
    return True


def _is_date_region(words: list[str], tokens: _DateWords) -> bool:
    """Is this differing run of words nothing but date material?

    Two conditions, and the second is what keeps a renumbered cross-reference out. Every word
    must be a rendering of one of the dates that moved, *and* at least one of them must be a
    rendering that cannot be mistaken for a reference number. A lone `5` becoming a lone `6`
    is a bare day number on both sides and would otherwise pass, even though "point 5" became
    "point 6" and no date was involved.

    An empty run, which is one side of a pure insertion or deletion, is vacuously date material;
    the other side of the same opcode is what carries the evidence.
    """
    trimmed = [word.strip(_PUNCTUATION) for word in words]
    if not trimmed:
        return True
    if not all(word and word in tokens.every for word in trimmed):
        return False
    return any(word in tokens.unmistakable for word in trimmed)


class _DateWords(NamedTuple):
    """Every rendering of a set of dates, and the subset that can only be a date."""

    every: frozenset[str]
    unmistakable: frozenset[str]


def _tokens(values: Iterable[date]) -> _DateWords:
    """Every way one of these dates can be written, as whitespace-separated tokens.

    Built from the dates themselves rather than found in the text: a token counts as date
    material only because a `DATE ISO` value in this very provision renders that way.

    The split is about ambiguity, not about correctness. A year, a month name and a fully
    written numeric date are dates and nothing else. A day number is a small integer, and a
    small integer in legal prose is usually a cross-reference, so a day counts as date material
    but never as the evidence that a region *is* one. The bare month *number* is absent from
    both sets for the same reason, only more so.
    """
    every: set[str] = set()
    unmistakable: set[str] = set()
    for value in values:
        month = _MONTHS[value.month - 1]
        unmistakable |= {
            str(value.year),
            month,
            month.lower(),
            month.upper(),
            value.isoformat(),
            f"{value.day}.{value.month}.{value.year}",
            f"{value.day:02d}.{value.month:02d}.{value.year}",
            f"{value.day:02d}/{value.month:02d}/{value.year}",
        }
        every |= {str(value.day), f"{value.day:02d}"}
    return _DateWords(every=frozenset(every | unmistakable), unmistakable=frozenset(unmistakable))
