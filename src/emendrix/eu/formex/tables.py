"""Table rows out of the markup: a `TBL` at a profiled position, read as keyed entries.

The tree reads a table as prose. This module reads the same element as a grid, without
changing a node: columns are placed by each cell's `COL` attribute, `ROWSPAN` and `COLSPAN`
are tracked per column so a span's copies are known as copies, rows are read through `BLK`
groups with the innermost `TI.BLK` heading as the row's group, and `ROW TYPE="HEADER"` rows are
the header. Measured 2026-10-16 over 526 cached packages: no cell lacks `COL`, and no `ROW` is
left outside the grid once `BLK` is read through.

Body rows become entries by the profile's key column: a row whose key cell is a `ROWSPAN` copy
continues the entry above it, and any other row starts one. Repeated header rows and blank
rows are dropped. Cells are stored verbatim, `None` where the row has no cell of its own at a
position; comparison happens only inside key reading, identifier reading and header matching.

Nothing here parses XML: the elements arrive already parsed through `eu.xml_`, and nothing
here reads a clock, the network or a model.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from emendrix.core import (
    EntryTable,
    Identifier,
    ProvisionLocation,
    TableEntry,
    TableReading,
    TableRef,
    normalize_for_comparison,
)
from emendrix.eu.formex.text import verbatim_text
from emendrix.eu.substances.keys import EMPTY_MARKS, entry_name, read_key
from emendrix.eu.substances.numbers import Scheme, identifiers_in
from emendrix.eu.substances.profiles import TableProfile, header_matches

__all__ = ["combine", "read_table", "read_tables"]

_OWN = ""
_ROWSPAN_COPY = "R"
_COLSPAN_COPY = "C"
_ABSENT = "-"


@dataclass(frozen=True)
class _Row:
    """One grid line. `marks[i]` says how position `i` was filled; copies carry their text."""

    header: bool
    cells: tuple[str, ...]
    marks: tuple[str, ...]
    group: str | None

    def own(self, col: int) -> bool:
        return self.marks[col - 1] == _OWN

    def published(self) -> tuple[str | None, ...]:
        """The row as stored: verbatim where the row has a cell, `None` everywhere else."""
        return tuple(
            text if mark == _OWN else None
            for text, mark in zip(self.cells, self.marks, strict=True)
        )

    def flat(self) -> tuple[str, ...]:
        return tuple(normalize_for_comparison(cell) for cell in self.cells)


def _int(raw: str | None) -> int | None:
    if raw is None or not raw.strip().isdigit():
        return None
    return int(raw.strip())


def _rows(element: Element, group: str | None) -> Iterator[tuple[Element, str | None]]:
    """A corpus's rows in document order, each with the innermost block heading above it."""
    for child in element:
        if child.tag == "ROW":
            yield child, group
        elif child.tag == "BLK":
            heading = child.find("TI.BLK")
            yield from _rows(child, group if heading is None else verbatim_text(heading))


def _grid(tbl: Element) -> list[_Row]:
    """Every row of the table's own corpora as a grid line, spans copied down and across."""
    pending: dict[int, tuple[int, str]] = {}
    raw: list[tuple[bool, dict[int, tuple[str, str]], str | None]] = []
    for corpus in tbl.findall("CORPUS"):
        for row, group in _rows(corpus, None):
            cells: dict[int, tuple[str, str]] = {}
            for col, (left, text) in sorted(pending.items()):
                cells[col] = (text, _ROWSPAN_COPY)
                if left == 1:
                    del pending[col]
                else:
                    pending[col] = (left - 1, text)
            free = 1
            for cell in row.findall("CELL"):
                declared = _int(cell.get("COL"))
                if declared is None:
                    while free in cells:
                        free += 1
                    declared = free
                across = max(1, _int(cell.get("COLSPAN")) or 1)
                down = max(1, _int(cell.get("ROWSPAN")) or 1)
                text = verbatim_text(cell)
                cells[declared] = (text, _OWN)
                for extra in range(1, across):
                    cells[declared + extra] = ("", _COLSPAN_COPY)
                if down > 1:
                    for extra in range(across):
                        pending[declared + extra] = (down - 1, text if extra == 0 else "")
                free = declared + across
            raw.append((row.get("TYPE") == "HEADER", cells, group))
    width = max([_int(tbl.get("COLS")) or 0] + [max(cells) for _, cells, _ in raw if cells])
    rows: list[_Row] = []
    for header, cells, group in raw:
        line = [cells.get(col, ("", _ABSENT)) for col in range(1, width + 1)]
        rows.append(_Row(header, tuple(t for t, _ in line), tuple(m for _, m in line), group))
    return rows


