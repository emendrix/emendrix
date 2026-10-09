"""Who an account tab is for, and the shared pages: not found, act unknown, not loaded.

The account tabs are the pages a suspended account still reaches. Signing in treats a
suspended account as signed out, so the banner that explains the suspension could never be
seen through `require_user`; here a live session of a suspended account is admitted to a
read-only view of its own account, where it can still sign out, export and delete.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db import Db
from emendrix_service.db.accounts import session_user
from emendrix_service.db.enums import UserStatus
from emendrix_service.watch.forms import LOCATION_FORMS, NAME_LIMIT
from emendrix_service.watch.logic import WHAT_A_WATCH_DOES
from emendrix_service.web.csrf import SESSION_COOKIE, session_hash
from emendrix_service.web.session import SignedIn, SignInRequired, current_user, remember_reader
from emendrix_service.web.templating import render_page

__all__ = [
    "Holder",
    "account_holder",
    "copy",
    "not_found",
    "not_loaded",
    "unknown_act",
]


class Holder(BaseModel):
    """Whose account page this is."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(description="The account's id.")
    email: str = Field(description="The account's address, shown to its owner only.")


def copy() -> dict[str, object]:
    """The fixed wording every watch page may show."""
    return {
        "what_a_watch_does": WHAT_A_WATCH_DOES,
        "name_limit": NAME_LIMIT,
        "location_forms": LOCATION_FORMS,
    }


async def account_holder(request: Request) -> Holder:
    """The signed-in account, or a suspended one still holding a live session.

    Either way the header names the reader: `current_user` notes an active one, and a suspended
    one is noted here, because signing in treats it as signed out.
    """
    signed_in: SignedIn | None = await current_user(request)
    if signed_in is not None:
        return Holder(user_id=signed_in.user_id, email=signed_in.email)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db: Db = request.app.state.db
        async with db.transaction() as tx:
            row = await session_user(tx, session_hash(token), request.app.state.clock.now())
        if row is not None and row.status is UserStatus.SUSPENDED:
            remember_reader(request, row.email)
            return Holder(user_id=row.user_id, email=row.email)
    raise SignInRequired("/account/")


def not_found(request: Request) -> Response:
    """The 404 page for a watchlist or item that is not the reader's own."""
    return render_page(
        request,
        "web/error.html",
        title="Page not found",
        status=404,
        heading="Page not found",
        message="There is no account page at this address.",
        error_id=None,
    )


def unknown_act(request: Request, act: str) -> Response:
    """The 404 page for an act this site does not watch."""
    return render_page(
        request, "watch/unknown_act.html", title="Act not found", status=404, act=act[:80]
    )


def not_loaded(request: Request) -> Response:
    """What a watch page says before the record has ever been loaded."""
    return render_page(request, "watch/not_loaded.html", title="Not available yet", status=503)
