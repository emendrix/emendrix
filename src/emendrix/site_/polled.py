"""What the poller last did, read out of the file it writes.

The site does not import the poller: it reads a document the poller wrote, the way it reads
the eval report and the committed changelog entries. So the shape below is this module's own
and deliberately partial, and unknown fields are ignored. `tests/site_/test_polled.py` holds
it against a real state file so the two cannot drift apart unnoticed.

`checked_through` is the end of the window the poller read, which is a cursor and not the
moment it ran, so every sentence built from it says the corpus was read up to that date. A
site that dressed it as a run time would be making the one claim this fact exists to let a
reader check.

`by_act` is the same pending rows grouped per act, keyed by the stored `act_key` string
(`corpus:key`), so the catalogue can tell a reader which watched act is waiting on what. A
quiet act and a watched one whose consolidation has been announced but cannot be read yet look
the same on every page that lists only what changed; this is the fact that tells them apart.

No clock: what is here is what the file says, and how current that is is the reader's
judgement to make from a date the page prints.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["PolledState", "Waiting", "read_polled"]

SCHEMA: Final = 1
"""The state-file schema this reader understands. A file stamped otherwise is not read: the
fields below are named in it, and guessing at a layout nothing here has seen is how a page
starts printing a number that means something else."""


class Waiting(BaseModel):
    """One consolidation the poller was told about and could not read yet, as its row says."""

    model_config = ConfigDict(frozen=True)

    version: str | None = Field(
        default=None, description="The consolidated version announced; None when not yet known."
    )
    state: str = Field(
        description="`consolidation_pending`, or `english_unavailable` when no English text is "
        "offered; any other string is passed on as stored."
    )
    first_seen: date | None = Field(
        default=None, description="When the poller first saw it; None where unreadable."
    )


class PolledState(BaseModel):
    """The two facts a reader needs about a corpus that looks quiet."""

    model_config = ConfigDict(frozen=True)

    checked_through: date | None = Field(
        default=None,
        description="The end of the last window the poller read; None if it has never polled.",
    )
    waiting: int = Field(default=0, ge=0, description="Consolidations announced without text.")
    waiting_since: date | None = Field(
        default=None, description="When the oldest of those was first seen; None if none."
    )
    by_act: dict[str, tuple[Waiting, ...]] = Field(
        default_factory=dict,
        description="The same rows per stored `act_key` (`corpus:key`), each act's rows sorted "
        "by first sighting, then version; an act with nothing waiting has no key.",
    )


def _day(value: object) -> date | None:
    """The day a stored timestamp names, or None where the field holds no readable date."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def read_polled(path: Path | None) -> PolledState | None:
    """The poller's own record, or None where there is none to read.

    A missing, unreadable or foreign-schema file is None and not an error: a site build must
    not fail because a deployment chose not to hand it this, and a deployment that handed it
    a broken one is better served by a page that says nothing than by a page that is wrong.
    """
    if path is None:
        return None
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA:
        return None
    rows = payload.get("pending")
    pending = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    seen = [day for day in (_day(row.get("first_seen")) for row in pending) if day is not None]
    return PolledState(
        checked_through=_day(payload.get("last_window_end")),
        waiting=len(pending),
        waiting_since=min(seen, default=None),
        by_act=_by_act(pending),
    )


def _waiting(row: dict[str, object]) -> Waiting:
    version, state = row.get("version"), row.get("state")
    return Waiting(
        version=version if isinstance(version, str) else None,
        state=state if isinstance(state, str) else "consolidation_pending",
        first_seen=_day(row.get("first_seen")),
    )


def _by_act(pending: list[dict[str, object]]) -> dict[str, tuple[Waiting, ...]]:
    """Rows grouped by act, in a total order: undated rows last, unknown versions first.

    A row with no readable `act_key` names no act and is counted in `waiting` alone.
    """
    grouped: dict[str, list[Waiting]] = {}
    for row in pending:
        key = row.get("act_key")
        if isinstance(key, str) and key:
            grouped.setdefault(key, []).append(_waiting(row))
    return {
        key: tuple(
            sorted(
                rows,
                key=lambda item: (
                    item.first_seen is None,
                    item.first_seen or date.min,
                    item.version or "",
                    item.state,
                ),
            )
        )
        for key, rows in sorted(grouped.items())
    }
