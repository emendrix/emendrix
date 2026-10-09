"""Accounts: login links, users and their consents, sessions, the first watchlist, the audit log.

Every function works inside the caller's transaction and returns a frozen value or a count,
never an ORM row. Tokens and session ids arrive already hashed; nothing here sees the secret
itself. A link is consumed by one conditional `UPDATE`, so two posts of the same link race on
the row and exactly one of them wins.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select, update

from emendrix_service.db.engine import Tx
from emendrix_service.db.enums import (
    AuditAction,
    Cadence,
    ConsentKind,
    ItemKind,
    OutboxStatus,
    TokenPurpose,
    UserStatus,
)
from emendrix_service.db.guards import insert_once
from emendrix_service.db.tables_app import (
    AuditLog,
    Consent,
    LoginToken,
    Outbox,
    User,
    UserSession,
    WatchItem,
    Watchlist,
)
from emendrix_service.db.tables_content import Act

__all__ = [
    "FIRST_WATCHLIST",
    "SessionUser",
    "TokenRow",
    "UserRow",
    "act_label",
    "audit",
    "consume_token",
    "count_recent_tokens",
    "create_first_watchlist",
    "create_login_token",
    "create_session",
    "create_user_with_consents",
    "delete_session",
    "delete_sessions_for",
    "mark_outbox_sent",
    "mark_signed_in",
    "session_user",
    "touch_session",
    "user_by_email",
]

FIRST_WATCHLIST = "My watchlist"

_DAY = timedelta(days=1)


class TokenRow(BaseModel):
    """A login link that was just consumed."""

    model_config = ConfigDict(frozen=True)

    email: str = Field(description="The address the link was sent to.")
    purpose: TokenPurpose = Field(description="What the link was asked for.")
    intent: dict[str, object] | None = Field(description="The pending watch item, if any.")


class UserRow(BaseModel):
    """One account."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="The account's id.")
    email: str = Field(description="The confirmed address.")
    status: UserStatus = Field(description="Whether mail may go to it.")


