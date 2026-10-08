"""The index and the catalogue as this server reads them.

These are the server's own models of files `emendrix` writes, because the server must not
import `emendrix`: that distribution carries the model stage, and a reader of verified records
has no business being able to reach it. A contract test in the `emendrix` suite holds every
model here to the one it mirrors, so a field the writer adds or retypes fails a test there
rather than a request here.

Enumerated values are kept as the strings the documents store, and nothing here derives a
value: a field is either read off the file or absent from the model. Unknown keys are ignored,
so a document that gains a field still reads. The models of one payload are in `payload.py`:
the index is what a tool lists from and a payload what it quotes from, and they are read at
different moments for different reasons.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ActIndex",
    "ActRow",
    "Catalogue",
    "CatalogueAct",
    "EntryCounts",
    "EventRow",
    "ProvisionRow",
    "RepairRow",
    "RootIndex",
    "SignalRow",
]

_FROZEN = ConfigDict(frozen=True)

# --- the index ------------------------------------------------------------------------------


class RepairRow(BaseModel):
    """One repair a payload records, reduced to what it was and when."""

    model_config = _FROZEN

    kind: str = Field(description="The repair's own free-text kind, as the payload stores it.")
    repaired_on: date = Field(description="The date the payload records for the repair.")


class SignalRow(BaseModel):
    """The three signals' statuses on one change, each the stored status string."""

    model_config = _FROZEN

    structural_diff: str = Field(description="`observed`, `absent` or `unavailable`.")
    corpus_metadata: str = Field(description="`observed`, `absent` or `unavailable`.")
    instruction_parse: str = Field(description="`observed`, `absent` or `unavailable`.")


class EntryCounts(BaseModel):
    """The counts a payload carries for its event, as the index copies them."""

    model_config = _FROZEN

    touched: int = Field(default=0, ge=0, description="Top-level units the event touched.")
    substantive: int = Field(default=0, ge=0, description="Touched units whose text moved.")
    date_only: int = Field(default=0, ge=0, description="Units whose every change is DEFERRED.")
    textless: int = Field(default=0, ge=0, description="Units carrying no text on either side.")
    disputed: int = Field(default=0, ge=0, description="Changes the signals disagree about.")
    quoted: int = Field(default=0, ge=0, description="Sentences written as verbatim quotations.")
    unexplained: int = Field(default=0, ge=0, description="Changes that ship with no prose.")


class ProvisionRow(BaseModel):
    """One change to one provision in one event, without its text."""

    model_config = _FROZEN

    version: str = Field(description="The `to_version` of the event this change belongs to.")
    change_type: str = Field(description="The change's type as the structural diff named it.")
    previous_location: str | None = Field(
        description="Canonical location a renumbered provision had before; null otherwise."
    )
    disputed: bool = Field(description="Whether the three signals disagree about this change.")
    dispute_reason: str | None = Field(
        description="Which signal disagreed and how; null exactly when not disputed."
    )
    signals: SignalRow = Field(description="Each signal's status on this change.")
    text: Literal["both", "before", "after", "none"] = Field(
        description="Which verbatim sides the payload carries."
    )
    in_force: date | None = Field(description="The change's in-force date, null when none.")
    applies_from: str = Field(description="An ISO date, else `unknown` or `unchanged`.")
    dates_added: tuple[date, ...] = Field(description="Dates the provision carries after only.")
    dates_removed: tuple[date, ...] = Field(description="Dates it carried before only.")
    outcome: str = Field(description="How the change left the citation gate.")
    unexplained_kind: str = Field(description="The counted kind of a missing explanation, or ''.")
    amending_acts: tuple[str, ...] = Field(description="Keys of acts named as amending it.")
    changed_within: tuple[str, ...] = Field(description="Sub-provision coordinates that differ.")
    occurrence: int = Field(ge=1, description="Which repeat of its location in the event, from 1.")


