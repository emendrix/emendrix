"""The Delivery tab: how one list reaches its reader, by email, by a personal feed, or both.

A reader with several lists edits one at a time, chosen by `?list=`; a reader with one never
sees a list's name here. A suspended account sees what is set, as text, with nothing to change.
"""

from __future__ import annotations

from typing import Final

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, UserStatus
from emendrix_service.db.watchlists import user_status, watchlists_for
from emendrix_service.watch.forms import Errors
from emendrix_service.watch.lists import list_choices, list_query, paused_notes, pick_list
from emendrix_service.watch.pages import Holder
from emendrix_service.web.frame import AccountFrame, frame_context
from emendrix_service.web.templating import render_page

__all__ = [
    "CARDS",
    "DELIVERY_NOTICES",
    "EXTRAS",
    "HEADING",
    "LEDE",
    "PAUSE",
    "Card",
    "Extra",
    "delivery_page",
]

HEADING: Final = "How you hear about changes"
LEDE: Final = (
    "By email, by a private feed, or both. Nothing is sent when nothing changed, unless you ask "
    "for the monthly note."
)

_FROZEN = ConfigDict(frozen=True)


class Card(BaseModel):
    """One email choice, drawn as a radio card."""

    model_config = _FROZEN

    cadence: Cadence = Field(description="The value the card posts.")
    title: str = Field(description="The card's title.")
    subline: str = Field(description="What the choice sends, and when.")
    badge: str | None = Field(description="A word set beside the title, or None.")


class Extra(BaseModel):
    """One checkbox under "Also tell me", explained by what it does for the reader."""

    model_config = _FROZEN

    field: str = Field(description="The form field and the watchlist setting it sets.")
    title: str = Field(description="What the box turns on.")
    subline: str = Field(description="Why a reader would want it.")


# The times are the settings' defaults (`digest_hour` 7 in Europe/Brussels), as the labels on
# the other watch pages state them.
CARDS: Final = (
    Card(
        cadence=Cadence.INSTANT,
        title="Every change",
        subline="One email for each change, as soon as it is in the record.",
        badge=None,
    ),
    Card(
        cadence=Cadence.DAILY,
        title="Daily digest",
        subline="07:00 Brussels time, only on days something changed.",
        badge=None,
    ),
    Card(
        cadence=Cadence.WEEKLY,
        title="Weekly digest",
        subline="Mondays 07:00 Brussels time, only in weeks something changed.",
        badge="Default",
    ),
    Card(
        cadence=Cadence.NONE,
        title="No email",
        subline="Follow your personal feed instead.",
        badge=None,
    ),
)

EXTRAS: Final = (
    Extra(
        field="date_alerts",
        title="Flag changes that add or remove a date",
        subline=(
            "A change that adds or removes a date in the text is marked in the email, so you "
            "see it first."
        ),
    ),
    Extra(
        field="heartbeat",
        title="A short note once a month when nothing changed",
        subline="So a quiet inbox means nothing changed, not that email stopped reaching you.",
    ),
)

PAUSE: Final = Extra(
    field="paused",
    title="Pause email for now",
    subline="Nothing is sent until you untick this, and your email choice above is kept.",
)

DELIVERY_NOTICES: Final[dict[str, str]] = {
    "saved": "Delivery settings saved.",
    "resumed": "Email resumed.",
}


async def delivery_page(
    request: Request,
    holder: Holder,
    *,
    raw_list: str = "",
    notice: str = "",
    errors: Errors = (),
) -> Response:
    """The Delivery tab for the list `raw_list` names, else the reader's oldest."""
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        status = await user_status(tx, holder.user_id)
        lists = await watchlists_for(tx, holder.user_id)
    current = pick_list(lists, raw_list)
    if current is None:
        return RedirectResponse("/account/", status_code=303)
    suspended = status is UserStatus.SUSPENDED
    frame = AccountFrame(
        tab="delivery",
        heading=HEADING,
        lede=LEDE,
        email=holder.email,
        item_count=sum(len(watchlist.items) for watchlist in lists),
        list_query=list_query(lists, current.id),
        suspended=suspended,
        paused=paused_notes(lists),
        notice=DELIVERY_NOTICES.get(notice),
    )
    return render_page(
        request,
        "watch/delivery.html",
        title="Delivery",
        status=400 if errors else 200,
        **frame_context(frame),
        watchlist=current,
        named=len(lists) > 1,
        choices=list_choices(lists, current.id),
        base="/account/delivery",
        cards=CARDS,
        extras=EXTRAS,
        pause=PAUSE,
        errors=errors,
        suspended=suspended,
        email=holder.email,
    )
