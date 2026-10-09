"""What the operator's status block reads: aggregate counts, and nothing that names a person.

Every query here counts or groups. None selects an address, a user id, a token digest or an
email body, so nothing this module returns can put a person into a status email or a log line.
Watch items are counted per act, never per account.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import (
    Cadence,
    DeliveryKind,
    ItemKind,
    MailEventKind,
    OutboxStatus,
    SuppressionReason,
    UserStatus,
)
from emendrix_service.db.tables_app import (
    Delivery,
    MailEvent,
    Outbox,
    Suppression,
    User,
    WatchItem,
    Watchlist,
)
from emendrix_service.db.tables_content import Load
from emendrix_service.db.tables_notify import Announced

__all__ = [
    "ActItems",
    "Announcements",
    "LastLoad",
    "MailHealth",
    "OutboxHealth",
    "Population",
    "announcements_since",
    "deliveries_since",
    "items_per_act",
    "last_load",
    "mail_health_since",
    "outbox_health",
    "population",
]

_FROZEN = ConfigDict(frozen=True)


class LastLoad(BaseModel):
    """The newest run of the loader."""

    model_config = _FROZEN

    started_at: datetime = Field(description="When it started.")
    finished_at: datetime | None = Field(description="When it finished; null if it did not.")
    root_sha256: str = Field(description="The digest of the root index it read.")
    upserted: int = Field(description="Events it wrote.")
    removed: int = Field(description="Events it deleted.")
    skipped: int = Field(description="Events it found unchanged.")


class Announcements(BaseModel):
    """Events the notifier judged in a window, by its verdict."""

    model_config = _FROZEN

    eligible: int = Field(description="Events matched against watchlists.")
    not_eligible: int = Field(description="Events judged and not announced.")


class OutboxHealth(BaseModel):
    """The state of the outbox at one instant."""

    model_config = _FROZEN

    queued: int = Field(description="Rows waiting to be sent.")
    oldest_queued_at: datetime | None = Field(
        description="When the oldest waiting row was written; null when none waits."
    )
    failed_since: int = Field(description="Rows written in the window that ended failed.")
    failed_held: int = Field(description="Failed rows still held, written at any time.")


class MailHealth(BaseModel):
    """What the mail provider reported in a window, and what is suppressed now."""

    model_config = _FROZEN

    events: dict[MailEventKind, int] = Field(description="Provider events in the window, by kind.")
    suppressions: dict[SuppressionReason, int] = Field(
        description="Every suppressed address held, by reason."
    )


class Population(BaseModel):
    """How many accounts and watchlists exist."""

    model_config = _FROZEN

    users: dict[UserStatus, int] = Field(description="Accounts, by status.")
    watchlists: dict[Cadence, int] = Field(description="Watchlists, by cadence.")
    paused: int = Field(description="Watchlists paused, whatever their cadence.")


class ActItems(BaseModel):
    """How many watch items name one act, summed over every watchlist."""

    model_config = _FROZEN

    corpus: str = Field(description="The act's corpus.")
    act_key: str = Field(description="The act's key in that corpus.")
    items: dict[ItemKind, int] = Field(description="Watch items naming the act, by kind.")


async def last_load(tx: Tx) -> LastLoad | None:
    """The newest load, or `None` before the first."""
    row = await tx.scalar(select(Load).order_by(Load.started_at.desc(), Load.id.desc()).limit(1))
    if row is None:
        return None
    return LastLoad(
        started_at=row.started_at,
        finished_at=row.finished_at,
        root_sha256=row.root_sha256,
        upserted=row.events_upserted,
        removed=row.events_removed,
        skipped=row.events_skipped,
    )


async def announcements_since(tx: Tx, since: datetime) -> Announcements:
    """Events first judged at or after `since`."""
    rows = await tx.execute(
        select(Announced.eligible, func.count())
        .where(Announced.first_seen_at >= since)
        .group_by(Announced.eligible)
    )
    counts = {bool(eligible): int(count) for eligible, count in rows}
    return Announcements(eligible=counts.get(True, 0), not_eligible=counts.get(False, 0))


async def deliveries_since(tx: Tx, since: datetime) -> dict[DeliveryKind, int]:
    """Deliveries written at or after `since`, by kind, every kind present."""
    rows = await tx.execute(
        select(Delivery.kind, func.count())
        .where(Delivery.created_at >= since)
        .group_by(Delivery.kind)
    )
    found = {kind: int(count) for kind, count in rows}
    return {kind: found.get(kind, 0) for kind in DeliveryKind}


async def outbox_health(tx: Tx, since: datetime) -> OutboxHealth:
    """The queue now, and the rows written at or after `since` that failed."""
    queued_count, oldest = (
        await tx.execute(
            select(func.count(), func.min(Outbox.created_at)).where(
                Outbox.status == OutboxStatus.QUEUED
            )
        )
    ).one()
    failed_held, failed_since = (
        await tx.execute(
            select(
                func.count(),
                func.count().filter(Outbox.created_at >= since),
            ).where(Outbox.status == OutboxStatus.FAILED)
        )
    ).one()
    return OutboxHealth(
        queued=int(queued_count),
        oldest_queued_at=oldest,
        failed_since=int(failed_since),
        failed_held=int(failed_held),
    )


async def mail_health_since(tx: Tx, since: datetime) -> MailHealth:
    """Provider events at or after `since`, and every suppression, each by kind."""
    events = await tx.execute(
        select(MailEvent.kind, func.count()).where(MailEvent.at >= since).group_by(MailEvent.kind)
    )
    reasons = await tx.execute(
        select(Suppression.reason, func.count()).group_by(Suppression.reason)
    )
    found_events = {kind: int(count) for kind, count in events}
    found_reasons = {reason: int(count) for reason, count in reasons}
    return MailHealth(
        events={kind: found_events.get(kind, 0) for kind in MailEventKind},
        suppressions={reason: found_reasons.get(reason, 0) for reason in SuppressionReason},
    )


async def population(tx: Tx) -> Population:
    """Accounts by status and watchlists by cadence."""
    users = await tx.execute(select(User.status, func.count()).group_by(User.status))
    cadences = await tx.execute(select(Watchlist.cadence, func.count()).group_by(Watchlist.cadence))
    paused = await tx.scalar(select(func.count()).where(Watchlist.paused))
    found_users = {status: int(count) for status, count in users}
    found_cadences = {cadence: int(count) for cadence, count in cadences}
    return Population(
        users={status: found_users.get(status, 0) for status in UserStatus},
        watchlists={cadence: found_cadences.get(cadence, 0) for cadence in Cadence},
        paused=int(paused or 0),
    )


async def items_per_act(tx: Tx) -> list[ActItems]:
    """Watch items grouped by the act they name, ordered by corpus and key."""
    rows = await tx.execute(
        select(WatchItem.corpus, WatchItem.act_key, WatchItem.kind, func.count())
        .group_by(WatchItem.corpus, WatchItem.act_key, WatchItem.kind)
        .order_by(WatchItem.corpus, WatchItem.act_key)
    )
    acts: dict[tuple[str, str], dict[ItemKind, int]] = {}
    for corpus, act_key, kind, count in rows:
        acts.setdefault((corpus, act_key), {item: 0 for item in ItemKind})[kind] = int(count)
    return [
        ActItems(corpus=corpus, act_key=act_key, items=items)
        for (corpus, act_key), items in sorted(acts.items())
    ]
