"""The table-entry repair: the keyed diff of every published change to a profiled table.

Entries written before payload schema `1.3` carry `table_entries: null` on every change, which
reads as "not read". For a change to a unit that holds a table the corpus reads as entries,
that is now a gap rather than a fact, and this repair closes it: it re-derives both versions
through the adapter's cache, one parse per version (`rederive.Trees`), and sets each such
change's `table_entries` exactly as the loop's DELTA stage computes it today
(`diff.compute_delta`), from the same two readings and the same unit pairing.

**Only `table_entries` moves.** Every verbatim text, explanation, citation, signal, sentence
and date is carried over byte-identical, `schema_version` becomes `1.3` because the document
now states the field's reading, and the record of the repair is appended. Nothing is asked of
any model, so no call is made and none is retracted.

**Which acts and units are profiled is data handed in**, a mapping from act key to the canonical
units its profiled tables sit in, built by the composition root from the corpus's own profiles.
So `needs` never parses a version of an act that has no profile, and no list of acts or units is
written anywhere in this package. A change the re-derivation cannot match, because neither
reading holds a profiled table in its unit, keeps `null` and is counted; so is every change of
an entry whose versions could not be produced or whose identifiers moved.

Core types, the committed document and the corpus seam. No clock, no network beyond the
adapter's cache, no model, no corpus vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, ProvisionTree, SignalStatus, VersionId
from emendrix.diff import diff_entries
from emendrix.diff.entries import profiled_units
from emendrix.graph.report import EmittedChange, RegisterSnapshot
from emendrix.output import SCHEMA_VERSION, ChangelogEntry
from emendrix.repair.entry import RepairResult, RepairTarget
from emendrix.repair.rederive import Trees

__all__ = [
    "KIND",
    "Profiled",
    "TableTally",
    "by_act",
    "needs",
    "newest_targets",
    "repair",
    "snapshot_for",
    "tabled_subject",
]

KIND = "tables"
"""What this repair is called, on the command line and in the record it writes."""

Profiled = Mapping[str, frozenset[str]]
"""Act key to the canonical top-level units its profiled tables sit in."""

_UNMOVED = (
    "The verbatim texts, every explanation, sentence and signal, and the detection date did "
    "not move."
)


def _units(change: Change) -> frozenset[str]:
    """The unit a change sits in on each side: renumbered, it has two."""
    location = change.provision.location
    return frozenset(
        {location.top_level.canonical, (change.previous_location or location).top_level.canonical}
    )


def _addressed(change: Change, units: frozenset[str]) -> bool:
    """A change the diff observed in a profiled unit, written before the field was stated."""
    return (
        change.table_entries is None
        and change.signals.structural_diff.status is not SignalStatus.ABSENT
        and bool(_units(change) & units)
    )


def needs(target: RepairTarget, profiled: Profiled) -> bool:
    """An entry of a profiled act holding a change in a profiled unit that reads `null`."""
    units = profiled.get(target.entry.act.key)
    return units is not None and any(
        _addressed(item.change, units) for item in target.entry.changes
    )


def _side(trees: Trees, entry: ChangelogEntry, version: VersionId) -> ProvisionTree | str:
    """One version's tree, or why there is none, refusing a tree served under other identifiers."""
    found = trees.of(entry.act, version)
    if isinstance(found, str):
        return found
    if (found.act, found.version) != (entry.act, version):
        return f"the corpus served {found.act.key} {found.version} for {version}"
    return found


def repair(target: RepairTarget, trees: Trees, profiled: Profiled) -> RepairResult:
    """Every addressed change of one entry given today's keyed diff of its unit's entries."""
    entry = target.entry
    units = profiled.get(entry.act.key, frozenset())
    addressed = sum(1 for item in entry.changes if _addressed(item.change, units))
    before, after = _side(trees, entry, entry.from_version), _side(trees, entry, entry.to_version)
    for side, version in ((before, entry.from_version), (after, entry.to_version)):
        if isinstance(side, str):
            note = f"{entry.act.key} {version}: {side}"
            return RepairResult(
                target=target, addressed=addressed, remaining=addressed, detail=(note,)
            )
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    read = profiled_units(before.table_entries) | profiled_units(after.table_entries)
    changes: list[EmittedChange] = []
    repaired = 0
    for item in entry.changes:
        change = item.change
        if not _addressed(change, units) or not _units(change) & read:
            changes.append(item)
            continue
        unit = change.provision.location.top_level
        delta = diff_entries(
            before.table_entries,
            after.table_entries,
            unit,
            unit_before=(change.previous_location or change.provision.location).top_level,
        )
        changes.append(
            item.model_copy(update={"change": change.model_copy(update={"table_entries": delta})})
        )
        repaired += 1
    remaining = addressed - repaired
    if not repaired:
        return RepairResult(target=target, addressed=addressed, remaining=remaining)
    rebuilt = entry.model_copy(update={"changes": tuple(changes), "schema_version": SCHEMA_VERSION})
    return RepairResult(
        target=target, addressed=addressed, repaired=repaired, remaining=remaining, entry=rebuilt
    )


