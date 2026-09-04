"""The restating repair: a note that quoted a library, rewritten in the register the code uses.

`explain/failures.py` states the rule this corrects: neither reader-facing reason is ever an
exception's own text, because what a library called its failure is a fact for the operator's log
and not for a published document. Entries written before the curated reasons existed carry that
text anyway, so a page can tell a reader `UnexpectedModelBehavior: Exceeded maximum output
retries (1)` where every entry beside it says the same thing in a sentence. This replaces the
note with the curated one and stamps the counted kind, which is what the code would write today.

**The kind matters as much as the sentence.** A note carrying none is invisible to
`repair explanations`, whose selector matches the kind or the curated reason and deliberately
never a dependency's error text. So restating a note is also what makes the change selectable,
and the paid repair can then be pointed at a gap that no selector could reach before.

**The selection is a set of exact strings, never a prefix or a substring.** Most of what that
field holds is the house register, and a change written before the kind existed carries a
curated reason with no kind on it, exactly like the notes here. Nothing but the text itself
tells the two apart, so anything looser would restate reasons that were never wrong.

**A note naming a provider that never answered is counted and left alone.** Neither kind is safe
to stamp on one: `model_failed` would say the model answered when it never did, and
`provider_unavailable` would tell `OutputRepo.holds_finished` the entry is unfinished, which
sends a later backfill to re-run whole transitions whose prose is already correct.

Core types and the committed document. No corpus, no clock, no network, no model, no key: this
module imports nothing that could reach any of them.
"""

from __future__ import annotations

import re
from typing import Final

from emendrix.explain import MODEL_FAILED
from emendrix.output import ChangelogEntry
from emendrix.repair.entry import RepairResult, RepairTarget, delta_of, moved, rebuild

__all__ = [
    "KIND",
    "PROVIDER_SHAPE",
    "RAW_MODEL_FAILURES",
    "WITHHELD_NOTE",
    "needs",
    "repair",
    "selected",
    "withheld",
]

KIND: Final = "unexplained"
"""What this repair is called, on the command line and in the record it writes."""

_MODEL_FAILED_KIND: Final = "model_failed"
"""The counted kind of a change the model answered about, unusably."""

RAW_MODEL_FAILURES: Final = frozenset(
    {
        "UnexpectedModelBehavior: Exceeded maximum output retries (1)",
    }
)
"""Every raw note that is a malformed answer, matched whole and never by prefix.

Measured 2026-09-04 over the published changelogs: 75 changes across 19 acts carry this one
string, and it is the only malformed-answer text any of them holds. A note not listed here is
one nobody has read, and adding it takes reading it first.
"""

PROVIDER_SHAPE: Final = re.compile(r"^(?:ModelAPIError|ModelHTTPError)\b")
"""A raw note naming the two exception classes `explain.provider_failed` reads as unreachable.

Anchored at the start, because these are the class names a note of that shape opens with. Such
a note is counted and never stamped: the reason is in the module docstring.
"""

WITHHELD_NOTE: Final = (
    "left exactly as found: a note naming a provider that never answered is not an answer that "
    "was unusable, and neither counted kind is true of one. The settled kind would say the model "
    "answered, and the unfinished kind would send a later backfill to re-run whole transitions "
    "whose explanations are already correct."
)
"""Printed whenever a pass met one, so a note it declined to touch is never a silent skip.

Written to follow a count and a noun, so it reads for one note and for many."""


def selected(entry: ChangelogEntry) -> tuple[int, ...]:
    """Indices of the changes whose note is a library's own text for a malformed answer.

    The kind must be empty as well as the text known: a change already carrying a kind was
    written by code that curates its reasons, and this repair has nothing to say about it.
    """
    return tuple(
        index
        for index, item in enumerate(entry.changes)
        if not item.unexplained_kind and item.unexplained in RAW_MODEL_FAILURES
    )


def withheld(entry: ChangelogEntry) -> tuple[int, ...]:
    """Indices of the changes whose note is a library's own text for an unreachable provider."""
    return tuple(
        index
        for index, item in enumerate(entry.changes)
        if not item.unexplained_kind and PROVIDER_SHAPE.match(item.unexplained)
    )


def needs(target: RepairTarget) -> bool:
    """Whether this repair has anything to say about one entry, restated or counted."""
    return bool(selected(target.entry) or withheld(target.entry))


def repair(target: RepairTarget) -> RepairResult:
    """Restate what can be restated, count what cannot, and say what moved.

    The rebuilt entry rides on the result only when it differs from what is committed, so a
    caller may run this over a whole repository and write nothing where it has nothing to say.
    """
    entry = target.entry
    restate, leave = selected(entry), withheld(entry)
    changes = list(entry.changes)
    detail: list[str] = []
    for index in restate:
        item = changes[index]
        changes[index] = item.model_copy(
            update={"unexplained": MODEL_FAILED, "unexplained_kind": _MODEL_FAILED_KIND}
        )
        detail.append(f"{_unit(entry, index)}: reason restated")
    for index in leave:
        detail.append(f"{_unit(entry, index)}: provider-shape note left as it is")
    rebuilt = rebuild(
        entry, delta=delta_of(entry), corroboration=entry.corroboration, changes=tuple(changes)
    )
    return RepairResult(
        target=target,
        addressed=len(restate) + len(leave),
        repaired=len(restate),
        remaining=len(leave),
        entry=rebuilt if moved(entry, rebuilt) else None,
        detail=tuple(detail),
    )


def _unit(entry: ChangelogEntry, index: int) -> str:
    return entry.changes[index].change.location.canonical
