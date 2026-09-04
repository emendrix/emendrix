"""The deterministic repair: the third signal recomputed over an entry already committed.

`corroborate` is a pure function of a delta and two signal reports, and both of its inputs
survive in the committed payload: the metadata signal round-trips out of it field for field, and
the changes the structural diff observed carry their own verbatim text. So an entry whose
instruction parse has since been corrected can be rebuilt with no provider, no cassette and no
re-diff, and the merge decides what ships exactly as it did the first time.

**The prose is carried over and the run record is not touched.** A unit only one signal saw
never had an explanation: it carries no text, so the explain stage recorded that it had nothing
to explain and made no call. Dropping such a unit therefore retracts no model call and no gate
decision, and the `explain` and `gate` blocks stay byte-identical.

**This repair drops nothing itself.** It recomputes the signal and hands the merge the result;
if the corrected signal still names a unit the diff did not see, the merge re-creates it and it
ships as before.

Core types only. The signal it is handed is built by a composition root that knows which corpus
this is; nothing here does.
"""

from __future__ import annotations

from collections import Counter

from emendrix.core import ActId, Change, Signal, SignalReport
from emendrix.corroborate import Corroboration, corroborate
from emendrix.explain import NOTHING_TO_EXPLAIN
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry
from emendrix.repair.entry import (
    ChangeKey,
    RepairResult,
    RepairTarget,
    changes_by_unit,
    delta_of,
    moved,
    rebuild,
    shift_between,
)

__all__ = ["KIND", "amending_act_of", "instructions_of", "needs", "repair", "signals_of"]

KIND = "corroboration"
"""What this repair is called, on the command line and in the record it writes."""

_NOTHING_TO_EXPLAIN_KIND = "nothing_to_explain"
"""The counted kind the explain stage records against a change that carries no text."""


def signals_of(entry: ChangelogEntry) -> SignalReport | None:
    """The metadata signal, rebuilt field for field from the committed payload.

    None when the entry carries no corroboration at all, which is a diff-only entry rather than
    a signal that saw nothing.
    """
    return _report_of(entry, Signal.CORPUS_METADATA)


def instructions_of(entry: ChangelogEntry) -> SignalReport | None:
    """The instruction signal as it was committed: what a re-parse replaces."""
    return _report_of(entry, Signal.INSTRUCTION_PARSE)


def amending_act_of(entry: ChangelogEntry) -> ActId | None:
    """The one act this entry's signals name as the amender, or None when that is not one act.

    The instruction signal is read only where the corroboration window named exactly one
    amending act, so a candidate entry names one act across every claim it carries. More than
    one, or none, is an entry whose third signal cannot be re-derived from the payload alone.
    """
    report = entry.corroboration
    if report is None:
        return None
    named = {
        claim.amending_act
        for signal in report.signals
        for claim in signal.claims
        if claim.amending_act is not None
    }
    return named.pop() if len(named) == 1 else None


def needs(target: RepairTarget) -> bool:
    """Whether this repair has a signal it could recompute for one entry.

    Two conditions, and each excludes a different thing. An entry whose committed instruction
    signal is unavailable is one the third signal took no part in, and reading it now would be
    adding a signal rather than correcting one, which is a different operation on a published
    document. An entry whose claims name no amending act, or more than one, is one whose third
    signal cannot be re-derived from the payload alone.
    """
    committed = instructions_of(target.entry)
    if committed is None or not committed.available:
        return False
    return amending_act_of(target.entry) is not None


def repair(target: RepairTarget, instructions: SignalReport | None) -> RepairResult:
    """Merge the recomputed third signal into the committed entry and say what moved.

    The rebuilt entry rides on the result only when it differs from what is committed, so a
    caller may run this over a whole repository and write nothing where it has nothing to say.
    """
    entry = target.entry
    merged = corroborate(delta_of(entry), metadata=signals_of(entry), instructions=instructions)
    rebuilt = rebuild(
        entry,
        delta=merged.delta,
        corroboration=merged.report,
        changes=_reattached(entry, merged),
    )
    addressed = len(entry.changes)
    if not moved(entry, rebuilt):
        return RepairResult(target=target, addressed=addressed)
    shift = shift_between(entry, rebuilt)
    return RepairResult(
        target=target,
        addressed=addressed,
        repaired=shift.changed,
        entry=rebuilt,
        detail=shift.lines,
    )


# ------------------------------------------------------------------ the pieces


def _report_of(entry: ChangelogEntry, signal: Signal) -> SignalReport | None:
    report = entry.corroboration
    if report is None:
        return None
    for committed in report.signals:
        if committed.signal is signal:
            return SignalReport(
                signal=committed.signal,
                available=committed.available,
                claims=committed.claims,
                note=committed.note,
            )
    return None


def _reattached(entry: ChangelogEntry, merged: Corroboration) -> tuple[EmittedChange, ...]:
    """Each merged change carrying the prose the committed entry gave its unit.

    Keyed by the unit and the occurrence within it, which is the key corroboration itself
    compares on. A unit only one signal saw is disjoint from every unit the diff produced a
    change for, so a key can never move from a change that carries text to one that does not.
    """
    committed = changes_by_unit(entry)
    seen: Counter[str] = Counter()
    attached: list[EmittedChange] = []
    for change in merged.delta.changes:
        unit = change.unit.canonical
        key: ChangeKey = (unit, seen[unit])
        seen[unit] += 1
        found = committed.get(key)
        attached.append(
            _textless(change) if found is None else found.model_copy(update={"change": change})
        )
    return tuple(attached)


def _textless(change: Change) -> EmittedChange:
    """A unit the corrected signal names and the diff never saw: no text, and the stated reason.

    The same shape and the same curated reason the explain stage records against such a change,
    because that is what it is: a change nothing was ever asked about, and never a gap.
    """
    return EmittedChange(
        change=change,
        outcome=GateOutcome.UNEXPLAINED,
        unexplained=NOTHING_TO_EXPLAIN,
        unexplained_kind=_NOTHING_TO_EXPLAIN_KIND,
    )
