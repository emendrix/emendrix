"""How long each kind of row is kept, and when an unused account is warned and then deleted.

The table is data, so the operator documentation and the sweep read one declaration. Every
period is measured from a stored instant and the run's own `now`, and a row exactly at its
threshold is kept until the next run; nothing here reads a clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AUDIT_LIFE",
    "BODY_LIFE",
    "INACTIVE_AFTER",
    "LOGIN_TOKEN_GRACE",
    "MAIL_EVENT_LIFE",
    "NOTICE_PERIOD",
    "RETENTION",
    "ROW_LIFE",
    "Rule",
    "inactivity_due",
]

LOGIN_TOKEN_GRACE: Final = timedelta(hours=24)
BODY_LIFE: Final = timedelta(days=30)
ROW_LIFE: Final = timedelta(days=180)
MAIL_EVENT_LIFE: Final = timedelta(days=30)
AUDIT_LIFE: Final = timedelta(days=365)
INACTIVE_AFTER: Final = timedelta(days=730)
"""24 months without a sign-in, a page, a feed fetch or an unsubscribe click."""
NOTICE_PERIOD: Final = timedelta(days=30)


class Rule(BaseModel):
    """One row of the retention table."""

    model_config = ConfigDict(frozen=True)

    what: str = Field(description="The rows the rule applies to.")
    rule: str = Field(description="What happens to them, and when.")


RETENTION: Final = (
    Rule(what="login links", rule="deleted 24 hours after they expire"),
    Rule(what="sessions", rule="deleted once expired (30 days after last use)"),
    Rule(
        what="email bodies",
        rule="blanked 30 days after the email was sent, or written when it was never sent",
    ),
    Rule(what="emails and deliveries", rule="deleted 180 days after they were written"),
    Rule(
        what="matches",
        rule="deleted with the delivery that carried them; never carried, after 180 days",
    ),
    Rule(what="mail provider events", rule="deleted after 30 days"),
    Rule(what="the audit log", rule="deleted after 12 months"),
    Rule(
        what="inactive accounts",
        rule="unseen for 24 months: warned by email; deleted 30 days later unless seen again",
    ),
)


def inactivity_due(
    last_seen_at: datetime, notice_at: datetime | None, now: datetime
) -> Literal["none", "remind", "delete"]:
    """What the inactivity rule does to one account at `now`.

    A notice counts only while the account has not been seen since it; a sighting after the
    notice cancels it, and a later silence of 24 months earns a new one.
    """
    if notice_at is not None and last_seen_at <= notice_at:
        return "delete" if now - notice_at > NOTICE_PERIOD else "none"
    return "remind" if now - last_seen_at > INACTIVE_AFTER else "none"
