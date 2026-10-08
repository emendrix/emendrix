"""The change index as types: what a consumer reads before it decides which payload to fetch.

Two files per changelogs repository. `index.json` at the root holds one row per act, small
enough to poll; `<act_dir>/index.json` holds every event of one act and every row of every
provision it touched. Neither carries provision text, which is what the payload is for, and
neither carries a generation timestamp or a commit hash: a timestamp would make two builds of
one record differ, and a file cannot hold the hash of the commit that contains it. Freshness
is `updated_on`, a date the payloads already hold.

Every value is copied off a committed payload read through `ChangelogEntry`, never off its raw
JSON keys, because some of what a consumer wants (`dispute_reason`) is computed by the model
and absent from documents written before it existed. Enumerated values are stored as their
strings, so the schema a consumer reads names strings rather than Python enums. The builders
are in `index.py`; this module holds the shapes and nothing else.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix.output.counts import EntryCounts
from emendrix.output.disclaimer import DISCLAIMER

__all__ = [
    "INDEX_FILE",
    "INDEX_SCHEMA",
    "ActIndex",
    "ActRow",
    "EventRow",
    "ProvisionRow",
    "RepairRow",
    "RootIndex",
    "SignalRow",
]

INDEX_FILE: Final = "index.json"
"""The file name of both levels: the root's, and each act directory's."""

INDEX_SCHEMA: Final = "1.0"
"""Bumped whenever a consumer of the index would have to change to keep reading it."""

TextSides = Literal["both", "before", "after", "none"]


class RepairRow(BaseModel):
    """One repair a payload records, reduced to what it was and when."""

    model_config = ConfigDict(frozen=True)

    kind: str = Field(description="The repair's own free-text kind, as the payload stores it.")
    repaired_on: date = Field(description="The date the payload records for the repair.")


class SignalRow(BaseModel):
    """The three signals' statuses on one change, each the stored status string."""

    model_config = ConfigDict(frozen=True)

    structural_diff: str = Field(description="`observed`, `absent` or `unavailable`.")
    corpus_metadata: str = Field(description="`observed`, `absent` or `unavailable`.")
    instruction_parse: str = Field(description="`observed`, `absent` or `unavailable`.")


class ProvisionRow(BaseModel):
    """One change to one provision in one event, without its text."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(description="The `to_version` of the event this change belongs to.")
    change_type: str = Field(description="The change's type as the structural diff named it.")
    previous_location: str | None = Field(
        description="Canonical location a renumbered provision had before; null otherwise."
    )
    disputed: bool = Field(description="Whether the three signals disagree about this change.")
    dispute_reason: str | None = Field(
        description="Which signal disagreed and how, read through the payload model; null "
        "exactly when the change is not disputed."
    )
    signals: SignalRow = Field(description="Each signal's status on this change.")
    text: TextSides = Field(
        description="Which verbatim sides the payload carries: both, only one, or none."
    )
    in_force: date | None = Field(description="The change's in-force date, null when none.")
    applies_from: str = Field(
        description="An ISO date when the payload holds one, else `unknown` or `unchanged`."
    )
    dates_added: tuple[date, ...] = Field(description="Dates the provision carries after only.")
    dates_removed: tuple[date, ...] = Field(description="Dates the provision carried before only.")
    outcome: str = Field(description="How the change left the citation gate.")
    unexplained_kind: str = Field(description="The counted kind of a missing explanation, or ''.")
    amending_acts: tuple[str, ...] = Field(
        description="Keys of the acts a signal names as amending this provision."
    )
    changed_within: tuple[str, ...] = Field(
        description="Canonical sub-provision coordinates whose text differs."
    )
    occurrence: int = Field(
        ge=1,
        description="Which repeat of this location within its event, from 1, counted as the "
        "site counts it for the change's anchor.",
    )


class EventRow(BaseModel):
    """One committed payload: one amendment event of one act."""

    model_config = ConfigDict(frozen=True)

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
        description="Canonical units only the corpus metadata names, as the payload's "
        "corroboration report stores them; empty when it has none."
    )
    instruction_only_units: tuple[str, ...] = Field(
        description="Canonical units only the instruction parse names, as the payload's "
        "corroboration report stores them; empty when it has none."
    )


class ActIndex(BaseModel):
    """Every event of one act, newest first, and every touched provision's rows."""

    model_config = ConfigDict(frozen=True)

    index_schema: str = Field(default=INDEX_SCHEMA, description="The index format's version.")
    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    corpus: str = Field(description="The act's corpus namespace.")
    key: str = Field(description="The act's key within its corpus.")
    title: str = Field(description="The newest event's title for the act.")
    events: tuple[EventRow, ...] = Field(description="One row per payload, newest first.")
    provisions: dict[str, tuple[ProvisionRow, ...]] = Field(
        description="Rows per canonical top-level location, keys sorted, rows newest first "
        "then by occurrence."
    )


class ActRow(BaseModel):
    """One act as the root index lists it: where its index is, and what it counts."""

    model_config = ConfigDict(frozen=True)

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
    newest_in_force: date | None = Field(
        description="The latest in-force date of the newest event, null when it reports none."
    )
    first_detected_on: date = Field(description="The earliest `detected_on` over the events.")
    updated_on: date = Field(description="The latest `updated_on` over the events.")


class RootIndex(BaseModel):
    """The repository's index: one row per act holding at least one event."""

    model_config = ConfigDict(frozen=True)

    index_schema: str = Field(default=INDEX_SCHEMA, description="The index format's version.")
    disclaimer: str = Field(default=DISCLAIMER, description="Not legal advice.")
    acts: tuple[ActRow, ...] = Field(description="One row per act, sorted by (corpus, key).")
