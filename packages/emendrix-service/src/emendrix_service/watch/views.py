"""The frozen views `db.watchlists` returns and the watch pages draw.

Kept apart from the queries, as `feed.model` is from `db.feed`, so the pure rules in `watch`
can take these values without importing the database.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.models import CatalogueWaiting
from emendrix_service.db.enums import Cadence, ItemKind

__all__ = [
    "ActKey",
    "ActView",
    "EntryStamp",
    "ProvisionView",
    "WatchItemView",
    "WatchlistView",
]

ActKey = tuple[str, str]

_FROZEN = ConfigDict(frozen=True)


class WatchItemView(BaseModel):
    """One item of a watchlist: an act, one provision of it, or one CAS or EC number."""

    model_config = _FROZEN

    id: UUID = Field(description="The item's id.")
    kind: ItemKind = Field(description="A whole act, one provision of it, or a substance.")
    corpus: str | None = Field(default=None, description="The act's corpus; None: a substance.")
    act_key: str | None = Field(default=None, description="The act's key; None: a substance.")
    location: str | None = Field(
        default=None, description="The canonical location; None for the whole act."
    )
    identifier: str | None = Field(
        default=None, description="`scheme:value` of a watched CAS or EC number; else None."
    )

    def act(self) -> ActKey | None:
        """The act the item names; None for a watched number, which names none."""
        if self.corpus is None or self.act_key is None:
            return None
        return (self.corpus, self.act_key)


class WatchlistView(BaseModel):
    """One watchlist with its settings and its items, oldest item first."""

    model_config = _FROZEN

    id: UUID = Field(description="The watchlist's id.")
    name: str = Field(description="The name its owner gave it.")
    cadence: Cadence = Field(description="How often its matches are mailed.")
    date_alerts: bool = Field(description="Whether a change adding or removing a date is flagged.")
    heartbeat: bool = Field(description="Whether a monthly note is sent when nothing changed.")
    paused: bool = Field(description="Whether delivery is paused.")
    has_feed: bool = Field(description="Whether a personal feed token has been issued.")
    items: tuple[WatchItemView, ...] = Field(description="Its items.")


class ActView(BaseModel):
    """One watched act, as `content.acts` holds it."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus.")
    act_key: str = Field(description="The act's key.")
    label: str = Field(description="The catalogue's short label.")
    long_name: str = Field(description="The catalogue's long form, or ''.")
    aliases: tuple[str, ...] = Field(description="The catalogue's other names for the act.")
    url: str = Field(description="The act's page.")
    checked_through: date | None = Field(description="How far the poller has read, or None.")
    waiting: tuple[CatalogueWaiting, ...] = Field(description="Versions announced, not read.")


class ProvisionView(BaseModel):
    """One top-level unit of an act that the record holds a change to."""

    model_config = _FROZEN

    unit: str = Field(description="The canonical top-level location.")
    heading: str | None = Field(description="The heading of its newest stored change.")
    changes: int = Field(description="How many stored changes are filed under it.")


class EntryStamp(BaseModel):
    """One stored change to a table row carrying a watched number, with where its page is."""

    model_config = _FROZEN

    identifier: str = Field(description="`scheme:value` of the number the row carries.")
    row_key: str = Field(description="The table row's key.")
    key_label: str | None = Field(description="How the act names the key; None: by name.")
    name: str | None = Field(description="The row's name, when it has one.")
    kind: str = Field(description="`added`, `removed` or `amended`.")
    unit: str = Field(description="The top-level unit holding the table.")
    act_label: str = Field(description="The catalogue's label for the act, or its key.")
    in_force: date | None = Field(description="The change's own in-force date, when it has one.")
    detected_on: date = Field(description="When the record detected the change's event.")
    event_key: str = Field(description="The event's key.")
    url: str | None = Field(description="The event's page, once the catalogue names it.")
    anchor: str = Field(description="The change's anchor on that page.")