def newest_targets(targets: Iterable[RepairTarget], profiled: Profiled) -> tuple[RepairTarget, ...]:
    """Each profiled act's newest published entry, by entry key, in act order."""
    newest: dict[str, RepairTarget] = {}
    for target in targets:
        key = target.entry.act.key
        if key in profiled and (key not in newest or target.entry.key > newest[key].entry.key):
            newest[key] = target
    return tuple(newest[key] for key in sorted(newest))


def snapshot_for(target: RepairTarget, trees: Trees) -> RegisterSnapshot | str:
    """The register's reading of an entry's newer version, or why there is none."""
    tree = _side(trees, target.entry, target.entry.to_version)
    if isinstance(tree, str):
        return f"{target.entry.to_version}: {tree}"
    reading = tree.table_entries
    if not reading.tables and not reading.unrecognised:
        return f"{target.entry.to_version}: no profiled table was read"
    return RegisterSnapshot(act=tree.act, version=tree.version, reading=reading)


def tabled_subject(entry: ChangelogEntry, result: RepairResult) -> str:
    """`32006R1907: 02006R1907-20160308 tables repaired (1 of 1 changes)`, and what stayed."""
    phrase = f"{KIND} repaired ({result.repaired} of {result.addressed} changes)"
    return f"{entry.act.key}: {entry.to_version} {phrase}\n\n{_UNMOVED}"


class TableTally(BaseModel):
    """What one pass found for one act, or for every act: entries, changes and entry changes."""

    model_config = ConfigDict(frozen=True)

    act: str = Field(description="The act's key, or `total` for the sum over every act.")
    examined: int = Field(default=0, ge=0, description="Entries of the act the pass looked at.")
    rewritten: int = Field(default=0, ge=0, description="Entries the pass would rewrite.")
    gaining: int = Field(default=0, ge=0, description="Changes gaining `table_entries`.")
    unmatched: int = Field(default=0, ge=0, description="Changes addressed and left `null`.")
    underivable: int = Field(default=0, ge=0, description="Entries whose versions did not parse.")
    added: int = Field(default=0, ge=0)
    removed: int = Field(default=0, ge=0)
    amended: int = Field(default=0, ge=0, description="Amended entries, typography-only included.")
    typography_only: int = Field(default=0, ge=0)
    whitespace_only: int = Field(default=0, ge=0, description="Paired entries; not changes.")
    empty: int = Field(default=0, ge=0, description="Deltas read with no keyed entry moved.")
    unrecognised_tables: int = Field(default=0, ge=0, description="Newer sides, summed.")
    unkeyed_rows: int = Field(default=0, ge=0, description="Newer sides, summed.")
    failed_check_digits: int = Field(default=0, ge=0, description="Newer sides, summed.")
    unpaired: int = Field(default=0, ge=0, description="Keys printed a different number of times.")

    def plus(self, other: TableTally, *, act: str) -> TableTally:
        """The field-wise sum of two tallies, under the name given."""
        counts = {
            name: getattr(self, name) + getattr(other, name)
            for name in type(self).model_fields
            if name != "act"
        }
        return TableTally(act=act, **counts)


def _tally(result: RepairResult) -> TableTally:
    rebuilt = result.entry
    pairs = (
        () if rebuilt is None else zip(result.target.entry.changes, rebuilt.changes, strict=True)
    )
    found = [
        delta
        for old, new in pairs
        if old.change.table_entries is None and (delta := new.change.table_entries) is not None
    ]
    return TableTally(
        act=result.target.entry.act.key,
        rewritten=int(rebuilt is not None),
        gaining=result.repaired,
        unmatched=0 if result.detail else result.remaining,
        underivable=int(bool(result.detail)),
        added=sum(delta.count("added") for delta in found),
        removed=sum(delta.count("removed") for delta in found),
        amended=sum(delta.count("amended") for delta in found),
        typography_only=sum(delta.typography_only for delta in found),
        whitespace_only=sum(delta.whitespace_only for delta in found),
        empty=sum(1 for delta in found if not delta.changes),
        unrecognised_tables=sum(delta.gaps_after.unrecognised_tables for delta in found),
        unkeyed_rows=sum(delta.gaps_after.unkeyed_rows for delta in found),
        failed_check_digits=sum(delta.gaps_after.failed_check_digits for delta in found),
        unpaired=sum(len(delta.unpaired) for delta in found),
    )


def by_act(
    results: Iterable[RepairResult], examined: Mapping[str, int]
) -> tuple[tuple[TableTally, ...], TableTally]:
    """One tally per act examined, in key order, and the total over all of them."""
    acts = {key: TableTally(act=key, examined=count) for key, count in sorted(examined.items())}
    for result in results:
        found = _tally(result)
        held = acts.get(found.act, TableTally(act=found.act))
        acts[found.act] = held.plus(found, act=found.act)
    total = TableTally(act="total")
    for tally in acts.values():
        total = total.plus(tally, act="total")
    return tuple(acts.values()), total
