"""The register: every table entry of an act's newest version, beside the act's changelog.

A payload holds only what changed between two versions, so a reader asking where an identifier
appears today cannot answer from the payloads alone: an entry nobody amended since the first
version the record holds is in no payload at all. The register is that answer, one file per act
whose tables are read as entries, `<act_dir>/register.json`, holding the newest version's full
reading with every cell verbatim: the tables and their header rows, every entry in document
order, the profiled positions whose header did not match, and the gaps counted over the whole
reading.

It is the newest version's list, never a diff and never a history. It is written in the commit
of the act's newest entry and replaced by the next one, so an older entry written later, as a
backfill writes them, leaves a newer register where it is (`OutputRepo.write`).

Rendered the way every derived file of the record is: `indent=2` and a trailing newline, no
timestamp, every sequence in an order the reading already fixed. Nothing here knows which act,
which annex or which column; the adapter read the rows and stated its rules.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, EntryGaps, EntryTable, KeyRef, TableEntry, TableReading, TableRef
from emendrix.graph.report import RegisterSnapshot
from emendrix.output.disclaimer import DISCLAIMER
from emendrix.output.json_out import act_dir_for

__all__ = [
    "REGISTER_FILE",
    "REGISTER_SCHEMA",
    "Register",
    "coverage_of",
    "register_for",
    "register_path",
    "render_register",
]

REGISTER_FILE: Final = "register.json"
"""The register's file name inside its act's directory."""

REGISTER_SCHEMA: Final = "1.0"
"""Bumped whenever a reader of the register would have to change to keep reading it."""


class Register(BaseModel):
    """Every table entry of one version of one act, with what could not be read, counted."""

    model_config = ConfigDict(frozen=True)

    register_schema: str = Field(
        default=REGISTER_SCHEMA, description="The register format's version."
    )
    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    version: str = Field(description="The version the entries were read from: the newest held.")
    tables: tuple[EntryTable, ...] = Field(
        default=(), description="Every table read as entries, in document order."
    )
    entries: tuple[TableEntry, ...] = Field(
        default=(), description="Every entry, in document order: table position, then row order."
    )
    unrecognised: tuple[TableRef, ...] = Field(
        default=(), description="Profiled positions whose header did not match; never read."
    )
    coverage: EntryGaps = Field(
        default=EntryGaps(), description="What the reading could not key, read or trust."
    )


def coverage_of(reading: TableReading) -> EntryGaps:
    """The gaps of a whole reading: each repeated key once, where its second print stands."""
    return EntryGaps(
        unrecognised_tables=len(reading.unrecognised),
        unkeyed_rows=sum(1 for entry in reading.entries if entry.key is None),
        failed_check_digits=sum(entry.failed_check_digits for entry in reading.entries),
        repeated_keys=tuple(
            KeyRef(container=entry.container, table=entry.table, key=entry.key)
            for entry in reading.entries
            if entry.key is not None and entry.occurrence == 2
        ),
    )


def register_for(snapshot: RegisterSnapshot) -> Register:
    """The register of one version's reading. Pure: the same reading gives the same bytes."""
    reading = snapshot.reading
    return Register(
        corpus=snapshot.act.corpus,
        key=snapshot.act.key,
        version=str(snapshot.version),
        tables=reading.tables,
        entries=reading.entries,
        unrecognised=reading.unrecognised,
        coverage=coverage_of(reading),
    )


def register_path(act: ActId) -> str:
    """`eu/32008R1272/register.json`: beside the act's index, relative to the repository root."""
    return f"{act_dir_for(act)}/{REGISTER_FILE}"


def render_register(register: Register) -> str:
    """The register file's text: indented and newline-terminated, as every derived file is."""
    return register.model_dump_json(indent=2) + "\n"
