"""Taking a committed entry apart, putting it back, and deciding whether it moved.

The spine every repair kind hangs off. It reads the payload and never re-fetches or re-diffs:
the stored `Change` carries both verbatim texts, and today's parser over documents whose stored
text predates a parser fix would produce text the committed page does not show, which is exactly
the failure the citation gate exists to prevent.

Core types and the committed document only. No clock, no network, no model, no corpus.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, Delta, SignalSet, SignalStatus
from emendrix.corroborate import CorroborationReport
from emendrix.graph.report import EmittedChange, EmittedDelta
from emendrix.output import ChangelogEntry
from emendrix.output.json_out import RepairRecord

__all__ = [
    "RepairResult",
    "RepairTarget",
    "UnitShift",
    "changes_by_unit",
    "delta_of",
    "moved",
    "rebuild",
    "shift_between",
    "with_record",
]

ChangeKey = tuple[str, int]
"""One change's identity inside an entry: its unit, and which occurrence within that unit.

The unit is the key corroboration compares on and the key the payload is grouped by. The index
disambiguates a unit carrying more than one change, deterministically and without reading any
text, so re-attaching prose across a merge can never hand one change another's sentences.
"""


class RepairTarget(BaseModel):
    """One committed entry, with where it came from. The unit every repair addresses."""

    model_config = ConfigDict(frozen=True)

    path: Path = Field(description="The payload's path, relative to the repository root.")
    entry: ChangelogEntry


class RepairResult(BaseModel):
    """What one repair did to one entry: enough for the table, and for a test to check."""

    model_config = ConfigDict(frozen=True)

    target: RepairTarget
    repaired: int = Field(default=0, ge=0, description="Changes this repair actually changed.")
    remaining: int = Field(default=0, ge=0, description="Changes it addressed and could not fix.")
    entry: ChangelogEntry | None = Field(
        default=None, description="The rebuilt entry, or None when nothing moved."
    )
    detail: tuple[str, ...] = ()

    @property
    def would_change(self) -> bool:
        return self.entry is not None


class UnitShift(BaseModel):
    """What moved between two versions of one entry, at the unit of change.

    Gained and dropped units are the two halves of a signal changing its mind about what
    exists; the flipped flags are the third figure, and it is the one that decides whether any
    committed explanation was written under a prompt that is now false.
    """

    model_config = ConfigDict(frozen=True)

    gained: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()
    disputed_flipped: tuple[str, ...] = ()
    changed: int = Field(default=0, ge=0, description="Changes whose committed bytes moved.")

    @property
    def lines(self) -> tuple[str, ...]:
        """One line per unit that moved, in a fixed order, for the table and the audit record."""
        return (
            *(f"gained {unit}" for unit in self.gained),
            *(f"dropped {unit}" for unit in self.dropped),
            *(f"{unit}: disputed flag flipped" for unit in self.disputed_flipped),
        )


def delta_of(entry: ChangelogEntry) -> Delta:
    """The pre-corroboration delta: the changes the structural diff observed, signals stripped.

    A unit only another signal named carries no text and is not the diff's, so it is left out
    and `corroborate` puts it back if the signals still name it. Everything corroboration fills
    is stripped back to its default, because a merge over already-merged changes would read a
    stale verdict as an input.
    """
    return Delta(
        act=entry.act,
        from_version=entry.from_version,
        to_version=entry.to_version,
        changes=tuple(
            _stripped(item.change) for item in entry.changes if _observed_by_the_diff(item.change)
        ),
        unchanged_units=entry.summary.unchanged_units,
    )


def rebuild(
    entry: ChangelogEntry,
    *,
    delta: Delta,
    corroboration: CorroborationReport | None,
    changes: tuple[EmittedChange, ...],
) -> ChangelogEntry:
    """A committed entry with some part of it replaced, and `detected_on` carried over.

    `detected_on` is when the amendment was detected, not when this ran: a repair is not a
    detection. `explain` and `gate` are carried over untouched for the same reason. They record
    what one run did, and no repair retracts a call that was made; what a repair did is a
    `RepairRecord`.
    """
    shipped = Delta(
        act=delta.act,
        from_version=delta.from_version,
        to_version=delta.to_version,
        changes=tuple(item.change for item in changes),
        unchanged_units=delta.unchanged_units,
    )
    rebuilt = ChangelogEntry.of(
        EmittedDelta(
            act=shipped.act,
            from_version=shipped.from_version,
            to_version=shipped.to_version,
            summary=shipped.summary,
            changes=changes,
            corroboration=corroboration,
            explain=entry.explain,
            gate=entry.gate,
        ),
        detected_on=entry.detected_on,
        diff_only=entry.diff_only,
    )
    return rebuilt.model_copy(update={"repairs": entry.repairs})


def moved(before: ChangelogEntry, after: ChangelogEntry) -> bool:
    """Whether the rebuild is a real change, comparing `to_json()` on both sides.

    Both sides are serialised through today's model, so a field the schema gained since the
    entry was written is on both sides and never counts as a change on its own. Without that, a
    repair run over a whole repository would rewrite every file it read.
    """
    return before.to_json() != after.to_json()


def with_record(entry: ChangelogEntry, record: RepairRecord) -> ChangelogEntry:
    """The entry with one repair recorded on it, oldest first.

    Appended only once the substantive rebuild has been found to differ. The other order is
    self-perpetuating: a record added first makes every rebuild differ from its original by the
    record alone, so a repair that changed nothing writes, and the next run writes again.
    """
    return entry.model_copy(update={"repairs": (*entry.repairs, record)})


def changes_by_unit(entry: ChangelogEntry) -> dict[ChangeKey, EmittedChange]:
    """Every emitted change of one entry, keyed by unit and occurrence within that unit."""
    seen: Counter[str] = Counter()
    keyed: dict[ChangeKey, EmittedChange] = {}
    for item in entry.changes:
        unit = item.change.unit.canonical
        keyed[(unit, seen[unit])] = item
        seen[unit] += 1
    return keyed


def shift_between(before: ChangelogEntry, after: ChangelogEntry) -> UnitShift:
    """What a rebuild moved: units gained, units dropped, disputed flags flipped, changes moved.

    Computed here rather than beside each repair kind so the dry-run table and the audit record
    can never disagree about what one repair did.
    """
    left, right = changes_by_unit(before), changes_by_unit(after)
    units_before, units_after = _units(before), _units(after)
    return UnitShift(
        gained=tuple(unit for unit in units_after if unit not in units_before),
        dropped=tuple(unit for unit in units_before if unit not in units_after),
        disputed_flipped=tuple(
            unit
            for unit, disputed in units_before.items()
            if unit in units_after and units_after[unit] != disputed
        ),
        changed=sum(
            1
            for key in {*left, *right}
            if _serialised(left.get(key)) != _serialised(right.get(key))
        ),
    )


# ------------------------------------------------------------------ the pieces


def _observed_by_the_diff(change: Change) -> bool:
    """False exactly for the textless changes corroboration appended for another signal."""
    return change.signals.structural_diff.status is not SignalStatus.ABSENT


def _stripped(change: Change) -> Change:
    """One change as the diff produced it: everything the merge writes back to its default."""
    return change.model_copy(
        update={
            "signals": SignalSet(),
            "disputed": False,
            "amending_acts": (),
            "in_force": None,
        }
    )


def _units(entry: ChangelogEntry) -> dict[str, bool]:
    """Each top-level unit of one entry, in order, against whether any of its changes disputed."""
    units: dict[str, bool] = {}
    for item in entry.changes:
        unit = item.change.unit.canonical
        units[unit] = units.get(unit, False) or item.change.disputed
    return units


def _serialised(change: EmittedChange | None) -> str:
    return "" if change is None else change.model_dump_json()
