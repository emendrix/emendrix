"""Exactly-once keys refuse a second copy, and the refusal comes back as a value."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from emendrix_service.db import Db, Tx, insert_once
from emendrix_service.db.enums import Cadence, DeliveryKind, ItemKind
from emendrix_service.db.tables import Delivery, User, WatchItem, Watchlist
from tests.conftest import NOW

pytestmark = pytest.mark.anyio


async def a_watchlist(tx: Tx) -> uuid.UUID:
    user = User(
        email="guard@example.org",
        created_at=NOW,
        verified_at=NOW,
        last_signin_at=NOW,
        last_seen_at=NOW,
    )
    tx.add(user)
    await tx.flush()
    watchlist = Watchlist(
        user_id=user.id, name="Devices", cadence=Cadence.DAILY, date_alerts=False, created_at=NOW
    )
    tx.add(watchlist)
    await tx.flush()
    return watchlist.id


def delivery(watchlist_id: uuid.UUID) -> Delivery:
    return Delivery(
        watchlist_id=watchlist_id, kind=DeliveryKind.DAILY, period_key="2026-10-12", created_at=NOW
    )


def act_item(watchlist_id: uuid.UUID) -> WatchItem:
    return WatchItem(
        watchlist_id=watchlist_id,
        kind=ItemKind.ACT,
        corpus="eu",
        act_key="32017R0745",
        location=None,
        created_at=NOW,
    )


async def test_svc_a_second_delivery_for_one_period_is_refused_as_a_value(db: Db) -> None:
    async with db.transaction() as tx:
        watchlist_id = await a_watchlist(tx)
        assert await insert_once(tx, delivery(watchlist_id)) is True
        assert await insert_once(tx, delivery(watchlist_id)) is False
        # The refusal rolled back only its own savepoint: the transaction carries on.
        later = Delivery(
            watchlist_id=watchlist_id,
            kind=DeliveryKind.DAILY,
            period_key="2026-10-13",
            created_at=NOW,
        )
        assert await insert_once(tx, later) is True
    async with db.transaction() as tx:
        assert (await tx.execute(select(func.count()).select_from(Delivery))).scalar_one() == 2


async def test_svc_the_key_itself_raises_without_the_helper(db: Db) -> None:
    async with db.transaction() as tx:
        watchlist_id = await a_watchlist(tx)
        tx.add(delivery(watchlist_id))
    with pytest.raises(IntegrityError):
        async with db.transaction() as tx:
            tx.add(delivery(watchlist_id))


async def test_svc_a_duplicate_act_item_with_no_location_is_refused(db: Db) -> None:
    async with db.transaction() as tx:
        watchlist_id = await a_watchlist(tx)
        assert await insert_once(tx, act_item(watchlist_id)) is True
        assert await insert_once(tx, act_item(watchlist_id)) is False


async def test_svc_an_insert_refused_for_another_reason_still_raises(db: Db) -> None:
    with pytest.raises(IntegrityError):
        async with db.transaction() as tx:
            await insert_once(tx, delivery(uuid.uuid4()))
