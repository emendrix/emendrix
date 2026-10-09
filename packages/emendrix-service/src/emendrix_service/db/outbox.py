"""The outbox: every email the service sends is first a row here.

`enqueue` writes the row in the caller's transaction, beside the fact the email reports, so the
fact and its email commit or roll back together and no email is sent about something that was
never stored. Sending is a separate step that reads queued rows, which is also what retries one
whose first attempt failed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import OutboxPurpose, OutboxStatus
from emendrix_service.db.tables_app import Outbox
from emendrix_service.mail.message import OutgoingMail

__all__ = ["enqueue"]


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
