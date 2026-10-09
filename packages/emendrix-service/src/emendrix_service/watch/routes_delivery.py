"""The Delivery tab and its two posts: saving one list's delivery, and resuming its email.

Every post names the signed-in account, and an id that is not one of its own answers 404, the
same as an id that does not exist. A successful post ends in a 303 back to the tab it came from,
carrying a notice code rather than any value the reader typed.
"""

from __future__ import annotations

from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response

from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.db import Db
from emendrix_service.db.watchlists import update_watchlist, watchlist_of
from emendrix_service.watch.delivery import delivery_page
from emendrix_service.watch.forms import Back, parse_back, parse_delivery, parse_id
from emendrix_service.watch.pages import Holder, account_holder, not_found
from emendrix_service.web.csrf import csrf_protect
from emendrix_service.web.session import SignedIn, require_user

__all__ = ["router"]

router = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])

User = Annotated[SignedIn, Depends(require_user)]
EDIT = [Depends(post_limit)]

_TABS: Final[dict[Back, str]] = {
    "watching": "/account/?list={id}&notice={notice}",
    "delivery": "/account/delivery?list={id}&notice={notice}",
    "account": "/account/settings?notice={notice}",
}


@router.get("/delivery")
async def delivery(
    request: Request,
    holder: Annotated[Holder, Depends(account_holder)],
    chosen: Annotated[str, Query(alias="list")] = "",
    notice: str = "",
) -> Response:
    return await delivery_page(request, holder, raw_list=chosen, notice=notice)


@router.post("/watchlists/{watchlist_id}/delivery", dependencies=EDIT)
async def save(request: Request, user: User, watchlist_id: str) -> Response:
    wanted = parse_id(watchlist_id)
    if wanted is None:
        return not_found(request)
    parsed = parse_delivery(await request.form())
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        mine = await watchlist_of(tx, user.user_id, wanted)
        if mine is not None and not isinstance(parsed, tuple):
            await update_watchlist(
                tx,
                user.user_id,
                wanted,
                name=mine.name,
                cadence=parsed.cadence,
                date_alerts=parsed.date_alerts,
                heartbeat=parsed.heartbeat,
                paused=parsed.paused,
            )
    if mine is None:
        return not_found(request)
    if isinstance(parsed, tuple):
        holder = Holder(user_id=user.user_id, email=user.email)
        return await delivery_page(request, holder, raw_list=str(wanted), errors=parsed)
    return _back("delivery", mine.id, "saved")


@router.post("/watchlists/{watchlist_id}/resume", dependencies=EDIT)
async def resume(request: Request, user: User, watchlist_id: str) -> Response:
    wanted = parse_id(watchlist_id)
    if wanted is None:
        return not_found(request)
    back = parse_back(await request.form())
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        mine = await watchlist_of(tx, user.user_id, wanted)
        if mine is not None and mine.paused:
            await update_watchlist(
                tx,
                user.user_id,
                wanted,
                name=mine.name,
                cadence=mine.cadence,
                date_alerts=mine.date_alerts,
                heartbeat=mine.heartbeat,
                paused=False,
            )
    if mine is None:
        return not_found(request)
    return _back(back, mine.id, "resumed")


def _back(tab: Back, watchlist_id: UUID, notice: str) -> Response:
    return RedirectResponse(_TABS[tab].format(id=watchlist_id, notice=notice), status_code=303)
