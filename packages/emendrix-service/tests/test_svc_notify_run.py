"""`notify` judges each event once and writes what it owes; history and repairs never alert.

Each test loads a copy of the record fixture. Going live is played out the way it happens: the
record holds two events when the notifier first runs, which it records as history, and then
the poller publishes a third, detected after `LIVE_SINCE`.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import ColumnElement, func, select

from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, ItemKind, OutboxPurpose, UserStatus
from emendrix_service.db.tables import Announced, Base, Delivery, Match, Outbox, User, WatchItem
from emendrix_service.db.tables import Watchlist as WatchlistRow
from emendrix_service.load.cli import load_once
from emendrix_service.notify.run import NotifyCounts, notify
from emendrix_service.settings import ServiceSettings
from tests.conftest import NOW, settings_values
from tests.test_svc_load_run import (
    CountingRecord,
    Json,
    copy_record,
    edit_act_index,
    edit_payload,
    read_json,
    retitle,
)

pytestmark = pytest.mark.anyio

LIVE = date(2026, 10, 1)
NEW = "toy/house-rules@v3"
"""The event the poller publishes after going live."""

Item = tuple[ItemKind, str | None]
WHOLE_ACT: tuple[Item, ...] = ((ItemKind.ACT, None),)


def notify_settings(record: CountingRecord, **extra: object) -> ServiceSettings:
    return ServiceSettings.model_validate(
        {
            **settings_values(),
            "changelogs": record.changelogs,
            "catalogue": record.catalogue_path,
            "live_since": LIVE,
            "smtp_host": "relay.example.org",
            "mail_from": "Emendrix alerts <alerts@example.org>",
            **extra,
        }
    )


async def add_watchlist(
    db: Db,
    email: str,
    *,
    cadence: Cadence = Cadence.WEEKLY,
    items: tuple[Item, ...] = WHOLE_ACT,
    act: str = "house-rules",
    paused: bool = False,
    status: UserStatus = UserStatus.ACTIVE,
    heartbeat: bool = True,
    created_at: datetime = NOW - timedelta(days=20),
) -> UUID:
    """A user with one watchlist holding `items` on `act`; the watchlist's id."""
    async with db.transaction() as tx:
        user = User(
            email=email,
            status=status,
            created_at=created_at,
            verified_at=created_at,
            last_signin_at=created_at,
            last_seen_at=created_at,
        )
        tx.add(user)
        await tx.flush()
        watchlist = WatchlistRow(
            user_id=user.id,
            name=f"{cadence.value} list",
            cadence=cadence,
            date_alerts=True,
            heartbeat=heartbeat,
            paused=paused,
            created_at=created_at,
        )
        tx.add(watchlist)
        await tx.flush()
        for kind, location in items:
            tx.add(
                WatchItem(
                    watchlist_id=watchlist.id,
                    kind=kind,
                    corpus="toy",
                    act_key=act,
                    location=location,
                    created_at=created_at,
                )
            )
        return watchlist.id


def without_v3(index: Json) -> None:
    events = index["events"]
    provisions = index["provisions"]
    assert isinstance(events, list) and isinstance(provisions, dict)
    index["events"] = [event for event in events if event["to_version"] != "v3"]
    for unit in list(provisions):
        provisions[unit] = [row for row in provisions[unit] if row["version"] != "v3"]
        if not provisions[unit]:
            del provisions[unit]


async def go_live(
    db: Db, record: CountingRecord, *, detected_on: date = date(2026, 10, 10)
) -> None:
    """Load and notify with v3 unpublished, then publish v3 as detected on `detected_on`."""
    settings = notify_settings(record)
    original = read_json(record.changelogs / "toy" / "house-rules" / "index.json")
    edit_act_index(record.changelogs, "house-rules", without_v3)
    await load_once(settings, db, FixedClock(NOW - timedelta(days=5)))
    first = await notify(db, settings, NOW - timedelta(days=5))
    assert first == NotifyCounts(announced=2)

    def publish(index: Json) -> None:
        index.clear()
        index.update(copy.deepcopy(original))
        events = index["events"]
        assert isinstance(events, list)
        for event in events:
            if event["to_version"] == "v3":
                event["detected_on"] = detected_on.isoformat()

    edit_act_index(record.changelogs, "house-rules", publish)
    await load_once(settings, db, FixedClock(NOW - timedelta(days=1)))


async def count(db: Db, table: type[Base], *where: ColumnElement[bool]) -> int:
    async with db.transaction() as tx:
        query = select(func.count()).select_from(table).where(*where)
        return int(await tx.scalar(query) or 0)


