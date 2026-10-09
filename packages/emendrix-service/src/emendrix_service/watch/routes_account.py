"""The Watching tab and the list editor: create, rename, delete, and add or remove items.

Every write names the signed-in account, and an id that is not one of its own answers 404, the
same as an id that does not exist. Every successful post ends in a 303 back to the Watching tab
showing the list it changed, carrying a notice code (`?notice=`) rather than any value the
reader typed.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response

from emendrix_record.locations import human
from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.db import Db
from emendrix_service.db.enums import ItemKind
from emendrix_service.db.watchlists import (
    ActView,
    act_by_key,
    acts_roster,
    add_item,
    content_loaded,
    create_watchlist,
    delete_watchlist,
    provisions_of,
    remove_item,
    update_watchlist,
    watchlist_of,
    watchlists_for,
)
from emendrix_service.watch.forms import (
    Errors,
    parse_id,
    parse_location_field,
    parse_name,
    parse_pick,
)
from emendrix_service.watch.logic import readable, resolve_paste, roster_label, sort_provisions
from emendrix_service.watch.pages import (
    Holder,
    account_holder,
    copy,
    not_found,
    not_loaded,
    unknown_act,
)
from emendrix_service.watch.watching import watching_page
from emendrix_service.web.csrf import csrf_protect
from emendrix_service.web.session import SignedIn, require_user
from emendrix_service.web.templating import render_page

__all__ = ["router"]

router = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])

User = Annotated[SignedIn, Depends(require_user)]
EDIT = [Depends(post_limit)]
PASTE_LIMIT = 100
PASTE_EMPTY = f"Paste 1 to {PASTE_LIMIT} locations, one to a line."


def _back(watchlist_id: UUID | None, notice: str) -> Response:
    chosen = f"list={watchlist_id}&" if watchlist_id is not None else ""
    return RedirectResponse(f"/account/?{chosen}notice={notice}", status_code=303)


@router.get("/")
async def watching(
    request: Request,
    holder: Annotated[Holder, Depends(account_holder)],
    chosen: Annotated[str, Query(alias="list")] = "",
    notice: str = "",
    new: str = "",
) -> Response:
    return await watching_page(request, holder, raw_list=chosen, notice=notice, new=new == "1")


@router.post("/watchlists", dependencies=EDIT)
async def create(request: Request, user: User) -> Response:
    parsed = parse_name(await request.form())
    if isinstance(parsed, tuple):
        holder = Holder(user_id=user.user_id, email=user.email)
        return await watching_page(request, holder, new=True, errors=parsed)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        created = await create_watchlist(
            tx, user.user_id, parsed.name, request.app.state.clock.now()
        )
    return _back(created, "created")


@router.post("/watchlists/{watchlist_id}/name", dependencies=EDIT)
async def rename(request: Request, user: User, watchlist_id: str) -> Response:
    wanted = parse_id(watchlist_id)
    if wanted is None:
        return not_found(request)
    parsed = parse_name(await request.form())
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        mine = await watchlist_of(tx, user.user_id, wanted)
        if mine is not None and not isinstance(parsed, tuple):
            await update_watchlist(
                tx,
                user.user_id,
                wanted,
                name=parsed.name,
                cadence=mine.cadence,
                date_alerts=mine.date_alerts,
                heartbeat=mine.heartbeat,
                paused=mine.paused,
            )
    if mine is None:
        return not_found(request)
    if isinstance(parsed, tuple):
        holder = Holder(user_id=user.user_id, email=user.email)
        return await watching_page(request, holder, raw_list=str(wanted), errors=parsed)
    return _back(wanted, "renamed")


@router.get("/watchlists/{watchlist_id}/delete")
async def confirm_delete(request: Request, user: User, watchlist_id: str) -> Response:
    wanted = parse_id(watchlist_id)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        mine = await watchlist_of(tx, user.user_id, wanted) if wanted is not None else None
    if mine is None:
        return not_found(request)
    return render_page(request, "watch/confirm_delete.html", title="Delete a list", watchlist=mine)


@router.post("/watchlists/{watchlist_id}/delete", dependencies=EDIT)
async def delete(request: Request, user: User, watchlist_id: str) -> Response:
    wanted = parse_id(watchlist_id)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        gone = wanted is not None and await delete_watchlist(tx, user.user_id, wanted)
    return _back(None, "deleted") if gone else not_found(request)


async def _picker(
    request: Request,
    user: SignedIn,
    watchlist_id: str,
    act_key: str,
    *,
    errors: Errors = (),
    added: tuple[str, ...] = (),
    paste: str = "",
    typed: str = "",
) -> Response:
    wanted = parse_id(watchlist_id)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        lists = await watchlists_for(tx, user.user_id)
        mine = next((wl for wl in lists if wl.id == wanted), None)
        loaded = await content_loaded(tx)
        act = await act_by_key(tx, act_key) if act_key and readable(act_key) else None
        roster = await acts_roster(tx)
        provisions = await provisions_of(tx, act.corpus, act.act_key) if act else []
    if mine is None:
        return not_found(request)
    if not loaded:
        return not_loaded(request)
    if act_key and act is None:
        return unknown_act(request, act_key)
    held = {item.location for item in mine.items if act and item.act_key == act.act_key}
    heading = f"Add to {mine.name}" if len(lists) > 1 else "Add to your list"
    return render_page(
        request,
        "watch/picker.html",
        title=heading,
        heading=heading,
        back=f"/account/?list={mine.id}",
        status=400 if errors and not added else 200,
        watchlist=mine,
        act=act,
        roster=[(row.act_key, roster_label(row)) for row in roster],
        provisions=[(row, human(row.unit)) for row in sort_provisions(provisions)],
        held=held,
        errors=errors,
        added=added,
        paste=paste,
        typed=typed,
        **copy(),
    )


@router.get("/watchlists/{watchlist_id}/add")
async def picker(request: Request, user: User, watchlist_id: str, act: str = "") -> Response:
    return await _picker(request, user, watchlist_id, act)


async def _add_all(
    request: Request, user: SignedIn, watchlist_id: UUID, act: ActView, picked: list[str | None]
) -> bool | None:
    """Add every picked item; whether any was new, or None when the watchlist is not theirs."""
    db: Db = request.app.state.db
    now = request.app.state.clock.now()
    fresh = False
    async with db.transaction() as tx:
        for location in picked:
            kind = ItemKind.ACT if location is None else ItemKind.PROVISION
            added = await add_item(
                tx, user.user_id, watchlist_id, kind, act.corpus, act.act_key, location, now
            )
            if added is None:
                return None
            fresh = fresh or added
    return fresh


@router.post("/watchlists/{watchlist_id}/items", dependencies=EDIT)
async def add(request: Request, user: User, watchlist_id: str) -> Response:
    form = await request.form()
    wanted = parse_id(watchlist_id)
    act_key = form.get("act")
    mode = form.get("mode")
    if wanted is None or not isinstance(act_key, str) or not act_key:
        return not_found(request)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        act = await act_by_key(tx, act_key) if readable(act_key) else None
    if act is None:
        return unknown_act(request, act_key)
    text = form.get("lines") if mode == "paste" else form.get("location")
    text = text if isinstance(text, str) else ""
    picked: list[str | None] | Errors
    unresolved: list[str] = []
    if mode == "pick":
        picked = parse_pick(form)
    elif mode == "text":
        found = parse_location_field(text)
        picked = [found] if isinstance(found, str) else found
    elif mode == "paste":
        resolved, unresolved = resolve_paste(text, act)
        if len(resolved) + len(unresolved) > PASTE_LIMIT:
            resolved, unresolved = [], []
            text = ""
        picked = list[str | None](resolved) if resolved or unresolved else (PASTE_EMPTY,)
    else:
        picked = ("The form could not be read.",)
    if isinstance(picked, tuple):
        typed = text if mode == "text" else ""
        return await _picker(request, user, watchlist_id, act_key, errors=picked, typed=typed)
    fresh = await _add_all(request, user, wanted, act, picked) if picked else False
    if fresh is None:
        return not_found(request)
    if unresolved:
        errors = tuple(
            f"“{line[:80]}” is not a location this page can read." for line in unresolved
        )
        return await _picker(
            request,
            user,
            watchlist_id,
            act_key,
            errors=errors,
            added=tuple(human(location) for location in picked if location is not None),
            paste="\n".join(unresolved),
        )
    return _back(wanted, "added" if fresh else "already")


@router.post("/watchlists/{watchlist_id}/items/{item_id}/delete", dependencies=EDIT)
async def remove(request: Request, user: User, watchlist_id: str, item_id: str) -> Response:
    wanted, item = parse_id(watchlist_id), parse_id(item_id)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        gone = (
            wanted is not None
            and item is not None
            and await remove_item(tx, user.user_id, wanted, item)
        )
    return _back(wanted, "removed") if gone else not_found(request)
