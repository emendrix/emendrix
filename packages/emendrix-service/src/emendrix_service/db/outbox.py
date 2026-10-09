"""The outbox: every email the service sends is first a row here.

`enqueue` writes the row in the caller's transaction, beside the fact the email reports, so the
fact and its email commit or roll back together and no email is sent about something that was
never stored. Sending is a separate step that reads queued rows, which is also what retries one
whose first attempt failed.

**Claiming.** `claim_due` locks due rows with `FOR UPDATE SKIP LOCKED` and moves their
`next_attempt_at` to a lease in the same transaction. The lock lasts only until the
claim commits; the lease is what keeps a second drain off a row while the first sends it outside
any transaction, and a drain that dies mid-send leaves rows that fall due again when the lease
ends. Every mark applies only to a row still `queued`, so a row another writer has already
marked sent is never moved back.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import OutboxPurpose, OutboxStatus, UserStatus
from emendrix_service.db.tables_app import Outbox, User
from emendrix_service.mail.message import OutgoingMail

__all__ = [
    "OutboxRow",
    "claim_due",
    "enqueue",
    "extend_lease",
    "mark_failed",
    "mark_retry",
    "mark_sent",
    "mark_suppressed",
]


async def enqueue(
    tx: Tx,
    *,
    purpose: OutboxPurpose,
    to: str,
    mail: OutgoingMail,
    user_id: UUID | None,
    delay: timedelta = timedelta(0),
    now: datetime,
) -> UUID:
    """Queue `mail` for `to`, first due at `now + delay`, and return the new row's id.

    `to` is the address the row is sent to; `user_id` is null for mail to someone who has no
    account yet (a sign-up link) or to the operator. Headers are stored as a JSON list of
    `[name, value]` pairs, so their order survives the round trip.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("enqueue needs a timezone-aware instant")
    if delay < timedelta(0):
        raise ValueError("an email cannot be due before it was written")
    row = Outbox(
        user_id=user_id,
        purpose=purpose,
        to_email=to,
        subject=mail.subject,
        text_body=mail.text,
        html_body=mail.html,
        headers=[[name, value] for name, value in mail.headers],
        status=OutboxStatus.QUEUED,
        attempts=0,
        next_attempt_at=now + delay,
        created_at=now,
    )
    tx.add(row)
    await tx.flush()
    return row.id


class OutboxRow(BaseModel):
    """A queued row as the drain sends it, with the status of the account it belongs to."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="The row's id, which also names the message.")
    user_id: UUID | None = Field(description="The account the email is for, if any.")
    user_status: UserStatus | None = Field(
        description="That account's status when the row was claimed; null without an account."
    )
    purpose: OutboxPurpose = Field(description="Why the email was written.")
    to_email: str = Field(description="The address the email goes to.")
    subject: str = Field(description="The subject line.")
    text_body: str = Field(description="The plain-text body.")
    html_body: str = Field(description="The HTML body.")
    headers: tuple[tuple[str, str], ...] = Field(description="Extra headers, in order.")
    attempts: int = Field(description="Sends tried before this one.")


async def claim_due(tx: Tx, now: datetime, limit: int, *, lease_until: datetime) -> list[OutboxRow]:
    """Up to `limit` queued rows due at `now`, oldest due first, leased until `lease_until`.

    Rows another transaction holds locked are skipped rather than waited for.
    """
    query = (
        select(Outbox, User.status)
        .outerjoin(User, User.id == Outbox.user_id)
        .where(Outbox.status == OutboxStatus.QUEUED, Outbox.next_attempt_at <= now)
        .order_by(Outbox.next_attempt_at, Outbox.id)
        .limit(limit)
        .with_for_update(skip_locked=True, of=Outbox)
    )
    claimed = [
        OutboxRow(
            id=row.id,
            user_id=row.user_id,
            user_status=status,
            purpose=row.purpose,
            to_email=row.to_email,
            subject=row.subject,
            text_body=row.text_body,
            html_body=row.html_body,
            headers=tuple((name, value) for name, value in row.headers),
            attempts=row.attempts,
        )
        for row, status in await tx.execute(query)
    ]
    if claimed:
        await tx.execute(
            update(Outbox)
            .where(Outbox.id.in_([row.id for row in claimed]))
            .values(next_attempt_at=lease_until)
        )
    return claimed


async def _mark(tx: Tx, outbox_id: UUID, **values: object) -> bool:
    result = await tx.execute(
        update(Outbox)
        .where(Outbox.id == outbox_id, Outbox.status == OutboxStatus.QUEUED)
        .values(**values)
    )
    return bool(getattr(result, "rowcount", 0))


async def extend_lease(tx: Tx, outbox_id: UUID, until: datetime) -> bool:
    """Keep a claimed row from other drains until `until`; `False` when it is no longer queued."""
    return await _mark(tx, outbox_id, next_attempt_at=until)


async def mark_sent(tx: Tx, outbox_id: UUID, provider_id: str | None, now: datetime) -> bool:
    """Record that the relay accepted the row; `False` when it was no longer queued."""
    return await _mark(
        tx,
        outbox_id,
        status=OutboxStatus.SENT,
        attempts=Outbox.attempts + 1,
        provider_message_id=provider_id,
        sent_at=now,
        last_error=None,
    )


async def mark_retry(tx: Tx, outbox_id: UUID, error: str, next_at: datetime) -> bool:
    """Count a transient refusal and make the row due again at `next_at`."""
    return await _mark(
        tx, outbox_id, attempts=Outbox.attempts + 1, last_error=error, next_attempt_at=next_at
    )


async def mark_failed(tx: Tx, outbox_id: UUID, error: str) -> bool:
    """Count a last refusal and stop sending the row."""
    return await _mark(
        tx, outbox_id, status=OutboxStatus.FAILED, attempts=Outbox.attempts + 1, last_error=error
    )


async def mark_suppressed(tx: Tx, outbox_id: UUID) -> bool:
    """Stop the row unsent, because its address is suppressed or its account suspended."""
    return await _mark(tx, outbox_id, status=OutboxStatus.SUPPRESSED)
