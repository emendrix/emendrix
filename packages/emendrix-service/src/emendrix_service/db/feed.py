"""The personal feed's queries: its token, the watchlist behind it, and recent changes.

A feed token is stored only as its sha256 in `watchlists.feed_token_hash`, which is unique, so a
hash names at most one watchlist; replacing it is one `UPDATE`, after which the old token names
nothing. The changes are read newest event first by the date the event took effect (the latest
of its in-force dates, else the day it was detected), the order a feed reader expects and the
date the public feeds stamp an entry with.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, tuple_, update

from emendrix_service.db.engine import Tx
from emendrix_service.db.tables import Act, Change, Event, User, Watchlist
from emendrix_service.feed.logic import event_dated
from emendrix_service.feed.model import FeedChange
from emendrix_service.notify.facts import ChangeFacts, EventFacts

__all__ = [
    "FeedWatchlist",
    "recent_changes_for_acts",
    "set_feed_token",
    "touch_seen",
    "watchlist_by_feed_hash",
]

EVENTS_PER_READ: Final = 50
"""Events whose changes are read in one statement, newest first, until the limit is reached."""

_DAY = timedelta(days=1)


class FeedWatchlist(BaseModel):
    """The watchlist a feed token names."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="The watchlist's id, which also names its feed.")
    user_id: UUID = Field(description="Its owner.")
    name: str = Field(description="Its name.")
    created_at: datetime = Field(description="When it was made.")


async def set_feed_token(tx: Tx, user_id: UUID, watchlist_id: UUID, token_hash: bytes) -> bool:
    """Give the account's watchlist a new feed token; False when the watchlist is not theirs."""
    changed = await tx.scalar(
        update(Watchlist)
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
        .values(feed_token_hash=token_hash)
        .returning(Watchlist.id)
    )
    return changed is not None


async def watchlist_by_feed_hash(tx: Tx, token_hash: bytes) -> FeedWatchlist | None:
    """The watchlist whose current feed token has this hash; None for any other hash."""
    row = await tx.scalar(select(Watchlist).where(Watchlist.feed_token_hash == token_hash))
    if row is None:
        return None
    return FeedWatchlist(id=row.id, user_id=row.user_id, name=row.name, created_at=row.created_at)


async def touch_seen(tx: Tx, user_id: UUID, now: datetime) -> bool:
    """Move the account's `last_seen_at` to `now`, at most once a day; whether it moved."""
    moved = await tx.scalar(
        update(User)
        .where(User.id == user_id, User.last_seen_at < now - _DAY)
        .values(last_seen_at=now)
        .returning(User.id)
    )
    return moved is not None


async def recent_changes_for_acts(
    tx: Tx, acts: Iterable[tuple[str, str]], limit: int = 500
) -> list[FeedChange]:
    """Up to `limit` changes of `acts`, newest event first; an event with no page is left out.

    Ties are broken by detection date and then event key, both newest first, so the order is
    the same on every read of the same rows.
    """
    wanted = sorted(set(acts))
    if not wanted:
        return []
    rows = await tx.scalars(
        select(Event).where(tuple_(Event.corpus, Event.act_key).in_(wanted), Event.url.is_not(None))
    )
    events = sorted(
        (EventFacts.model_validate(row, from_attributes=True) for row in rows),
        key=lambda e: (event_dated(e), e.detected_on, e.event_key),
        reverse=True,
    )
    labels = {
        (corpus, key): label
        for corpus, key, label in await tx.execute(
            select(Act.corpus, Act.act_key, Act.label).where(
                tuple_(Act.corpus, Act.act_key).in_(wanted)
            )
        )
    }
    found: list[FeedChange] = []
    for start in range(0, len(events), EVENTS_PER_READ):
        batch = {event.event_key: event for event in events[start : start + EVENTS_PER_READ]}
        changes = await tx.scalars(select(Change).where(Change.event_key.in_(batch)))
        by_event: dict[str, list[ChangeFacts]] = {key: [] for key in batch}
        for row in changes:
            by_event[row.event_key].append(ChangeFacts.model_validate(row, from_attributes=True))
        for key, event in batch.items():
            label = labels.get((event.corpus, event.act_key), event.act_key)
            for change in sorted(by_event[key], key=lambda c: (c.location, c.occurrence)):
                found.append(FeedChange(change=change, event=event, act_label=label))
                if len(found) >= limit:
                    return found
    return found