class EventRow(BaseModel):
    """One committed payload: one amendment event of one act."""

    model_config = _FROZEN

    to_version: str = Field(description="The version the event produced; its identity.")
    from_version: str = Field(description="The version the event was computed from.")
    detected_on: date = Field(description="The date the run observed the event.")
    in_force: tuple[date, ...] = Field(description="The in-force dates the changes report.")
    updated_on: date = Field(description="The latest of `detected_on` and every repair's date.")
    schema_version: str = Field(description="The payload's own schema version.")
    path: str = Field(description="The payload's path relative to the repository root.")
    sha256: str = Field(description="Hex sha256 of the payload's committed bytes.")
    diff_only: bool = Field(description="Whether the payload was written with no model stage.")
    counts: EntryCounts = Field(description="The payload's own counts, as stored.")
    repairs: tuple[RepairRow, ...] = Field(description="Repairs the payload records, in order.")
    evidence: bool = Field(description="Whether the payload carries any evidence digest.")
    metadata_only_units: tuple[str, ...] = Field(
        description="Units only the corpus metadata names; never change rows."
    )
    instruction_only_units: tuple[str, ...] = Field(
        description="Units only the instruction parse names; never change rows."
    )


class ActIndex(BaseModel):
    """Every event of one act, newest first, and every touched provision's rows."""

    model_config = _FROZEN

    index_schema: str = Field(description="The index format's version.")
    disclaimer: str = Field(description="Not legal advice.")
    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    title: str = Field(description="The newest event's title for the act.")
    events: tuple[EventRow, ...] = Field(description="One row per payload, newest first.")
    provisions: dict[str, tuple[ProvisionRow, ...]] = Field(
        description="Rows per canonical top-level location, rows newest first then by occurrence."
    )


class ActRow(BaseModel):
    """One act as the root index lists it: where its index is, and what it counts."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    title: str = Field(description="The newest event's title for the act.")
    index: str = Field(description="Path of the act's index relative to the repository root.")
    index_sha256: str = Field(description="Hex sha256 of that index file's bytes.")
    events: int = Field(ge=0, description="Events the act index lists.")
    changes: int = Field(ge=0, description="Provision rows the act index lists.")
    provisions: int = Field(ge=0, description="Distinct top-level locations it lists.")
    disputed: int = Field(ge=0, description="Provision rows marked disputed.")
    newest_version: str = Field(description="The newest event's `to_version`.")
    newest_in_force: date | None = Field(description="The newest event's latest in-force date.")
    first_detected_on: date = Field(description="The earliest `detected_on` over the events.")
    updated_on: date = Field(description="The latest `updated_on` over the events.")


class RootIndex(BaseModel):
    """The repository's index: one row per act holding at least one event."""

    model_config = _FROZEN

    index_schema: str = Field(description="The index format's version.")
    disclaimer: str = Field(description="Not legal advice.")
    acts: tuple[ActRow, ...] = Field(description="One row per act, sorted by (corpus, key).")


# --- the catalogue --------------------------------------------------------------------------


class CatalogueAct(BaseModel):
    """One watched act: the watchlist's names for it, and where the site shows it."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The watchlist's short label.")
    long_name: str = Field(description="The watchlist's long form, or ''.")
    aliases: tuple[str, ...] = Field(description="Other names the watchlist gives the act.")
    domain: str = Field(description="The watchlist's sector for the act, or ''.")
    url: str = Field(description="The act's page, as the site build wrote its address.")
    feed: str | None = Field(description="The act's Atom feed; null when the build wrote none.")
    eurlex_url: str = Field(description="The act on EUR-Lex, or ''.")
    provisions: dict[str, str] = Field(
        description="Canonical top-level location to its provision page."
    )
    events: dict[str, str] = Field(description="Entry key to its event page.")


class Catalogue(BaseModel):
    """Every watched act the site build knows, with the addresses of its pages."""

    model_config = _FROZEN

    catalogue_schema: str = Field(description="The catalogue format's version.")
    disclaimer: str = Field(description="Not legal advice.")
    provenance: str = Field(description="Where the file comes from.")
    acts: tuple[CatalogueAct, ...] = Field(description="One row per watched act.")
