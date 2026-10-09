"""The notifier's queries: announcements, the items an event is matched against, matches,
deliveries, and the facts an email is composed from.

Exactly-once rests on three unique keys, each written in the caller's transaction beside what it
guards: `notify.announced` (an event is judged once), the primary key of `matches` (a change is
owed to a watchlist once) and `unique(watchlist_id, kind, period_key)` on `deliveries` (one
email per period). A second writer racing the first waits on the key and is then refused, which
`insert_once` and `ON CONFLICT DO NOTHING` turn into an answer rather than an error. A match is
assigned only while its `delivery_id` is null, so two deliveries can never both carry it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, delete, exists, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import Cadence, DeliveryKind, UserStatus
from emendrix_service.db.guards import insert_once
from emendrix_service.db.tables import (
    Act,
    Announced,
    Change,
    Delivery,
    Event,
    Match,
    User,
    WatchItem,
    Watchlist,
)
from emendrix_service.notify.facts import (
    ChangeFacts,
    DigestInputs,
    EventFacts,
    ItemFacts,
    MatchKey,
    MatchRow,
    WatchlistFacts,
)

__all__ = [
    "act_labels",
    "active_in_month",
    "active_items_for_act",
    "announced_count",
    "assign",
    "attach_outbox",
    "create_delivery",
    "delete_delivery",
    "digest_inputs",
    "due_watchlists",
    "event_changes",
    "has_delivery",
    "insert_matches",
    "record_announcement",
    "unannounced_events",
    "unassigned_matches",
    "watchlist_facts",
    "watchlist_items",
]

BATCH = 1000
"""Matches written per statement."""

_MAILED = (Watchlist.paused.is_(False), User.status == UserStatus.ACTIVE)
"""A watchlist that may receive email: not paused, and its owner not suspended."""


def _event(row: Event) -> EventFacts:
    return EventFacts.model_validate(row, from_attributes=True)


def _change(row: Change) -> ChangeFacts:
    # The stored sentences are JSON objects, validated into `StoredSentence` values here.
    return ChangeFacts.model_validate(row, from_attributes=True)


def _item(item: WatchItem, watchlist: Watchlist) -> ItemFacts:
    return ItemFacts(
        item_id=item.id,
        watchlist_id=item.watchlist_id,
        kind=item.kind,
        corpus=item.corpus,
        act_key=item.act_key,
        location=item.location,
        cadence=watchlist.cadence,
        date_alerts=watchlist.date_alerts,
    )


def _match(row: Row[UUID, str, str, int, bool]) -> MatchRow:
    watchlist_id, event_key, location, occurrence, date_alert = row
    key = MatchKey(event_key=event_key, location=location, occurrence=occurrence)
    return MatchRow(watchlist_id=watchlist_id, key=key, date_alert=date_alert)


_KEY = (Match.event_key, Match.location, Match.occurrence)
_MATCH_COLUMNS = (Match.watchlist_id, *_KEY, Match.date_alert)


async def announced_count(tx: Tx) -> int:
    """How many events the notifier has judged."""
    return int(await tx.scalar(select(func.count()).select_from(Announced)) or 0)


async def unannounced_events(tx: Tx) -> list[EventFacts]:
    """Every stored event not yet judged, oldest detection first."""
    judged = exists().where(Announced.event_key == Event.event_key)
    query = select(Event).where(~judged).order_by(Event.detected_on, Event.event_key)
    return [_event(row) for row in (await tx.scalars(query)).all()]


async def record_announcement(tx: Tx, key: str, eligible: bool, reason: str, now: datetime) -> bool:
    """Judge `key` once; `False` when another run has already judged it."""
    row = Announced(event_key=key, first_seen_at=now, eligible=eligible, reason=reason)
    return await insert_once(tx, row)


async def event_changes(tx: Tx, event_key: str) -> list[ChangeFacts]:
    """The stored changes of one event."""
    query = select(Change).where(Change.event_key == event_key)
    return [_change(row) for row in (await tx.scalars(query)).all()]


async def active_items_for_act(tx: Tx, corpus: str, act_key: str) -> list[ItemFacts]:
    """Every item on the act of a watchlist that is mailed: not paused, not `none`, not
    suspended."""
    query = (
        select(WatchItem, Watchlist)
        .join(Watchlist, Watchlist.id == WatchItem.watchlist_id)
        .join(User, User.id == Watchlist.user_id)
        .where(WatchItem.corpus == corpus, WatchItem.act_key == act_key)
        .where(Watchlist.cadence != Cadence.NONE, *_MAILED)
        .order_by(WatchItem.watchlist_id, WatchItem.id)
    )
    return [_item(item, watchlist) for item, watchlist in (await tx.execute(query)).all()]


async def insert_matches(tx: Tx, rows: Sequence[MatchRow], now: datetime) -> list[MatchRow]:
    """Write each match not already written; the ones this call wrote."""
    written: list[MatchRow] = []
    # A statement carries at most 65 535 parameters; six per row, so rows go in batches.
    for start in range(0, len(rows), BATCH):
        values = [
            {**row.model_dump(exclude={"key"}), **row.key.model_dump(), "matched_at": now}
            for row in rows[start : start + BATCH]
        ]
        statement = insert(Match).values(values).on_conflict_do_nothing()
        found = await tx.execute(statement.returning(*_MATCH_COLUMNS))
        written.extend(_match(row) for row in found.all())
    return written


async def unassigned_matches(tx: Tx, watchlist_id: UUID, before: datetime) -> list[MatchRow]:
    """The watchlist's matches recorded before `before` that no delivery carries yet."""
    query = select(*_MATCH_COLUMNS).where(
        Match.watchlist_id == watchlist_id,
        Match.delivery_id.is_(None),
        Match.matched_at < before,
    )
    return [_match(row) for row in (await tx.execute(query)).all()]


