"""The Watching tab: what a reader watches, grouped by act, each item with its newest change.

The tab has three shapes. A reader with no list, or with one list that watches nothing, sees the
first visit: three steps and every act the catalogue lists. A reader with one list sees its items
and never the word "list", a list's name, a rename box or a switcher, because that list is their
account. With a second list the switcher and the list's name appear.

An item's newest change is found by containment on canonical locations over every stored change
of the watched acts, read once per page. Every date and heading shown is a stored one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final, Literal

from fastapi import Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.locations import within
from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence, UserStatus
from emendrix_service.db.latest import ChangeStamp, change_stamps
from emendrix_service.db.watchlists import (
    ActKey,
    ActView,
    ProvisionView,
    WatchItemView,
    WatchlistView,
    acts_by_key,
    acts_roster,
    provisions_by_act,
    user_status,
    watchlists_for,
)
from emendrix_service.watch.delivery import CARDS
from emendrix_service.watch.forms import NAME_LIMIT, Errors
from emendrix_service.watch.lists import list_choices, list_query, paused_notes, pick_list
from emendrix_service.watch.logic import (
    NO_CHANGE_YET,
    NOTICES,
    ItemLine,
    canonical_sort_key,
    coverage_line,
    describe_item,
)
from emendrix_service.watch.pages import Holder
from emendrix_service.web.frame import EYEBROW, AccountFrame, frame_context
from emendrix_service.web.templating import render_page

__all__ = [
    "ActGroup",
    "ItemRow",
    "Mode",
    "Strip",
    "coverage_short",
    "group_by_act",
    "latest_for",
    "latest_line",
    "strip_for",
    "watching_page",
]

Mode = Literal["first_visit", "single", "several"]

HEADING: Final = "What you watch"
LEDE_ONE: Final = (
    "When the record shows a change to anything below, you hear about it the way you chose "
    "under Delivery."
)
LEDE_SEVERAL: Final = "Each list has its own email and feed. Use one per product, client or team."
FIRST_HEADING: Final = "Hear when EU law you rely on changes"
FIRST_LEDE: Final = (
    "Pick an act, or one article or annex in it. When the record shows a change, you get the "
    "old and new text by email or in a private feed."
)
NOT_LISTED: Final = "The site's catalogue does not list this act."

_FROZEN = ConfigDict(frozen=True)

_WHEN: Final[dict[Cadence, str]] = {
    Cadence.DAILY: "07:00 Brussels time",
    Cadence.WEEKLY: "Mondays 07:00 Brussels time",
}
"""The time a digest goes, as the Delivery tab's cards state it."""


class ItemRow(ItemLine):
    """One watched item as the Watching tab draws it, with its newest change."""

    latest_text: str = Field(description="The newest change's date, or that there is none.")
    latest_url: str | None = Field(description="That change on its event page, when it has one.")


class ActGroup(BaseModel):
    """One watched act's block: its name, how far the record has read it, and its items."""

    model_config = _FROZEN

    act_key: str = Field(description="The act's key.")
    label: str = Field(description="The catalogue's label, or the key once the catalogue drops it.")
    long_name: str = Field(description="The catalogue's long form when it differs, or ''.")
    url: str | None = Field(description="The act's page, when the catalogue lists the act.")
    coverage_short: str = Field(description="`Checked to 2026-08-12`, or `Not checked yet`.")
    waiting: bool = Field(description="Whether something is announced that the record lacks.")
    coverage_note: str | None = Field(description="The whole coverage sentence, when waiting.")
    rows: tuple[ItemRow, ...] = Field(description="Its items: the whole act first, then in order.")


class Strip(BaseModel):
    """How one list reaches its reader, in three short values."""

    model_config = _FROZEN

    email: str = Field(description="The email choice and when it goes, or `Paused`.")
    feed: str = Field(description="`On` or `Off`.")
    dates: str = Field(description="`Flagged` or `Not flagged`.")


def _newest(stamp: ChangeStamp) -> tuple[date, str]:
    return (stamp.in_force or stamp.detected_on, stamp.event_key)


def _touches(stamp: ChangeStamp, watched: str) -> bool:
    # The three provision rules an email matches by (docs/accounts.md, "Matching"), so the row
    # never says "no change" about a change the reader was emailed.
    if within(stamp.location, watched) or stamp.unit == watched:
        return True
    if any(within(w, watched) or within(watched, w) for w in stamp.changed_within):
        return True
    return not stamp.changed_within and within(watched, stamp.location)


def latest_for(item: WatchItemView, stamps: Sequence[ChangeStamp]) -> ChangeStamp | None:
    """The newest stored change that touches `item`, or None.

    A whole act takes any change of the act. A provision takes a change at or beneath it, or
    filed under it as its unit, or one the record says changed something inside or around it,
    or a whole unit holding it whose changed part the record does not name. Newest is by the
    change's in-force date, else the day its event was detected, and then by event key, so the
    choice never depends on read order.
    """
    found = [
        stamp
        for stamp in stamps
        if (stamp.corpus, stamp.act_key) == (item.corpus, item.act_key)
        and (item.location is None or _touches(stamp, item.location))
    ]
    return max(found, key=_newest, default=None)


