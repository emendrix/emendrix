"""The landing a "Watch this substance" link opens: `/account/watch?substance=cas-50-00-0`.

The value is read by `watch.substances.read_substance` and never guessed: a value that is no
number is shown back with the reason, one that reads both as a CAS and an EC number offers both,
and a CLP Index No is refused with the numbers its row is recorded to print. A visitor who is
signed out is sent a sign-up link that returns them to this landing once confirmed, signed in,
so the number is one button away; a reader who is signed in adds it with that button.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote
from uuid import UUID

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from starlette.datastructures import FormData

from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.auth.service import request_link_from
from emendrix_service.db import Db, Tx
from emendrix_service.db.accounts import FIRST_WATCHLIST
from emendrix_service.db.enums import ItemKind, TokenPurpose
from emendrix_service.db.watchlists import (
    add_item,
    create_watchlist,
    identifiers_of_row,
    watchlists_for,
)
from emendrix_service.notify.matching import substance_label
from emendrix_service.watch.forms import Errors, parse_id, parse_signup
from emendrix_service.watch.pages import copy, not_found
from emendrix_service.watch.substances import (
    INDEX_NOT_WATCHED,
    address,
    landing_path,
    read_substance,
    substance_page,
)
from emendrix_service.web.session import SignedIn
from emendrix_service.web.templating import render_page

__all__ = ["NEW", "substance_landing", "substance_watch", "target_watchlist"]

NEW = "new"
"""The watchlist field's value when the reader has none and one is to be made."""


async def target_watchlist(tx: Tx, user_id: UUID, chosen: object, now: datetime) -> UUID | None:
    """The list a landing's form names: a new first one when asked and the reader has none."""
    if chosen == NEW and not await watchlists_for(tx, user_id):
        return await create_watchlist(tx, user_id, FIRST_WATCHLIST, now)
    return parse_id(chosen) if isinstance(chosen, str) else None


async def _not_watchable(request: Request, raw: str) -> Response:
    reading = read_substance(raw)
    site_url: str = request.app.state.settings.site_url
    printed: list[tuple[str, str, str]] = []
    if reading.index is not None:
        db: Db = request.app.state.db
        async with db.transaction() as tx:
            found = await identifiers_of_row(tx, reading.index)
        printed = [
            (substance_label(i), substance_page(site_url, i), landing_path(i)) for i in found
        ]
    choices = [(substance_label(i), landing_path(i)) for i in reading.identifiers]
    return render_page(
        request,
        "watch/substance_unknown.html",
        title="Not a number to watch",
        status=400 if reading.outcome == "invalid" else 200,
        reading=reading,
        choices=choices,
        printed=printed,
        index_not_watched=INDEX_NOT_WATCHED,
        lookup=f"{site_url}/substances/",
    )


async def substance_landing(
    request: Request,
    reader: SignedIn | None,
    raw: str,
    *,
    email: str = "",
    errors: Errors = (),
) -> Response:
    """The landing for one number, signed in or out; a value that is none says why."""
    reading = read_substance(raw)
    if reading.outcome != "watchable":
        return await _not_watchable(request, raw)
    identifier = reading.identifiers[0]
    label = substance_label(identifier)
    common: dict[str, object] = {
        "substance": address(identifier),
        "label": label,
        "unresolved": "",
        "errors": errors,
        **copy(),
    }
    status = 400 if errors else 200
    if reader is None:
        signup_open = request.app.state.settings.signup_open
        return render_page(
            request,
            "watch/watch_signed_out.html",
            title=f"Watch {label}",
            status=status,
            email=email,
            signup_open=signup_open,
            signin=f"/account/signin?next={quote(landing_path(identifier), safe='/')}",
            **common,
        )
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        watchlists = await watchlists_for(tx, reader.user_id)
    holding = [wl.name for wl in watchlists if any(i.identifier == identifier for i in wl.items)]
    return render_page(
        request,
        "watch/watch_signed_in.html",
        title=f"Watch {label}",
        status=status,
        watchlists=watchlists,
        holding=holding,
        new=NEW,
        **common,
    )


async def substance_watch(
    request: Request, reader: SignedIn | None, form: FormData, raw: str
) -> Response:
    """The landing's form posted: a sign-up link for a visitor, else the number added."""
    reading = read_substance(raw)
    if reading.outcome != "watchable":
        return await _not_watchable(request, raw)
    identifier = reading.identifiers[0]
    if reader is None:
        signup = parse_signup(form)
        if isinstance(signup, tuple):
            typed = form.get("email")
            email = typed if isinstance(typed, str) else ""
            return await substance_landing(request, reader, raw, email=email, errors=signup)
        send = await request_link_from(
            request,
            email=signup.email,
            purpose=TokenPurpose.SIGNUP,
            next_path=landing_path(identifier),
        )
        response = render_page(request, "auth/check_inbox.html", title="Check your inbox")
        response.background = send
        return response
    await post_limit(request)
    db: Db = request.app.state.db
    now = request.app.state.clock.now()
    async with db.transaction() as tx:
        target = await target_watchlist(tx, reader.user_id, form.get("watchlist"), now)
        added = (
            await add_item(
                tx,
                reader.user_id,
                target,
                ItemKind.SUBSTANCE,
                None,
                None,
                None,
                now,
                identifier=identifier,
            )
            if target is not None
            else None
        )
    if target is None or added is None:
        return not_found(request)
    notice = "added" if added else "already"
    return RedirectResponse(f"/account/?list={target}&notice={notice}", status_code=303)
