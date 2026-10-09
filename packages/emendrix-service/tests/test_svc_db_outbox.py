"""`enqueue` writes one queued row holding exactly the mail it was given."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from emendrix_service.db import Db
from emendrix_service.db.enums import OutboxPurpose, OutboxStatus
from emendrix_service.db.outbox import enqueue
from emendrix_service.db.tables import Outbox
from emendrix_service.mail.message import OutgoingMail
from tests.conftest import NOW

pytestmark = pytest.mark.anyio

MAIL = OutgoingMail(
    to="reader@example.org",
    subject="Your sign-in link",
    text="Open the link.",
    html="<p>Open the link.</p>",
    headers=(
        ("List-Unsubscribe", "<https://example.org/u/unsubscribe/t>"),
        ("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),
    ),
)


async def test_svc_enqueue_writes_a_queued_row_with_the_mail(db: Db) -> None:
    async with db.transaction() as tx:
        row_id = await enqueue(
            tx,
            purpose=OutboxPurpose.SIGNIN,
            to=MAIL.to,
            mail=MAIL,
            user_id=None,
            delay=timedelta(minutes=5),
            now=NOW,
        )
    async with db.transaction() as tx:
        row = (await tx.execute(select(Outbox).where(Outbox.id == row_id))).scalar_one()
    assert (row.status, row.purpose, row.attempts) == (
        OutboxStatus.QUEUED,
        OutboxPurpose.SIGNIN,
        0,
    )
    assert (row.to_email, row.subject, row.text_body, row.html_body) == (
        MAIL.to,
        MAIL.subject,
        MAIL.text,
        MAIL.html,
    )
    assert row.headers == [[name, value] for name, value in MAIL.headers]
    assert row.next_attempt_at == NOW + timedelta(minutes=5)
    assert row.created_at == NOW
    assert (row.user_id, row.sent_at, row.last_error, row.provider_message_id) == (
        None,
        None,
        None,
        None,
    )


async def test_svc_enqueue_without_a_delay_is_due_at_once(db: Db) -> None:
    async with db.transaction() as tx:
        row_id = await enqueue(
            tx, purpose=OutboxPurpose.OPERATOR, to=MAIL.to, mail=MAIL, user_id=None, now=NOW
        )
        row = await tx.get_one(Outbox, row_id)
        assert row.next_attempt_at == NOW


async def test_svc_enqueue_refuses_a_naive_instant(db: Db) -> None:
    async with db.transaction() as tx:
        with pytest.raises(ValueError, match="timezone-aware"):
            await enqueue(
                tx,
                purpose=OutboxPurpose.OPERATOR,
                to=MAIL.to,
                mail=MAIL,
                user_id=None,
                now=NOW.replace(tzinfo=None),
            )
