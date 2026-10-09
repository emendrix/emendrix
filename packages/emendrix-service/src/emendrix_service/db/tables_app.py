"""The `app` schema: user data. It lives only in this database and its backups.

Nothing here has a foreign key into `content`: a user's rows name changes by natural key alone
(`corpus`, `act_key`, `event_key`, `location`, `occurrence`), so reloading the record never
cascades into anyone's watchlist. Every row that belongs to a person goes when their `users`
row goes, through `ON DELETE CASCADE`; `suppressions`, `mail_events` and `audit_log` carry no
foreign key and outlive the account under their own retention.

Decided here, where the column list leaves it open: surrogate keys of rows nobody links to
(`consents`, `mail_events`, `audit_log`) are `bigint` identities; `outbox.to_email` is plain
`text`, because it is the address as written to the relay; `deliveries.outbox_id` is set null
when retention removes the email, since the delivery row alone is the exactly-once guard; and
`matches.delivery_id` restricts, so a delivery cannot vanish under the matches it delivered.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Identity, Index, UniqueConstraint, false, text, true
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from emendrix_service.db.base import Base
from emendrix_service.db.enums import (
    AuditAction,
    Cadence,
    ConsentKind,
    DeliveryKind,
    ItemKind,
    MailEventKind,
    OutboxPurpose,
    OutboxStatus,
    SuppressionReason,
    TokenPurpose,
    UserStatus,
)

__all__ = [
    "AuditLog",
    "Consent",
    "Delivery",
    "LoginToken",
    "MailEvent",
    "Match",
    "Outbox",
    "Suppression",
    "User",
    "UserSession",
    "WatchItem",
    "Watchlist",
]

APP = {"schema": "app"}
USERS = "app.users.id"
WATCHLISTS = "app.watchlists.id"


class User(Base):
    """One confirmed address."""

    __tablename__ = "users"
    __table_args__ = APP

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.ACTIVE)
    created_at: Mapped[datetime]
    verified_at: Mapped[datetime]
    last_signin_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    inactivity_notice_at: Mapped[datetime | None]


class Consent(Base):
    """Proof of double opt-in, and of which version of the notice was accepted."""

    __tablename__ = "consents"
    __table_args__ = APP

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USERS, ondelete="CASCADE"))
    kind: Mapped[ConsentKind]
    version: Mapped[str]
    granted_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]


class LoginToken(Base):
    """A login link, stored only as the sha256 of its token."""

    __tablename__ = "login_tokens"
    __table_args__ = (Index(None, "email", "created_at"), APP)

    token_hash: Mapped[bytes] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT)
    purpose: Mapped[TokenPurpose]
    intent: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class UserSession(Base):
    """A signed-in browser, stored only as the sha256 of its cookie."""

    __tablename__ = "sessions"
    __table_args__ = (Index(None, "user_id"), APP)

    id_hash: Mapped[bytes] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USERS, ondelete="CASCADE"))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    last_used_at: Mapped[datetime]


class Watchlist(Base):
    """A named set of watch items with one cadence."""

    __tablename__ = "watchlists"
    __table_args__ = APP

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USERS, ondelete="CASCADE"))
    name: Mapped[str]
    cadence: Mapped[Cadence]
    date_alerts: Mapped[bool]
    heartbeat: Mapped[bool] = mapped_column(default=True, server_default=true())
    paused: Mapped[bool] = mapped_column(default=False, server_default=false())
    feed_token_hash: Mapped[bytes | None] = mapped_column(unique=True)
    created_at: Mapped[datetime]


class WatchItem(Base):
    """One act, or one provision of it, that a watchlist follows. A NULL location is the act."""

    __tablename__ = "watch_items"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "kind",
            "corpus",
            "act_key",
            "location",
            postgresql_nulls_not_distinct=True,
        ),
        APP,
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(WATCHLISTS, ondelete="CASCADE"))
    kind: Mapped[ItemKind]
    corpus: Mapped[str]
    act_key: Mapped[str]
    location: Mapped[str | None]
    created_at: Mapped[datetime]


class Match(Base):
    """The fact that one change is owed to one watchlist; `delivery_id` is null until mailed."""

    __tablename__ = "matches"
    __table_args__ = (
        Index(None, "delivery_id", postgresql_where=text("delivery_id IS NULL")),
        APP,
    )

    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(WATCHLISTS, ondelete="CASCADE"), primary_key=True
    )
    event_key: Mapped[str] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column(primary_key=True)
    occurrence: Mapped[int] = mapped_column(primary_key=True)
    date_alert: Mapped[bool]
    matched_at: Mapped[datetime]
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app.deliveries.id"))


class Delivery(Base):
    """One email owed to one watchlist for one period: the exactly-once guard."""

    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("watchlist_id", "kind", "period_key"), APP)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(WATCHLISTS, ondelete="CASCADE"))
    kind: Mapped[DeliveryKind]
    period_key: Mapped[str]
    outbox_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app.outbox.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime]


class Outbox(Base):
    """One rendered email, kept so a failed send is retried exactly as it was written."""

    __tablename__ = "outbox"
    __table_args__ = (Index(None, "status", "next_attempt_at"), APP)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(USERS, ondelete="CASCADE"))
    purpose: Mapped[OutboxPurpose]
    to_email: Mapped[str]
    subject: Mapped[str]
    text_body: Mapped[str]
    html_body: Mapped[str]
    headers: Mapped[list[list[str]]] = mapped_column(JSONB)
    status: Mapped[OutboxStatus] = mapped_column(default=OutboxStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    next_attempt_at: Mapped[datetime]
    last_error: Mapped[str | None]
    provider_message_id: Mapped[str | None]
    created_at: Mapped[datetime]
    sent_at: Mapped[datetime | None]


class Suppression(Base):
    """An address that receives no more mail, stored only as the sha256 of the address."""

    __tablename__ = "suppressions"
    __table_args__ = APP

    email_sha256: Mapped[bytes] = mapped_column(primary_key=True)
    reason: Mapped[SuppressionReason]
    created_at: Mapped[datetime]


class MailEvent(Base):
    """One provider report about one message, kept 30 days to count soft bounces."""

    __tablename__ = "mail_events"
    __table_args__ = (Index(None, "email_sha256", "at"), APP)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email_sha256: Mapped[bytes]
    kind: Mapped[MailEventKind]
    provider_message_id: Mapped[str | None]
    at: Mapped[datetime]


class AuditLog(Base):
    """One account action, kept 12 months; `user_id` has no foreign key so it outlives them."""

    __tablename__ = "audit_log"
    __table_args__ = APP

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID]
    action: Mapped[AuditAction]
    at: Mapped[datetime]
