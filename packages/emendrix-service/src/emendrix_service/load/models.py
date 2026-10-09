"""The rows the loader writes, one frozen model per `content` table, and the shapes it reads.

Kept apart from `rows.py`, which builds them from the record: the database's query module takes
and returns these, and must not depend on how they are built.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.models import ProvisionRow

__all__ = [
    "ActLoad",
    "ChangeLoad",
    "EventLoad",
    "FiledRow",
    "Json",
    "ProvisionLoad",
    "StoredUnitChange",
]

Json = dict[str, object]

_FROZEN = ConfigDict(frozen=True)


class ActLoad(BaseModel):
    """One `content.acts` row."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    act_key: str = Field(description="The act's key within its corpus.")
    label: str = Field(description="The catalogue's short label.")
    long_name: str = Field(description="The catalogue's long form, or ''.")
    domain: str = Field(description="The catalogue's sector, or ''.")
    aliases: tuple[str, ...] = Field(description="The catalogue's other names for the act.")
    url: str = Field(description="The act's page, as the catalogue gives it.")
    feed: str | None = Field(description="The act's feed, as the catalogue gives it.")
    title: str = Field(description="The root index's title, or the label for a quiet act.")
    index_sha256: str | None = Field(
        description="The act index's hash once every event it lists is stored; else null or "
        "the hash of the last index that was."
    )
    checked_through: date | None = Field(description="The catalogue's `checked_through`.")
    waiting: tuple[Json, ...] = Field(description="The catalogue's `waiting`, as JSON.")


class EventLoad(BaseModel):
    """One `content.events` row."""

    model_config = _FROZEN

    event_key: str = Field(description="`corpus/act_key@to_version`, stable across repairs.")
    corpus: str = Field(description="The act's corpus namespace.")
    act_key: str = Field(description="The act's key within its corpus.")
    entry_key: str = Field(description="The payload's file stem, the catalogue's event key.")
    from_version: str = Field(description="The index row's `from_version`.")
    to_version: str = Field(description="The index row's `to_version`.")
    detected_on: date = Field(description="The index row's `detected_on`.")
    in_force: tuple[date, ...] = Field(description="The index row's `in_force`.")
    updated_on: date = Field(description="The index row's `updated_on`.")
    path: str = Field(description="The payload's path in the changelogs repository.")
    sha256: str = Field(description="The payload's hash, as the index states and the read found.")
    url: str | None = Field(description="The event's page, as the catalogue gives it.")


class ChangeLoad(BaseModel):
    """One `content.changes` row."""

    model_config = _FROZEN

    event_key: str = Field(description="The event the change belongs to.")
    location: str = Field(description="The change's own canonical location.")
    occurrence: int = Field(ge=1, description="Which repeat of `location` in the event, from 1.")
    unit: str = Field(description="The top-level unit the act index files the change under.")
    change_type: str = Field(description="The payload's `change_type`.")
    heading: str | None = Field(description="The payload's heading.")
    previous_location: str | None = Field(description="The payload's `previous_location`.")
    disputed: bool = Field(description="The index row's `disputed`.")
    dispute_reason: str | None = Field(description="The index row's `dispute_reason`.")
    signals: Json = Field(description="The payload's three signals, as JSON.")
    in_force: date | None = Field(description="The payload's `in_force`.")
    applies_from: str = Field(description="An ISO date, `unknown` or `unchanged`.")
    dates_added: tuple[date, ...] = Field(description="The payload's `dates_added`.")
    dates_removed: tuple[date, ...] = Field(description="The payload's `dates_removed`.")
    amending_acts: tuple[str, ...] = Field(description="Keys of the acts the payload names.")
    changed_within: tuple[str, ...] = Field(description="The payload's `changed_within`.")
    outcome: str = Field(description="How the change left the citation gate.")
    unexplained_kind: str = Field(description="The payload's `unexplained_kind`.")
    unexplained: str = Field(description="The payload's `unexplained`.")
    sentences: tuple[Json, ...] = Field(
        description="Each stored sentence, then the applicability note marked `note: true`."
    )
    anchor: str = Field(description="The change's fragment on its event page.")


class ProvisionLoad(BaseModel):
    """One `content.provisions` row."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus namespace.")
    act_key: str = Field(description="The act's key within its corpus.")
    unit: str = Field(description="The top-level unit.")
    heading: str | None = Field(description="The heading of the unit's newest stored change.")
    newest_version: str = Field(description="The `to_version` of that change's event.")
    changes: int = Field(ge=1, description="Stored changes filed under the unit.")


class StoredUnitChange(BaseModel):
    """What a provision row is computed from: one stored change, as read back."""

    model_config = _FROZEN

    unit: str = Field(description="The change's unit.")
    to_version: str = Field(description="Its event's `to_version`.")
    location: str = Field(description="The change's own location.")
    occurrence: int = Field(ge=1, description="Its occurrence.")
    heading: str | None = Field(description="Its heading.")


class FiledRow(BaseModel):
    """The act index's row for one payload change, and the unit it is filed under."""

    model_config = _FROZEN

    unit: str = Field(description="The act index's key the row sits under.")
    row: ProvisionRow = Field(description="The row.")