def _body(rows: list[_Row]) -> list[_Row]:
    """Body rows: header rows, rows repeating a header line and blank rows left out."""
    header_lines = {row.flat() for row in rows if row.header}
    body: list[_Row] = []
    for row in rows:
        if row.header or row.flat() in header_lines:
            continue
        if all(cell in EMPTY_MARKS for cell in row.flat()):
            continue
        body.append(row)
    return body


def _entries(ref: TableRef, body: list[_Row], profile: TableProfile) -> list[TableEntry]:
    """Rows into entries by the key column; a rowspan copy of the key continues an entry."""
    groups: list[list[_Row]] = []
    for row in body:
        if row.marks[profile.key_col - 1] == _ROWSPAN_COPY and groups:
            groups[-1].append(row)
        else:
            groups.append([row])
    seen: Counter[str] = Counter()
    entries: list[TableEntry] = []
    for rows in groups:
        first = rows[0]
        reading = read_key(first.cells[profile.key_col - 1], profile.key_form)
        key = reading.key if first.own(profile.key_col) else None
        identifiers, failed = _identifiers(rows, profile)
        if reading.failed and profile.key_col not in profile.index_cols:
            failed += 1
        occurrence = 1
        if key is not None:
            seen[key] += 1
            occurrence = seen[key]
        name = None
        if first.own(profile.name_col):
            drop = profile.key_form == "number" and profile.key_col == profile.name_col
            name = entry_name(first.cells[profile.name_col - 1], drop_number=drop)
        entries.append(
            TableEntry(
                unit=ref.unit,
                container=ref.container,
                table=ref.table,
                key=key,
                occurrence=occurrence,
                group=first.group,
                rows=tuple(row.published() for row in rows),
                identifiers=identifiers,
                failed_check_digits=failed,
                name=name,
            )
        )
    return entries


def _identifiers(rows: list[_Row], profile: TableProfile) -> tuple[tuple[Identifier, ...], int]:
    """The union of the entry's identifiers over its own cells, sorted, and the failed count."""
    columns: dict[int, list[Scheme]] = {}
    by_scheme: tuple[tuple[Scheme, tuple[int, ...]], ...] = (
        ("cas", profile.cas_cols),
        ("ec", profile.ec_cols),
        ("index", profile.index_cols),
    )
    for scheme, cols in by_scheme:
        for col in cols:
            columns.setdefault(col, []).append(scheme)
    found: set[Identifier] = set()
    failed = 0
    for row in rows:
        for col, schemes in columns.items():
            if col <= len(row.cells) and row.own(col):
                valid, bad = identifiers_in(row.cells[col - 1], schemes)
                found.update(valid)
                failed += bad
    return tuple(sorted(found, key=lambda one: (one.scheme, one.value))), failed


def read_table(
    tbl: Element, ref: TableRef, profile: TableProfile
) -> tuple[EntryTable, list[TableEntry]] | None:
    """One profiled table as its header and entries, or `None` when the header fails."""
    rows = _grid(tbl)
    header = tuple(row.published() for row in rows if row.header)
    if not header_matches(profile, header):
        return None
    table = EntryTable(
        unit=ref.unit,
        container=ref.container,
        table=ref.table,
        key_label=profile.key_label,
        header=header,
    )
    return table, _entries(ref, _body(rows), profile)


def read_tables(
    tables: Iterable[tuple[Element, ProvisionLocation, int]],
    unit: ProvisionLocation,
    profiles: Iterable[TableProfile],
) -> TableReading:
    """Every profiled table among `tables`, each `(element, container, ordinal)` of one unit.

    A table at an unprofiled position is ignored whatever its header says; one at a profiled
    position whose header fails is listed in `unrecognised` and never read.
    """
    wanted = {
        (profile.container, profile.table): profile
        for profile in profiles
        if profile.unit == unit.canonical
    }
    read: list[EntryTable] = []
    entries: list[TableEntry] = []
    unrecognised: list[TableRef] = []
    for element, container, ordinal in tables:
        profile = wanted.get((container.canonical, ordinal))
        if profile is None:
            continue
        ref = TableRef(unit=unit, container=container, table=ordinal)
        result = read_table(element, ref, profile)
        if result is None:
            unrecognised.append(ref)
            continue
        read.append(result[0])
        entries.extend(result[1])
    return TableReading(
        tables=tuple(read), entries=tuple(entries), unrecognised=tuple(unrecognised)
    )


def combine(readings: Iterable[TableReading]) -> TableReading:
    """Several units' readings as one, in the order given."""
    tables: list[EntryTable] = []
    entries: list[TableEntry] = []
    unrecognised: list[TableRef] = []
    for reading in readings:
        tables.extend(reading.tables)
        entries.extend(reading.entries)
        unrecognised.extend(reading.unrecognised)
    return TableReading(
        tables=tuple(tables), entries=tuple(entries), unrecognised=tuple(unrecognised)
    )
