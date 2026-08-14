"""Merging three signals into one delta, without losing any of them.

The structural diff is the primary shipped signal and the only one carrying text; the
corpus's modification metadata is the evaluation reference set; the instruction parse is a
measured cross-check. This module holds them against each other at the unit of change and
writes what it finds onto every `Change`:

- each signal's verdict lands in `Change.signals` as `OBSERVED`, `ABSENT` or `UNAVAILABLE`.
  A signal that could not be computed is `UNAVAILABLE` and **never** dissents;
- `Change.disputed` follows from those verdicts (it is derived in `core.delta`, not asserted
  here) and is true when the signals disagree on presence *or* on kind;
- a unit another signal names and the diff does not is appended to the delta as a change with
  no text and `structural_diff = ABSENT`. It ships `disputed`. It is never dropped, and it is
  never merged into a neighbour;
- `Change.in_force` is filled from whatever date the metadata gives the unit (clock 1).

Everything is core types. No corpus vocabulary reaches this module: the roles, the verbs and the
notice formats stay in the adapter that read them, and `tests/test_architecture.py` greps for
it.

**The metadata is a reference, never an oracle.** On the REACH 2008→2009 transition the diff
finds 40 units and the annotations name 9, because the corpus annotates a blanket amendment once
and does not enumerate where it lands. That produces 33 disputed changes here, and it should:
the disagreement is the finding. Both figures are asserted in
`tests/corroborate/test_eu_corroboration.py`, and they include the one metadata unit the diff
cannot key. Discarding that unit to make the counts tidier is forbidden: it is a real
disagreement and it is exactly what this package exists to publish.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from emendrix.core import (
    ActId,
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionRef,
    Signal,
    SignalObservation,
    SignalReport,
    SignalSet,
    SignalStatus,
    comparable_kind,
    sort_changes,
)
from emendrix.corroborate.report import CorroborationReport, report_of

__all__ = ["Corroboration", "corroborate"]


class Corroboration(BaseModel):
    """The delta as the three signals leave it, and the measurement of their agreement."""

    model_config = ConfigDict(frozen=True)

    delta: Delta
    report: CorroborationReport

    @property
    def disputed(self) -> int:
        return self.delta.summary.disputed


def corroborate(
    delta: Delta,
    *,
    metadata: SignalReport | None = None,
    instructions: SignalReport | None = None,
) -> Corroboration:
    """Merge the two non-diff signals into `delta` and measure how far the three agree.

    A signal passed as `None`, or as a report with `available=False`, is one this corpus or this
    act could not supply. It is recorded as `UNAVAILABLE` on every change and takes no part in
    the agreement figures.
    """
    others = (
        _report(Signal.CORPUS_METADATA, metadata),
        _report(Signal.INSTRUCTION_PARSE, instructions),
    )
    kinds = {report.signal: report.kinds_by_unit() for report in others}
    in_force = others[0].in_force_by_unit()

    merged = [_merge_change(change, others, kinds, in_force) for change in delta.changes]
    seen = {change.unit.canonical for change in delta.changes}
    extra = _missing_units(delta, others, kinds, in_force, seen)
    updated = delta.model_copy(update={"changes": _interleave(merged, extra)})
    return Corroboration(delta=updated, report=report_of(updated, others, kinds))


def _interleave(ordered: list[Change], extra: list[Change]) -> tuple[Change, ...]:
    """Put each appended change where its location belongs in the delta's own order.

    The diff emits document order of the new version with deletions at their old anchor, and
    that order is more informative than a location sort, so it is preserved rather than
    recomputed (`core.sort_changes` is the fallback for engines that have no such order). Each
    appended change is placed before the first change that sorts after it, which lands it among
    its neighbours instead of in a clump at the end, and does so deterministically, which is
    what byte-stable changelogs require.
    """
    if not extra:
        return tuple(ordered)
    result = list(ordered)
    for change in sort_changes(tuple(extra)):
        key = change.location.sort_key
        index = next(
            (position for position, seen in enumerate(result) if seen.location.sort_key > key),
            len(result),
        )
        result.insert(index, change)
    return tuple(result)


# ------------------------------------------------------------------ per change


def _report(signal: Signal, given: SignalReport | None) -> SignalReport:
    return given if given is not None else SignalReport.unavailable(signal)


def _observation(
    report: SignalReport, kinds: dict[str, frozenset[ChangeType]], unit: ProvisionLocation
) -> SignalObservation:
    if not report.available:
        return SignalObservation(status=SignalStatus.UNAVAILABLE, detail=report.note)
    claimed = kinds.get(unit.canonical)
    if claimed is None:
        return SignalObservation(status=SignalStatus.ABSENT, detail=report.note)
    sources = [claim.source for claim in report.claims_for(unit) if claim.source]
    return SignalObservation(
        status=SignalStatus.OBSERVED,
        detail="; ".join(dict.fromkeys(sources)) or report.note,
        change_types=tuple(sorted(claimed)),
    )


def _amending_acts(others: tuple[SignalReport, ...], unit: ProvisionLocation) -> tuple[ActId, ...]:
    """Every act the signals name as amending `unit`, deduplicated, first mention first.

    Order is stable because `others` is consulted in the fixed order `Signal` declares and each
    report's claims are in document order, so two runs of one delta produce identical bytes.
    `ActId` hashes on `(corpus, key)`, so the same act named by two signals appears once.
    """
    return tuple(
        dict.fromkeys(
            claim.amending_act
            for report in others
            if report.available
            for claim in report.claims_for(unit)
            if claim.amending_act is not None
        )
    )


def _signal_set(
    diff: SignalObservation,
    others: tuple[SignalReport, ...],
    kinds: dict[Signal, dict[str, frozenset[ChangeType]]],
    unit: ProvisionLocation,
) -> SignalSet:
    metadata, instructions = others
    return SignalSet(
        structural_diff=diff,
        corpus_metadata=_observation(metadata, kinds[metadata.signal], unit),
        instruction_parse=_observation(instructions, kinds[instructions.signal], unit),
    )


def _merge_change(
    change: Change,
    others: tuple[SignalReport, ...],
    kinds: dict[Signal, dict[str, frozenset[ChangeType]]],
    in_force: dict[str, date],
) -> Change:
    diff = SignalObservation(
        status=SignalStatus.OBSERVED,
        detail=Signal.STRUCTURAL_DIFF.value,
        change_types=(comparable_kind(change.change_type),),
    )
    signals = _signal_set(diff, others, kinds, change.unit)
    update: dict[str, object] = {
        "signals": signals,
        "disputed": signals.disagreement,
        "amending_acts": _amending_acts(others, change.unit),
    }
    stamped = in_force.get(change.unit.canonical)
    if stamped is not None and change.in_force is None:
        update["in_force"] = stamped
    return change.model_copy(update=update)


def _missing_units(
    delta: Delta,
    others: tuple[SignalReport, ...],
    kinds: dict[Signal, dict[str, frozenset[ChangeType]]],
    in_force: dict[str, date],
    seen: set[str],
) -> list[Change]:
    """Units another signal names that the diff never produced a change for.

    They ship as changes with no text: the diff is the only signal that has any, so
    "the metadata says Article 12 changed and the diff disagrees" is a change with a location,
    a kind, no quotable text and `disputed=True`.
    """
    # Signals are consulted in the fixed order `Signal` declares, so which one supplies an
    # appended change never depends on dict iteration order.
    extra: dict[str, Change] = {}
    for report in others:
        if not report.available:
            continue
        for unit in report.units:
            key = unit.canonical
            if key in seen or key in extra:
                continue
            diff = SignalObservation(
                status=SignalStatus.ABSENT, detail=Signal.STRUCTURAL_DIFF.value
            )
            signals = _signal_set(diff, others, kinds, unit)
            extra[key] = Change(
                change_type=_claimed_kind(others, kinds, key),
                provision=ProvisionRef(act=delta.act, version=delta.to_version, location=unit),
                in_force=in_force.get(key),
                signals=signals,
                disputed=signals.disagreement,
                amending_acts=_amending_acts(others, unit),
            )
    return list(extra.values())


def _claimed_kind(
    others: tuple[SignalReport, ...],
    kinds: dict[Signal, dict[str, frozenset[ChangeType]]],
    unit: str,
) -> ChangeType:
    """What an appended change is typed as: what the signals say, or `MODIFIED` if they differ.

    The diff is the signal that classifies and it did not see this unit at all, so where the
    remaining signals do not agree on one kind the weakest true statement is the one to ship.
    The disagreement itself is not lost: it is in the `SignalSet` and in `disputed`.
    """
    claimed = {
        kind
        for report in others
        if report.available
        for kind in kinds[report.signal].get(unit) or frozenset()
    }
    return claimed.pop() if len(claimed) == 1 else ChangeType.MODIFIED
