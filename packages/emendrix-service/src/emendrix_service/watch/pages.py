"""The account page and the pages every watch route shares: not found, act unknown, not loaded.

The account page is the one page a suspended account still reaches. Signing in treats a
suspended account as signed out, so the banner that explains the suspension could never be
seen through `require_user`; here a live session of a suspended account is admitted to a
read-only view of its own account, with no form but signing out.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db import Db
from emendrix_service.db.accounts import session_user
from emendrix_service.db.enums import Cadence, UserStatus
from emendrix_service.db.watchlists import (
    ActKey,
    WatchlistView,
    acts_by_key,
    provisions_by_act,
    user_status,
    watchlists_for,
)
from emendrix_service.watch.forms import LOCATION_FORMS, NAME_LIMIT, Errors
from emendrix_service.watch.logic import (
    CADENCE_LABELS,
    DATE_ALERTS_LABEL,
    HEARTBEAT_LABEL,
    NOTICES,
    WHAT_A_WATCH_DOES,
    ItemLine,
    canonical_sort_key,
    coverage_line,
    describe_item,
)
from emendrix_service.web.csrf import SESSION_COOKIE, session_hash
from emendrix_service.web.session import SignedIn, SignInRequired, current_user
from emendrix_service.web.templating import render_page

__all__ = [
    "Holder",
    "Section",
    "account_holder",
    "account_page",
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


class Section(BaseModel):
    """One watchlist on the account page, with its items described."""

    model_config = ConfigDict(frozen=True)

    watchlist: WatchlistView = Field(description="The watchlist.")
    lines: tuple[ItemLine, ...] = Field(description="Its items, by act and canonical order.")


def copy() -> dict[str, object]:
    """The fixed wording every watch page may show."""
    return {
        "cadences": [(cadence.value, CADENCE_LABELS[cadence]) for cadence in Cadence],
        "date_alerts_label": DATE_ALERTS_LABEL,
        "heartbeat_label": HEARTBEAT_LABEL,
        "what_a_watch_does": WHAT_A_WATCH_DOES,
        "name_limit": NAME_LIMIT,
        "location_forms": LOCATION_FORMS,
    }


async def account_holder(request: Request) -> Holder:
    """The signed-in account, or a suspended one still holding a live session."""
    signed_in: SignedIn | None = await current_user(request)
    if signed_in is not None:
        return Holder(user_id=signed_in.user_id, email=signed_in.email)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db: Db = request.app.state.db
        async with db.transaction() as tx:
            row = await session_user(tx, session_hash(token), request.app.state.clock.now())
        if row is not None and row.status is UserStatus.SUSPENDED:
            return Holder(user_id=row.user_id, email=row.email)
    raise SignInRequired("/account/")


async def account_page(
    request: Request,
    holder: Holder,
    *,
    notice: str | None = None,
    errors: Errors = (),
) -> Response:
    """The account page: every watchlist, its items and settings, and the acts' coverage."""
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        status = await user_status(tx, holder.user_id)
        watchlists = await watchlists_for(tx, holder.user_id)
        keys: set[ActKey] = {(i.corpus, i.act_key) for wl in watchlists for i in wl.items}
        acts = await acts_by_key(tx, keys)
        provisions = await provisions_by_act(tx, keys)
    sections = []
    for watchlist in watchlists:
        items = sorted(
            watchlist.items,
            key=lambda item: (
                acts[item.corpus, item.act_key].label
                if (item.corpus, item.act_key) in acts
                else item.act_key,
                item.location is not None,
                canonical_sort_key(item.location or ""),
            ),
        )
        lines = tuple(
            describe_item(
                item, acts.get((item.corpus, item.act_key)), provisions[item.corpus, item.act_key]
            )
            for item in items
        )
        sections.append(Section(watchlist=watchlist, lines=lines))
    coverage = sorted(
        (
            (acts[key].label, acts[key].url, coverage_line(acts[key]))
            if key in acts
            else (key[1], None, "The site's catalogue does not list this act.")
            for key in keys
        ),
        key=lambda row: row[0],
    )
    return render_page(
        request,
        "watch/account.html",
        title="Your account",
        status=400 if errors else 200,
        email=holder.email,
        suspended=status is UserStatus.SUSPENDED,
        notice=NOTICES.get(notice or ""),
        errors=errors,
        sections=sections,
        coverage=coverage,
        **copy(),
    )


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
