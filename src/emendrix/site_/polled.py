"""What the poller last did, read out of the file it writes.

The site does not import the poller: it reads a document the poller wrote, the way it reads
the eval report and the committed changelog entries. So the shape below is this module's own
and deliberately partial, and unknown fields are ignored. `tests/site_/test_polled.py` holds
it against a real state file so the two cannot drift apart unnoticed.

`checked_through` is the end of the window the poller read, which is a cursor and not the
moment it ran, so every sentence built from it says the corpus was read up to that date. A
site that dressed it as a run time would be making the one claim this fact exists to let a
reader check.

No clock: what is here is what the file says, and how current that is is the reader's
judgement to make from a date the page prints.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["PolledState", "read_polled"]

SCHEMA: Final = 1
"""The state-file schema this reader understands. A file stamped otherwise is not read: the
fields below are named in it, and guessing at a layout nothing here has seen is how a page
starts printing a number that means something else."""


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
    )
