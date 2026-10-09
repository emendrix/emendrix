"""Addresses that receive no more mail, the provider's events that decide it, and suspension.

An address is held only as the sha256 of its lower-cased form, so a suppression and the events
behind it can outlive the account without keeping the address. Postgres computes the same digest
with its built-in `sha256(convert_to(lower(email::text), 'UTF8'))`, which needs no extension, so
an account is found by digest without the address ever leaving the database.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import Text, cast, func, select, update

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import MailEventKind, SuppressionReason, UserStatus
from emendrix_service.db.guards import insert_once
from emendrix_service.db.tables_app import MailEvent, Suppression, User

__all__ = [
    "email_sha256",
    "is_suppressed",
    "record_event",
    "soft_bounces_since",
    "suppress",
    "suspend_users_with",
]


def email_sha256(address: str) -> bytes:
    """The digest an address is suppressed and counted under."""
    return hashlib.sha256(address.lower().encode("utf-8")).digest()


async def is_suppressed(tx: Tx, digest: bytes) -> bool:
    """Whether mail to the address with `digest` is suppressed."""
    found = await tx.execute(
        select(Suppression.email_sha256).where(Suppression.email_sha256 == digest)
    )
    return found.first() is not None


async def suppress(tx: Tx, digest: bytes, reason: SuppressionReason, now: datetime) -> bool:
    """Suppress the address; `False` when it already was, whose first reason then stands."""
    return await insert_once(tx, Suppression(email_sha256=digest, reason=reason, created_at=now))


async def record_event(
    tx: Tx, digest: bytes, kind: MailEventKind, provider_message_id: str | None, at: datetime
) -> None:
    """Keep one event the provider reported about mail to the address."""
    tx.add(
        MailEvent(email_sha256=digest, kind=kind, provider_message_id=provider_message_id, at=at)
    )
    await tx.flush()


async def soft_bounces_since(tx: Tx, digest: bytes, since: datetime) -> int:
    """How many soft bounces of the address the provider reported at or after `since`."""
    count = await tx.scalar(
        select(func.count())
        .select_from(MailEvent)
        .where(
            MailEvent.email_sha256 == digest,
            MailEvent.kind == MailEventKind.SOFT_BOUNCE,
            MailEvent.at >= since,
        )
    )
    return int(count or 0)


async def suspend_users_with(tx: Tx, digest: bytes) -> int:
    """Suspend the account whose address has `digest`; how many accounts changed (0 or 1)."""
    result = await tx.execute(
        update(User)
        .where(
            func.sha256(func.convert_to(func.lower(cast(User.email, Text)), "UTF8")) == digest,
            User.status != UserStatus.SUSPENDED,
        )
        .values(status=UserStatus.SUSPENDED)
    )
    return int(getattr(result, "rowcount", 0))
