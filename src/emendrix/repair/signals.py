"""The rules the second opinions follow, applied to every entry already committed.

Two signals are rebuilt from the claims the entry already carries, and the merge decides again
what ships. The metadata signal is read through a normaliser the composition root hands in,
which is where a corpus says which of its location codes name a unit and which name a
container; nothing here knows. The instruction signal follows one rule that is generic over any
corpus: a signal that was read and claims nothing in the window has no reading of it, so it is
unavailable rather than silent, and silence never dissents. A unit only the instruction parse
names leaves the change list for the report's `instruction_only_units`, which the merge itself
decides.

**Nothing is fetched and nothing is asked.** Both signals come out of the committed payload, so
the repair needs no network, no clock and no model, and a notice that has gained annotations
since the entry was published cannot reach it. The rows it stops appending carry no text and
were never asked about, so no model call is retracted, and the `explain` and `gate` blocks are
carried over byte-identical, as is every sentence.

Core types only, and the committed document.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import SignalReport
from emendrix.output import ChangelogEntry
from emendrix.repair.corroborate import instructions_of, remerge, signals_of
from emendrix.repair.entry import RepairResult, RepairTarget, changes_by_unit

__all__ = [
    "KIND",
    "SILENT",
    "Normaliser",
    "SignalTally",
    "by_act",
    "needs",
    "repair",
    "silence_unavailable",
    "tally_of",
]

KIND = "signals"
"""What this repair is called, on the command line and in the record it writes."""

SILENT = "nothing claimed in this window, so this signal has no reading of it"
"""The clause the instruction signal's note ends on when it claims nothing in its window."""

Normaliser = Callable[[SignalReport | None], SignalReport | None]
"""A committed metadata signal read under the corpus's own rules for its location codes."""


def needs(target: RepairTarget) -> bool:
    """Every entry the second opinions took part in; a diff-only entry has none to correct."""
    return target.entry.corroboration is not None


def silence_unavailable(report: SignalReport | None) -> SignalReport | None:
    """An instruction signal that claims nothing, reported unavailable with a note saying so.

    The note keeps what the committed one said, which is how a reader tells an act that was
    read and claimed nothing here from one that could not be read at all.
    """
    if report is None or not report.available or report.claims:
        return report
    note = f"{report.note}, {SILENT}" if report.note else SILENT
    return SignalReport.unavailable(report.signal, note=note)


def repair(target: RepairTarget, *, normalise_metadata: Normaliser) -> RepairResult:
    """Both second opinions rebuilt under today's rules from the entry's own claims, and merged.

    An entry is rewritten only where the rules move a signal, a verdict or a row. One they
    leave as it is would still re-serialise differently if it was written under an older schema
    or with an older wording of the textless reason, and those are corrected when something
    rewrites the entry, never in bulk by a pass with nothing of its own to say.
    """
    entry = target.entry
    result = remerge(
        target,
        metadata=normalise_metadata(signals_of(entry)),
        instructions=silence_unavailable(instructions_of(entry)),
    )
    if result.entry is None or _signals_moved(entry, result.entry):
        return result
    return RepairResult(target=target, addressed=result.addressed)


class SignalTally(BaseModel):
    """What one pass did to the changes of one act, or of a whole repository.

    Every figure is a count of change rows, so the before and after columns are over different
    rows wherever a row stopped being appended. That is the point of printing both rather than
    a rate.
    """

    model_config = ConfigDict(frozen=True)

    act: str = Field(description="The act's key, or `total` for the sum over every act.")
    entries: int = Field(default=0, ge=0, description="Entries addressed.")
    changed: int = Field(default=0, ge=0, description="Entries the pass would rewrite.")
    changes_before: int = Field(default=0, ge=0)
    changes_after: int = Field(default=0, ge=0)
    disputed_before: int = Field(default=0, ge=0)
    disputed_after: int = Field(default=0, ge=0)
    textless_before: int = Field(default=0, ge=0, description="Rows no signal gave text for.")
    textless_after: int = Field(default=0, ge=0)
    instruction_only: int = Field(
        default=0, ge=0, description="Units the rebuilt reports list as named only by the parse."
    )
    cleared: int = Field(default=0, ge=0, description="Changes flipping disputed to undisputed.")
    raised: int = Field(default=0, ge=0, description="Changes flipping undisputed to disputed.")

    def plus(self, other: SignalTally, *, act: str) -> SignalTally:
        """The field-wise sum of two tallies, under the name given."""
        counts = {
            name: getattr(self, name) + getattr(other, name)
            for name in type(self).model_fields
            if name != "act"
        }
        return SignalTally(act=act, **counts)


def tally_of(result: RepairResult) -> SignalTally:
    """One entry's figures, before and after. An entry that does not move counts the same twice."""
    before = result.target.entry
    after = before if result.entry is None else result.entry
    left, right = changes_by_unit(before), changes_by_unit(after)
    shared = left.keys() & right.keys()
    report = after.corroboration
    return SignalTally(
        act=before.act.key,
        entries=1,
        changed=int(result.entry is not None),
        changes_before=len(before.changes),
        changes_after=len(after.changes),
        disputed_before=before.counts.disputed,
        disputed_after=after.counts.disputed,
        textless_before=_textless(before),
        textless_after=_textless(after),
        instruction_only=0 if report is None else len(report.instruction_only_units),
        cleared=sum(1 for key in shared if left[key].change.disputed > right[key].change.disputed),
        raised=sum(1 for key in shared if left[key].change.disputed < right[key].change.disputed),
    )


def by_act(results: Iterable[RepairResult]) -> tuple[tuple[SignalTally, ...], SignalTally]:
    """One tally per act in the order the acts were met, and the total over all of them."""
    acts: dict[str, SignalTally] = {}
    for result in results:
        found = tally_of(result)
        held = acts.get(found.act)
        acts[found.act] = found if held is None else held.plus(found, act=found.act)
    total = SignalTally(act="total")
    for tally in acts.values():
        total = total.plus(tally, act="total")
    return tuple(acts.values()), total


def _signals_moved(before: ChangelogEntry, after: ChangelogEntry) -> bool:
    """Whether the corroboration report or any change's own record differs between the two."""
    if before.corroboration != after.corroboration:
        return True
    return tuple(item.change for item in before.changes) != tuple(
        item.change for item in after.changes
    )


def _textless(entry: ChangelogEntry) -> int:
    return sum(1 for item in entry.changes if item.change.textless)
