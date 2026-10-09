"""The drain sends each due row once, retries on schedule, and respects suppressions."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import anyio
import pytest
from sqlalchemy import select

from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import (
    OutboxPurpose,
    OutboxStatus,
    SuppressionReason,
    UserStatus,
)
from emendrix_service.db.outbox import enqueue
from emendrix_service.db.suppressions import email_sha256, suppress, suspend_users_with
from emendrix_service.db.tables import Outbox, Suppression, User
from emendrix_service.mail.drain import DrainCounts, drain
from emendrix_service.mail.message import OutgoingMail, SendResult
from emendrix_service.mail.port import RecordingMailer
from tests.conftest import NOW

pytestmark = pytest.mark.anyio

SENDER = "Emendrix alerts <alerts@example.org>"

TRANSIENT = SendResult(accepted=False, error="451 4.3.0 try again later")
PERMANENT = SendResult(accepted=False, permanent=True, error="550 5.1.1 unknown user")


def mail(to: str = "reader@example.org") -> OutgoingMail:
    return OutgoingMail(
        to=to,
        subject="Article 6 changed",
        text="text",
        html="<p>html</p>",
        headers=(("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),),
    )


async def add_user(db: Db, email: str, status: UserStatus = UserStatus.ACTIVE) -> UUID:
    async with db.transaction() as tx:
        user = User(
            email=email,
            status=status,
            created_at=NOW,
            verified_at=NOW,
            last_signin_at=NOW,
            last_seen_at=NOW,
        )
        tx.add(user)
        await tx.flush()
        return user.id


async def queue(
    db: Db,
    to: str = "reader@example.org",
    *,
    user_id: UUID | None = None,
    purpose: OutboxPurpose = OutboxPurpose.INSTANT,
    delay: timedelta = timedelta(0),
) -> UUID:
    async with db.transaction() as tx:
        return await enqueue(
            tx, purpose=purpose, to=to, mail=mail(to), user_id=user_id, delay=delay, now=NOW
        )


async def row(db: Db, outbox_id: UUID) -> Outbox:
    async with db.transaction() as tx:
        return (await tx.execute(select(Outbox).where(Outbox.id == outbox_id))).scalar_one()


async def run(db: Db, mailer: RecordingMailer, clock: FixedClock, limit: int = 200) -> DrainCounts:
    return await drain(db, mailer, SENDER, clock, limit=limit, pace=0)


async def test_svc_mail_drain_sends_a_due_row_and_leaves_a_future_one(
    db: Db, mailer: RecordingMailer, clock: FixedClock
) -> None:
    due = await queue(db)
    later = await queue(db, delay=timedelta(hours=1))
    assert await run(db, mailer, clock) == DrainCounts(sent=1)
    sent = await row(db, due)
    assert (sent.status, sent.attempts, sent.sent_at) == (OutboxStatus.SENT, 1, NOW)
    assert sent.provider_message_id == "recorded-0"
    untouched = await row(db, later)
    assert (untouched.status, untouched.attempts) == (OutboxStatus.QUEUED, 0)
    assert untouched.next_attempt_at == NOW + timedelta(hours=1)
    ((sender, sent_mail),) = mailer.attempts
    assert sender == SENDER
    assert sent_mail.headers == (
        ("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),
        ("Message-ID", f"<{due}@example.org>"),
    )


async def test_svc_mail_drain_retries_on_schedule_then_fails(db: Db, clock: FixedClock) -> None:
    mailer = RecordingMailer([TRANSIENT] * 4)
    outbox_id = await queue(db)
    for wait in (timedelta(minutes=1), timedelta(minutes=10), timedelta(minutes=60)):
        start = clock.now()
        assert await run(db, mailer, clock) == DrainCounts(retried=1)
        assert (await row(db, outbox_id)).next_attempt_at == start + wait
        clock.advance(wait - timedelta(seconds=1))
        assert await run(db, mailer, clock) == DrainCounts()
        clock.advance(timedelta(seconds=1))
    assert await run(db, mailer, clock) == DrainCounts(failed=1)
    failed = await row(db, outbox_id)
    assert (failed.status, failed.attempts, failed.last_error) == (
        OutboxStatus.FAILED,
        4,
        TRANSIENT.error,
    )
    ids = {mail.headers[-1] for _, mail in mailer.attempts}
    assert len(mailer.attempts) == 4 and len(ids) == 1
    async with db.transaction() as tx:
        assert (await tx.execute(select(Suppression))).first() is None


async def test_svc_mail_drain_a_permanent_refusal_suppresses_and_suspends(
    db: Db, clock: FixedClock
) -> None:
    user_id = await add_user(db, "Reader@Example.org")
    first = await queue(db, "Reader@Example.org", user_id=user_id)
    mailer = RecordingMailer([PERMANENT])
    assert await run(db, mailer, clock) == DrainCounts(failed=1)
    assert (await row(db, first)).status == OutboxStatus.FAILED
    async with db.transaction() as tx:
        suppression = (await tx.execute(select(Suppression))).scalar_one()
        user = (await tx.execute(select(User).where(User.id == user_id))).scalar_one()
    assert suppression.email_sha256 == email_sha256("reader@example.org")
    assert suppression.reason == SuppressionReason.HARD_BOUNCE
    assert user.status == UserStatus.SUSPENDED

    second = await queue(db, "reader@example.org", user_id=user_id)
    assert await run(db, mailer, clock) == DrainCounts(suppressed=1)
    assert (await row(db, second)).status == OutboxStatus.SUPPRESSED
    assert len(mailer.attempts) == 1


async def test_svc_mail_drain_never_hands_a_suppressed_address_to_the_mailer(
    db: Db, mailer: RecordingMailer, clock: FixedClock
) -> None:
    async with db.transaction() as tx:
        await suppress(tx, email_sha256("gone@example.org"), SuppressionReason.COMPLAINT, NOW)
    held = await queue(db, "gone@example.org")
    operator = await queue(db, "gone@example.org", purpose=OutboxPurpose.OPERATOR)
    assert await run(db, mailer, clock) == DrainCounts(suppressed=2)
    assert mailer.attempts == []
    for outbox_id in (held, operator):
        assert (await row(db, outbox_id)).status == OutboxStatus.SUPPRESSED


async def test_svc_mail_drain_holds_a_suspended_account_but_not_operator_mail(
    db: Db, mailer: RecordingMailer, clock: FixedClock
) -> None:
    user_id = await add_user(db, "paused@example.org", UserStatus.SUSPENDED)
    held = await queue(db, "paused@example.org", user_id=user_id)
    operator = await queue(
        db, "paused@example.org", user_id=user_id, purpose=OutboxPurpose.OPERATOR
    )
    assert await run(db, mailer, clock) == DrainCounts(sent=1, suppressed=1)
    assert (await row(db, held)).status == OutboxStatus.SUPPRESSED
    assert (await row(db, operator)).status == OutboxStatus.SENT


async def test_svc_mail_drain_skips_a_row_already_sent(
    db: Db, mailer: RecordingMailer, clock: FixedClock
) -> None:
    outbox_id = await queue(db)
    async with db.transaction() as tx:
        stored = (await tx.execute(select(Outbox).where(Outbox.id == outbox_id))).scalar_one()
        stored.status = OutboxStatus.SENT
    assert await run(db, mailer, clock) == DrainCounts()
    assert mailer.attempts == []


async def test_svc_mail_drain_stops_at_its_limit(
    db: Db, mailer: RecordingMailer, clock: FixedClock
) -> None:
    for number in range(25):
        await queue(db, f"reader{number}@example.org")
    assert await run(db, mailer, clock, limit=22) == DrainCounts(sent=22)
    assert await run(db, mailer, clock) == DrainCounts(sent=3)
    assert len({mail.to for mail in mailer.sent}) == 25


class YieldingMailer(RecordingMailer):
    """Gives the other drain a turn during every send, as a relay's round trip would."""

    async def send(self, mail: OutgoingMail, *, sender: str) -> SendResult:
        await anyio.sleep(0.001)
        return await super().send(mail, sender=sender)


async def test_svc_mail_drain_two_drains_send_each_row_once(db: Db, clock: FixedClock) -> None:
    mailer = YieldingMailer()
    for number in range(45):
        await queue(db, f"reader{number}@example.org")
    results: list[DrainCounts] = []

    async def one() -> None:
        results.append(await run(db, mailer, clock))

    async with anyio.create_task_group() as group:
        group.start_soon(one)
        group.start_soon(one)
    assert sum(result.sent for result in results) == 45
    assert len(mailer.sent) == 45
    assert len({mail.to for mail in mailer.sent}) == 45


async def test_svc_mail_drain_the_sql_digest_equals_the_python_one(db: Db) -> None:
    user_id = await add_user(db, "Mixed.Case@Example.ORG")
    async with db.transaction() as tx:
        assert await suspend_users_with(tx, email_sha256("other@example.org")) == 0
        assert await suspend_users_with(tx, email_sha256("Mixed.Case@Example.ORG")) == 1
        user = (await tx.execute(select(User).where(User.id == user_id))).scalar_one()
    assert user.status == UserStatus.SUSPENDED
