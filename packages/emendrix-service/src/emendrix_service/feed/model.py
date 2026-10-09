"""The values the personal feed is built from: a stored change with its event, and an entry.

Kept apart from the rules and the queries so that `db.feed` can return them and `feed.logic`
can build entries from them without importing the database.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.notify.facts import ChangeFacts, EventFacts

__all__ = ["FeedChange", "FeedEntry", "FeedHead"]

_FROZEN = ConfigDict(frozen=True)


class FeedChange(BaseModel):
    """One stored change with its event and its act's label."""

    model_config = _FROZEN

    change: ChangeFacts = Field(description="The change.")
    event: EventFacts = Field(description="The event it belongs to.")
    act_label: str = Field(description="The catalogue's label for the act, or its key.")


class FeedEntry(BaseModel):
    """One watched change as one Atom entry."""

    model_config = _FROZEN

    link: str = Field(description="The change on its event page: the entry's id and its link.")
    title: str = Field(description="`<act label>: <location> <change type>`.")
    updated: date = Field(description="When the event took effect.")
    content: str = Field(description="The stored facts, in the email's words.")


class FeedHead(BaseModel):
    """What the feed says about itself."""

    model_config = _FROZEN

    watchlist_id: UUID = Field(description="The watchlist, which names the feed's id.")
    name: str = Field(description="The watchlist's name.")
    created_at: datetime = Field(description="When the watchlist was made.")
