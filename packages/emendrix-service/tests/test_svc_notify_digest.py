"""`digest` mails each due watchlist its owed matches once, and the monthly note when quiet."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from emendrix_service import DISCLAIMER
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, DeliveryKind, ItemKind, OutboxPurpose
from emendrix_service.db.tables import Delivery, Match, Outbox, Watchlist
from emendrix_service.load.cli import load_once
from emendrix_service.notify.digest_run import DigestCounts, digest
from emendrix_service.notify.run import notify
from tests.conftest import NOW
from tests.test_svc_load_run import copy_record, edit_act_index
from tests.test_svc_notify_run import (
    add_watchlist,
    count,
    go_live,
    notify_settings,
    without_v3,
)

pytestmark = pytest.mark.anyio

NOVEMBER = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
"""The first Monday of November, 07:00 in Brussels after the clocks went back."""


async def test_svc_notify_the_weekly_digest_sends_once_on_monday(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    weekly = await add_watchlist(
        db, "weekly@example.org", items=((ItemKind.PROVISION, "AR 2"), (ItemKind.ACT, None))
    )
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW - timedelta(days=1))
    assert await digest(db, settings, NOW - timedelta(minutes=1)) == DigestCounts()
    assert await digest(db, settings, NOW) == DigestCounts(weekly=1)
    async with db.transaction() as tx:
        delivery = (await tx.scalars(select(Delivery))).one()
        outbox = (await tx.scalars(select(Outbox))).one()
    assert (delivery.watchlist_id, delivery.kind, delivery.period_key) == (
        weekly,
        DeliveryKind.WEEKLY,
        "2026-W42",
    )
    assert (outbox.purpose, outbox.to_email, delivery.outbox_id) == (
        OutboxPurpose.WEEKLY,
        "weekly@example.org",
        outbox.id,
    )
    assert outbox.subject == "[Emendrix] House Rules of Flat 3B: 5 watched provisions changed"
    assert DISCLAIMER in outbox.text_body and DISCLAIMER in outbox.html_body
    assert "Why: you watch House Rules of Flat 3B Article 2" in outbox.text_body
    assert await count(db, Match, Match.delivery_id == delivery.id) == 5
    assert await digest(db, settings, NOW) == DigestCounts()
    assert await digest(db, settings, NOW + timedelta(days=2)) == DigestCounts()
    assert await count(db, Outbox) == 1


async def test_svc_notify_a_match_after_the_boundary_waits_for_the_next_period(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "weekly@example.org")
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW + timedelta(hours=1))
    assert await digest(db, settings, NOW + timedelta(hours=2)) == DigestCounts()
    assert await count(db, Delivery) == 0
    assert await digest(db, settings, NOW + timedelta(days=7)) == DigestCounts(weekly=1)


async def test_svc_notify_a_day_with_nothing_owed_leaves_no_delivery(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "daily@example.org", cadence=Cadence.DAILY)
    await go_live(db, record)
    settings = notify_settings(record)
    assert await digest(db, settings, NOW) == DigestCounts()
    assert await count(db, Delivery) == 0
    await notify(db, settings, NOW + timedelta(hours=1))
    tomorrow = NOW + timedelta(days=1)
    assert await digest(db, settings, tomorrow) == DigestCounts(daily=1)
    async with db.transaction() as tx:
        delivery = (await tx.scalars(select(Delivery))).one()
    assert (delivery.kind, delivery.period_key) == (DeliveryKind.DAILY, "2026-10-13")


async def test_svc_notify_a_paused_watchlist_digest_waits(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    paused = await add_watchlist(db, "weekly@example.org")
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW - timedelta(days=1))
    async with db.transaction() as tx:
        (await tx.get_one(Watchlist, paused)).paused = True
    assert await digest(db, settings, NOW) == DigestCounts()
    assert await count(db, Delivery) == 0


async def test_svc_notify_the_monthly_note_only_after_a_quiet_month(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    settings = notify_settings(record)
    september = datetime(2026, 9, 1, tzinfo=UTC)
    quiet = await add_watchlist(db, "quiet@example.org", act="garden-rules", created_at=september)
    await add_watchlist(db, "busy@example.org", created_at=september)
    await add_watchlist(
        db, "off@example.org", act="garden-rules", created_at=september, heartbeat=False
    )
    late = datetime(2026, 10, 20, tzinfo=UTC)
    await add_watchlist(db, "new@example.org", act="garden-rules", created_at=late)
    await go_live(db, record)
    await notify(db, settings, NOW - timedelta(days=1))
    assert await digest(db, settings, NOW) == DigestCounts(weekly=1)
    assert await digest(db, settings, NOVEMBER - timedelta(minutes=1)) == DigestCounts()
    assert await digest(db, settings, NOVEMBER) == DigestCounts(heartbeat=1)
    async with db.transaction() as tx:
        note = (
            await tx.scalars(select(Outbox).where(Outbox.purpose == OutboxPurpose.HEARTBEAT))
        ).one()
        delivery = (
            await tx.scalars(select(Delivery).where(Delivery.kind == DeliveryKind.HEARTBEAT))
        ).one()
    assert note.to_email == "quiet@example.org"
    assert note.subject == "[Emendrix] Still watching: nothing changed in October"
    assert "Garden Rules of Flat 3B" in note.text_body
    assert (delivery.watchlist_id, delivery.period_key) == (quiet, "2026-11")
    assert DISCLAIMER in note.text_body and DISCLAIMER in note.html_body
    assert await digest(db, settings, NOVEMBER + timedelta(hours=1)) == DigestCounts()
    assert await digest(db, settings, NOVEMBER + timedelta(days=1)) == DigestCounts()


async def test_svc_notify_a_change_the_record_dropped_sends_no_empty_digest(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "weekly@example.org")
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW - timedelta(days=1))
    edit_act_index(record.changelogs, "house-rules", without_v3)
    assert (await load_once(settings, db, FixedClock(NOW))).removed == 1
    assert await digest(db, settings, NOW) == DigestCounts()
    assert (await count(db, Delivery), await count(db, Outbox)) == (0, 0)