async def test_svc_notify_the_first_run_records_everything_as_history(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    settings = notify_settings(record)
    await add_watchlist(db, "instant@example.org", cadence=Cadence.INSTANT)
    await load_once(settings, db, FixedClock(NOW))
    assert await notify(db, settings, NOW) == NotifyCounts(announced=3)
    async with db.transaction() as tx:
        rows = (await tx.execute(select(Announced.eligible, Announced.reason))).all()
    assert sorted(rows) == [(False, "bootstrap")] * 3
    assert await count(db, Match) == 0
    assert await count(db, Outbox) == 0
    assert await notify(db, settings, NOW) == NotifyCounts()


async def test_svc_notify_a_new_event_alerts_instant_watchers_once(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    instant = await add_watchlist(db, "instant@example.org", cadence=Cadence.INSTANT)
    weekly = await add_watchlist(
        db, "weekly@example.org", items=((ItemKind.PROVISION, "AR 2 PA 1"),)
    )
    await go_live(db, record)
    counts = await notify(db, notify_settings(record), NOW - timedelta(days=1))
    assert counts == NotifyCounts(announced=1, eligible=1, matches=6, deliveries=1)
    async with db.transaction() as tx:
        judged = await tx.get_one(Announced, NEW)
        outbox = (await tx.scalars(select(Outbox))).all()
        weekly_matches = (await tx.scalars(select(Match).where(Match.watchlist_id == weekly))).all()
        delivery = (await tx.scalars(select(Delivery))).one()
    assert (judged.eligible, judged.reason) == (True, "fresh")
    assert [(row.purpose, row.to_email) for row in outbox] == [
        (OutboxPurpose.INSTANT, "instant@example.org")
    ]
    assert outbox[0].subject == "[Emendrix] House Rules of Flat 3B: 5 watched provisions changed"
    assert (delivery.watchlist_id, delivery.period_key, delivery.outbox_id) == (
        instant,
        NEW,
        outbox[0].id,
    )
    assert [(m.location, m.delivery_id) for m in weekly_matches] == [("AR 2", None)]
    assert await count(db, Match, Match.delivery_id == delivery.id) == 5
    # The record's provision text never reaches an email.
    assert "Tuesday" not in outbox[0].text_body + outbox[0].html_body
    assert "you watch House Rules of Flat 3B" in outbox[0].text_body


async def test_svc_notify_a_repaired_event_is_never_announced_again(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "instant@example.org", cadence=Cadence.INSTANT)
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW - timedelta(days=1))
    edit_payload(record.changelogs, "house-rules", "v3", retitle("Bins and recycling"))
    assert (await load_once(settings, db, FixedClock(NOW))).upserted == 1
    assert await notify(db, settings, NOW) == NotifyCounts()
    assert (await count(db, Announced), await count(db, Match), await count(db, Outbox)) == (
        3,
        5,
        1,
    )


async def test_svc_notify_paused_none_and_suspended_get_nothing(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "paused@example.org", cadence=Cadence.INSTANT, paused=True)
    await add_watchlist(db, "feedonly@example.org", cadence=Cadence.NONE)
    await add_watchlist(
        db, "bounced@example.org", cadence=Cadence.INSTANT, status=UserStatus.SUSPENDED
    )
    await add_watchlist(db, "other@example.org", act="garden-rules")
    await go_live(db, record)
    counts = await notify(db, notify_settings(record), NOW)
    assert counts == NotifyCounts(announced=1, eligible=1)
    assert await count(db, Match) == 0


async def test_svc_notify_history_and_backfills_never_alert(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "instant@example.org", cadence=Cadence.INSTANT)
    await go_live(db, record, detected_on=date(2026, 9, 30))
    assert await notify(db, notify_settings(record), NOW) == NotifyCounts(announced=1)
    async with db.transaction() as tx:
        assert (await tx.get_one(Announced, NEW)).reason == "before_live"
    assert await count(db, Match) == 0


async def test_svc_notify_an_event_without_its_page_waits_for_one(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "instant@example.org", cadence=Cadence.INSTANT)
    catalogue = read_json(record.catalogue_path)
    acts = catalogue["acts"]
    assert isinstance(acts, list)
    events = acts[1]["events"]
    page = events.pop("v3")
    record.catalogue_path.write_text(json_text(catalogue), encoding="utf-8")
    await go_live(db, record)
    settings = notify_settings(record)
    assert await notify(db, settings, NOW) == NotifyCounts(deferred=1)
    assert await count(db, Announced) == 2
    events["v3"] = page
    record.catalogue_path.write_text(json_text(catalogue), encoding="utf-8")
    await load_once(settings, db, FixedClock(NOW))
    counts = await notify(db, settings, NOW)
    assert (counts.announced, counts.eligible, counts.deliveries) == (1, 1, 1)


def json_text(value: object) -> str:
    return json.dumps(value, indent=2) + "\n"
