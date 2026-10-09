"""The mail provider's delivery events, received under `/u/hooks/`.

`POST /u/hooks/scaleway/{secret}` is authenticated by its path secret alone, compared in
constant time, over TLS. A missing or wrong secret answers 404, so the route does not show that
it exists. The body is read raw (the provider posts JSON as `text/plain`) and capped at 64 KiB.

A subscription confirmation is logged once, at WARNING, with the address the operator must open
by hand to confirm it; the service never fetches it, because the transport is the only module
that connects out. Each event is recorded in its own transaction. A hard bounce or a complaint
suppresses the address and suspends its account, and so does a third soft bounce within seven
days. Log lines carry counts, never an address.
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta
from typing import Final

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from emendrix_service.clock import Clock
from emendrix_service.db import Db
from emendrix_service.db.enums import MailEventKind, SuppressionReason
from emendrix_service.db.suppressions import (
    email_sha256,
    record_event,
    soft_bounces_since,
    suppress,
    suspend_users_with,
)
from emendrix_service.mail.scaleway import Confirmation, ProviderEvent, parse_envelope
from emendrix_service.settings import ServiceSettings

__all__ = [
    "BODY_LIMIT",
    "SCALEWAY_PATH",
    "SOFT_BOUNCE_LIMIT",
    "SOFT_BOUNCE_WINDOW",
    "apply_event",
    "router",
]

SCALEWAY_PATH: Final = "/u/hooks/scaleway/{secret}"

BODY_LIMIT: Final = 64 * 1024
"""The largest body read; an SNS envelope of one event is a few KiB."""

SOFT_BOUNCE_LIMIT: Final = 3
SOFT_BOUNCE_WINDOW: Final = timedelta(days=7)
"""Three soft bounces within seven days suppress an address."""

IMMEDIATE: Final = {
    MailEventKind.HARD_BOUNCE: SuppressionReason.HARD_BOUNCE,
    MailEventKind.COMPLAINT: SuppressionReason.COMPLAINT,
}

log = logging.getLogger(__name__)

router = APIRouter()


def _not_found() -> PlainTextResponse:
    return PlainTextResponse("Not Found", status_code=404)


def _authentic(settings: ServiceSettings, secret: str) -> bool:
    expected = settings.webhook_secret
    if expected is None:
        return False
    return hmac.compare_digest(secret.encode("utf-8"), expected.get_secret_value().encode("utf-8"))


async def _body(request: Request) -> bytes | None:
    """The body, or `None` once it passes `BODY_LIMIT`."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > BODY_LIMIT:
        return None
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > BODY_LIMIT:
            return None
    return bytes(body)


async def apply_event(db: Db, event: ProviderEvent, now: datetime) -> bool:
    """Record one event and suppress its address when it calls for it; `True` when recorded.

    An event of an ignored type, or naming no recipient, is not recorded.
    """
    if event.kind is None or event.recipient is None:
        return False
    digest = email_sha256(event.recipient)
    async with db.transaction() as tx:
        await record_event(tx, digest, event.kind, event.provider_message_id, event.at or now)
        reason = IMMEDIATE.get(event.kind)
        if reason is None and event.kind == MailEventKind.SOFT_BOUNCE:
            recent = await soft_bounces_since(tx, digest, now - SOFT_BOUNCE_WINDOW)
            if recent >= SOFT_BOUNCE_LIMIT:
                reason = SuppressionReason.SOFT_BOUNCES
        if reason is not None:
            await suppress(tx, digest, reason, now)
            await suspend_users_with(tx, digest)
    return True


@router.post(SCALEWAY_PATH, include_in_schema=False)
async def scaleway(secret: str, request: Request) -> PlainTextResponse:
    """Receive one post from the provider's Topics and Events subscription."""
    if not _authentic(request.app.state.settings, secret):
        return _not_found()
    body = await _body(request)
    if body is None:
        return PlainTextResponse("Content Too Large", status_code=413)
    envelope = parse_envelope(body)
    if envelope is None:
        return PlainTextResponse("Bad Request", status_code=400)
    if isinstance(envelope, Confirmation):
        log.warning(
            "the mail provider asks to confirm its webhook subscription; open this address "
            "once, by hand, to confirm it: %s",
            envelope.subscribe_url,
        )
        return PlainTextResponse("ok")
    db: Db = request.app.state.db
    clock: Clock = request.app.state.clock
    recorded = 0
    for event in envelope.events:
        recorded += await apply_event(db, event, clock.now())
    log.info(
        "mail provider events: %d received, %d recorded, %d ignored",
        len(envelope.events),
        recorded,
        len(envelope.events) - recorded,
    )
    return PlainTextResponse("ok")
