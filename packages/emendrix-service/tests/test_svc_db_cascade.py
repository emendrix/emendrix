"""Deleting a person deletes their rows and nothing else; reloading the record touches no one."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from emendrix_service.db import Db, Tx
from emendrix_service.db.enums import (
    AuditAction,
    Cadence,
    ConsentKind,
    DeliveryKind,
    ItemKind,
    OutboxPurpose,
    SuppressionReason,
)
from emendrix_service.db.outbox import enqueue
from emendrix_service.db.tables import (
    Act,
    AuditLog,
    Base,
    Change,
    Consent,
    Delivery,
    Event,
    Match,
    Suppression,
    User,
    UserSession,
    WatchItem,
    Watchlist,
)
from emendrix_service.mail.message import OutgoingMail
from tests.conftest import NOW

pytestmark = pytest.mark.anyio

EVENT_KEY = "eu/32017R0745@20260101"

OWNED = (
    "app.users",
    "app.consents",
    "app.sessions",
    "app.watchlists",
    "app.watch_items",
    "app.matches",
    "app.deliveries",
    "app.outbox",
)
"""The tables whose rows belong to one person and go with them."""


async def counts(tx: Tx) -> dict[str, int]:
    found: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        found[table.fullname] = (await tx.execute(select(func.count()).select_from(table))).one()[0]
    return found


async def a_person(tx: Tx, email: str) -> uuid.UUID:
    """One user with a row in every table that belongs to them."""
    user = User(email=email, created_at=NOW, verified_at=NOW, last_signin_at=NOW, last_seen_at=NOW)
    tx.add(user)
    await tx.flush()
    tx.add(Consent(user_id=user.id, kind=ConsentKind.SERVICE_EMAIL, version="1", granted_at=NOW))
    tx.add(
        UserSession(
            id_hash=email.encode(),
            user_id=user.id,
            created_at=NOW,
            expires_at=NOW + timedelta(days=30),
            last_used_at=NOW,
        )
    )
    watchlist = Watchlist(
        user_id=user.id, name="Devices", cadence=Cadence.WEEKLY, date_alerts=True, created_at=NOW
    )
    tx.add(watchlist)
    await tx.flush()
    tx.add(
        WatchItem(
            watchlist_id=watchlist.id,
            kind=ItemKind.ACT,
            corpus="eu",
            act_key="32017R0745",
            created_at=NOW,
        )
    )
    mail = OutgoingMail(to=email, subject="Weekly", text="t", html="<p>h</p>")
    outbox_id = await enqueue(
        tx, purpose=OutboxPurpose.WEEKLY, to=email, mail=mail, user_id=user.id, now=NOW
    )
    delivery = Delivery(
        watchlist_id=watchlist.id,
        kind=DeliveryKind.WEEKLY,
        period_key="2026-W42",
        outbox_id=outbox_id,
        created_at=NOW,
    )
    tx.add(delivery)
    await tx.flush()
    tx.add(
        Match(
            watchlist_id=watchlist.id,
            event_key=EVENT_KEY,
            location="AR 6",
            occurrence=1,
            date_alert=False,
            matched_at=NOW,
            delivery_id=delivery.id,
        )
    )
    tx.add(
        Suppression(email_sha256=email.encode(), reason=SuppressionReason.COMPLAINT, created_at=NOW)
    )
    tx.add(AuditLog(user_id=user.id, action=AuditAction.EXPORT, at=NOW))
    await tx.flush()
    return user.id


def an_event() -> tuple[Event, Change]:
    event = Event(
        event_key=EVENT_KEY,
        corpus="eu",
        act_key="32017R0745",
        entry_key="20260101",
        from_version="20250101",
        to_version="20260101",
        detected_on=NOW.date(),
        in_force=[NOW.date()],
        updated_on=NOW.date(),
        path="eu/32017R0745/20260101.json",
        sha256="0" * 64,
    )
    change = Change(
        event_key=EVENT_KEY,
        location="AR 6",
        occurrence=1,
        unit="AR 6",
        change_type="modified",
        disputed=False,
        signals={},
        applies_from="unknown",
        dates_added=[],
        dates_removed=[],
        amending_acts=[],
        changed_within=[],
        outcome="explained",
        unexplained_kind="",
        unexplained="",
        sentences=[],
        anchor="change-ar-6",
    )
    return event, change


async def test_svc_deleting_a_user_removes_their_rows_and_keeps_the_logs(db: Db) -> None:
    async with db.transaction() as tx:
        gone = await a_person(tx, "leaving@example.org")
        await a_person(tx, "staying@example.org")
    async with db.transaction() as tx:
        await tx.execute(text("DELETE FROM app.users WHERE id = :id"), {"id": gone})
    async with db.transaction() as tx:
        after = await counts(tx)
    for name in OWNED:
        assert after[name] == 1, name
    assert after["app.suppressions"] == 2
    assert after["app.audit_log"] == 2


async def test_svc_emptying_content_leaves_every_app_row(db: Db) -> None:
    async with db.transaction() as tx:
        await a_person(tx, "reader@example.org")
        event, change = an_event()
        tx.add(
            Act(
                corpus="eu",
                act_key="32017R0745",
                label="MDR",
                long_name="",
                domain="",
                aliases=[],
                url="https://example.org/acts/32017R0745/",
                title="Medical Devices Regulation",
                waiting=[],
            )
        )
        tx.add(event)
        await tx.flush()
        tx.add(change)
    async with db.transaction() as tx:
        before = await counts(tx)
        content = [
            table.fullname for table in Base.metadata.sorted_tables if table.schema == "content"
        ]
        await tx.execute(text(f"TRUNCATE {', '.join(content)} RESTART IDENTITY CASCADE"))
    async with db.transaction() as tx:
        after = await counts(tx)
    assert before["content.changes"] == 1
    for name, count in after.items():
        expected = 0 if name.startswith("content.") else before[name]
        assert count == expected, name
    assert after["app.matches"] == 1
