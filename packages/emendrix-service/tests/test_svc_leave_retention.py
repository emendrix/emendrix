"""`retention`: every row of the table, either side of its threshold, and the inactivity cycle."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from emendrix_service import DISCLAIMER
from emendrix_service.cli import app
from emendrix_service.db import Db, Tx
from emendrix_service.db.accounts import mark_signed_in
from emendrix_service.db.enums import (
    AuditAction,
    Cadence,
    DeliveryKind,
    MailEventKind,
    OutboxPurpose,
    OutboxStatus,
    TokenPurpose,
)
from emendrix_service.db.outbox import enqueue
from emendrix_service.db.tables import (
    AuditLog,
    Delivery,
    LoginToken,
    MailEvent,
    Match,
    Outbox,
    User,
    UserSession,
    Watchlist,
)
from emendrix_service.leave.logic import RETENTION, inactivity_due
from emendrix_service.leave.retention import INACTIVITY_SUBJECT, RetentionCounts, retain
from emendrix_service.mail.message import OutgoingMail
from emendrix_service.settings import ServiceSettings
from tests.conftest import NOW
from tests.test_svc_load_cli import environment as environment
from tests.test_svc_load_cli import last_line

pytestmark = pytest.mark.anyio

MINUTE = timedelta(minutes=1)
DAY = timedelta(days=1)


def ago(days: float, margin: timedelta = timedelta(0)) -> datetime:
    return NOW - timedelta(days=days) + margin


async def a_user(tx: Tx, email: str, *, seen: datetime = NOW) -> uuid.UUID:
    user = User(
        email=email, created_at=seen, verified_at=seen, last_signin_at=seen, last_seen_at=seen
    )
    tx.add(user)
    await tx.flush()
    return user.id


async def a_watchlist(tx: Tx, user_id: uuid.UUID) -> uuid.UUID:
    row = Watchlist(
        user_id=user_id, name="Flat rules", cadence=Cadence.WEEKLY, date_alerts=True, created_at=NOW
    )
    tx.add(row)
    await tx.flush()
    return row.id


async def total(db: Db, table: type[object], *where: object) -> int:
    async with db.transaction() as tx:
        query = select(func.count()).select_from(table).where(*where)  # type: ignore[arg-type]
        return int(await tx.scalar(query) or 0)


def test_svc_leave_the_inactivity_rule_reminds_then_deletes_and_a_sighting_cancels() -> None:
    old = NOW - timedelta(days=731)
    assert inactivity_due(NOW - timedelta(days=729), None, NOW) == "none"
    assert inactivity_due(old, None, NOW) == "remind"
    assert inactivity_due(old, NOW, NOW + timedelta(days=29)) == "none"
    assert inactivity_due(old, NOW, NOW + timedelta(days=31)) == "delete"
    seen_again = NOW + timedelta(days=10)
    assert inactivity_due(seen_again, NOW, NOW + timedelta(days=31)) == "none"
    assert inactivity_due(seen_again, NOW, seen_again + timedelta(days=731)) == "remind"
    assert len(RETENTION) == 8


async def test_svc_leave_links_sessions_events_and_the_audit_log_age_out(
    db: Db, settings: ServiceSettings
) -> None:
    async with db.transaction() as tx:
        user = await a_user(tx, "reader@example.org")
        for name, expires in ((b"gone", ago(1, -MINUTE)), (b"kept", ago(1, MINUTE))):
            tx.add(
                LoginToken(
                    token_hash=name,
                    email="reader@example.org",
                    purpose=TokenPurpose.SIGNIN,
                    created_at=expires,
                    expires_at=expires,
                )
            )
        for name, expires in ((b"gone", NOW - MINUTE), (b"kept", NOW + MINUTE)):
            tx.add(
                UserSession(
                    id_hash=name,
                    user_id=user,
                    created_at=ago(30),
                    expires_at=expires,
                    last_used_at=ago(30),
                )
            )
        for at in (ago(30, -MINUTE), ago(30, MINUTE)):
            tx.add(MailEvent(email_sha256=b"digest", kind=MailEventKind.SOFT_BOUNCE, at=at))
        for at in (ago(365, -MINUTE), ago(365, MINUTE)):
            tx.add(AuditLog(user_id=user, action=AuditAction.EXPORT, at=at))
    counts = await retain(db, settings, NOW)
    assert counts == RetentionCounts(login_tokens=1, sessions=1, mail_events=1, audit_log=1)
    async with db.transaction() as tx:
        assert (await tx.scalars(select(LoginToken.token_hash))).all() == [b"kept"]
        assert (await tx.scalars(select(UserSession.id_hash))).all() == [b"kept"]
    assert await total(db, MailEvent) == 1
    assert await total(db, AuditLog) == 1
    assert await retain(db, settings, NOW) == RetentionCounts()


async def an_email(
    tx: Tx, user: uuid.UUID, *, created: datetime, sent: datetime | None, status: OutboxStatus
) -> uuid.UUID:
    mail = OutgoingMail(to="reader@example.org", subject="Weekly", text="text", html="<p>h</p>")
    outbox_id = await enqueue(
        tx, purpose=OutboxPurpose.WEEKLY, to=mail.to, mail=mail, user_id=user, now=created
    )
    row = await tx.get_one(Outbox, outbox_id)
    row.status, row.sent_at = status, sent
    await tx.flush()
    return outbox_id


async def test_svc_leave_bodies_blank_after_30_days_and_rows_go_after_180(
    db: Db, settings: ServiceSettings
) -> None:
    async with db.transaction() as tx:
        user = await a_user(tx, "reader@example.org")
        blanked = await an_email(
            tx, user, created=ago(31), sent=ago(30, -MINUTE), status=OutboxStatus.SENT
        )
        recent = await an_email(
            tx, user, created=ago(31), sent=ago(30, MINUTE), status=OutboxStatus.SENT
        )
        failed = await an_email(
            tx, user, created=ago(30, -MINUTE), sent=None, status=OutboxStatus.FAILED
        )
        queued = await an_email(tx, user, created=ago(40), sent=None, status=OutboxStatus.QUEUED)
        old = await an_email(
            tx, user, created=ago(180, -MINUTE), sent=ago(180), status=OutboxStatus.SENT
        )
        young = await an_email(
            tx, user, created=ago(180, MINUTE), sent=ago(180), status=OutboxStatus.SENT
        )
    counts = await retain(db, settings, NOW)
    assert (counts.bodies, counts.outbox) == (4, 1)
    async with db.transaction() as tx:
        bodies = {row.id: row.text_body + row.html_body for row in await tx.scalars(select(Outbox))}
    assert set(bodies) == {blanked, recent, failed, queued, young}
    assert old not in bodies
    assert {key for key, body in bodies.items() if body} == {recent, queued}


async def test_svc_leave_deliveries_go_with_their_matches_and_unassigned_matches_age_out(
    db: Db, settings: ServiceSettings
) -> None:
    async with db.transaction() as tx:
        watchlist = await a_watchlist(tx, await a_user(tx, "reader@example.org"))
        for period, created in (("2026-W14", ago(180, -MINUTE)), ("2026-W15", ago(180, MINUTE))):
            delivery = Delivery(
                watchlist_id=watchlist,
                kind=DeliveryKind.WEEKLY,
                period_key=period,
                created_at=created,
            )
            tx.add(delivery)
            await tx.flush()
            tx.add(
                Match(
                    watchlist_id=watchlist,
                    event_key=f"toy/house-rules@{period}",
                    location="AR 2",
                    occurrence=1,
                    date_alert=False,
                    matched_at=created,
                    delivery_id=delivery.id,
                )
            )
        for event, matched in (("old", ago(180, -MINUTE)), ("young", ago(180, MINUTE))):
            tx.add(
                Match(
                    watchlist_id=watchlist,
                    event_key=f"toy/house-rules@{event}",
                    location="AR 2",
                    occurrence=1,
                    date_alert=False,
                    matched_at=matched,
                )
            )
    counts = await retain(db, settings, NOW)
    assert (counts.deliveries, counts.matches) == (1, 2)
    async with db.transaction() as tx:
        assert (await tx.scalars(select(Delivery.period_key))).all() == ["2026-W15"]
        events = sorted((await tx.scalars(select(Match.event_key))).all())
    assert events == ["toy/house-rules@2026-W15", "toy/house-rules@young"]


async def test_svc_leave_an_unused_account_is_warned_then_deleted(
    db: Db, settings: ServiceSettings
) -> None:
    async with db.transaction() as tx:
        idle = await a_user(tx, "idle@example.org", seen=ago(730, -MINUTE))
        await a_watchlist(tx, idle)
        returning = await a_user(tx, "returning@example.org", seen=ago(731))
        await a_user(tx, "edge@example.org", seen=ago(730, MINUTE))
    assert await retain(db, settings, NOW) == RetentionCounts(reminded=2)
    async with db.transaction() as tx:
        notes = (
            await tx.scalars(select(Outbox).where(Outbox.purpose == OutboxPurpose.INACTIVITY))
        ).all()
        noticed = (
            await tx.scalars(select(User.email).where(User.inactivity_notice_at == NOW))
        ).all()
    assert sorted(note.to_email for note in notes) == ["idle@example.org", "returning@example.org"]
    note = notes[0]
    assert note.subject == INACTIVITY_SUBJECT
    assert "2026-11-11" in note.text_body and "https://example.org/account/signin" in note.text_body
    assert DISCLAIMER in note.text_body and DISCLAIMER in note.html_body
    assert sorted(noticed) == ["idle@example.org", "returning@example.org"]
    assert await retain(db, settings, NOW + DAY) == RetentionCounts(reminded=1), "the edge"
    async with db.transaction() as tx:
        await mark_signed_in(tx, returning, NOW + 10 * DAY)
    assert await retain(db, settings, NOW + 30 * DAY) == RetentionCounts()
    assert await retain(db, settings, NOW + 30 * DAY + MINUTE) == RetentionCounts(deleted=1)
    async with db.transaction() as tx:
        left = (await tx.scalars(select(User.email).order_by(User.email))).all()
        deleted = (
            await tx.scalars(select(AuditLog.user_id).where(AuditLog.action == AuditAction.DELETE))
        ).all()
    assert left == ["edge@example.org", "returning@example.org"]
    assert deleted == [idle]
    assert await total(db, Watchlist) == 0


def test_svc_leave_retention_runs_and_ends_with_its_marker(
    environment: pytest.MonkeyPatch,
) -> None:
    result = CliRunner().invoke(app, ["retention"])
    assert result.exit_code == 0, result.output
    assert last_line(result.stdout) == {
        "emendrix_service": "retention",
        "status": "complete",
        **RetentionCounts().model_dump(),
    }
