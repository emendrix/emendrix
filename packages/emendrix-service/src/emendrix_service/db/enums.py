"""Every closed set of values a column holds, each a Postgres enum in the schema of its table.

The Python `StrEnum` is the one declaration: `base.py` maps each class to a named Postgres enum
holding its values, so a column typed with one of these classes accepts nothing else at either
end. Adding a value to a type that exists needs a migration (`ALTER TYPE ... ADD VALUE`), which is
why no value is declared before a feature uses it.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "AuditAction",
    "Cadence",
    "ConsentKind",
    "DeliveryKind",
    "ItemKind",
    "MailEventKind",
    "OutboxPurpose",
    "OutboxStatus",
    "SuppressionReason",
    "TokenPurpose",
    "UserStatus",
]


class UserStatus(StrEnum):
    """Whether mail may go to an account; `suspended` after a hard bounce or a complaint."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class ConsentKind(StrEnum):
    """What a person agreed to: receiving the service's email, or one version of the notice."""

    SERVICE_EMAIL = "service_email"
    PRIVACY_NOTICE = "privacy_notice"


class TokenPurpose(StrEnum):
    """What a login link was asked for; a link is bound to its purpose and its address."""

    SIGNUP = "signup"
    SIGNIN = "signin"


class Cadence(StrEnum):
    """How often a watchlist's matches are mailed; `none` keeps them for the feed only."""

    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"
    NONE = "none"


class ItemKind(StrEnum):
    """What a watch item names: a whole act, or one provision of it matched by containment.

    `amending_act` (every change an amending act makes) and `preset` (a published group of
    provisions) are the planned additions; each needs a migration adding its value.
    """

    ACT = "act"
    PROVISION = "provision"


class DeliveryKind(StrEnum):
    """Which email a delivery row stands for; with its period it is sent at most once."""

    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"
    HEARTBEAT = "heartbeat"


class OutboxPurpose(StrEnum):
    """Why an email was written, which decides how it may be retried and retained."""

    SIGNIN = "signin"
    SIGNUP = "signup"
    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"
    HEARTBEAT = "heartbeat"
    INACTIVITY = "inactivity"
    OPERATOR = "operator"


class OutboxStatus(StrEnum):
    """Where an outbox row stands; only `queued` rows are picked up to send."""

    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class SuppressionReason(StrEnum):
    """Why an address receives no more mail."""

    HARD_BOUNCE = "hard_bounce"
    COMPLAINT = "complaint"
    SOFT_BOUNCES = "soft_bounces"


class MailEventKind(StrEnum):
    """What the mail provider reported about one message."""

    HARD_BOUNCE = "hard_bounce"
    SOFT_BOUNCE = "soft_bounce"
    COMPLAINT = "complaint"
    DELIVERED = "delivered"


class AuditAction(StrEnum):
    """An account action kept in the audit log for a year."""

    EXPORT = "export"
    DELETE = "delete"
    FEED_ROTATE = "feed_rotate"
    SIGNOUT_ALL = "signout_all"
    UNSUBSCRIBE = "unsubscribe"
