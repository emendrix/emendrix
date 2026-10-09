"""Every stored change of the watched acts, with the dates that order it, in one read.

The Watching tab shows each watched item's newest change. Which changes fall within an item is
containment on canonical locations, which `watch.watching` decides in pure code, so this module
fetches the changes of every watched act at once rather than asking once per item.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, tuple_

from emendrix_service.db.engine import Tx
from emendrix_service.db.tables_content import Change, Event

__all__ = ["ChangeStamp", "change_stamps"]


class ChangeStamp(BaseModel):
    """One stored change, reduced to where it is, when, and where its page is."""

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(description="The act's corpus.")
    act_key: str = Field(description="The act's key.")
    location: str = Field(description="The change's canonical location.")
    unit: str = Field(description="The top-level unit holding the location.")
    in_force: date | None = Field(description="The change's own in-force date, when it has one.")
    detected_on: date = Field(description="When the record detected the change's event.")
    event_key: str = Field(description="The event's key.")
    url: str | None = Field(description="The event's page, once the catalogue names it.")
    anchor: str = Field(description="The change's anchor on that page.")
    changed_within: tuple[str, ...] = Field(
        description="The coordinates inside the unit the record lists as changed, if any."
    )


async def change_stamps(tx: Tx, acts: Iterable[tuple[str, str]]) -> list[ChangeStamp]:
    """Every stored change of the acts `(corpus, act_key)` names, in a fixed order."""
    wanted = sorted(set(acts))
    if not wanted:
        return []
    rows = await tx.execute(
        select(
            Event.corpus,
            Event.act_key,
            Change.location,
            Change.unit,
            Change.in_force,
            Event.detected_on,
            Event.event_key,
            Event.url,
            Change.anchor,
            Change.changed_within,
        )
        .join(Event, Event.event_key == Change.event_key)
        .where(tuple_(Event.corpus, Event.act_key).in_(wanted))
        .order_by(Event.corpus, Event.act_key, Event.event_key, Change.location, Change.occurrence)
    )
    return [
        ChangeStamp(
            corpus=row.corpus,
            act_key=row.act_key,
            location=row.location,
            unit=row.unit,
            in_force=row.in_force,
            detected_on=row.detected_on,
            event_key=row.event_key,
            url=row.url,
            anchor=row.anchor,
            changed_within=tuple(row.changed_within),
        )
        for row in rows
    ]
