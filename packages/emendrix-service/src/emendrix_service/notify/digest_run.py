"""`digest`: mail each due daily and weekly watchlist its owed matches, and the monthly note.

Each watchlist is handled in its own transaction. The period's delivery row is written first;
a second run racing this one waits on its unique key and is then refused, so a period is mailed
at most once. A period with nothing owed removes its row again in the same transaction, which
leaves the period open for a match a slower writer commits late; nothing is sent for it.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.locations import human
from emendrix_service.db import Db, Tx
from emendrix_service.db import notify as store
from emendrix_service.db.enums import Cadence, DeliveryKind, OutboxPurpose
from emendrix_service.db.outbox import enqueue
from emendrix_service.notify.facts import ItemFacts
from emendrix_service.notify.model import DigestKind, Heartbeat
from emendrix_service.notify.periods import (
    Period,
    daily_due,
    heartbeat_due,
    local,
    previous_month,
    weekly_due,
)
from emendrix_service.notify.render import render_heartbeat, unsubscribe_url
from emendrix_service.notify.run import deliver
from emendrix_service.settings import ServiceSettings

__all__ = ["DigestCounts", "digest"]

_log = logging.getLogger(__name__)

MONTHS: Final = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""Month names written out, so the note does not depend on the process's locale."""


class DigestCounts(BaseModel):
    """What one `digest` run queued."""

    model_config = ConfigDict(frozen=True)

    daily: int = Field(default=0, description="Daily digests queued.")
    weekly: int = Field(default=0, description="Weekly digests queued.")
    heartbeat: int = Field(default=0, description="Monthly notes queued.")
    failed: int = Field(default=0, description="Watchlists whose transaction failed.")

    @property
    def deliveries(self) -> int:
        """Every email this run queued."""
        return self.daily + self.weekly + self.heartbeat


def _failed(watchlist_id: UUID, error: Exception) -> None:
    # One watchlist that cannot be written must not hold back the others; the next run retries.
    _log.error("watchlist %s was not planned: %s", watchlist_id, type(error).__name__)


async def _digest_one(
    tx: Tx, settings: ServiceSettings, watchlist_id: UUID, period: Period, now: datetime
) -> bool:
    owed = await store.unassigned_matches(tx, watchlist_id, period.boundary)
    if not owed:
        return False
    kind: DigestKind = "daily" if period.kind == "daily" else "weekly"
    return await deliver(
        tx,
        settings,
        watchlist_id=watchlist_id,
        kind=kind,
        period_key=period.key,
        keys=[row.key for row in owed],
        now=now,
    )


def _watched(item: ItemFacts, labels: dict[str, str]) -> str:
    label = labels.get(f"{item.corpus}/{item.act_key}", item.act_key)
    return label if item.location is None else f"{label} {human(item.location)}"


async def _heartbeat_one(
    tx: Tx, settings: ServiceSettings, watchlist_id: UUID, period: Period, now: datetime
) -> bool:
    if await store.has_delivery(tx, watchlist_id, DeliveryKind.HEARTBEAT, period.key):
        return False
    start, end = previous_month(period, settings.zone())
    if await store.active_in_month(tx, watchlist_id, start, end):
        return False
    watchlist = await store.watchlist_facts(tx, watchlist_id)
    if watchlist is None:
        return False
    items = await store.watchlist_items(tx, watchlist_id)
    labels = await store.act_labels(tx, ((item.corpus, item.act_key) for item in items))
    watched = tuple(_watched(item, labels) for item in items)
    if not watched:
        return False
    delivery_id = await store.create_delivery(
        tx, watchlist_id, DeliveryKind.HEARTBEAT, period.key, now
    )
    if delivery_id is None:
        return False
    note = Heartbeat(
        watchlist_name=watchlist.name,
        month=MONTHS[local(start, settings.zone()).month - 1],
        watched=watched,
    )
    mail = render_heartbeat(
        note,
        to=watchlist.email,
        site_url=settings.site_url,
        manage_url=f"{settings.site_url}/account/",
        unsubscribe_url=unsubscribe_url(
            settings.site_url, watchlist_id, secret=settings.secret_key
        ),
    )
    outbox_id = await enqueue(
        tx,
        purpose=OutboxPurpose.HEARTBEAT,
        to=watchlist.email,
        mail=mail,
        user_id=watchlist.user_id,
        now=now,
    )
    await store.attach_outbox(tx, delivery_id, outbox_id)
    return True


async def digest(db: Db, settings: ServiceSettings, now: datetime) -> DigestCounts:
    """Queue every daily, weekly and monthly email due at `now`."""
    zone, hour = settings.zone(), settings.digest_hour
    sent = {"daily": 0, "weekly": 0, "heartbeat": 0, "failed": 0}
    for cadence, period in (
        (Cadence.DAILY, daily_due(now, zone, hour)),
        (Cadence.WEEKLY, weekly_due(now, zone, hour)),
    ):
        if period is None:
            continue
        async with db.transaction() as tx:
            due = await store.due_watchlists(tx, cadence)
        for watchlist_id in due:
            try:
                async with db.transaction() as tx:
                    sent[period.kind] += await _digest_one(tx, settings, watchlist_id, period, now)
            except Exception as error:
                sent["failed"] += 1
                _failed(watchlist_id, error)
    note = heartbeat_due(now, zone, hour)
    if note is not None:
        start, _ = previous_month(note, zone)
        async with db.transaction() as tx:
            due = await store.due_watchlists(tx, heartbeat_before=start)
        for watchlist_id in due:
            try:
                async with db.transaction() as tx:
                    sent["heartbeat"] += await _heartbeat_one(tx, settings, watchlist_id, note, now)
            except Exception as error:
                sent["failed"] += 1
                _failed(watchlist_id, error)
    return DigestCounts(**sent)
