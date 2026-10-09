"""Who is signed in: the session cookie, checked against its stored hash on each request.

A session lives 30 days from its last use. Sliding the expiry is a write, so it happens at most
once an hour per session, and the browser's cookie is renewed in the same response by
`CookieWriter`. An expired session or a suspended account reads as signed out.

The header names the reader only on a page whose route resolved who reads it: `current_user`
notes an active one with `remember_reader`, and a route that admits a suspended account can
note it the same way. Every other page (sign-in, privacy, an error) shows the signed-out link,
which is intended: such a page is the same whoever asks for it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final
from urllib.parse import quote
from uuid import UUID

from fastapi import Request, Response
from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.auth.logic import SESSION_LIFE, session_expiry
from emendrix_service.clock import Clock
from emendrix_service.db import Db
from emendrix_service.db.accounts import session_user, touch_session
from emendrix_service.db.enums import UserStatus
from emendrix_service.web.csrf import SESSION_COOKIE, session_hash

__all__ = [
    "SLIDE_EVERY",
    "SignInRequired",
    "SignedIn",
    "clear_session_cookie",
    "current_user",
    "reader_email",
    "remember_reader",
    "require_user",
    "set_session_cookie",
]

SLIDE_EVERY: Final = timedelta(hours=1)

REFRESH: Final = "emendrix_session_refresh"
"""The request-state key holding a session token whose cookie is to be sent again."""

_CHECKED: Final = "emendrix_signed_in"

_READER: Final = "emendrix_reader_email"


class SignedIn(BaseModel):
    """The account a request is signed in to."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(description="The account's id.")
    email: str = Field(description="The account's address, for showing to its owner only.")
    session_hash: bytes = Field(description="The sha256 of this browser's session cookie.")


class SignInRequired(Exception):
    """Raised by `require_user`; answered with a 303 to the sign-in page."""

    def __init__(self, next_path: str) -> None:
        super().__init__("sign-in required")
        self.next_path = next_path

    def location(self) -> str:
        return f"/account/signin?next={quote(self.next_path, safe='/')}"


def set_session_cookie(response: Response, token: str) -> None:
    """Keep this browser signed in with `token` for the life of a session."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFE.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Make this browser forget its session cookie."""
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


async def current_user(request: Request) -> SignedIn | None:
    """The signed-in account, or None. Read once per request and kept on its state."""
    if hasattr(request.state, _CHECKED):
        found: SignedIn | None = getattr(request.state, _CHECKED)
        return found
    signed_in = await _load(request)
    setattr(request.state, _CHECKED, signed_in)
    if signed_in is not None:
        remember_reader(request, signed_in.email)
    return signed_in


def remember_reader(request: Request, email: str) -> None:
    """Note who this request's page is for, so the header can name them."""
    setattr(request.state, _READER, email)


def reader_email(request: Request) -> str | None:
    """The address `remember_reader` noted for this request, if any."""
    email: str | None = getattr(request.state, _READER, None)
    return email


async def _load(request: Request) -> SignedIn | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    hashed = session_hash(token)
    db: Db = request.app.state.db
    clock: Clock = request.app.state.clock
    now = clock.now()
    async with db.transaction() as tx:
        row = await session_user(tx, hashed, now)
        if row is None or row.status is not UserStatus.ACTIVE:
            return None
        if now - row.last_used_at >= SLIDE_EVERY:
            await touch_session(tx, hashed, now, session_expiry(now), user_id=row.user_id)
            setattr(request.state, REFRESH, token)
    return SignedIn(user_id=row.user_id, email=row.email, session_hash=hashed)


async def require_user(request: Request) -> SignedIn:
    """The signed-in account; a visitor who is not signed in is sent to sign in first."""
    signed_in = await current_user(request)
    if signed_in is None:
        path = request.url.path
        if request.method == "GET" and request.url.query:
            path = f"{path}?{request.url.query}"
        raise SignInRequired(path if request.method == "GET" else "/account/")
    return signed_in