async def due_watchlists(
    tx: Tx, cadence: Cadence | None = None, *, heartbeat_before: datetime | None = None
) -> list[UUID]:
    """The mailed watchlists of one cadence; or, given `heartbeat_before`, those of any mailed
    cadence with the monthly note on that were made before it."""
    query = select(Watchlist.id).join(User, User.id == Watchlist.user_id).where(*_MAILED)
    if cadence is not None:
        query = query.where(Watchlist.cadence == cadence)
    if heartbeat_before is not None:
        query = query.where(
            Watchlist.heartbeat.is_(True),
            Watchlist.cadence != Cadence.NONE,
            Watchlist.created_at < heartbeat_before,
        )
    return list((await tx.scalars(query.order_by(Watchlist.id))).all())


async def create_delivery(
    tx: Tx, watchlist_id: UUID, kind: DeliveryKind, period_key: str, now: datetime
) -> UUID | None:
    """The new delivery's id, or `None` when the period already has its delivery."""
    row = Delivery(watchlist_id=watchlist_id, kind=kind, period_key=period_key, created_at=now)
    return row.id if await insert_once(tx, row) else None


async def has_delivery(tx: Tx, watchlist_id: UUID, kind: DeliveryKind, period_key: str) -> bool:
    """Whether the period already has its delivery; a read, so a rerun writes nothing."""
    found = exists().where(
        Delivery.watchlist_id == watchlist_id,
        Delivery.kind == kind,
        Delivery.period_key == period_key,
    )
    return bool(await tx.scalar(select(found)))


async def delete_delivery(tx: Tx, delivery_id: UUID) -> None:
    """Remove a delivery that found nothing to carry, so the period's guard is not spent."""
    await tx.execute(delete(Delivery).where(Delivery.id == delivery_id))


async def assign(
    tx: Tx, delivery_id: UUID, watchlist_id: UUID, keys: Iterable[MatchKey]
) -> list[MatchRow]:
    """Give the delivery each of the watchlist's matches at `keys` still unassigned; those it
    took."""
    wanted = [(key.event_key, key.location, key.occurrence) for key in keys]
    if not wanted:
        return []
    statement = (
        update(Match)
        .where(
            Match.watchlist_id == watchlist_id,
            Match.delivery_id.is_(None),
            tuple_(*_KEY).in_(wanted),
        )
        .values(delivery_id=delivery_id)
        .returning(*_MATCH_COLUMNS)
    )
    return [_match(row) for row in (await tx.execute(statement)).all()]


