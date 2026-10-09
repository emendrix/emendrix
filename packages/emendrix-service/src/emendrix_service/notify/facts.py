"""The stored facts the notifier reasons over, as frozen values the database module returns.

Kept apart from the rules that read them (`eligibility`, `matching`, `compose`) so the query
module can build them without importing a rule, and so every rule is a function over values
that a test writes by hand.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db.enums import Cadence, ItemKind

__all__ = [
    "ChangeFacts",
    "Citation",
    "DigestInputs",
    "EventFacts",
    "ItemFacts",
    "MatchKey",
    "MatchRow",
    "StoredSentence",
    "WatchlistFacts",
]

_FROZEN = ConfigDict(frozen=True)


class EventFacts(BaseModel):
    """One `content.events` row, as much of it as judging and rendering an event needs."""

    model_config = _FROZEN

    event_key: str = Field(description="`corpus/act_key@to_version`, stable across repairs.")
    corpus: str = Field(description="The act's corpus namespace.")
    act_key: str = Field(description="The act's key within its corpus.")
    from_version: str = Field(description="The version the event compares from.")
    to_version: str = Field(description="The version the event compares to.")
    detected_on: date = Field(description="The day the pipeline detected the event.")
    in_force: tuple[date, ...] = Field(default=(), description="The event's in-force dates.")
    url: str | None = Field(default=None, description="The event's page; null while unbuilt.")


class Citation(BaseModel):
    """One citation of a stored sentence, exactly as stored."""

    model_config = _FROZEN

    label: str = Field(description="The display form the record stores.")
    url: str = Field(description="Where the cited provision is shown.")


class StoredSentence(BaseModel):
    """One stored sentence of a change's explanation, unaltered."""

    model_config = _FROZEN

    text: str = Field(description="The sentence as stored.")
    fallback: bool = Field(default=False, description="Written by the gate as a quotation.")
    note: bool = Field(default=False, description="The applicability note, stored last.")
    citations: tuple[Citation, ...] = Field(default=(), description="What it cites.")


class ChangeFacts(BaseModel):
    """One `content.changes` row: the stored facts of one change, never its provision text."""

    model_config = _FROZEN

    event_key: str = Field(description="The event the change belongs to.")
    location: str = Field(description="The change's own canonical location.")
    occurrence: int = Field(default=1, ge=1, description="Which repeat of the location, from 1.")
    change_type: str = Field(description="The change type as the record names it.")
    heading: str | None = Field(default=None, description="The provision's stored heading.")
    disputed: bool = Field(default=False, description="Whether the signals disagree.")
    dispute_reason: str | None = Field(default=None, description="The stored reason code.")
    applies_from: str = Field(
        default="unknown", description="An ISO date, `unknown` or `unchanged`, as stored."
    )
    dates_added: tuple[date, ...] = Field(default=(), description="Dates the new text names.")
    dates_removed: tuple[date, ...] = Field(default=(), description="Dates the old text named.")
    amending_acts: tuple[str, ...] = Field(default=(), description="Keys of amending acts.")
    changed_within: tuple[str, ...] = Field(default=(), description="Sub-provisions that moved.")
    unexplained: str = Field(default="", description="Why there are no sentences, when none.")
    sentences: tuple[StoredSentence, ...] = Field(default=(), description="The stored prose.")
    anchor: str = Field(default="", description="The change's fragment on its event page.")


class ItemFacts(BaseModel):
    """One watch item with what matching and delivery need to know of its watchlist."""

    model_config = _FROZEN

    item_id: UUID = Field(description="The item's id.")
    watchlist_id: UUID = Field(description="The watchlist it belongs to.")
    kind: ItemKind = Field(description="A whole act, or one provision of it.")
    corpus: str = Field(description="The act's corpus namespace.")
    act_key: str = Field(description="The act's key.")
    location: str | None = Field(default=None, description="The watched location; null for an act.")
    cadence: Cadence = Field(default=Cadence.WEEKLY, description="The watchlist's cadence.")
    date_alerts: bool = Field(default=True, description="Whether date changes are flagged.")


class WatchlistFacts(BaseModel):
    """A watchlist as an email about it needs it: its name and where the email goes."""

    model_config = _FROZEN

    watchlist_id: UUID = Field(description="The watchlist's id.")
    user_id: UUID = Field(description="Its owner.")
    email: str = Field(description="The owner's address.")
    name: str = Field(description="The watchlist's name.")
    cadence: Cadence = Field(description="How often it is mailed.")
    created_at: datetime = Field(description="When it was made.")


class MatchKey(BaseModel):
    """The key of one change: event, location and occurrence."""

    model_config = _FROZEN

    event_key: str = Field(description="The event.")
    location: str = Field(description="The change's own location.")
    occurrence: int = Field(ge=1, description="Which repeat of the location.")


class MatchRow(BaseModel):
    """One change owed to one watchlist."""

    model_config = _FROZEN

    watchlist_id: UUID = Field(description="The watchlist owed the change.")
    key: MatchKey = Field(description="The change.")
    date_alert: bool = Field(description="Whether the change is flagged as a date change.")


class DigestInputs(BaseModel):
    """Everything one email about a set of matches is composed from."""

    model_config = _FROZEN

    watchlist: WatchlistFacts = Field(description="The watchlist the email is for.")
    events: tuple[EventFacts, ...] = Field(description="The events the matches belong to.")
    changes: tuple[ChangeFacts, ...] = Field(description="The matched changes.")
    labels: dict[str, str] = Field(description="Each act's label, keyed `corpus/act_key`.")
    items: tuple[ItemFacts, ...] = Field(description="The watchlist's items as they stand now.")
    date_alerts: frozenset[MatchKey] = Field(description="The matches flagged as date changes.")
