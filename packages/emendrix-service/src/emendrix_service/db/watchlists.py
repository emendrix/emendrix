"""Watchlists and their items, and the catalogue reads the watch pages show beside them.

**Every read and write of a watchlist is scoped by the account that asks.** A watchlist or item
id belonging to another account reads as absent (`None`, `False`), never as forbidden, so a
page cannot be used to learn that an id exists. The `content` reads return what the loader
stored, unchanged: an act's waiting rows are read back with the catalogue's own model.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Exists, delete, exists, func, or_, select, tuple_, update

from emendrix_record.models import CatalogueWaiting
from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import Cadence, ItemKind, UserStatus
from emendrix_service.db.guards import insert_once
from emendrix_service.db.tables_app import User, WatchItem, Watchlist
from emendrix_service.db.tables_content import Act, Provision

__all__ = [
    "ActKey",
    "ActView",
    "ProvisionView",
    "WatchItemView",
    "WatchlistView",
    "act_by_key",
    "acts_by_key",
    "acts_roster",
    "add_item",
    "content_loaded",
    "create_watchlist",
    "delete_watchlist",
    "provisions_by_act",
    "provisions_of",
    "remove_item",
    "update_watchlist",
    "user_status",
    "watchlist_of",
    "watchlists_for",
]

ActKey = tuple[str, str]

_FROZEN = ConfigDict(frozen=True)


class WatchItemView(BaseModel):
    """One item of a watchlist."""

    model_config = _FROZEN

    id: UUID = Field(description="The item's id.")
    kind: ItemKind = Field(description="A whole act or one provision of it.")
    corpus: str = Field(description="The act's corpus.")
    act_key: str = Field(description="The act's key.")
    location: str | None = Field(description="The canonical location; None for the whole act.")


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


def _act(row: Act) -> ActView:
    return ActView(
        corpus=row.corpus,
        act_key=row.act_key,
        label=row.label,
        long_name=row.long_name,
        aliases=tuple(row.aliases),
        url=row.url,
        checked_through=row.checked_through,
        waiting=tuple(CatalogueWaiting.model_validate(entry) for entry in row.waiting),
    )


def _owned(user_id: UUID, watchlist_id: UUID) -> Exists:
    return exists().where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)


async def watchlists_for(tx: Tx, user_id: UUID) -> list[WatchlistView]:
    """Every watchlist of the account, oldest first, each with its items."""
    lists = (
        await tx.scalars(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.created_at, Watchlist.id)
        )
    ).all()
    ids = [row.id for row in lists]
    items: dict[UUID, list[WatchItemView]] = {wid: [] for wid in ids}
    if ids:
        rows = await tx.scalars(
            select(WatchItem)
            .where(WatchItem.watchlist_id.in_(ids))
            .order_by(WatchItem.created_at, WatchItem.id)
        )
        for item in rows:
            items[item.watchlist_id].append(
                WatchItemView(
                    id=item.id,
                    kind=item.kind,
                    corpus=item.corpus,
                    act_key=item.act_key,
                    location=item.location,
                )
            )
    return [
        WatchlistView(
            id=row.id,
            name=row.name,
            cadence=row.cadence,
            date_alerts=row.date_alerts,
            heartbeat=row.heartbeat,
            paused=row.paused,
            has_feed=row.feed_token_hash is not None,
            items=tuple(items[row.id]),
        )
        for row in lists
    ]


async def watchlist_of(tx: Tx, user_id: UUID, watchlist_id: UUID) -> WatchlistView | None:
    """One watchlist of the account; None when the id is not one of its own."""
    return next((wl for wl in await watchlists_for(tx, user_id) if wl.id == watchlist_id), None)


async def create_watchlist(tx: Tx, user_id: UUID, name: str, now: datetime) -> UUID:
    """A new watchlist with the defaults a first one has: weekly, date alerts and monthly note."""
    row = Watchlist(
        user_id=user_id,
        name=name,
        cadence=Cadence.WEEKLY,
        date_alerts=True,
        heartbeat=True,
        paused=False,
        created_at=now,
    )
    tx.add(row)
    await tx.flush()
    return row.id


async def update_watchlist(
    tx: Tx,
    user_id: UUID,
    watchlist_id: UUID,
    *,
    name: str,
    cadence: Cadence,
    date_alerts: bool,
    heartbeat: bool,
    paused: bool,
) -> UUID | None:
    """Change a watchlist's settings; None when the id is not one of the account's own."""
    changed = await tx.scalar(
        update(Watchlist)
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
        .values(
            name=name, cadence=cadence, date_alerts=date_alerts, heartbeat=heartbeat, paused=paused
        )
        .returning(Watchlist.id)
    )
    return changed


async def delete_watchlist(tx: Tx, user_id: UUID, watchlist_id: UUID) -> bool:
    """Remove a watchlist and, by cascade, its items; False when it is not the account's."""
    gone = await tx.scalar(
        delete(Watchlist)
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
        .returning(Watchlist.id)
    )
    return gone is not None


