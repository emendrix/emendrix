"""Sending a login link: the I/O around the rules in `logic`. Confirming one is `confirm`.

A link request looks up the address and counts its recent links in every case, so a known and
an unknown address cost the same queries; only a request that will send anything writes. The
email is queued in the outbox in the same transaction as its token and sent after the commit; a
send that fails leaves the row queued for the drain to retry. A page sends after its response
has gone out, so the relay's round trip never shows in how long the page took.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final
from urllib.parse import quote
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from emendrix_record.locations import human
from emendrix_service.auth.logic import (
    LINK_LIFE,
    Silent,
    WatchIntent,
    consent_version,
    decide_link,
    link_expiry,
    local_path,
    may_sign_up,
    new_token,
)
from emendrix_service.auth.ratelimit import SlidingWindow, link_window
from emendrix_service.clock import Clock
from emendrix_service.db import Db, Tx
from emendrix_service.db.accounts import (
    act_label,
    count_recent_tokens,
    create_login_token,
    mark_outbox_sent,
    user_by_email,
)
from emendrix_service.db.enums import OutboxPurpose, TokenPurpose, UserStatus
from emendrix_service.db.outbox import enqueue
from emendrix_service.mail.port import Mailer, OutgoingMail, send_now
from emendrix_service.settings import ServiceSettings, variable
from emendrix_service.web.client import client_ip
from emendrix_service.web.templating import render_mail

__all__ = [
    "SIGNIN_SUBJECT",
    "Queued",
    "deliver",
    "notice_version",
    "queue_link",
    "request_link",
    "request_link_from",
]

SIGNIN_SUBJECT: Final = "Sign in to Emendrix"
HOUR: Final = timedelta(hours=1)

logger = logging.getLogger(__name__)


def notice_version(settings: ServiceSettings) -> str | None:
    """The version of the configured privacy notice, or None when there is none to accept."""
    if settings.privacy_notice is None:
        return None
    try:
        return consent_version(settings.privacy_notice.read_bytes())
    except OSError:
        return None


async def _watch_label(tx: Tx, intent: WatchIntent | None) -> str:
    """`Annex I of MDR`: what a sign-up link offers to watch, in the catalogue's own words."""
    if intent is None:
        return ""
    act = await act_label(tx, intent.corpus, intent.act_key) or intent.act_key
    return f"{human(intent.location)} of {act}" if intent.location else act


class Queued(BaseModel):
    """A login link written to the outbox and not yet handed to the relay."""

    model_config = ConfigDict(frozen=True)

    purpose: TokenPurpose = Field(description="What the link does.")
    outbox_id: UUID = Field(description="The outbox row holding the email.")
    mail: OutgoingMail = Field(description="The email, as queued.")


async def queue_link(
    db: Db,
    settings: ServiceSettings,
    clock: Clock,
    *,
    email: str,
    purpose: TokenPurpose,
    intent: WatchIntent | None,
    ip: str,
    window: SlidingWindow,
    next_path: str | None = None,
) -> Queued | Silent:
    """Queue a login link for `email` when the rules allow one; else why nothing was queued.

    `email` is already normalised. Whatever this returns, the reader is shown the same page.
    """
    if not window.hit(ip):
        logger.info("link request: %s", Silent.IP_LIMITED)
        return Silent.IP_LIMITED
    now = clock.now()
    async with db.transaction() as tx:
        user = await user_by_email(tx, email)
        recent = await count_recent_tokens(tx, email, now - HOUR)
        decided = decide_link(
            asked=purpose,
            known=user is not None,
            active=user is not None and user.status is UserStatus.ACTIVE,
            may_sign_up=may_sign_up(
                email, signup_open=settings.signup_open, allowlist=settings.signup_allowlist
            ),
            has_notice=notice_version(settings) is not None,
            recent=recent,
        )
        if isinstance(decided, Silent):
            logger.info("link request: %s", decided)
            return decided
        token, token_hash = new_token()
        await create_login_token(
            tx,
            token_hash=token_hash,
            email=email,
            purpose=decided,
            intent=intent.model_dump() if intent is not None else None,
            now=now,
            expires_at=link_expiry(now),
        )
        link = f"{settings.site_url}/account/confirm/{token}"
        if (target := local_path(next_path)) is not None:
            link = f"{link}?next={quote(target, safe='/')}"
        if decided is TokenPurpose.SIGNUP:
            label = await _watch_label(tx, intent)
            subject = (
                f"Confirm your address to start watching {label}"
                if label
                else "Confirm your address for Emendrix"
            )
        else:
            label, subject = "", SIGNIN_SUBJECT
        text, markup = render_mail(
            f"auth/mail_{decided.value}",
            site_url=settings.site_url,
            link=link,
            label=label,
            minutes=int(LINK_LIFE.total_seconds() // 60),
            unsubscribe=None,
        )
        mail = OutgoingMail(to=email, subject=subject, text=text, html=markup)
        outbox_id = await enqueue(
            tx,
            purpose=OutboxPurpose(decided.value),
            to=email,
            mail=mail,
            user_id=user.id if user is not None else None,
            now=now,
        )
    return Queued(purpose=decided, outbox_id=outbox_id, mail=mail)


async def deliver(
    db: Db, mailer: Mailer, settings: ServiceSettings, clock: Clock, queued: Queued
) -> None:
    """Hand a queued link to the relay; one that is refused stays queued for the drain."""
    if settings.mail_from is None:
        logger.warning("link request: queued; %s is not set", variable("mail_from"))
        return
    result = await send_now(mailer, queued.mail, sender=settings.mail_from)
    if result.accepted:
        async with db.transaction() as tx:
            await mark_outbox_sent(tx, queued.outbox_id, result.provider_message_id, clock.now())
        logger.info("link request: %s link sent", queued.purpose)
    else:
        logger.warning("link request: %s link queued; the relay refused it", queued.purpose)


async def request_link(
    db: Db,
    mailer: Mailer,
    settings: ServiceSettings,
    clock: Clock,
    *,
    email: str,
    purpose: TokenPurpose,
    intent: WatchIntent | None,
    ip: str,
    window: SlidingWindow,
    next_path: str | None = None,
) -> TokenPurpose | Silent:
    """Queue and send a login link in one go; what was sent, or why nothing was."""
    queued = await queue_link(
        db,
        settings,
        clock,
        email=email,
        purpose=purpose,
        intent=intent,
        ip=ip,
        window=window,
        next_path=next_path,
    )
    if isinstance(queued, Silent):
        return queued
    await deliver(db, mailer, settings, clock, queued)
    return queued.purpose


async def request_link_from(
    request: Request,
    *,
    email: str,
    purpose: TokenPurpose,
    intent: WatchIntent | None = None,
    next_path: str | None = None,
) -> BackgroundTask | None:
    """Queue a link for the address a form was given; the send, to run after the response.

    The caller sets the returned task as its response's `background`. Sending after the page
    has gone out keeps the relay's round trip out of the response time, which would otherwise
    tell a known address (a link is sent) from an unknown one (nothing is).
    """
    state = request.app.state
    queued = await queue_link(
        state.db,
        state.settings,
        state.clock,
        email=email,
        purpose=purpose,
        intent=intent,
        ip=client_ip(request, state.settings),
        window=link_window(request),
        next_path=next_path,
    )
    if isinstance(queued, Silent):
        return None
    return BackgroundTask(deliver, state.db, state.mailer, state.settings, state.clock, queued)
