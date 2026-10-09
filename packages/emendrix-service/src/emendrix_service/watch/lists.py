"""Choosing one of a reader's lists, and what the switcher between them shows.

A reader with one list never sees the word: the switcher is absent, no `list` query is carried,
and a paused banner does not name the list. Pure, so the routes decide what to read and these
functions only decide what to show.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db.watchlists import WatchlistView
from emendrix_service.web.frame import PausedNote

__all__ = ["ListChoice", "list_choices", "list_query", "paused_notes", "pick_list"]


class ListChoice(BaseModel):
    """One list as the switcher draws it."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="The list's id.")
    name: str = Field(description="The name its owner gave it.")
    item_count: int = Field(description="How many items it holds.")
    current: bool = Field(description="Whether this page shows it.")


def pick_list(watchlists: Sequence[WatchlistView], raw: str) -> WatchlistView | None:
    """The reader's list whose id `raw` names, else their oldest, else None.

    An id that is malformed or not the reader's own falls back to the oldest list rather than
    failing, so a stale link still lands somewhere useful and reveals nothing.
    """
    try:
        wanted = UUID(raw)
    except ValueError:
        wanted = None
    for watchlist in watchlists:
        if watchlist.id == wanted:
            return watchlist
    return watchlists[0] if watchlists else None


def list_choices(watchlists: Sequence[WatchlistView], current: UUID) -> tuple[ListChoice, ...]:
    """Every list, oldest first, with `current` marked."""
    return tuple(
        ListChoice(
            id=watchlist.id,
            name=watchlist.name,
            item_count=len(watchlist.items),
            current=watchlist.id == current,
        )
        for watchlist in watchlists
    )


def list_query(watchlists: Sequence[WatchlistView], current: UUID) -> str:
    """The query naming `current` in a tab link: '' when the reader has only one list."""
    return f"?list={current}" if len(watchlists) > 1 else ""


def paused_notes(watchlists: Sequence[WatchlistView]) -> tuple[PausedNote, ...]:
    """One banner note per paused list, naming it only when there are several."""
    named = len(watchlists) > 1
    return tuple(
        PausedNote(
            name=watchlist.name if named else None,
            resume_action=f"/account/watchlists/{watchlist.id}/resume",
        )
        for watchlist in watchlists
        if watchlist.paused
    )
