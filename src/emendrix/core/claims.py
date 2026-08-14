"""What one signal claims, in a shape no signal's own vocabulary shows through.

Three independent signals say where an act changed. Two of them, the corpus's own modification
metadata and the parse of the amending document's instruction prose, are capabilities of one
adapter, and their records are full of that corpus's vocabulary. This module is the narrow form
they are reduced to before corroboration sees them: a location, a kind, optionally the date the
signal says it took effect, a string that says where in the source it came from, and, where the
signal names it, the act whose amendment the claim reports.

The core therefore never learns what a role code or an instruction verb is, and
`emendrix.corroborate` runs unchanged on the toy corpus.

## The comparison convention

Two rules turn a claim into something comparable at the unit of change, and both are here
rather than in any adapter because both are about the change model, not about any corpus.

1. **`DEFERRED` and `RENUMBERED` compare as `MODIFIED`.** They are refinements the structural
   diff makes and no other signal can make: a corpus that annotates "replaced" is not
   dissenting from "the date it applies from moved".
2. **Only a claim about the unit itself can insert or delete that unit.** An annotation on
   `AR 5 PA 1 ALN 1 PTA (bb)` with the corpus's insert role says a point was inserted *into*
   Article 5, so Article 5 was modified. Reading it as "Article 5 was inserted" would
   manufacture a disagreement with the diff on every act. Verified against the AI Act's 88
   annotations on 2026-08-06: this rule maps them onto exactly the diff's 7 insertions and 38
   modifications, with no disagreement (asserted by `tests/diff/test_eu_ai_act.py`).
"""

from __future__ import annotations

from datetime import date
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core.changes import ChangeType, Signal
from emendrix.core.identifiers import ActId
from emendrix.core.location import ProvisionLocation

__all__ = ["COMPARABLE_KIND", "SignalClaim", "SignalReport", "comparable_kind"]

COMPARABLE_KIND: Final[dict[ChangeType, ChangeType]] = {
    ChangeType.INSERTED: ChangeType.INSERTED,
    ChangeType.MODIFIED: ChangeType.MODIFIED,
    ChangeType.DELETED: ChangeType.DELETED,
    ChangeType.RENUMBERED: ChangeType.MODIFIED,
    ChangeType.DEFERRED: ChangeType.MODIFIED,
}
"""Rule 1 above, as a table: what a change type is compared *as* across signals."""


def comparable_kind(change_type: ChangeType) -> ChangeType:
    """The kind `change_type` is compared as when two signals are held against each other."""
    return COMPARABLE_KIND[change_type]


class SignalClaim(BaseModel):
    """One signal's statement that one location changed, in one way, at one date.

    `location` is kept at whatever depth the signal published it, because a corpus that
    annotates `AR 5 PA 1 ALN 1 PTA (bb)` is saying something the unit-level comparison throws
    away and later stages want back. Comparison happens on `unit` and `unit_kind`.
    """

    model_config = ConfigDict(frozen=True)

    location: ProvisionLocation
    change_type: ChangeType | None = Field(
        default=None, description="What the signal says happened *at* `location`, if it says."
    )
    in_force: date | None = Field(
        default=None, description="The date the signal says the change took effect (clock 1)."
    )
    source: str | None = Field(
        default=None, description="Where in the signal's source this came from; for audit only."
    )
    amending_act: ActId | None = Field(
        default=None,
        description="The act whose amendment this claim reports, where the signal names one.",
    )

    @property
    def unit(self) -> ProvisionLocation:
        """The top-level provision this claim is counted under."""
        return self.location.top_level

    @property
    def unit_kind(self) -> ChangeType | None:
        """How this claim reads at unit granularity: rule 2 of the module docstring."""
        if self.change_type is None:
            return None
        if self.location.depth == 1:
            return comparable_kind(self.change_type)
        return ChangeType.MODIFIED


class SignalReport(BaseModel):
    """Everything one signal has to say about one pair of versions.

    `available` is the difference between *this signal saw nothing here* and *this signal
    could not be computed at all*. A corpus that publishes no modification metadata does not
    dissent from the diff, and a report that cannot tell the two apart turns every act into a
    dispute (`SignalStatus.UNAVAILABLE` is the value that carries it downstream).
    """

    model_config = ConfigDict(frozen=True)

    signal: Signal
    available: bool = True
    claims: tuple[SignalClaim, ...] = ()
    note: str | None = Field(
        default=None, description="Why this signal is unavailable, or what it is scoped to."
    )

    @classmethod
    def unavailable(cls, signal: Signal, note: str | None = None) -> Self:
        """A signal that could not be computed, which is not a signal that saw nothing."""
        return cls(signal=signal, available=False, note=note)

    @property
    def units(self) -> tuple[ProvisionLocation, ...]:
        """The distinct top-level units this signal names, in canonical order."""
        seen = {claim.unit.canonical: claim.unit for claim in self.claims}
        return tuple(sorted(seen.values(), key=lambda unit: unit.sort_key))

    def kinds_by_unit(self) -> dict[str, frozenset[ChangeType]]:
        """Unit → every kind this signal claimed for it. A unit can carry more than one."""
        collected: dict[str, set[ChangeType]] = {}
        for claim in self.claims:
            kinds = collected.setdefault(claim.unit.canonical, set())
            if (kind := claim.unit_kind) is not None:
                kinds.add(kind)
        return {unit: frozenset(kinds) for unit, kinds in collected.items()}

    def in_force_by_unit(self) -> dict[str, date]:
        """Unit → the earliest date this signal gives it (clock 1), where it gives one."""
        dates: dict[str, date] = {}
        for claim in self.claims:
            if claim.in_force is None:
                continue
            key = claim.unit.canonical
            found = dates.get(key)
            if found is None or claim.in_force < found:
                dates[key] = claim.in_force
        return dates

    def claims_for(self, unit: ProvisionLocation) -> tuple[SignalClaim, ...]:
        """Every claim that lands in `unit`, in the order the signal published them."""
        key = unit.canonical
        return tuple(claim for claim in self.claims if claim.unit.canonical == key)
