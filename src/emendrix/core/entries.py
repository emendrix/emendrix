"""Table entries: the keyed rows of a table an act prints, read beside the provision tree.

A provision tree knows a table only as prose inside the enclosing provision's text. The rows
are still there in the markup, and some acts number their rows and give each one identifiers
that a reader looks a substance up by. This module is the vocabulary for those rows once an
adapter has read them: a **table entry** is a keyed group of rows, with the identifiers its
cells carry and its cells verbatim, and a **table reading** is every entry of one version of
an act together with what could not be read.

Entries ride *beside* the nodes, never as nodes. A table interior turned into locations would
move sub-localisation and every figure computed over the tree, and the rows of one act's
table reuse the enumerators the tree already uses for provisions.

"Entry" everywhere else in this project means a changelog entry. Here it is always a table
entry, which is why the field on the tree and the names below say `table_entries` and
`TableEntry` rather than `entries` and `Entry`.

Generic by construction: a key is a string the adapter chose by a rule it states, an
identifier is a `(scheme, value)` pair whose scheme the corpus defines, and a cell is text.
Nothing here knows which act, which annex or which column.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core.location import ProvisionLocation

__all__ = [
    "EntryGaps",
    "EntryOrder",
    "EntryTable",
    "Identifier",
    "KeyRef",
    "TableEntry",
    "TableReading",
    "TableRef",
    "entry_order",
]

Cells = tuple[str | None, ...]
"""One row as the grid holds it: verbatim cell text, or `None` where the row has no cell of
its own at that position (a span from another cell covers it, or the row is short)."""

_CHUNKS: Final = re.compile(r"\d+|\D+")


class Identifier(BaseModel):
    """One identifier a row carries, in the canonical form of its scheme."""

    model_config = ConfigDict(frozen=True)

    scheme: str = Field(description="The corpus-defined scheme name, lower case.")
    value: str = Field(description="The canonical spelling of the value under its scheme.")


class TableRef(BaseModel):
    """Which table of which unit: the unit, the located node holding it, and its ordinal."""

    model_config = ConfigDict(frozen=True)

    unit: ProvisionLocation = Field(description="The top-level unit the table sits in.")
    container: ProvisionLocation = Field(
        description="The deepest located node holding the table, as the tree places it."
    )
    table: int = Field(ge=1, description="1-based ordinal among every table in the container.")


class EntryTable(TableRef):
    """A table whose rows are read as entries: how its key is named, and its header rows."""

    key_label: str | None = Field(
        description="How a key is named in prose, or `None` when the key is the entry's name."
    )
    header: tuple[Cells, ...] = Field(
        default=(), description="The header rows, cells verbatim; `None` where a span covers."
    )


class TableEntry(TableRef):
    """A keyed group of rows, with its identifiers and its cells verbatim."""

    key: str | None = Field(
        description="The row key by the adapter's rule; `None` is an unkeyed row, kept and counted."
    )
    occurrence: int = Field(
        default=1, ge=1, description="1-based among this table's entries sharing this key."
    )
    group: str | None = Field(
        default=None, description="Verbatim heading of the innermost block the rows sit in."
    )
    rows: tuple[Cells, ...] = Field(
        description="Every row of the entry, cells verbatim; `None` where a span covers."
    )
    identifiers: tuple[Identifier, ...] = Field(
        default=(), description="Sorted, deduplicated, and valid under the scheme's check."
    )
    failed_check_digits: int = Field(
        default=0, ge=0, description="Identifier-shaped values in identifier columns that fail."
    )
    name: str | None = Field(
        default=None,
        description="First line of the name cell; a leading entry number and its `.` dropped.",
    )


class TableReading(BaseModel):
    """Every entry of one version of an act, and the tables that could not be read."""

    model_config = ConfigDict(frozen=True)

    tables: tuple[EntryTable, ...] = Field(default=(), description="In document order.")
    entries: tuple[TableEntry, ...] = Field(
        default=(), description="In document order: table position, then row order."
    )
    unrecognised: tuple[TableRef, ...] = Field(
        default=(), description="Profiled positions whose header did not match; never read."
    )


class KeyRef(BaseModel):
    """One key of one table, named without its rows."""

    model_config = ConfigDict(frozen=True)

    container: ProvisionLocation = Field(description="The located node holding the table.")
    table: int = Field(ge=1, description="1-based ordinal among every table in the container.")
    key: str = Field(description="The key as the entry carries it.")


class EntryGaps(BaseModel):
    """What a reading could not key, read or trust, counted rather than hidden."""

    model_config = ConfigDict(frozen=True)

    unrecognised_tables: int = Field(default=0, ge=0)
    unkeyed_rows: int = Field(default=0, ge=0)
    failed_check_digits: int = Field(default=0, ge=0)
    repeated_keys: tuple[KeyRef, ...] = Field(
        default=(), description="Every key one table prints more than once."
    )


EntryOrder = tuple[tuple[tuple[int, int, str], ...], str, int]
"""The sort key `entry_order` returns: natural chunks, then the key itself, then occurrence."""


def entry_order(key: str, occurrence: int = 1) -> EntryOrder:
    """The natural order of entry keys: digit runs compare as integers, so `5` < `46a` < `68`.

    Two entries with the same key order by occurrence, and two spellings that read as the
    same number (`05`, `5`) are kept apart by the key itself, so the order is total and the
    output byte-stable. Callers sort by the table's position first; this orders within one.
    """
    chunks = tuple(
        (0, int(chunk), "") if chunk.isdigit() else (1, 0, chunk) for chunk in _CHUNKS.findall(key)
    )
    return (chunks, key, occurrence)
