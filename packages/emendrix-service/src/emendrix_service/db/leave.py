"""Leaving: one-click unsubscribe, the export, deleting an account, and the retention sweeps.

Every function works inside the caller's transaction. The export reads only rows that name the
account (by `user_id`, or by watchlist for the rows a watchlist owns) and never a secret's
digest: no `token_hash`, `id_hash` or `feed_token_hash` leaves this module, and outbox bodies
and headers stay behind because the headers carry the unsubscribe token. Rows keyed by the
address alone (login links, a sign-up email sent before the account existed) are deleted with
the account but are not exported.

**Deletion forgets the address everywhere but a complaint.** The cascade removes every row with
a foreign key to the account. The rows that name the address instead (login links, sign-up mail
sent before the account existed, provider events and suppressions) are removed by address or
its digest, except a suppression for a complaint, which is kept as a digest so that a deleted
account cannot be used to mail someone who said the mail was unwanted. A hard bounce is about
the address and not the person, so deleting the account forgets it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Text, cast, delete, func, select, update

from emendrix_service.db.accounts import audit
from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import AuditAction, Cadence, OutboxStatus, SuppressionReason
from emendrix_service.db.suppressions import email_sha256
from emendrix_service.db.tables_app import (
    AuditLog,
    Consent,
    Delivery,
    LoginToken,
    MailEvent,
    Match,
    Outbox,
    Suppression,
    User,
    UserSession,
    WatchItem,
    Watchlist,
)
from emendrix_service.leave.model import (
    ExportAudit,
    ExportConsent,
    ExportDelivery,
    ExportDocument,
    ExportItem,
    ExportMatch,
    ExportOutbox,
    ExportSession,
    ExportUser,
    ExportWatchlist,
    InactiveUser,
    UnsubscribeTarget,
)

__all__ = [
    "blank_old_bodies",
    "delete_expired_sessions",
    "delete_old_audit",
    "delete_old_deliveries",
    "delete_old_login_tokens",
    "delete_old_mail_events",
    "delete_old_outbox",
    "delete_old_unassigned_matches",
    "delete_user",
    "export_rows",
    "inactivity_candidates",
    "lock_inactive",
    "mark_inactivity_notice",
    "unsubscribe",
    "unsubscribe_target",
]


_DAY = timedelta(days=1)


def _count(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def unsubscribe_target(tx: Tx, watchlist_id: UUID) -> UnsubscribeTarget | None:
    """The watchlist an unsubscribe link names; None when it has been deleted."""
    row = (
        await tx.execute(
            select(Watchlist.name, Watchlist.cadence).where(Watchlist.id == watchlist_id)
        )
    ).one_or_none()
    return None if row is None else UnsubscribeTarget(name=row.name, cadence=row.cadence)


async def unsubscribe(tx: Tx, watchlist_id: UUID, now: datetime) -> Literal["done", "gone"]:
    """Stop the watchlist's email, keeping its feed; `gone` when the watchlist does not exist.

    A second call changes nothing: the audit line is written only when the cadence moved, and
    the owner's `last_seen_at` moves at most once a day.
    """
    owner = await tx.scalar(select(Watchlist.user_id).where(Watchlist.id == watchlist_id))
    if owner is None:
        return "gone"
    moved = await tx.execute(
        update(Watchlist)
        .where(Watchlist.id == watchlist_id, Watchlist.cadence != Cadence.NONE)
        .values(cadence=Cadence.NONE)
    )
    if _count(moved):
        await audit(tx, owner, AuditAction.UNSUBSCRIBE, now)
    await tx.execute(
        update(User)
        .where(User.id == owner, User.last_seen_at < now - _DAY)
        .values(last_seen_at=now)
    )
    return "done"


async def export_rows(tx: Tx, user_id: UUID) -> ExportDocument | None:
    """Every row the account owns, as the export file holds it; None when there is no account."""
    user = await tx.get(User, user_id)
    if user is None:
        return None
    lists = (
        await tx.scalars(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.created_at, Watchlist.id)
        )
    ).all()
    ids = [row.id for row in lists]
    items = await tx.scalars(
        select(WatchItem)
        .where(WatchItem.watchlist_id.in_(ids))
        .order_by(WatchItem.watchlist_id, WatchItem.created_at, WatchItem.id)
    )
    matches = await tx.scalars(
        select(Match)
        .where(Match.watchlist_id.in_(ids))
        .order_by(Match.watchlist_id, Match.event_key, Match.location, Match.occurrence)
    )
    deliveries = await tx.scalars(
        select(Delivery)
        .where(Delivery.watchlist_id.in_(ids))
        .order_by(Delivery.created_at, Delivery.id)
    )
    outbox = await tx.scalars(
        select(Outbox).where(Outbox.user_id == user_id).order_by(Outbox.created_at, Outbox.id)
    )
    consents = await tx.scalars(
        select(Consent).where(Consent.user_id == user_id).order_by(Consent.granted_at, Consent.id)
    )
    sessions = await tx.scalars(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.created_at, UserSession.expires_at)
    )
    audit_rows = await tx.scalars(
        select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.at, AuditLog.id)
    )

    return ExportDocument(
        user=ExportUser.model_validate(user, from_attributes=True),
        consents=_take(ExportConsent, consents),
        watchlists=tuple(
            ExportWatchlist(
                id=row.id,
                name=row.name,
                cadence=row.cadence,
                date_alerts=row.date_alerts,
                heartbeat=row.heartbeat,
                paused=row.paused,
                has_feed=row.feed_token_hash is not None,
                created_at=row.created_at,
            )
            for row in lists
        ),
        items=_take(ExportItem, items),
        matches=_take(ExportMatch, matches),
        deliveries=_take(ExportDelivery, deliveries),
        outbox=_take(ExportOutbox, outbox),
        sessions=_take(ExportSession, sessions),
        audit_log=_take(ExportAudit, audit_rows),
    )


def _take[M: BaseModel](model: type[M], rows: Iterable[object]) -> tuple[M, ...]:
    """Each row copied into `model`, in the order given."""
    return tuple(model.model_validate(row, from_attributes=True) for row in rows)


async def delete_user(tx: Tx, user_id: UUID, now: datetime) -> bool:
    """Delete the account and every row that names it, keep only a complaint's digest, and
    record the deletion by uuid; False when there was no account."""
    email = await tx.scalar(select(User.email).where(User.id == user_id))
    if email is None:
        return False
    digest = email_sha256(email)
    lowered = func.lower(cast(Outbox.to_email, Text)) == email.lower()
    await tx.execute(delete(LoginToken).where(LoginToken.email == email))
    await tx.execute(delete(Outbox).where(Outbox.user_id.is_(None), lowered))
    await tx.execute(delete(MailEvent).where(MailEvent.email_sha256 == digest))
    await tx.execute(
        delete(Suppression).where(
            Suppression.email_sha256 == digest,
            Suppression.reason != SuppressionReason.COMPLAINT,
        )
    )
    # A match restricts the delivery it names, so matches go before the cascade reaches either.
    owned = select(Watchlist.id).where(Watchlist.user_id == user_id).scalar_subquery()
    await tx.execute(delete(Match).where(Match.watchlist_id.in_(owned)))
    await tx.execute(delete(User).where(User.id == user_id))
    await audit(tx, user_id, AuditAction.DELETE, now)
    return True


# --- retention ------------------------------------------------------------------------------


async def delete_old_login_tokens(tx: Tx, expired_before: datetime) -> int:
    """Remove login links that expired before `expired_before`."""
    return _count(
        await tx.execute(delete(LoginToken).where(LoginToken.expires_at < expired_before))
    )


async def delete_expired_sessions(tx: Tx, now: datetime) -> int:
    """Remove sessions past their expiry."""
    return _count(await tx.execute(delete(UserSession).where(UserSession.expires_at < now)))


async def blank_old_bodies(tx: Tx, before: datetime) -> int:
    """Blank the bodies of finished emails sent (or, never sent, written) before `before`.

    A queued row keeps its body, because the drain still needs it.
    """
    finished = func.coalesce(Outbox.sent_at, Outbox.created_at)
    result = await tx.execute(
        update(Outbox)
        .where(
            Outbox.status != OutboxStatus.QUEUED,
            finished < before,
            (Outbox.text_body != "") | (Outbox.html_body != ""),
        )
        .values(text_body="", html_body="")
    )
    return _count(result)


async def delete_old_deliveries(tx: Tx, before: datetime) -> tuple[int, int]:
    """Remove deliveries made before `before` and the matches they carried; both counts.

    A match restricts the delivery it names, so its matches go first, in the same transaction.
    """
    old = select(Delivery.id).where(Delivery.created_at < before).scalar_subquery()
    matches = _count(await tx.execute(delete(Match).where(Match.delivery_id.in_(old))))
    deliveries = _count(await tx.execute(delete(Delivery).where(Delivery.created_at < before)))
    return deliveries, matches


async def delete_old_outbox(tx: Tx, before: datetime) -> int:
    """Remove outbox rows written before `before`; a delivery naming one keeps its row."""
    return _count(await tx.execute(delete(Outbox).where(Outbox.created_at < before)))


async def delete_old_unassigned_matches(tx: Tx, before: datetime) -> int:
    """Remove matches no delivery took that were recorded before `before`."""
    result = await tx.execute(
        delete(Match).where(Match.delivery_id.is_(None), Match.matched_at < before)
    )
    return _count(result)


async def delete_old_mail_events(tx: Tx, before: datetime) -> int:
    """Remove provider events reported before `before`."""
    return _count(await tx.execute(delete(MailEvent).where(MailEvent.at < before)))


async def delete_old_audit(tx: Tx, before: datetime) -> int:
    """Remove audit lines written before `before`."""
    return _count(await tx.execute(delete(AuditLog).where(AuditLog.at < before)))


async def inactivity_candidates(tx: Tx, seen_before: datetime) -> list[UUID]:
    """Accounts unseen since `seen_before`, or holding an inactivity notice, oldest seen first."""
    query = (
        select(User.id)
        .where((User.last_seen_at < seen_before) | User.inactivity_notice_at.is_not(None))
        .order_by(User.last_seen_at, User.id)
    )
    return list((await tx.scalars(query)).all())


async def lock_inactive(tx: Tx, user_id: UUID) -> InactiveUser | None:
    """The account's sighting and notice, locked until the transaction ends; None when gone.

    The lock makes a sign-in that commits first win: it is read here, and decides.
    """
    row = (
        await tx.execute(
            select(User.id, User.email, User.last_seen_at, User.inactivity_notice_at)
            .where(User.id == user_id)
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        return None
    return InactiveUser(
        id=row.id,
        email=row.email,
        last_seen_at=row.last_seen_at,
        inactivity_notice_at=row.inactivity_notice_at,
    )


async def mark_inactivity_notice(tx: Tx, user_id: UUID, now: datetime) -> None:
    """Record that the account was told it will be deleted."""
    await tx.execute(update(User).where(User.id == user_id).values(inactivity_notice_at=now))
