"""The personal feed under `/u/`, and minting its address under `/account/`.

A feed is addressed by a secret token, never by a session: a feed reader holds no cookie, and
the fetch reads none and sets none. The token is 128 random bits stored only as its sha256, so
the database cannot show it again; replacing it makes the old address answer 410, the same as an
address that was never issued, since both are gone. The request log drops the token from the
path (`web.security.loggable_path`), so it is written nowhere.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from emendrix_service.auth.ratelimit import post_limit
from emendrix_service.db import Db
from emendrix_service.db.accounts import audit
from emendrix_service.db.enums import AuditAction
from emendrix_service.db.feed import (
    recent_changes_for_acts,
    set_feed_token,
    touch_seen,
    watchlist_by_feed_hash,
)
from emendrix_service.db.notify import watchlist_items
from emendrix_service.feed.logic import feed_entries
from emendrix_service.feed.model import FeedHead
from emendrix_service.feed.render import atom
from emendrix_service.watch.forms import parse_id
from emendrix_service.web.csrf import csrf_protect
from emendrix_service.web.errors import render_error
from emendrix_service.web.session import SignedIn, require_user
from emendrix_service.web.templating import render_page

__all__ = ["ATOM_TYPE", "feed_hash", "router"]

ATOM_TYPE: Final = "application/atom+xml; charset=utf-8"

User = Annotated[SignedIn, Depends(require_user)]

links = APIRouter(prefix="/u")
account = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])


def feed_hash(token: str) -> bytes:
    """The sha256 a feed token is stored under."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def _feed_url(site_url: str, token: str) -> str:
    return f"{site_url}/u/feed/{token}.xml"


@links.get("/feed/{token}.xml")
async def feed(request: Request, token: str) -> Response:
    state = request.app.state
    site_url: str = state.settings.site_url
    db: Db = state.db
    async with db.transaction() as tx:
        watchlist = await watchlist_by_feed_hash(tx, feed_hash(token))
        if watchlist is None:
            return render_error(request, 410)
        items = await watchlist_items(tx, watchlist.id)
        changes = await recent_changes_for_acts(tx, {(i.corpus, i.act_key) for i in items})
        await touch_seen(tx, watchlist.user_id, state.clock.now())
    head = FeedHead(watchlist_id=watchlist.id, name=watchlist.name, created_at=watchlist.created_at)
    body = atom(
        head,
        feed_entries(changes, items, site_url=site_url),
        site_url=site_url,
        feed_url=_feed_url(site_url, token),
    )
    return Response(body, media_type=ATOM_TYPE, headers={"cache-control": "private, no-store"})


@account.post("/feed/rotate", dependencies=[Depends(post_limit)])
async def rotate(request: Request, user: User) -> Response:
    form = await request.form()
    wanted = form.get("watchlist_id")
    watchlist_id = parse_id(wanted) if isinstance(wanted, str) else None
    if watchlist_id is None:
        return render_error(request, 404)
    token = secrets.token_urlsafe(16)
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        mine = await set_feed_token(tx, user.user_id, watchlist_id, feed_hash(token))
        if mine:
            await audit(tx, user.user_id, AuditAction.FEED_ROTATE, request.app.state.clock.now())
    if not mine:
        return render_error(request, 404)
    return render_page(
        request,
        "feed/rotated.html",
        title="Your personal feed",
        feed_url=_feed_url(request.app.state.settings.site_url, token),
        watchlist_id=watchlist_id,
    )


router = APIRouter()
router.include_router(links)
router.include_router(account)
