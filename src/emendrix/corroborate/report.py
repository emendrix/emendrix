"""What corroboration measured: per-signal unit sets, pairwise agreement, disagreements.

The report is the object the eval harness scores and the changelog surfaces, and it exists so
that a claim about agreement between the signals is a number somebody can check rather than a
sentence. Everything in it is at the unit of change, the top-level provision, because that is
the granularity the two location vocabularies agree on and the one the headline metric is
stated at.

**Precision and recall are directional and say so.** `precision` is of `left` against `right`:
of the units the left signal named, the share the right signal also named. Nothing here calls
either signal correct. Where the structural diff names 40 units and the corpus metadata names 9,
it is the metadata that is incomplete, and the report's job is to publish the disagreement
rather than to resolve it. Both counts are asserted in
`tests/corroborate/test_eu_corroboration.py`.

Core types only, no corpus anywhere: this runs unchanged on the toy corpus.
"""

from __future__ import annotations

from itertools import combinations
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import (
    ActId,
    Change,
    ChangeType,
    Delta,
    ProvisionLocation,
    Signal,
    SignalClaim,
    SignalReport,
    SignalStatus,
    VersionId,
    comparable_kind,
)

__all__ = [
    "CorroborationReport",
    "Disagreement",
    "SignalAgreement",
    "SignalUnits",
    "agreement",
    "report_of",
]


class SignalUnits(BaseModel):
    """One signal's verdict: the top-level units it named, and the claims behind them.

    `units` is the comparison surface, deduplicated to top level, and it is what every
    agreement figure is computed over. `claims` is what the signal actually said, at the depth
    it said it, kept because a corpus that annotates `AR 5 PA 1 ALN 1 PTA (bb)` is saying
    something the unit-level comparison throws away. The structural diff carries no claims: it
    produces the changes themselves, so a copy here would be a second delta.
    """

    model_config = ConfigDict(frozen=True)

    signal: Signal
    available: bool = True
    units: tuple[ProvisionLocation, ...] = ()
    note: str | None = None
    claims: tuple[SignalClaim, ...] = Field(
        default=(),
        description="What this signal claimed, at the depth it claimed it. Empty for the diff.",
    )

    @property
    def count(self) -> int:
        return len(self.units)

    @classmethod
    def of(cls, report: SignalReport) -> Self:
        return cls(
            signal=report.signal,
            available=report.available,
            units=report.units,
            note=report.note,
            claims=report.claims,
        )


class SignalAgreement(BaseModel):
    """How far two signals agree on which units changed. Directional: see the module docstring."""

    model_config = ConfigDict(frozen=True)

    left: Signal
    right: Signal
    left_units: int = Field(ge=0)
    right_units: int = Field(ge=0)
    shared: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0, description="Share of `left`'s units `right` names.")
    recall: float = Field(ge=0.0, le=1.0, description="Share of `right`'s units `left` names.")
    f1: float = Field(ge=0.0, le=1.0)
    kind_mismatches: int = Field(
        default=0, ge=0, description="Shared units the two signals classify differently."
    )


class Disagreement(BaseModel):
    """One unit the signals do not agree about, and what the disagreement is.

    Never a defect of the diff by construction: it is a defect of *something*, and which one
    is a finding for the eval harness to argue, not for this module to assume.
    """

    model_config = ConfigDict(frozen=True)

    unit: ProvisionLocation
    reason: str
    observed_by: tuple[Signal, ...] = ()
    absent_from: tuple[Signal, ...] = ()
    kinds: tuple[tuple[Signal, tuple[ChangeType, ...]], ...] = ()


