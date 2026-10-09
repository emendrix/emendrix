"""The values leaving works over: the export file's sections, and what retention reads.

The export's models name exactly the columns a person gets back. A column holding a secret's
digest (`token_hash`, `id_hash`, `feed_token_hash`) has no field here, so it cannot reach the
file by accident; an outbox row is metadata only, because its body and headers are the email
itself, headers carrying the unsubscribe token.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service import DISCLAIMER
from emendrix_service.db.enums import (
    AuditAction,
    Cadence,
    ConsentKind,
    DeliveryKind,
    ItemKind,
    OutboxPurpose,
    OutboxStatus,
    UserStatus,
)

__all__ = [
    "EXPORT_FORMAT",
    "ExportAudit",
    "ExportConsent",
    "ExportDelivery",
    "ExportDocument",
    "ExportItem",
    "ExportMatch",
    "ExportOutbox",
    "ExportSession",
    "ExportUser",
    "ExportWatchlist",
    "InactiveUser",
    "UnsubscribeTarget",
]

EXPORT_FORMAT: Final = "emendrix-account-export/1"

_FROZEN = ConfigDict(frozen=True)


class ExportUser(BaseModel):
    """The account itself."""

    model_config = _FROZEN

    id: UUID = Field(description="The account's id.")
    email: str = Field(description="The confirmed address.")
    status: UserStatus = Field(description="Whether mail may go to it.")
    created_at: datetime = Field(description="When the account was made.")
    verified_at: datetime = Field(description="When the address was confirmed.")
    last_signin_at: datetime = Field(description="The last sign-in.")
    last_seen_at: datetime = Field(description="The last sign-in, page, feed fetch or unsubscribe.")
    inactivity_notice_at: datetime | None = Field(description="When it was told of deletion.")


class ExportConsent(BaseModel):
    """One consent given at sign-up."""

    model_config = _FROZEN

    kind: ConsentKind = Field(description="What was agreed to.")
    version: str = Field(description="The version of the notice agreed to.")
    granted_at: datetime = Field(description="When.")
    withdrawn_at: datetime | None = Field(description="When it was withdrawn, if it was.")


class ExportWatchlist(BaseModel):
    """One watchlist and its settings; whether a feed exists, never its token."""

    model_config = _FROZEN

    id: UUID = Field(description="The watchlist's id.")
    name: str = Field(description="Its name.")
    cadence: Cadence = Field(description="How often it is mailed.")
    date_alerts: bool = Field(description="Whether date changes are flagged.")
    heartbeat: bool = Field(description="Whether the monthly note is sent.")
    paused: bool = Field(description="Whether delivery is paused.")
    has_feed: bool = Field(description="Whether a personal feed address exists.")
    created_at: datetime = Field(description="When it was made.")


class ExportItem(BaseModel):
    """One watch item."""

    model_config = _FROZEN

    id: UUID = Field(description="The item's id.")
    watchlist_id: UUID = Field(description="Its watchlist.")
    kind: ItemKind = Field(description="A whole act or one provision of it.")
    corpus: str = Field(description="The act's corpus.")
    act_key: str = Field(description="The act's key.")
    location: str | None = Field(description="The canonical location; null for the whole act.")
    created_at: datetime = Field(description="When it was added.")


class ExportMatch(BaseModel):
    """One change owed to a watchlist."""

    model_config = _FROZEN

    watchlist_id: UUID = Field(description="The watchlist.")
    event_key: str = Field(description="The event.")
    location: str = Field(description="The change's location.")
    occurrence: int = Field(description="Which repeat of the location.")
    date_alert: bool = Field(description="Whether it was flagged as a date change.")
    matched_at: datetime = Field(description="When it was matched.")
    delivery_id: UUID | None = Field(description="The delivery that carried it, if any.")


class ExportDelivery(BaseModel):
    """One email owed to a watchlist for one period."""

    model_config = _FROZEN

    id: UUID = Field(description="The delivery's id.")
    watchlist_id: UUID = Field(description="The watchlist.")
    kind: DeliveryKind = Field(description="Which email it is.")
    period_key: str = Field(description="The period it covers.")
    outbox_id: UUID | None = Field(description="The email that carried it, while kept.")
    created_at: datetime = Field(description="When it was planned.")


class ExportOutbox(BaseModel):
    """One email written to the account: what, to where, and what became of it."""

    model_config = _FROZEN

    id: UUID = Field(description="The email's id.")
    purpose: OutboxPurpose = Field(description="Why it was written.")
    to_email: str = Field(description="The address it went to.")
    subject: str = Field(description="Its subject.")
    status: OutboxStatus = Field(description="Whether it was sent.")
    attempts: int = Field(description="Sends tried.")
    created_at: datetime = Field(description="When it was written.")
    sent_at: datetime | None = Field(description="When the relay accepted it.")


class ExportSession(BaseModel):
    """One signed-in browser: when it began and when it ends, nothing that identifies it."""

    model_config = _FROZEN

    created_at: datetime = Field(description="When the browser signed in.")
    expires_at: datetime = Field(description="When the session ends unless used.")


class ExportAudit(BaseModel):
    """One account action kept in the audit log."""

    model_config = _FROZEN

    action: AuditAction = Field(description="What was done.")
    at: datetime = Field(description="When.")


class ExportDocument(BaseModel):
    """The export file: every row the account owns, the disclaimer and the format's name."""

    model_config = _FROZEN

    format: Literal["emendrix-account-export/1"] = Field(
        default=EXPORT_FORMAT, description="The name and version of this file's layout."
    )
    disclaimer: str = Field(default=DISCLAIMER, description="The not-legal-advice disclaimer.")
    user: ExportUser = Field(description="The account.")
    consents: tuple[ExportConsent, ...] = Field(description="Consents given.")
    watchlists: tuple[ExportWatchlist, ...] = Field(description="Watchlists.")
    items: tuple[ExportItem, ...] = Field(description="Watch items.")
    matches: tuple[ExportMatch, ...] = Field(description="Changes owed.")
    deliveries: tuple[ExportDelivery, ...] = Field(description="Emails planned.")
    outbox: tuple[ExportOutbox, ...] = Field(description="Emails written, without bodies.")
    sessions: tuple[ExportSession, ...] = Field(description="Signed-in browsers.")
    audit_log: tuple[ExportAudit, ...] = Field(description="Account actions.")


class UnsubscribeTarget(BaseModel):
    """The watchlist an unsubscribe link names, as its page shows it."""

    model_config = _FROZEN

    name: str = Field(description="The watchlist's name.")
    cadence: Cadence = Field(description="How often it is mailed now.")


class InactiveUser(BaseModel):
    """What the inactivity rule reads of one account."""

    model_config = _FROZEN

    id: UUID = Field(description="The account's id.")
    email: str = Field(description="Where the notice goes.")
    last_seen_at: datetime = Field(description="The last sighting.")
    inactivity_notice_at: datetime | None = Field(description="When it was told, if it was.")
