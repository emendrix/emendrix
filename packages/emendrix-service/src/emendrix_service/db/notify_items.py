"""What matching reads: the watch items an event is matched against, and the stored changes
with the table hits a substance item is matched on.

Kept apart from `notify.py`, which writes the notifier's ledger and composes from these reads.
An act or provision item is read for one act; a substance item for the numbers one event's
table hits carry, because a number can appear in a table of any act.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import select, tuple_

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import Cadence, ItemKind, UserStatus
from emendrix_service.db.tables import Change, TableHit, User, WatchItem, Watchlist
from emendrix_service.notify.facts import ChangeFacts, ItemFacts, RowHit

__all__ = [
    "MAILED",
    "active_items_for_act",
    "active_substance_items",
    "acts_named",
    "event_changes",
    "item_facts",
    "table_hits",
    "watchlist_items",
    "with_hits",
]

MAILED: Final = (Watchlist.paused.is_(False), User.status == UserStatus.ACTIVE)
"""A watchlist that may receive email: not paused, and its owner not suspended."""

_HIT_ORDER: Final = (
    TableHit.event_key,
    TableHit.location,
    TableHit.occurrence,
    TableHit.container,
    TableHit.table_ordinal,
    TableHit.row_key,
    TableHit.row_occurrence,
    TableHit.side,
    TableHit.identifier,
)
"""The table hits' primary key: table, then row key, then side, then number."""

ChangeKey = tuple[str, str, int]


def item_facts(item: WatchItem, watchlist: Watchlist) -> ItemFacts:
    """One stored item with what matching and delivery need of its watchlist."""
    substance = item.kind == ItemKind.SUBSTANCE
    return ItemFacts(
        item_id=item.id,
        watchlist_id=item.watchlist_id,
        kind=item.kind,
        corpus=None if substance else item.corpus,
        act_key=None if substance else item.act_key,
        location=item.location,
        identifier=item.identifier,
        cadence=watchlist.cadence,
        date_alerts=watchlist.date_alerts,
    )


def acts_named(items: Iterable[ItemFacts]) -> set[tuple[str, str]]:
    """The `(corpus, act_key)` of every item that names an act; a substance item names none."""
    return {
        (item.corpus, item.act_key)
        for item in items
        if item.corpus is not None and item.act_key is not None
    }


def _hit(row: TableHit) -> RowHit:
    return RowHit.model_validate(row, from_attributes=True)


async def table_hits(tx: Tx, keys: Iterable[ChangeKey]) -> dict[ChangeKey, tuple[RowHit, ...]]:
    """The table hits of the changes `(event_key, location, occurrence)` names, each in key
    order; a change with none is absent."""
    wanted = sorted(set(keys))
    found: dict[ChangeKey, list[RowHit]] = defaultdict(list)
    if wanted:
        changed = tuple_(TableHit.event_key, TableHit.location, TableHit.occurrence)
        query = select(TableHit).where(changed.in_(wanted)).order_by(*_HIT_ORDER)
        for row in (await tx.scalars(query)).all():
            found[(row.event_key, row.location, row.occurrence)].append(_hit(row))
    return {key: tuple(hits) for key, hits in found.items()}


async def with_hits(tx: Tx, changes: Sequence[Change]) -> list[ChangeFacts]:
    """The stored changes as facts, each carrying its table hits."""
    keys = [(row.event_key, row.location, row.occurrence) for row in changes]
    found = await table_hits(tx, keys)
    # The stored sentences are JSON objects, validated into `StoredSentence` values here.
    return [
        ChangeFacts.model_validate(row, from_attributes=True).model_copy(
            update={"table_hits": found.get(key, ())}
        )
        for row, key in zip(changes, keys, strict=True)
    ]


async def event_changes(tx: Tx, event_key: str) -> list[ChangeFacts]:
    """The stored changes of one event, with their table hits."""
    query = select(Change).where(Change.event_key == event_key)
    return await with_hits(tx, (await tx.scalars(query)).all())


async def active_items_for_act(tx: Tx, corpus: str, act_key: str) -> list[ItemFacts]:
    """Every item on the act of a watchlist that is mailed: not paused, not `none`, not
    suspended."""
    query = (
        select(WatchItem, Watchlist)
        .join(Watchlist, Watchlist.id == WatchItem.watchlist_id)
        .join(User, User.id == Watchlist.user_id)
        .where(WatchItem.corpus == corpus, WatchItem.act_key == act_key)
        .where(Watchlist.cadence != Cadence.NONE, *MAILED)
        .order_by(WatchItem.watchlist_id, WatchItem.id)
    )
    return [item_facts(item, watchlist) for item, watchlist in (await tx.execute(query)).all()]


async def active_substance_items(tx: Tx, event_key: str) -> list[ItemFacts]:
    """Every substance item of a mailed watchlist whose number a table hit of the event carries.

    Narrowed by the hits rather than by act, so a number is matched in every act it appears in.
    """
    carried = select(TableHit.identifier).where(TableHit.event_key == event_key)
    query = (
        select(WatchItem, Watchlist)
        .join(Watchlist, Watchlist.id == WatchItem.watchlist_id)
        .join(User, User.id == Watchlist.user_id)
        .where(WatchItem.kind == ItemKind.SUBSTANCE, WatchItem.identifier.in_(carried))
        .where(Watchlist.cadence != Cadence.NONE, *MAILED)
        .order_by(WatchItem.watchlist_id, WatchItem.id)
    )
    return [item_facts(item, watchlist) for item, watchlist in (await tx.execute(query)).all()]


async def watchlist_items(tx: Tx, watchlist_id: UUID) -> list[ItemFacts]:
    """Every item of one watchlist, as it stands now: acts first, then numbers."""
    query = (
        select(WatchItem, Watchlist)
        .join(Watchlist, Watchlist.id == WatchItem.watchlist_id)
        .where(WatchItem.watchlist_id == watchlist_id)
        .order_by(
            WatchItem.corpus,
            WatchItem.act_key,
            WatchItem.location,
            WatchItem.identifier,
            WatchItem.id,
        )
    )
    return [item_facts(item, watchlist) for item, watchlist in (await tx.execute(query)).all()]
