"""The outbox drain: send every queued row that is due, exactly once, with retries on schedule.

Rows are claimed in batches, each claim committed with a lease (see `db/outbox.py`), so any
number of drains may run at once and each row is handed to the relay by one of them. Sending
happens outside any transaction; each outcome is then recorded in its own short one, so a
crash loses at most the outcome of one send, and the lease brings that row back.

Before a row is sent, its address is checked against the suppressions and its account against
suspension. An `operator` email has no account to suspend and is held only by suppression. A
permanent refusal suppresses the address and suspends its account; a transient one is retried
1, 10 and 60 minutes after the first, second and third attempts, and the row fails when its
fourth attempt is refused.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

import anyio
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emendrix_service.clock import Clock
from emendrix_service.db import Db
from emendrix_service.db.enums import OutboxPurpose, SuppressionReason, UserStatus
from emendrix_service.db.outbox import (
    OutboxRow,
    claim_due,
    extend_lease,
    mark_failed,
    mark_retry,
    mark_sent,
    mark_suppressed,
)
from emendrix_service.db.suppressions import (
    email_sha256,
    is_suppressed,
    suppress,
    suspend_users_with,
)
from emendrix_service.mail.message import OutgoingMail, SendResult
from emendrix_service.mail.mime import MESSAGE_ID, message_id_for
from emendrix_service.mail.port import Mailer, send_now

__all__ = ["BACKOFF", "BATCH", "LEASE", "PACE", "DrainCounts", "drain", "outgoing"]

BATCH: Final = 20
"""Rows claimed in one transaction."""

LEASE: Final = timedelta(minutes=10)
"""How long a claimed row is kept from other drains while it is being sent."""

BACKOFF: Final = (timedelta(minutes=1), timedelta(minutes=10), timedelta(minutes=60))
"""The wait after the first, second and third refused attempts; the next refusal is final."""

PACE: Final = 0.1
"""Seconds between two sends: at most ten a second reach the relay."""


class DrainCounts(BaseModel):
    """What one drain did with the rows it claimed."""

    model_config = ConfigDict(frozen=True)

    sent: int = Field(default=0, description="Rows the relay accepted.")
    retried: int = Field(default=0, description="Rows refused for now and due again later.")
    failed: int = Field(default=0, description="Rows refused for good.")
    suppressed: int = Field(
        default=0, description="Rows not sent: address suppressed or account suspended."
    )

    def plus(self, other: DrainCounts) -> DrainCounts:
        """Both counts added together."""
        return DrainCounts(
            sent=self.sent + other.sent,
            retried=self.retried + other.retried,
            failed=self.failed + other.failed,
            suppressed=self.suppressed + other.suppressed,
        )


def outgoing(row: OutboxRow, sender: str) -> OutgoingMail:
    """The mail a row holds, carrying the `Message-ID` every attempt at it shares."""
    headers = row.headers
    if not any(name.lower() == MESSAGE_ID.lower() for name, _ in headers):
        headers = (*headers, (MESSAGE_ID, message_id_for(row.id, sender)))
    return OutgoingMail(
        to=row.to_email,
        subject=row.subject,
        text=row.text_body,
        html=row.html_body,
        headers=headers,
    )


def held_by_account(row: OutboxRow) -> bool:
    """Whether the row's account is suspended; an operator email has no account to hold it."""
    return row.purpose != OutboxPurpose.OPERATOR and row.user_status == UserStatus.SUSPENDED


async def drain(
    db: Db,
    mailer: Mailer,
    sender: str,
    clock: Clock,
    *,
    limit: int = 200,
    pace: float = PACE,
) -> DrainCounts:
    """Send up to `limit` due rows from `sender` and say what became of them."""
    counts = DrainCounts()
    pacer = _Pacer(pace)
    handled = 0
    while handled < limit:
        now = clock.now()
        async with db.transaction() as tx:
            batch = await claim_due(tx, now, min(BATCH, limit - handled), lease_until=now + LEASE)
        if not batch:
            break
        for row in batch:
            counts = counts.plus(await _one(db, mailer, sender, clock, pacer, row))
        handled += len(batch)
    return counts


class _Pacer:
    """Waits `pace` seconds before every send but the first; it sleeps and reads no clock."""

    def __init__(self, pace: float) -> None:
        self._pace = pace
        self._started = False

    async def wait(self) -> None:
        if self._started and self._pace > 0:
            await anyio.sleep(self._pace)
        self._started = True


async def _one(
    db: Db, mailer: Mailer, sender: str, clock: Clock, pacer: _Pacer, row: OutboxRow
) -> DrainCounts:
    digest = email_sha256(row.to_email)
    await pacer.wait()
    async with db.transaction() as tx:
        if held_by_account(row) or await is_suppressed(tx, digest):
            await mark_suppressed(tx, row.id)
            return DrainCounts(suppressed=1)
        # A batch's rows are sent one after another, so each renews its lease just before its
        # own send rather than relying on the one taken when the batch was claimed.
        if not await extend_lease(tx, row.id, clock.now() + LEASE):
            return DrainCounts()
    try:
        mail = outgoing(row, sender)
    except ValidationError:
        # A row that cannot be rebuilt is this service's fault, never the recipient's.
        async with db.transaction() as tx:
            await mark_failed(tx, row.id, "the stored email is not valid")
        return DrainCounts(failed=1)
    result = await send_now(mailer, mail, sender=sender)
    return await _record(db, clock, row, digest, result)


async def _record(
    db: Db, clock: Clock, row: OutboxRow, digest: bytes, result: SendResult
) -> DrainCounts:
    now = clock.now()
    async with db.transaction() as tx:
        if result.accepted:
            await mark_sent(tx, row.id, result.provider_message_id, now)
            return DrainCounts(sent=1)
        if result.permanent:
            await mark_failed(tx, row.id, result.error)
            await suppress(tx, digest, SuppressionReason.HARD_BOUNCE, now)
            await suspend_users_with(tx, digest)
            return DrainCounts(failed=1)
        if row.attempts < len(BACKOFF):
            await mark_retry(tx, row.id, result.error, now + BACKOFF[row.attempts])
            return DrainCounts(retried=1)
        await mark_failed(tx, row.id, result.error)
        return DrainCounts(failed=1)