class SessionUser(BaseModel):
    """A live session and the account it belongs to."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(description="The account's id.")
    email: str = Field(description="The account's address.")
    status: UserStatus = Field(description="The account's status.")
    last_used_at: datetime = Field(description="When the session's expiry last slid.")


def _user(row: User) -> UserRow:
    return UserRow(id=row.id, email=row.email, status=row.status)


async def create_login_token(
    tx: Tx,
    *,
    token_hash: bytes,
    email: str,
    purpose: TokenPurpose,
    intent: dict[str, object] | None,
    now: datetime,
    expires_at: datetime,
) -> None:
    """Store a login link by the hash of its token."""
    tx.add(
        LoginToken(
            token_hash=token_hash,
            email=email,
            purpose=purpose,
            intent=intent,
            created_at=now,
            expires_at=expires_at,
        )
    )
    await tx.flush()


async def count_recent_tokens(tx: Tx, email: str, since: datetime) -> int:
    """How many links were made for `email` at or after `since`, whatever became of them."""
    count = await tx.scalar(
        select(func.count())
        .select_from(LoginToken)
        .where(LoginToken.email == email, LoginToken.created_at >= since)
    )
    return int(count or 0)


async def consume_token(tx: Tx, token_hash: bytes, now: datetime) -> TokenRow | None:
    """Mark a live, unused link used and return it; None when it is unknown, used or expired."""
    row = (
        await tx.execute(
            update(LoginToken)
            .where(
                LoginToken.token_hash == token_hash,
                LoginToken.used_at.is_(None),
                LoginToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(LoginToken.email, LoginToken.purpose, LoginToken.intent)
        )
    ).one_or_none()
    if row is None:
        return None
    return TokenRow(email=row.email, purpose=row.purpose, intent=row.intent)


async def user_by_email(tx: Tx, email: str) -> UserRow | None:
    """The account holding `email`, compared without regard to case."""
    row = await tx.scalar(select(User).where(User.email == email))
    return _user(row) if row is not None else None


async def create_user_with_consents(
    tx: Tx, email: str, notice_version: str, now: datetime
) -> UserRow | None:
    """A new, confirmed account with its two consents; None when the address already has one."""
    user = User(
        email=email,
        status=UserStatus.ACTIVE,
        created_at=now,
        verified_at=now,
        last_signin_at=now,
        last_seen_at=now,
    )
    if not await insert_once(tx, user):
        return None
    for kind, version in (
        (ConsentKind.SERVICE_EMAIL, notice_version),
        (ConsentKind.PRIVACY_NOTICE, notice_version),
    ):
        tx.add(Consent(user_id=user.id, kind=kind, version=version, granted_at=now))
    await tx.flush()
    return _user(user)


async def mark_signed_in(tx: Tx, user_id: UUID, now: datetime) -> None:
    """Record a sign-in, which is also a sighting."""
    await tx.execute(
        update(User).where(User.id == user_id).values(last_signin_at=now, last_seen_at=now)
    )


async def create_session(
    tx: Tx, *, id_hash: bytes, user_id: UUID, now: datetime, expires_at: datetime
) -> None:
    """Store a session by the hash of its cookie."""
    tx.add(
        UserSession(
            id_hash=id_hash,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
            last_used_at=now,
        )
    )
    await tx.flush()


async def session_user(tx: Tx, id_hash: bytes, now: datetime) -> SessionUser | None:
    """The live session stored under `id_hash`, with its account; None when absent or expired."""
    row = (
        await tx.execute(
            select(User.id, User.email, User.status, UserSession.last_used_at)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.id_hash == id_hash, UserSession.expires_at > now)
        )
    ).one_or_none()
    if row is None:
        return None
    return SessionUser(
        user_id=row.id, email=row.email, status=row.status, last_used_at=row.last_used_at
    )


async def touch_session(
    tx: Tx, id_hash: bytes, now: datetime, expires_at: datetime, *, user_id: UUID
) -> None:
    """Slide a session's expiry; move its account's `last_seen_at` at most once a day."""
    await tx.execute(
        update(UserSession)
        .where(UserSession.id_hash == id_hash)
        .values(last_used_at=now, expires_at=expires_at)
    )
    await tx.execute(
        update(User)
        .where(User.id == user_id, User.last_seen_at < now - _DAY)
        .values(last_seen_at=now)
    )


async def delete_session(tx: Tx, id_hash: bytes) -> int:
    """Remove one session; the count removed, 0 or 1."""
    result = await tx.execute(delete(UserSession).where(UserSession.id_hash == id_hash))
    return int(result.rowcount)  # type: ignore[attr-defined]


async def delete_sessions_for(tx: Tx, user_id: UUID) -> int:
    """Remove every session of an account; the count removed."""
    result = await tx.execute(delete(UserSession).where(UserSession.user_id == user_id))
    return int(result.rowcount)  # type: ignore[attr-defined]


async def create_first_watchlist(
    tx: Tx,
    user_id: UUID,
    *,
    corpus: str,
    act_key: str,
    location: str | None,
    now: datetime,
) -> UUID:
    """The id of the watchlist a sign-up creates, with the defaults and the one item asked for."""
    watchlist = Watchlist(
        user_id=user_id,
        name=FIRST_WATCHLIST,
        cadence=Cadence.WEEKLY,
        date_alerts=True,
        heartbeat=True,
        paused=False,
        created_at=now,
    )
    tx.add(watchlist)
    await tx.flush()
    tx.add(
        WatchItem(
            watchlist_id=watchlist.id,
            kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
            corpus=corpus,
            act_key=act_key,
            location=location,
            created_at=now,
        )
    )
    await tx.flush()
    return watchlist.id


async def audit(tx: Tx, user_id: UUID, action: AuditAction, now: datetime) -> None:
    """Keep one account action in the audit log."""
    tx.add(AuditLog(user_id=user_id, action=action, at=now))
    await tx.flush()


async def mark_outbox_sent(
    tx: Tx, outbox_id: UUID, provider_message_id: str | None, now: datetime
) -> bool:
    """Record that a queued email was accepted by the relay; False when it was not queued.

    Only a queued row moves, so a drain that sent the row first is never overwritten.
    """
    result = await tx.execute(
        update(Outbox)
        .where(Outbox.id == outbox_id, Outbox.status == OutboxStatus.QUEUED)
        .values(
            status=OutboxStatus.SENT,
            sent_at=now,
            provider_message_id=provider_message_id,
            attempts=Outbox.attempts + 1,
        )
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def act_label(tx: Tx, corpus: str, act_key: str) -> str | None:
    """The short name the catalogue gives an act, once the record has been loaded."""
    label = await tx.scalar(select(Act.label).where(Act.corpus == corpus, Act.act_key == act_key))
    return str(label) if label is not None else None
