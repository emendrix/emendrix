"""A substance item is matched in whatever act a moved table row carries its number.

The record copy is the one the load tests give a table-entry diff: `house-rules` v3, the event
published after going live, moves three rows of its Annex I. No substance item names that act.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from emendrix_service import DISCLAIMER
from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, ItemKind, OutboxPurpose
from emendrix_service.db.tables import Match, Outbox, Watchlist
from emendrix_service.db.watchlists import add_item
from emendrix_service.notify.digest_run import DigestCounts, digest
from emendrix_service.notify.run import NotifyCounts, notify
from tests.conftest import NOW
from tests.test_svc_load_tables import tabled_record
from tests.test_svc_notify_run import Item, add_watchlist, go_live, notify_settings

pytestmark = pytest.mark.anyio

ENTRY_7 = "you watch CAS 50-00-0; entry 7 in House Rules of Flat 3B Annex I was amended"
DUST = (
    "you watch CAS 7732-18-5; the entry for Dust of the shelves in House Rules of Flat 3B "
    "Annex I was added"
)


async def watch(
    db: Db,
    email: str,
    *identifiers: str,
    cadence: Cadence = Cadence.INSTANT,
    items: tuple[Item, ...] = (),
    act: str = "house-rules",
    created_at: datetime = NOW - timedelta(days=20),
) -> UUID:
    """A watchlist holding `items` on `act` and a substance item per identifier."""
    watchlist_id = await add_watchlist(
        db, email, cadence=cadence, items=items, act=act, created_at=created_at
    )
    async with db.transaction() as tx:
        user_id = (await tx.get_one(Watchlist, watchlist_id)).user_id
        for identifier in identifiers:
            added = await add_item(
                tx,
                user_id,
                watchlist_id,
                ItemKind.SUBSTANCE,
                None,
                None,
                None,
                created_at,
                identifier=identifier,
            )
            assert added is True
    return watchlist_id


async def matched(db: Db, watchlist_id: UUID) -> list[str]:
    async with db.transaction() as tx:
        query = select(Match.location).where(Match.watchlist_id == watchlist_id)
        return sorted((await tx.scalars(query)).all())


async def test_svc_notify_a_substance_item_gets_an_instant_email_beside_an_act_item(
    db: Db, tmp_path: Path
) -> None:
    record = tabled_record(tmp_path)
    both = await watch(db, "both@example.org", "cas:50-00-0", items=((ItemKind.PROVISION, "AR 2"),))
    typography = await watch(db, "typography@example.org", "cas:64-17-5")
    elsewhere = await watch(db, "elsewhere@example.org", "ec:200-001-8", act="garden-rules")
    await go_live(db, record)
    counts = await notify(db, notify_settings(record), NOW - timedelta(days=1))
    assert counts == NotifyCounts(announced=1, eligible=1, matches=3, deliveries=2)
    assert await matched(db, both) == ["AN I", "AR 2"]
    assert await matched(db, typography) == []
    assert await matched(db, elsewhere) == ["AN I"]
    async with db.transaction() as tx:
        outbox = {
            row.to_email: row
            for row in (await tx.scalars(select(Outbox))).all()
            if row.purpose == OutboxPurpose.INSTANT
        }
    assert set(outbox) == {"both@example.org", "elsewhere@example.org"}
    mail = outbox["both@example.org"]
    assert f"Why: {ENTRY_7}" in mail.text_body
    assert "Why: you watch House Rules of Flat 3B Article 2" in mail.text_body
    assert DISCLAIMER in mail.text_body and DISCLAIMER in mail.html_body
    assert (
        "you watch EC 200-001-8; entry 7 in House Rules of Flat 3B Annex I was amended"
        in outbox["elsewhere@example.org"].text_body
    )


async def test_svc_notify_a_substance_item_gets_a_digest_line_by_the_row_name(
    db: Db, tmp_path: Path
) -> None:
    record = tabled_record(tmp_path)
    await watch(db, "weekly@example.org", "cas:7732-18-5", cadence=Cadence.WEEKLY)
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW - timedelta(days=1))
    assert await digest(db, settings, NOW) == DigestCounts(weekly=1)
    async with db.transaction() as tx:
        mail = (await tx.scalars(select(Outbox))).one()
    assert f"Why: {DUST}" in mail.text_body
    assert "House Rules of Flat 3B" in mail.subject
    assert DISCLAIMER in mail.text_body and DISCLAIMER in mail.html_body


async def test_svc_notify_the_monthly_note_names_a_watched_number(db: Db, tmp_path: Path) -> None:
    record = tabled_record(tmp_path)
    september = datetime(2026, 9, 1, tzinfo=UTC)
    await watch(
        db, "quiet@example.org", "cas:64-17-5", cadence=Cadence.WEEKLY, created_at=september
    )
    await go_live(db, record)
    settings = notify_settings(record)
    await notify(db, settings, NOW - timedelta(days=1))
    november = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
    assert await digest(db, settings, november) == DigestCounts(heartbeat=1)
    async with db.transaction() as tx:
        note = (await tx.scalars(select(Outbox))).one()
    assert "CAS 64-17-5" in note.text_body
    assert DISCLAIMER in note.text_body
