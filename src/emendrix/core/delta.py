"""One delta: the changes between two versions of one act, ordered so output is byte-stable.

A `Change` is produced by deterministic machinery only. Its type comes from the structural
diff, never from a model; its `before`/`after` are verbatim; its two clocks are separate
because "in force" and "applies from" are different questions. `SignalSet`, in
`emendrix.core.changes`, records which of the three independent signals saw it, so a
disagreement ships as `disputed` instead of being silently dropped or merged away.

This module knows nothing about how any of that is computed, only what the answer looks like.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from emendrix.core.changes import (
    Applicability,
    ApplicabilityUnknown,
    ChangeType,
    SignalSet,
    SignalStatus,
)
from emendrix.core.identifiers import ActId, ProvisionRef, VersionId
from emendrix.core.location import ProvisionLocation
from emendrix.core.provisions import ProvisionText

__all__ = [
    "Change",
    "Delta",
    "DeltaSummary",
    "sort_changes",
]


class Change(BaseModel):
    """One provision that changed between two versions of one act.

    The unit is the top-level provision; `changed_within` carries the finer coordinates
    the diff could localise, and `dates_removed`/`dates_added` the machine-readable dates that
    moved. Both are detail attached to the unit, never a second unit of their own.

    `amending_acts` is attribution, not classification: it says which acts a signal names as
    amending this unit. The structural diff carries no such fact, so the field is filled by
    corroboration and is empty when no signal names one.
    """

    model_config = ConfigDict(frozen=True)

    change_type: ChangeType
    provision: ProvisionRef
    heading: str | None = None
    before: ProvisionText | None = Field(default=None, description="Verbatim; None if inserted.")
    after: ProvisionText | None = Field(default=None, description="Verbatim; None if deleted.")
    previous_location: ProvisionLocation | None = Field(
        default=None, description="The location a renumbered provision had before."
    )
    changed_within: tuple[ProvisionLocation, ...] = Field(
        default=(),
        description="Sub-provision coordinates whose own text differs: detail, not the unit.",
    )
    amending_acts: tuple[ActId, ...] = Field(
        default=(),
        description="Acts a signal names as amending this unit; empty when none names one.",
    )
    dates_removed: tuple[date, ...] = Field(
        default=(), description="Machine-readable dates the provision carried before and not after."
    )
    dates_added: tuple[date, ...] = Field(
        default=(), description="Machine-readable dates the provision carries after and not before."
    )
    in_force: date | None = None
    applies_from: Applicability = ApplicabilityUnknown()
    signals: SignalSet = SignalSet()
    disputed: bool = Field(
        default=False, description="Signals disagree. Derived from `signals`, not free."
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_disputed(cls, data: Any) -> Any:
        """Fill `disputed` from the signals, and reject a value that contradicts them."""
        if not isinstance(data, dict):
            return data
        raw_signals = data.get("signals")
        if raw_signals is None:
            signals = SignalSet()
        elif isinstance(raw_signals, SignalSet):
            signals = raw_signals
        elif isinstance(raw_signals, dict):
            signals = SignalSet.model_validate(raw_signals)
        else:
            return data
        expected = signals.disagreement
        if data.get("disputed") is None:
            return {**data, "disputed": expected}
        if bool(data["disputed"]) != expected:
            raise ValueError(
                f"disputed={data['disputed']!r} contradicts the signals "
                f"(disagreement={expected!r}); it is derived, not asserted"
            )
        return data

    @model_validator(mode="after")
    def _texts_match_change_type(self) -> Self:
        # The structural diff is the only signal carrying text. Where it explicitly did
        # *not* see the change, which is a unit another signal names and the diff does not,
        # there is no text to carry, and demanding some would force the corroborator to drop
        # the disagreement instead of shipping it (`disputed`: never silently dropped).
        if self.signals.structural_diff.status is not SignalStatus.ABSENT:
            self._require_texts()
        if self.change_type is ChangeType.RENUMBERED and self.previous_location is None:
            raise ValueError("a RENUMBERED change must carry `previous_location`")
        if self.change_type is ChangeType.DEFERRED and not isinstance(self.applies_from, date):
            raise ValueError("a DEFERRED change must carry the new `applies_from` date")
        return self

    def _require_texts(self) -> None:
        # Presence is tested with `is None`, not truthiness: an empty provision text is a
        # text, and verbatim means verbatim.
        if self.change_type is ChangeType.INSERTED and (
            self.before is not None or self.after is None
        ):
            raise ValueError("an INSERTED change has no `before` text and must have an `after`")
        if self.change_type is ChangeType.DELETED and (
            self.after is not None or self.before is None
        ):
            raise ValueError("a DELETED change has no `after` text and must have a `before`")
        if self.change_type is ChangeType.MODIFIED and (self.before is None or self.after is None):
            raise ValueError("a MODIFIED change must carry both `before` and `after`")

    @property
    def location(self) -> ProvisionLocation:
        return self.provision.location

    @property
    def unit(self) -> ProvisionLocation:
        """The top-level unit this change is counted under."""
        return self.provision.location.top_level

    @property
    def textless(self) -> bool:
        """No text on either side: the one signal that carries text did not see this unit.

        The corroborator's appended change: it has a location, a kind and `disputed=True` and
        nothing quotable at all. The question is asked here rather than in each renderer so a
        count, a prompt and a page cannot disagree about what the class is. Tested with
        `is None`, never truthiness: an empty provision text is a text.
        """
        return self.before is None and self.after is None


def sort_changes(changes: tuple[Change, ...]) -> tuple[Change, ...]:
    """Order changes deterministically by location; output stability is a contract.

    Diff engines should emit document order of the *new* version with insertions in place;
    this is the fallback ordering that makes any two runs byte-identical.
    """
    return tuple(sorted(changes, key=lambda change: change.location.sort_key))


class DeltaSummary(BaseModel):
    """Counts for one delta, in a fixed field order so rendering is byte-stable."""

    model_config = ConfigDict(frozen=True)

    inserted: int = 0
    modified: int = 0
    deleted: int = 0
    renumbered: int = 0
    deferred: int = 0
    touched_units: int = 0
    unchanged_units: int = 0
    disputed: int = 0


class Delta(BaseModel):
    """Everything that changed between two versions of one act, in a deterministic order."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    from_version: VersionId
    to_version: VersionId
    changes: tuple[Change, ...] = ()
    unchanged_units: int = Field(
        default=0, ge=0, description="Top-level units compared and found identical."
    )

    @model_validator(mode="after")
    def _changes_belong_to_this_act(self) -> Self:
        foreign = {
            str(change.provision.act) for change in self.changes if change.provision.act != self.act
        }
        if foreign:
            raise ValueError(f"delta for {self.act} carries changes of {sorted(foreign)}")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> DeltaSummary:
        counts = {change_type: 0 for change_type in ChangeType}
        for change in self.changes:
            counts[change.change_type] += 1
        return DeltaSummary(
            inserted=counts[ChangeType.INSERTED],
            modified=counts[ChangeType.MODIFIED],
            deleted=counts[ChangeType.DELETED],
            renumbered=counts[ChangeType.RENUMBERED],
            deferred=counts[ChangeType.DEFERRED],
            touched_units=len({change.unit.canonical for change in self.changes}),
            unchanged_units=self.unchanged_units,
            disputed=sum(1 for change in self.changes if change.disputed),
        )
