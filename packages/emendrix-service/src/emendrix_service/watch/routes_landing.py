"""The landing every "Watch this" link opens: `/account/watch?act=<key>[&loc=<location>]`.

The act is named by its key, as the site's link sends it, and must be one `content` holds; the
location is read by the documented parser or shown back unresolved, never guessed. A visitor
who is signed out is asked for an address and sent a sign-up link carrying the item, and sees
the same "check your inbox" page whatever became of the request. A reader who is signed in adds
the item with one button.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from emendrix_service.auth.logic import WatchIntent
from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.auth.service import request_link_from
from emendrix_service.db import Db
from emendrix_service.db.accounts import FIRST_WATCHLIST
from emendrix_service.db.enums import ItemKind, TokenPurpose
from emendrix_service.db.watchlists import (
    ActView,
    act_by_key,
    add_item,
    content_loaded,
    create_watchlist,
    watchlists_for,
)
from emendrix_service.watch.forms import Errors, parse_id, parse_signup
from emendrix_service.watch.logic import read_location, readable, watch_label
from emendrix_service.watch.pages import copy, not_found, not_loaded, unknown_act
from emendrix_service.web.csrf import csrf_protect
from emendrix_service.web.session import SignedIn, current_user
from emendrix_service.web.templating import render_page

__all__ = ["router"]

router = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])

Reader = Annotated[SignedIn | None, Depends(current_user)]
NEW = "new"
"""The watchlist field's value when the reader has none and one is to be made."""


async def _act(request: Request, act_key: str) -> ActView | Response:
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        if not await content_loaded(tx):
            return not_loaded(request)
        act = await act_by_key(tx, act_key) if act_key and readable(act_key) else None
    return act if act is not None else unknown_act(request, act_key)


async def _landing(
    request: Request,
    reader: SignedIn | None,
    act: ActView,
    loc: str,
    *,
    email: str = "",
    errors: Errors = (),
) -> Response:
    location = read_location(loc) if loc else None
    common: dict[str, object] = {
        "act": act,
        "location": location,
        "unresolved": " ".join(loc.split())[:80] if loc and location is None else "",
        "label": watch_label(act, location),
        "errors": errors,
        **copy(),
    }
    title = f"Watch {common['label']}"
    status = 400 if errors else 200
    if reader is None:
        settings = request.app.state.settings
        landing = WatchIntent(corpus=act.corpus, act_key=act.act_key, location=location).landing()
        return render_page(
            request,
            "watch/watch_signed_out.html",
            title=title,
            status=status,
            email=email,
            signup_open=settings.signup_open,
            signin=f"/account/signin?next={quote(landing, safe='/')}",
            **common,
        )
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        watchlists = await watchlists_for(tx, reader.user_id)
    holding = [
        wl.name
        for wl in watchlists
        if any(
            (i.corpus, i.act_key, i.location) == (act.corpus, act.act_key, location)
            for i in wl.items
        )
    ]
    return render_page(
        request,
        "watch/watch_signed_in.html",
        title=title,
        status=status,
        watchlists=watchlists,
        holding=holding,
        new=NEW,
        **common,
    )


@router.get("/watch")
async def landing(request: Request, reader: Reader, act: str = "", loc: str = "") -> Response:
    found = await _act(request, act)
    if isinstance(found, Response):
        return found
    return await _landing(request, reader, found, loc)


@router.post("/watch")
async def watch(request: Request, reader: Reader) -> Response:
    form = await request.form()
    act_key, loc = form.get("act"), form.get("loc")
    found = await _act(request, act_key if isinstance(act_key, str) else "")
    if isinstance(found, Response):
        return found
    loc = loc if isinstance(loc, str) else ""
    location = read_location(loc) if loc else None
    if loc and location is None:
        return await _landing(request, reader, found, loc)
    if reader is None:
        signup = parse_signup(form)
        if isinstance(signup, tuple):
            typed = form.get("email")
            email = typed if isinstance(typed, str) else ""
            return await _landing(request, reader, found, loc, email=email, errors=signup)
        intent = WatchIntent(corpus=found.corpus, act_key=found.act_key, location=location)
        send = await request_link_from(
            request, email=signup.email, purpose=TokenPurpose.SIGNUP, intent=intent
        )
        response = render_page(request, "auth/check_inbox.html", title="Check your inbox")
        response.background = send
        return response
    await post_limit(request)
    chosen = form.get("watchlist")
    db: Db = request.app.state.db
    now = request.app.state.clock.now()
    kind = ItemKind.ACT if location is None else ItemKind.PROVISION
    async with db.transaction() as tx:
        if chosen == NEW and not await watchlists_for(tx, reader.user_id):
            target = await create_watchlist(tx, reader.user_id, FIRST_WATCHLIST, now)
        else:
            target_id = parse_id(chosen) if isinstance(chosen, str) else None
            if target_id is None:
                return not_found(request)
            target = target_id
        added = await add_item(
            tx, reader.user_id, target, kind, found.corpus, found.act_key, location, now
        )
    if added is None:
        return not_found(request)
    notice = "added" if added else "already"
    return RedirectResponse(f"/account/?notice={notice}#wl-{target}", status_code=303)
