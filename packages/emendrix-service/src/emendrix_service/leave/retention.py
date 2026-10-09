"""The retention sweep: each rule of `logic.RETENTION` applied in a transaction of its own.

A rule that fails is logged by its name and the error's type and the others still run, so one
locked table does not keep every other row past its time; the run then reports `failed`. The
inactivity rule works one account at a time, locking the account's row and deciding on what it
reads there, so a sign-in that commits first cancels a deletion.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db import Db, Tx
from emendrix_service.db import leave as store
from emendrix_service.db.enums import OutboxPurpose
from emendrix_service.db.outbox import enqueue
from emendrix_service.leave.logic import (
    AUDIT_LIFE,
    BODY_LIFE,
    INACTIVE_AFTER,
    LOGIN_TOKEN_GRACE,
    MAIL_EVENT_LIFE,
    NOTICE_PERIOD,
    ROW_LIFE,
    inactivity_due,
)
from emendrix_service.mail.message import OutgoingMail
from emendrix_service.notify.render import PREFIX
from emendrix_service.settings import ServiceSettings
from emendrix_service.web.templating import render_mail

__all__ = ["INACTIVITY_SUBJECT", "RetentionCounts", "inactivity_mail", "retain"]

_log = logging.getLogger(__name__)

INACTIVITY_SUBJECT: Final = f"{PREFIX} Your account will be deleted unless you sign in"


class RetentionCounts(BaseModel):
    """What one sweep removed, blanked or sent, rule by rule."""

    model_config = ConfigDict(frozen=True)

    login_tokens: int = Field(default=0, description="Login links deleted.")
    sessions: int = Field(default=0, description="Expired sessions deleted.")
    bodies: int = Field(default=0, description="Email bodies blanked.")
    deliveries: int = Field(default=0, description="Deliveries deleted.")
    outbox: int = Field(default=0, description="Outbox rows deleted.")
    matches: int = Field(default=0, description="Matches deleted, carried or never carried.")
    mail_events: int = Field(default=0, description="Provider events deleted.")
    audit_log: int = Field(default=0, description="Audit lines deleted.")
    reminded: int = Field(default=0, description="Inactive accounts warned.")
    deleted: int = Field(default=0, description="Inactive accounts deleted.")
    failed: int = Field(default=0, description="Rules or accounts whose transaction failed.")


def inactivity_mail(to: str, *, site_url: str, delete_on: datetime) -> OutgoingMail:
    """The warning an unused account gets, 30 days before it is deleted."""
    text, html = render_mail(
        "leave/mail_inactivity",
        site_url=site_url,
        signin=f"{site_url}/account/signin",
        delete_on=delete_on.date().isoformat(),
        reason="this address has an account that has not been used for two years.",
        unsubscribe=None,
    )
    return OutgoingMail(to=to, subject=INACTIVITY_SUBJECT, text=text, html=html)


async def _account(
    db: Db, settings: ServiceSettings, user_id: UUID, now: datetime
) -> Literal["none", "remind", "delete"]:
    """Apply the inactivity rule to one account; what it did."""
    async with db.transaction() as tx:
        user = await store.lock_inactive(tx, user_id)
        if user is None:
            return "none"
        due = inactivity_due(user.last_seen_at, user.inactivity_notice_at, now)
        if due == "remind":
            mail = inactivity_mail(
                user.email, site_url=settings.site_url, delete_on=now + NOTICE_PERIOD
            )
            await enqueue(
                tx,
                purpose=OutboxPurpose.INACTIVITY,
                to=user.email,
                mail=mail,
                user_id=user.id,
                now=now,
            )
            await store.mark_inactivity_notice(tx, user.id, now)
        elif due == "delete":
            await store.delete_user(tx, user.id, now)
        return due


async def retain(db: Db, settings: ServiceSettings, now: datetime) -> RetentionCounts:
    """Apply every retention rule once at `now`."""
    counts: dict[str, int] = {}
    failed = 0

    async def rule(name: str, run: Callable[[Tx], Awaitable[dict[str, int]]]) -> None:
        nonlocal failed
        try:
            async with db.transaction() as tx:
                found = await run(tx)
        except Exception as error:
            _log.error("the retention rule %s did not complete: %s", name, type(error).__name__)
            failed += 1
            return
        for key, value in found.items():
            counts[key] = counts.get(key, 0) + value

    async def deliveries(tx: Tx) -> dict[str, int]:
        gone, carried = await store.delete_old_deliveries(tx, now - ROW_LIFE)
        return {"deliveries": gone, "matches": carried}

    async def login_tokens(tx: Tx) -> dict[str, int]:
        return {"login_tokens": await store.delete_old_login_tokens(tx, now - LOGIN_TOKEN_GRACE)}

    async def sessions(tx: Tx) -> dict[str, int]:
        return {"sessions": await store.delete_expired_sessions(tx, now)}

    async def bodies(tx: Tx) -> dict[str, int]:
        return {"bodies": await store.blank_old_bodies(tx, now - BODY_LIFE)}

    async def outbox(tx: Tx) -> dict[str, int]:
        return {"outbox": await store.delete_old_outbox(tx, now - ROW_LIFE)}

    async def unassigned(tx: Tx) -> dict[str, int]:
        return {"matches": await store.delete_old_unassigned_matches(tx, now - ROW_LIFE)}

    async def mail_events(tx: Tx) -> dict[str, int]:
        return {"mail_events": await store.delete_old_mail_events(tx, now - MAIL_EVENT_LIFE)}

    async def audit_log(tx: Tx) -> dict[str, int]:
        return {"audit_log": await store.delete_old_audit(tx, now - AUDIT_LIFE)}

    for name, run in (
        ("login_tokens", login_tokens),
        ("sessions", sessions),
        ("bodies", bodies),
        ("deliveries", deliveries),
        ("outbox", outbox),
        ("matches", unassigned),
        ("mail_events", mail_events),
        ("audit_log", audit_log),
    ):
        await rule(name, run)
    candidates: list[UUID] = []
    try:
        async with db.transaction() as tx:
            candidates = await store.inactivity_candidates(tx, now - INACTIVE_AFTER)
    except Exception as error:
        _log.error("the inactive accounts were not read: %s", type(error).__name__)
        failed += 1
    for user_id in candidates:
        try:
            done = await _account(db, settings, user_id, now)
        except Exception as error:
            _log.error("account %s was not swept: %s", user_id, type(error).__name__)
            failed += 1
            continue
        if done == "remind":
            counts["reminded"] = counts.get("reminded", 0) + 1
        elif done == "delete":
            counts["deleted"] = counts.get("deleted", 0) + 1
    return RetentionCounts(failed=failed, **counts)
