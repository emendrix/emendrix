"""Entries carrying a textless row, in the two shapes the published record holds one.

**A row only the instruction parse named.** Until 2026-10-08 a unit only the instruction parse
named, which neither the structural diff nor the corpus metadata named, was appended to the
delta as a change with no text and shipped `disputed`. Since then `corroborate` lists such a
unit in the report's `instruction_only_units` instead, so it can no longer produce the row.
Published entries written before that date still carry it, and a repair has to meet them, so
`with_instruction_only_row` puts one back into an entry the shipped writer produced. The row is
built from the committed signals with the verdicts the merge gave one (the diff `ABSENT`, the
metadata `ABSENT` against its own note, the instruction parse `OBSERVED`), and the report is
re-measured by the shipped `report_of` over the delta that holds it, so the dispute, the unit
counts and the agreement figures are the ones such an entry was published with.

**A row the metadata names.** That one the merge still appends, so `named_by_metadata` adds the
unit to the committed metadata claims and lets the shipped repair build the row. It is the
textless change a repair keeps, which is what a test about restating one needs.

A sibling of `repaired_repo.py`, split out because both shapes are one subject.
"""

from __future__ import annotations

from emendrix.core import (
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionRef,
    Signal,
    SignalClaim,
    SignalObservation,
    SignalReport,
    SignalSet,
    SignalStatus,
)
from emendrix.corroborate.report import report_of
from emendrix.output import ChangelogEntry
from emendrix.repair import RepairTarget, rebuild
from emendrix.repair.corroborate import instructions_of, repair, signals_of, textless_change

__all__ = ["named_by_metadata", "with_instruction_only_row"]


def with_instruction_only_row(entry: ChangelogEntry, unit: ProvisionLocation) -> ChangelogEntry:
    """`entry` with `unit` appended the way the loop appended it before 2026-10-08.

    The committed instruction signal must name `unit` and the committed metadata must not,
    which is the only shape the rule that retired this row applies to.
    """
    metadata, instructions = signals_of(entry), instructions_of(entry)
    assert metadata is not None and instructions is not None, entry.to_version
    assert unit.canonical in {item.canonical for item in instructions.units}
    assert unit.canonical not in {item.canonical for item in metadata.units}

    signals = SignalSet(
        structural_diff=SignalObservation(
            status=SignalStatus.ABSENT, detail=Signal.STRUCTURAL_DIFF.value
        ),
        corpus_metadata=_verdict(metadata, unit),
        instruction_parse=_verdict(instructions, unit),
    )
    row = Change(
        change_type=_kind(instructions, unit),
        provision=ProvisionRef(act=entry.act, version=entry.to_version, location=unit),
        signals=signals,
        disputed=signals.disagreement,
        amending_acts=tuple(
            dict.fromkeys(
                claim.amending_act
                for claim in instructions.claims_for(unit)
                if claim.amending_act is not None
            )
        ),
    )
    index = next(
        (
            position
            for position, item in enumerate(entry.changes)
            if item.change.location.sort_key > unit.sort_key
        ),
        len(entry.changes),
    )
    changes = (*entry.changes[:index], textless_change(row), *entry.changes[index:])
    delta = Delta(
        act=entry.act,
        from_version=entry.from_version,
        to_version=entry.to_version,
        changes=tuple(item.change for item in changes),
        unchanged_units=entry.summary.unchanged_units,
    )
    others = (metadata, instructions)
    kinds = {report.signal: report.kinds_by_unit() for report in others}
    return rebuild(
        entry, delta=delta, corroboration=report_of(delta, others, kinds), changes=changes
    )


def _verdict(report: SignalReport, unit: ProvisionLocation) -> SignalObservation:
    """One available signal's verdict on `unit`, as the merge records it."""
    if not report.available:
        return SignalObservation(status=SignalStatus.UNAVAILABLE, detail=report.note)
    claimed = report.kinds_by_unit().get(unit.canonical)
    if claimed is None:
        return SignalObservation(status=SignalStatus.ABSENT, detail=report.note)
    sources = [claim.source for claim in report.claims_for(unit) if claim.source]
    return SignalObservation(
        status=SignalStatus.OBSERVED,
        detail="; ".join(dict.fromkeys(sources)) or report.note,
        change_types=tuple(sorted(claimed)),
    )


def _kind(report: SignalReport, unit: ProvisionLocation) -> ChangeType:
    """What the signal says the unit is, or `MODIFIED` where it does not say one thing."""
    claimed = report.kinds_by_unit().get(unit.canonical) or frozenset()
    return next(iter(claimed)) if len(claimed) == 1 else ChangeType.MODIFIED


def named_by_metadata(target: RepairTarget, unit: ProvisionLocation) -> RepairTarget:
    """`target` with `unit` also claimed by its committed metadata, merged by the shipped repair.

    The claim names the act the committed instruction signal names, so the entry still names
    one amending act and stays a candidate for every repair that asks for one.
    """
    entry = target.entry
    report, instructions = entry.corroboration, instructions_of(entry)
    assert report is not None and instructions is not None, entry.to_version
    amender = next(
        (claim.amending_act for claim in instructions.claims if claim.amending_act), None
    )
    signals = tuple(
        item.model_copy(
            update={
                "claims": (*item.claims, SignalClaim(location=unit, amending_act=amender)),
                "units": tuple(sorted({*item.units, unit}, key=lambda location: location.sort_key)),
            }
        )
        if item.signal is Signal.CORPUS_METADATA
        else item
        for item in report.signals
    )
    claimed = entry.model_copy(
        update={"corroboration": report.model_copy(update={"signals": signals})}
    )
    merged = repair(RepairTarget(path=target.path, entry=claimed), instructions)
    assert merged.entry is not None, entry.to_version
    return RepairTarget(path=target.path, entry=merged.entry)
