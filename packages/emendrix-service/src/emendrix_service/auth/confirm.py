"""Confirming a login link: the confirm page's POST, never its GET, consumes the link.

Mail scanners fetch every link they see, so a GET that consumed the link would sign the scanner
in and leave the reader a dead link. Confirming a sign-up makes the account; confirming a
sign-in opens a session on the account the link was sent for.
"""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from emendrix_service.auth.logic import (
    WatchIntent,
    hash_token,
    local_path,
    new_token,
    session_expiry,
)
from emendrix_service.auth.service import notice_version
from emendrix_service.clock import Clock
from emendrix_service.db import Db
from emendrix_service.db.accounts import (
    consume_token,
    create_first_watchlist,
    create_session,
    create_user_with_consents,
    mark_signed_in,
    user_by_email,
)
from emendrix_service.db.enums import TokenPurpose, UserStatus
from emendrix_service.settings import ServiceSettings

__all__ = ["Confirmed", "Refused", "confirm"]

logger = logging.getLogger(__name__)


class Confirmed(BaseModel):
    """A link that signed a browser in."""

    model_config = ConfigDict(frozen=True)

    session_token: str = Field(description="The new session's cookie value.")
    user_id: UUID = Field(description="The account signed in to.")
    signed_up: bool = Field(description="Whether the account was made by this link.")
    next_path: str = Field(description="The local path to send the browser to.")


class Refused(BaseModel):
    """A link that was unknown, used or expired; the reader is told only that."""

    model_config = ConfigDict(frozen=True)


class _Undo(Exception):
    """Rolls a confirmation back so the link stays unused."""


def _intent(stored: dict[str, object] | None) -> WatchIntent | None:
    if stored is None:
        return None
    try:
        return WatchIntent.model_validate(stored)
    except ValidationError:
        return None


async def confirm(
    db: Db,
    settings: ServiceSettings,
    clock: Clock,
    token_text: str,
    *,
    next_path: str | None = None,
) -> Confirmed | Refused:
    """Consume a link and open a session for it, making the account first for a sign-up.

    A sign-up is one transaction: the account, its two consents, the first watchlist with the
    link's watch item and the session commit together or not at all. A sign-up confirmed while
    no privacy notice is configured is rolled back, leaving the link unused.
    """
    version = notice_version(settings)
    now = clock.now()
    try:
        async with db.transaction() as tx:
            row = await consume_token(tx, hash_token(token_text), now)
            if row is None:
                logger.info("confirm: refused")
                return Refused()
            intent = _intent(row.intent)
            user = await user_by_email(tx, row.email)
            signed_up = False
            if user is None and row.purpose is TokenPurpose.SIGNUP:
                if version is None:
                    raise _Undo
                user = await create_user_with_consents(tx, row.email, version, now)
                if user is None:
                    raise _Undo
                signed_up = True
                if intent is not None:
                    await create_first_watchlist(
                        tx,
                        user.id,
                        corpus=intent.corpus,
                        act_key=intent.act_key,
                        location=intent.location,
                        now=now,
                    )
            elif user is None or user.status is not UserStatus.ACTIVE:
                logger.info("confirm: refused")
                return Refused()
            else:
                await mark_signed_in(tx, user.id, now)
            token, token_hash = new_token()
            await create_session(
                tx, id_hash=token_hash, user_id=user.id, now=now, expires_at=session_expiry(now)
            )
    except _Undo:
        logger.warning("confirm: sign-up not completed; the link stays unused")
        return Refused()
    landing = intent.landing() if intent is not None and not signed_up else "/account/"
    logger.info("confirm: user %s %s", user.id, "signed up" if signed_up else "signed in")
    return Confirmed(
        session_token=token,
        user_id=user.id,
        signed_up=signed_up,
        next_path=local_path(next_path) or landing,
    )
