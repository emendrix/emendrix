"""The site build's substance files as a reader reads them.

A site build writes, beside its `catalogue.json`, `substances.json` (every CAS and EC number an
entry in the record prints, and every Index No whose entry lands on one of their pages) and one
file per number under `substances/`, named `<scheme>-<value>.json`. Neither is part of the record:
both are derived from the committed registers and payloads. These are a reader's models of them,
held to the writer's by a contract test in the `emendrix` suite, as `models.py` is. An entry and
its rows reuse the payload's models, because they are the same rows.

A number the list does not hold is printed by no entry the record holds, which says nothing
about the law: many entries name a group of substances and print no number.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.payload import IdentifierRecord, TableEntryRecord

__all__ = [
    "SubstanceChange",
    "SubstanceEntry",
    "SubstanceFile",
    "SubstanceIndex",
    "SubstanceRow",
]

_FROZEN = ConfigDict(frozen=True)


class SubstanceRow(BaseModel):
    """One identifier, and where its page and its file are."""

    model_config = _FROZEN

    scheme: str = Field(description="`cas`, `ec`, or a row key's scheme such as `index`.")
    value: str = Field(description="The canonical value.")
    page: str = Field(description="The page it lands on.")
    file: str = Field(description="The file holding that page's facts.")
    canonical: str = Field(description="The page a search engine is pointed at for it.")


class SubstanceIndex(BaseModel):
    """Every number with a page, then every other identifier that lands on one."""

    model_config = _FROZEN

    substance_schema: str = Field(description="The format's version.")
    disclaimer: str = Field(description="Not legal advice.")
    provenance: str = Field(description="Where the file comes from.")
    substances: tuple[SubstanceRow, ...] = Field(description="One row per identifier.")


class SubstanceEntry(BaseModel):
    """One entry of an act's newest version that prints the number, as its register holds it."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    act: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The act's short label on the site.")
    version: str = Field(description="The version the register was read from.")
    key_label: str | None = Field(description="How the act names the key; null for a name key.")
    header: tuple[tuple[str | None, ...], ...] = Field(description="The table's header rows.")
    entry: TableEntryRecord = Field(description="The entry, its rows verbatim.")
    act_page: str = Field(description="The act's page.")
    provision_page: str | None = Field(description="The unit's page, where there is one.")
    last_changed: str | None = Field(
        description="The permalink of the newest recorded change to this entry; null for none."
    )


class SubstanceChange(BaseModel):
    """One recorded change to an entry printing the number."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    act: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The act's short label on the site.")
    version: str = Field(description="The version the change was recorded in.")
    dated: date = Field(description="The version's in-force date, else the day it was seen.")
    in_force: bool = Field(description="True when `dated` is the in-force date.")
    kind: str = Field(description="`added`, `amended` or `removed`.")
    typography_only: bool = Field(description="Amended only in spacing, dash forms or accents.")
    key_label: str | None = Field(description="How the act names the key; null for a name key.")
    header: tuple[tuple[str | None, ...], ...] = Field(description="The table's header rows.")
    before: TableEntryRecord | None = Field(description="The entry before; null when added.")
    after: TableEntryRecord | None = Field(description="The entry after; null when removed.")
    amending_acts: tuple[str, ...] = Field(
        description="The amending acts the change names, which may be fewer than made it."
    )
    event: str = Field(description="The permalink of the change block on its version page.")
    file: str = Field(description="The payload the change was read from, as the site serves it.")


class SubstanceFile(BaseModel):
    """One CAS or EC number: every entry that prints it now, and every change to such entries."""

    model_config = _FROZEN

    substance_schema: str = Field(description="The format's version.")
    disclaimer: str = Field(description="Not legal advice.")
    provenance: str = Field(description="Where the file comes from.")
    scheme: str = Field(description="`cas` or `ec`.")
    value: str = Field(description="The canonical value.")
    page: str = Field(description="The number's page.")
    canonical: str = Field(description="The page a search engine is pointed at for it.")
    identifiers: tuple[IdentifierRecord, ...] = Field(
        description="Every identifier the entries' rows carry, this one included."
    )
    entries: tuple[SubstanceEntry, ...] = Field(description="Act order, then document order.")
    history: tuple[SubstanceChange, ...] = Field(description="Newest first.")