async def attach_outbox(tx: Tx, delivery_id: UUID, outbox_id: UUID) -> None:
    """Record which outbox row carries the delivery."""
    await tx.execute(update(Delivery).where(Delivery.id == delivery_id).values(outbox_id=outbox_id))


async def active_in_month(tx: Tx, watchlist_id: UUID, start: datetime, end: datetime) -> bool:
    """Whether the watchlist was owed or sent a change between `start` and `end`."""
    delivered = exists().where(
        Delivery.watchlist_id == watchlist_id,
        Delivery.kind != DeliveryKind.HEARTBEAT,
        Delivery.created_at >= start,
        Delivery.created_at < end,
    )
    matched = exists().where(
        Match.watchlist_id == watchlist_id, Match.matched_at >= start, Match.matched_at < end
    )
    return bool(await tx.scalar(select(delivered | matched)))


async def watchlist_facts(tx: Tx, watchlist_id: UUID) -> WatchlistFacts | None:
    """The watchlist and its owner's address, or `None` when it is gone."""
    query = (
        select(Watchlist, User.email)
        .join(User, User.id == Watchlist.user_id)
        .where(Watchlist.id == watchlist_id)
    )
    found = (await tx.execute(query)).first()
    if found is None:
        return None
    watchlist, email = found
    return WatchlistFacts(
        watchlist_id=watchlist.id,
        user_id=watchlist.user_id,
        email=email,
        name=watchlist.name,
        cadence=watchlist.cadence,
        created_at=watchlist.created_at,
    )


async def watchlist_items(tx: Tx, watchlist_id: UUID) -> list[ItemFacts]:
    """Every item of one watchlist, as it stands now."""
    query = (
        select(WatchItem, Watchlist)
        .join(Watchlist, Watchlist.id == WatchItem.watchlist_id)
        .where(WatchItem.watchlist_id == watchlist_id)
        .order_by(WatchItem.corpus, WatchItem.act_key, WatchItem.location, WatchItem.id)
    )
    return [_item(item, watchlist) for item, watchlist in (await tx.execute(query)).all()]


async def act_labels(tx: Tx, acts: Iterable[tuple[str, str]]) -> dict[str, str]:
    """The catalogue's label of each act, keyed `corpus/act_key`."""
    wanted = list(set(acts))
    if not wanted:
        return {}
    query = select(Act.corpus, Act.act_key, Act.label).where(
        tuple_(Act.corpus, Act.act_key).in_(wanted)
    )
    return {f"{corpus}/{key}": label for corpus, key, label in (await tx.execute(query)).all()}


async def digest_inputs(
    tx: Tx, watchlist: WatchlistFacts, rows: Sequence[MatchRow]
) -> DigestInputs:
    """The events, changes, labels and items an email about `rows` is composed from."""
    keys = [(row.key.event_key, row.key.location, row.key.occurrence) for row in rows]
    changes: list[ChangeFacts] = []
    events: list[EventFacts] = []
    if keys:
        changed = select(Change).where(
            tuple_(Change.event_key, Change.location, Change.occurrence).in_(keys)
        )
        changes = [_change(row) for row in (await tx.scalars(changed)).all()]
        named = select(Event).where(Event.event_key.in_({key for key, _, _ in keys}))
        events = [_event(row) for row in (await tx.scalars(named)).all()]
    return DigestInputs(
        watchlist=watchlist,
        events=tuple(events),
        changes=tuple(changes),
        labels=await act_labels(tx, ((event.corpus, event.act_key) for event in events)),
        items=tuple(await watchlist_items(tx, watchlist.watchlist_id)),
        date_alerts=frozenset(row.key for row in rows if row.date_alert),
    )
