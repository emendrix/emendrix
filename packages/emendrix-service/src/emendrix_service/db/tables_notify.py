"""The `notify` schema: the notifier's own ledger. Not user data, and never rebuilt.

It is what lets `content` be truncated and reloaded without anyone being alerted twice: an event
is judged once, by `event_key`, and the judgement stays here whatever happens to the record's
copy. Alembic's version table lives in this schema too, beside the other thing that must survive
a reload.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from emendrix_service.db.base import Base

__all__ = ["Announced"]

NOTIFY = {"schema": "notify"}


class Announced(Base):
    """One event the notifier has judged, and whether it was eligible to announce."""

    __tablename__ = "announced"
    __table_args__ = NOTIFY

    event_key: Mapped[str] = mapped_column(primary_key=True)
    first_seen_at: Mapped[datetime]
    eligible: Mapped[bool]
    reason: Mapped[str]
