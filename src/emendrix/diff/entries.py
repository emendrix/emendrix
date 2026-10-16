"""The table-entry diff: two readings of one unit's tables in, one `EntryDelta` out.

Part of the DELTA stage, beside the tree diff rather than inside it. The tree diff decides
*whether* a unit changed from its comparison text; this module says *which keyed rows* of the
unit's profiled tables moved, by pairing entries on `(container, table, key, occurrence)` and
comparing the paired entries' block heading and cells. Nothing here knows which act, which
annex or which column: the adapter chose the keys and stated its rule.

Three grades of difference, in the order they are tested:

- equal verbatim: `unchanged`, counted;
- equal once every cell passes `normalize_for_comparison`: `whitespace_only`, counted and not
  a change, for the reason the comparison text exists at all (the serialisation chose the
  whitespace, the drafter did not);
- anything else: `amended`, and labelled `typography_only` when the two sides are equal once
  spacing, dash forms and accents are set aside. The label says what kind of difference it is.
  It never removes the change, because ruling a character swap not to count would be a
  judgement about the text itself that no deterministic stage may make.

A key printed a different number of times on the two sides is not paired at all: its rows are
not diffed and the key is listed in `unpaired`, since pairing the first with the first would
assert an identity the act did not state. Unkeyed entries are never paired and are counted.
Tables are told apart by their container's path *below* the unit and their ordinal, so a
renumbered unit still pairs its tables with the ones it had under its old number.

Deterministic throughout: no clock, no network, no model, every list sorted explicitly.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Final

from emendrix.core import (
    EntryChange,
    EntryDelta,
    EntryGaps,
    EntryKind,
    EntryOrder,
    EntryTable,
    KeyRef,
    ProvisionLocation,
    TableEntry,
    TableReading,
    TableRef,
    entry_order,
    normalize_for_comparison,
)

__all__ = ["diff_entries", "plain", "profiled_units"]

_DASHES: Final = str.maketrans(
    {chr(code): "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212)}
)
"""The hyphen and dash forms the fold reads as one character, and the minus sign with them."""

_TableKey = tuple[str, int]
"""A table within its unit: the container's path below the unit, and the table's ordinal."""
_GroupKey = tuple[str, int, str]


def plain(text: str) -> str:
    """A cell folded for the typography label: NFKD, accents and all whitespace dropped, one dash.

    Used only to *label* an amendment, never to decide whether one happened.
    """
    decomposed = unicodedata.normalize("NFKD", normalize_for_comparison(text).translate(_DASHES))
    return "".join(
        char for char in decomposed if not char.isspace() and not unicodedata.combining(char)
    )


def profiled_units(reading: TableReading) -> frozenset[str]:
    """The canonical units a reading says something about: a table read, or one it could not."""
    return frozenset(ref.unit.canonical for ref in (*reading.tables, *reading.unrecognised))


def diff_entries(
    before: TableReading,
    after: TableReading,
    unit: ProvisionLocation,
    *,
    unit_before: ProvisionLocation | None = None,
) -> EntryDelta:
    """The keyed diff of `unit`'s table entries between two readings.

    `unit_before` is the unit's location in the older version when it was renumbered; it
    defaults to `unit`. Both readings are restricted to the unit before anything is compared.
    """
    older = _Side(before, unit_before or unit)
    newer = _Side(after, unit)
    tables = _tables(older, newer)
    position = {_table_key(table): index for index, table in enumerate(tables)}
    changes: list[EntryChange] = []
    unpaired: list[KeyRef] = []
    unchanged = whitespace_only = 0
    groups = sorted(set(older.keyed) | set(newer.keyed), key=lambda g: _order(position, g))
    for group in groups:
        olds, news = older.keyed.get(group, []), newer.keyed.get(group, [])
        if not news:
            changes.extend(_change("removed", old, before=old) for old in olds)
            continue
        if not olds:
            changes.extend(_change("added", new, after=new) for new in news)
            continue
        if len(olds) != len(news):
            unpaired.append(KeyRef(container=olds[0].container, table=olds[0].table, key=group[2]))
            continue
        for old, new in zip(olds, news, strict=True):
            if (old.group, old.rows) == (new.group, new.rows):
                unchanged += 1
            elif _collapsed(old) == _collapsed(new):
                whitespace_only += 1
            else:
                changes.append(
                    _change(
                        "amended",
                        new,
                        before=old,
                        after=new,
                        typography_only=_folded(old) == _folded(new),
                    )
                )
    changes.sort(key=lambda c: _order(position, (*_table_key(c), c.key), c.occurrence))
    return EntryDelta(
        tables=tables,
        changes=tuple(changes),
        unchanged=unchanged,
        whitespace_only=whitespace_only,
        unpaired=tuple(unpaired),
        gaps_before=older.gaps(position),
        gaps_after=newer.gaps(position),
    )


class _Side:
    """One reading restricted to one unit, with its keyed entries grouped for pairing."""

    def __init__(self, reading: TableReading, unit: ProvisionLocation) -> None:
        self.tables = tuple(t for t in reading.tables if t.unit == unit)
        self.unrecognised = tuple(t for t in reading.unrecognised if t.unit == unit)
        self.entries = tuple(e for e in reading.entries if e.unit == unit)
        self.keyed: dict[_GroupKey, list[TableEntry]] = defaultdict(list)
        for entry in self.entries:
            if entry.key is not None:
                self.keyed[(*_table_key(entry), entry.key)].append(entry)

    def gaps(self, position: dict[_TableKey, int]) -> EntryGaps:
        """What this side could not key, read or trust; `unkeyed_rows` counts unkeyed entries."""
        repeated = [
            KeyRef(container=entries[0].container, table=entries[0].table, key=group[2])
            for group, entries in self.keyed.items()
            if len(entries) > 1
        ]
        repeated.sort(key=lambda ref: _order(position, (*_table_key(ref), ref.key)))
        return EntryGaps(
            unrecognised_tables=len(self.unrecognised),
            unkeyed_rows=sum(1 for entry in self.entries if entry.key is None),
            failed_check_digits=sum(entry.failed_check_digits for entry in self.entries),
            repeated_keys=tuple(repeated),
        )


def _table_key(ref: TableRef | EntryChange | KeyRef) -> _TableKey:
    below = " ".join(str(segment) for segment in ref.container.segments[1:])
    return (below, ref.table)


def _tables(older: _Side, newer: _Side) -> tuple[EntryTable, ...]:
    """The newer side's tables in its document order, then tables only the older side has.

    Positions the sort relies on come from this tuple; a key whose table is in neither list
    sorts after every table that is, by its own path and ordinal.
    """
    seen: set[_TableKey] = set()
    ordered: list[EntryTable] = []
    for table in (*newer.tables, *older.tables):
        if _table_key(table) not in seen:
            seen.add(_table_key(table))
            ordered.append(table)
    return tuple(ordered)


def _order(
    position: dict[_TableKey, int], group: _GroupKey, occurrence: int = 1
) -> tuple[int, str, int, EntryOrder]:
    """Table position first, then the table's own path and ordinal, then the natural key order."""
    below, table, key = group
    return (position.get((below, table), len(position)), below, table, entry_order(key, occurrence))


