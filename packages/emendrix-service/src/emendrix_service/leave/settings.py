"""The Account tab: who is signed in, signing out, the reader's data, and deleting the account.

A suspended account sees the whole tab: suspension stops mail, and signing out, exporting and
deleting must work whatever the mail does. Paused banners belong to the tabs that hold the lists,
so this one shows none.
"""

from __future__ import annotations

from typing import Final

from fastapi import Request
from fastapi.responses import Response

from emendrix_service.db import Db
from emendrix_service.db.enums import UserStatus
from emendrix_service.db.watchlists import user_status, watchlists_for
from emendrix_service.watch.pages import Holder
from emendrix_service.web.frame import AccountFrame, frame_context
from emendrix_service.web.templating import render_page

__all__ = ["HEADING", "LEDE", "TITLE", "settings_page"]

TITLE: Final = "Your account"
HEADING: Final = "You and your data"
LEDE: Final = "Your sign-in, and everything the service holds about you."


async def settings_page(request: Request, holder: Holder) -> Response:
    """The Account tab for `holder`, inside the account frame."""
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        status = await user_status(tx, holder.user_id)
        watchlists = await watchlists_for(tx, holder.user_id)
    suspended = status is UserStatus.SUSPENDED
    frame = AccountFrame(
        tab="account",
        heading=HEADING,
        lede=LEDE,
        email=holder.email,
        item_count=sum(len(watchlist.items) for watchlist in watchlists),
        list_query="",
        suspended=suspended,
        paused=(),
        notice=None,
    )
    return render_page(
        request,
        "leave/settings.html",
        title=TITLE,
        status=200,
        account_current=True,
        email=holder.email,
        suspended=suspended,
        **frame_context(frame),
    )
