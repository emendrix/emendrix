"""Every table of the three schemas, in one namespace, registered on `Base.metadata`.

The declarations are split by schema (`tables_app`, `tables_content`, `tables_notify`) so no
module passes the line cap; importing this module is what puts all of them on the metadata the
migrations and the test harness read.
"""

from __future__ import annotations

from emendrix_service.db.base import Base
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
from emendrix_service.db.tables_content import Act, Change, Event, Load, Provision
from emendrix_service.db.tables_notify import Announced

__all__ = [
    "Act",
    "Announced",
    "AuditLog",
    "Base",
    "Change",
    "Consent",
    "Delivery",
    "Event",
    "Load",
    "LoginToken",
    "MailEvent",
    "Match",
    "Outbox",
    "Provision",
    "Suppression",
    "User",
    "UserSession",
    "WatchItem",
    "Watchlist",
]