def _change(
    kind: EntryKind,
    at: TableEntry,
    *,
    before: TableEntry | None = None,
    after: TableEntry | None = None,
    typography_only: bool = False,
) -> EntryChange:
    if at.key is None:  # pragma: no cover - only keyed entries reach here
        raise ValueError("an unkeyed entry is never paired")
    return EntryChange(
        kind=kind,
        container=at.container,
        table=at.table,
        key=at.key,
        occurrence=at.occurrence,
        typography_only=typography_only,
        before=before,
        after=after,
    )


def _collapsed(entry: TableEntry) -> tuple[str | None, tuple[tuple[str | None, ...], ...]]:
    """The entry with every cell and its heading passed through the comparison normaliser."""
    return (_norm(entry.group), tuple(tuple(_norm(cell) for cell in row) for row in entry.rows))


def _folded(entry: TableEntry) -> tuple[str | None, tuple[tuple[str | None, ...], ...]]:
    """The entry with every cell and its heading folded for the typography label."""
    return (_fold(entry.group), tuple(tuple(_fold(cell) for cell in row) for row in entry.rows))


def _norm(cell: str | None) -> str | None:
    return None if cell is None else str(normalize_for_comparison(cell))


def _fold(cell: str | None) -> str | None:
    return None if cell is None else plain(cell)