def latest_line(stamp: ChangeStamp | None) -> tuple[str, str | None]:
    """What the row says about its newest change, and where that change's page is."""
    if stamp is None:
        return NO_CHANGE_YET, None
    url = f"{stamp.url}#{stamp.anchor}" if stamp.url else None
    if stamp.in_force is not None:
        return f"Latest change in force from {stamp.in_force.isoformat()}", url
    return f"Latest change recorded {stamp.detected_on.isoformat()}", url


def coverage_short(act: ActView) -> tuple[str, bool]:
    """How far the record has read the act, in a few words, and whether anything waits.

    Something waits when a consolidation is announced and not read yet, or a version is offered
    in no English text; the act's group then carries the whole sentence `coverage_line` writes.
    """
    short = (
        f"Checked to {act.checked_through.isoformat()}"
        if act.checked_through is not None
        else "Not checked yet"
    )
    return short, bool(act.waiting)


def _group(key: ActKey, act: ActView | None, rows: list[ItemRow]) -> ActGroup:
    note: str | None
    if act is None:
        short, waiting, note = "Not checked yet", True, NOT_LISTED
    else:
        short, waiting = coverage_short(act)
        note = coverage_line(act) if waiting else None
    return ActGroup(
        act_key=key[1],
        label=act.label if act is not None else key[1],
        long_name=act.long_name if act is not None and act.long_name != act.label else "",
        url=act.url if act is not None else None,
        coverage_short=short,
        waiting=waiting,
        coverage_note=note,
        rows=tuple(rows),
    )


def group_by_act(
    items: Sequence[WatchItemView],
    acts: Mapping[ActKey, ActView],
    provisions: Mapping[ActKey, list[ProvisionView]],
    stamps: Sequence[ChangeStamp],
) -> tuple[ActGroup, ...]:
    """`items` grouped by act, by act label, each act's whole-act item first, then in order."""

    def label(key: ActKey) -> str:
        return acts[key].label if key in acts else key[1]

    ordered = sorted(
        items,
        key=lambda item: (
            label((item.corpus, item.act_key)),
            item.corpus,
            item.act_key,
            item.location is not None,
            canonical_sort_key(item.location or ""),
        ),
    )
    grouped: dict[ActKey, list[ItemRow]] = {}
    for item in ordered:
        key = (item.corpus, item.act_key)
        line = describe_item(item, acts.get(key), provisions.get(key, []))
        text, url = latest_line(latest_for(item, stamps))
        grouped.setdefault(key, []).append(
            ItemRow(**line.model_dump(), latest_text=text, latest_url=url)
        )
    return tuple(_group(key, acts.get(key), rows) for key, rows in grouped.items())


def strip_for(watchlist: WatchlistView) -> Strip:
    """What the summary strip says about how `watchlist` reaches its reader."""
    if watchlist.paused:
        email = "Paused"
    else:
        title = next(card.title for card in CARDS if card.cadence == watchlist.cadence)
        when = _WHEN.get(watchlist.cadence)
        email = f"{title}, {when}" if when else title
    return Strip(
        email=email,
        feed="On" if watchlist.has_feed else "Off",
        dates="Flagged" if watchlist.date_alerts else "Not flagged",
    )


def _mode(lists: Sequence[WatchlistView]) -> Mode:
    if len(lists) > 1:
        return "several"
    return "single" if lists and lists[0].items else "first_visit"


async def watching_page(
    request: Request,
    holder: Holder,
    *,
    raw_list: str = "",
    notice: str = "",
    new: bool = False,
    errors: Errors = (),
) -> Response:
    """The Watching tab for the list `raw_list` names, else the reader's oldest."""
    db: Db = request.app.state.db
    async with db.transaction() as tx:
        status = await user_status(tx, holder.user_id)
        lists = await watchlists_for(tx, holder.user_id)
        current = pick_list(lists, raw_list)
        items = current.items if current is not None else ()
        keys: set[ActKey] = {(item.corpus, item.act_key) for item in items}
        acts = await acts_by_key(tx, keys)
        provisions = await provisions_by_act(tx, keys)
        stamps = await change_stamps(tx, keys)
        mode = _mode(lists)
        roster = await acts_roster(tx) if mode == "first_visit" else []
    first = mode == "first_visit"
    frame = AccountFrame(
        tab="watching",
        heading=FIRST_HEADING if first else HEADING,
        lede=FIRST_LEDE if first else LEDE_SEVERAL if mode == "several" else LEDE_ONE,
        email=holder.email,
        item_count=sum(len(watchlist.items) for watchlist in lists),
        list_query=list_query(lists, current.id) if current is not None else "",
        suspended=status is UserStatus.SUSPENDED,
        paused=paused_notes(lists),
        notice=NOTICES.get(notice),
        eyebrow="Welcome" if first else EYEBROW,
    )
    groups = group_by_act(items, acts, provisions, stamps)
    return render_page(
        request,
        "watch/watching.html",
        title="Start watching" if first else "Watching",
        status=400 if errors else 200,
        **frame_context(frame),
        mode=mode,
        suspended=frame.suspended,
        watchlist=current,
        choices=list_choices(lists, current.id) if current is not None else (),
        base="/account/",
        strip=strip_for(current) if current is not None else None,
        groups=groups,
        item_count=len(items),
        act_count=len(groups),
        roster=roster,
        new=new,
        errors=errors,
        name_limit=NAME_LIMIT,
    )