async def add_item(
    tx: Tx,
    user_id: UUID,
    watchlist_id: UUID,
    kind: ItemKind,
    corpus: str,
    act_key: str,
    location: str | None,
    now: datetime,
) -> bool | None:
    """Add one item; False when the watchlist holds it already, None when it is not theirs."""
    if not await tx.scalar(select(_owned(user_id, watchlist_id))):
        return None
    return await insert_once(
        tx,
        WatchItem(
            watchlist_id=watchlist_id,
            kind=kind,
            corpus=corpus,
            act_key=act_key,
            location=location,
            created_at=now,
        ),
    )


async def remove_item(tx: Tx, user_id: UUID, watchlist_id: UUID, item_id: UUID) -> bool:
    """Remove one item; False when it is not an item of one of the account's watchlists."""
    gone = await tx.scalar(
        delete(WatchItem)
        .where(
            WatchItem.id == item_id,
            WatchItem.watchlist_id == watchlist_id,
            _owned(user_id, watchlist_id),
        )
        .returning(WatchItem.id)
    )
    return gone is not None


async def content_loaded(tx: Tx) -> bool:
    """Whether the record has been loaded at all: a fresh deployment holds no act."""
    return bool(await tx.scalar(select(exists(select(Act.act_key)))))


async def acts_roster(tx: Tx) -> list[ActView]:
    """Every act the catalogue lists, by label."""
    rows = await tx.scalars(select(Act).order_by(Act.label, Act.corpus, Act.act_key))
    return [_act(row) for row in rows]


async def acts_by_key(tx: Tx, keys: Iterable[ActKey]) -> dict[ActKey, ActView]:
    """The stored acts among `keys`; an act the catalogue does not list is absent."""
    wanted = sorted(set(keys))
    if not wanted:
        return {}
    rows = await tx.scalars(select(Act).where(tuple_(Act.corpus, Act.act_key).in_(wanted)))
    return {(row.corpus, row.act_key): _act(row) for row in rows}


async def act_by_key(tx: Tx, act_key: str) -> ActView | None:
    """The act named by its key or by `corpus/key`; None when absent or the key is ambiguous."""
    rows = (
        await tx.scalars(
            select(Act).where(
                or_(Act.act_key == act_key, func.concat(Act.corpus, "/", Act.act_key) == act_key)
            )
        )
    ).all()
    return _act(rows[0]) if len(rows) == 1 else None


async def provisions_by_act(tx: Tx, keys: Iterable[ActKey]) -> dict[ActKey, list[ProvisionView]]:
    """The stored units of each act in `keys`, an act with none mapping to an empty list."""
    wanted = sorted(set(keys))
    found: dict[ActKey, list[ProvisionView]] = {key: [] for key in wanted}
    if not wanted:
        return found
    rows = await tx.scalars(
        select(Provision)
        .where(tuple_(Provision.corpus, Provision.act_key).in_(wanted))
        .order_by(Provision.unit)
    )
    for row in rows:
        found[(row.corpus, row.act_key)].append(
            ProvisionView(unit=row.unit, heading=row.heading, changes=row.changes)
        )
    return found


async def provisions_of(tx: Tx, corpus: str, act_key: str) -> list[ProvisionView]:
    """The stored units of one act, in text order; `watch.logic` puts them in canonical order."""
    return (await provisions_by_act(tx, [(corpus, act_key)]))[(corpus, act_key)]


async def user_status(tx: Tx, user_id: UUID) -> UserStatus | None:
    """Whether the account may be mailed; None when it does not exist."""
    status: UserStatus | None = await tx.scalar(select(User.status).where(User.id == user_id))
    return status