class CorroborationReport(BaseModel):
    """The measured result of merging three signals over one pair of versions."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    from_version: VersionId
    to_version: VersionId
    signals: tuple[SignalUnits, ...] = ()
    agreements: tuple[SignalAgreement, ...] = ()
    disagreements: tuple[Disagreement, ...] = ()
    metadata_only_units: tuple[ProvisionLocation, ...] = Field(
        default=(), description="Units another signal named and the structural diff did not."
    )

    @property
    def disputed_units(self) -> int:
        return len(self.disagreements)

    def units_of(self, signal: Signal) -> tuple[ProvisionLocation, ...]:
        return next((item.units for item in self.signals if item.signal is signal), ())

    def agreement_of(self, left: Signal, right: Signal) -> SignalAgreement | None:
        return next(
            (item for item in self.agreements if item.left is left and item.right is right), None
        )


def agreement(
    left: SignalUnits, right: SignalUnits, *, kind_mismatches: int = 0
) -> SignalAgreement:
    """Pairwise precision, recall and F1 of `left` against `right`, at unit granularity.

    Two empty sets agree perfectly, because a version pair where nothing changed is not a
    failure, and one empty set against a non-empty one scores zero, which is the honest reading.
    """
    left_units = {unit.canonical for unit in left.units}
    right_units = {unit.canonical for unit in right.units}
    shared = len(left_units & right_units)
    precision = 1.0 if not left_units else shared / len(left_units)
    recall = 1.0 if not right_units else shared / len(right_units)
    total = precision + recall
    return SignalAgreement(
        left=left.signal,
        right=right.signal,
        left_units=len(left_units),
        right_units=len(right_units),
        shared=shared,
        precision=precision,
        recall=recall,
        f1=0.0 if total == 0 else 2 * precision * recall / total,
        kind_mismatches=kind_mismatches,
    )


def pairs(available: tuple[SignalUnits, ...]) -> list[tuple[SignalUnits, SignalUnits]]:
    """Every ordered pair of available signals, in the fixed order `Signal` declares."""
    return [
        (left, right)
        for left, right in combinations(available, 2)
        if left.available and right.available
    ]


def report_of(
    delta: Delta,
    others: tuple[SignalReport, ...],
    kinds: dict[Signal, dict[str, frozenset[ChangeType]]],
) -> CorroborationReport:
    """Measure an already-merged delta: who saw what, how far they agree, and where they do not.

    Read off `Change.signals`, so the report cannot drift from what the delta actually ships.
    """
    diff_units = SignalUnits(
        signal=Signal.STRUCTURAL_DIFF,
        units=tuple(
            sorted(
                {
                    change.unit.canonical: change.unit
                    for change in delta.changes
                    if change.signals.structural_diff.observed
                }.values(),
                key=lambda unit: unit.sort_key,
            )
        ),
    )
    sets = (diff_units, *(SignalUnits.of(report) for report in others))
    return CorroborationReport(
        act=delta.act,
        from_version=delta.from_version,
        to_version=delta.to_version,
        signals=sets,
        agreements=tuple(_agreements(sets, delta, kinds)),
        disagreements=tuple(_disagreements(delta)),
        metadata_only_units=tuple(
            change.unit
            for change in delta.changes
            if change.signals.structural_diff.status is SignalStatus.ABSENT
        ),
    )


def _agreements(
    sets: tuple[SignalUnits, ...],
    delta: Delta,
    kinds: dict[Signal, dict[str, frozenset[ChangeType]]],
) -> list[SignalAgreement]:
    found: list[SignalAgreement] = []
    for left, right in pairs(sets):
        mismatches = sum(
            1
            for change in delta.changes
            if _both_observed(change, left.signal, right.signal)
            and not _kinds(change, left.signal, kinds) & _kinds(change, right.signal, kinds)
        )
        found.append(agreement(left, right, kind_mismatches=mismatches))
    return found


def _kinds(
    change: Change, signal: Signal, kinds: dict[Signal, dict[str, frozenset[ChangeType]]]
) -> frozenset[ChangeType]:
    if signal is Signal.STRUCTURAL_DIFF:
        return frozenset({comparable_kind(change.change_type)})
    return kinds[signal].get(change.unit.canonical) or frozenset()


def _both_observed(change: Change, left: Signal, right: Signal) -> bool:
    verdicts = dict(change.signals.observations)
    return all(verdicts[signal].observed for signal in (left, right))


def _disagreements(delta: Delta) -> list[Disagreement]:
    found: list[Disagreement] = []
    for change in delta.changes:
        if not change.disputed:
            continue
        observations = change.signals.observations
        observed = tuple(signal for signal, seen in observations if seen.observed)
        absent = tuple(
            signal for signal, seen in observations if seen.status is SignalStatus.ABSENT
        )
        kinds = tuple(
            (signal, seen.change_types) for signal, seen in observations if seen.change_types
        )
        found.append(
            Disagreement(
                unit=change.unit,
                reason=_reason(observed, absent),
                observed_by=observed,
                absent_from=absent,
                kinds=kinds,
            )
        )
    return found


def _reason(observed: tuple[Signal, ...], absent: tuple[Signal, ...]) -> str:
    if absent:
        seen = ", ".join(signal.value for signal in observed) or "no signal"
        missed = ", ".join(signal.value for signal in absent)
        return f"seen by {seen}, not by {missed}"
    return "signals disagree on the kind of change"
