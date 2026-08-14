"""What is pinned into `tests/fixtures/eu/`, and why — the data half of the fixture set.

Split out of `eu/fetch_fixtures.py`, which is the *mechanism* (fetch, trim, export, manifest).
This module is the list: hand-written document pins, the notification-feed windows, and the
merge with the pins the eval corpus generates for itself.

Both pin kinds name an identifier, never a URL — an act and a version, or a channel and a time
window. What request that turns into is decided by the code under test, which is what keeps the
fixture set equal to the set of requests the tests actually make.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.eu.feed import DEFAULT_CHANNEL

__all__ = [
    "EXTRA_PINS_NAME",
    "FEED_PINNED",
    "ORIGINAL",
    "PINNED",
    "FeedPin",
    "Pin",
    "PinSet",
    "merge_pins",
    "read_extra_pins",
    "write_extra_pins",
]

EXTRA_PINS_NAME: Final = "eval_pins.json"
"""Generated pins, written into the fixture directory by `emendrix eval build-corpus`."""


ORIGINAL: Final = "original"
"""`Pin.version` for the act as published in the OJ, as opposed to a consolidation of it."""


class Pin(BaseModel):
    """One pinned document: an act, optionally one of its versions, and why it is here.

    `version` is a consolidated CELEX (`02024R1689-20260727`), `"original"` for the act's own
    OJ text, or `None` to pin the act's notices — the tree notice that lists its versions and
    the branch notice that carries its modification annotations.
    """

    model_config = ConfigDict(frozen=True)

    celex: str
    version: str | None = None
    reason: str = ""

    @property
    def label(self) -> str:
        return self.celex if self.version is None else f"{self.celex}@{self.version}"


PINNED: Final[tuple[Pin, ...]] = (
    Pin(celex="32024R1689", reason="AI Act: tree + branch notices, the flagship act"),
    Pin(
        celex="32024R1689",
        version="02024R1689-20240712",
        reason="the eleven-languages-no-English version, which drives the fallback chain",
    ),
    Pin(
        celex="32024R1689",
        version="02024R1689-20260727",
        reason="AI Act v2, consolidated after the Digital Omnibus — flagship regression",
    ),
    Pin(
        celex="32026R1744",
        version=ORIGINAL,
        reason="Digital Omnibus: the amending act's own Formex, which quotes what it inserts",
    ),
    Pin(celex="32017R0745", reason="MDR: tree + branch notices"),
    Pin(celex="32017R0745", version="02017R0745-20170505", reason="MDR pair, before"),
    Pin(celex="32017R0745", version="02017R0745-20200424", reason="MDR pair, after"),
    Pin(
        celex="32020R0561",
        version=ORIGINAL,
        reason=(
            "the MDR postponement's own Formex — a second amending act for the instruction "
            "signal, and one that names the act it amends nowhere but in its own title"
        ),
    ),
    Pin(
        celex="32025R2457",
        version=ORIGINAL,
        reason=(
            "amends MDR Annex I through an article lead-in that names the annex once "
            "('Annex I to Regulation (EU) 2017/745 is amended as follows:') and then lists "
            "sections relative to it — the scope shape the instruction parser must not drop"
        ),
    ),
    Pin(
        celex="32006R1907",
        reason="REACH: 68 versions, 5 of them with no Formex at all, counted 2026-08-05",
    ),
    Pin(
        celex="32006R1907",
        version="02006R1907-20081012",
        reason="REACH pair, before — 2006 Formex generation, answers on celex/ not consolidation/",
    ),
    Pin(celex="32006R1907", version="02006R1907-20090120", reason="REACH pair, after"),
)


class FeedPin(BaseModel):
    """One pinned window of the notification feed — a channel and a half-open time range.

    Windows, not documents: the feed is addressed by time, so this is the identifier form that
    makes a feed fixture reproducible. Re-running the script re-requests the same window and
    gets the same bytes back (the archive does not change once a day is past).
    """

    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime
    channel: str = DEFAULT_CHANNEL
    reason: str = ""

    @property
    def label(self) -> str:
        return f"{self.channel}@{self.start:%Y-%m-%dT%H:%M}..{self.end:%H:%M}"


FEED_PINNED: Final[tuple[FeedPin, ...]] = (
    FeedPin(
        start=datetime(2026, 8, 5, 10, 0, 0),
        end=datetime(2026, 8, 5, 10, 5, 0),
        reason=(
            "five real minutes of the ingestion firehose, holding the AI Act's Digital Omnibus "
            "consolidation (02024R1689-20260727) among 46 entries — the flagship watch case"
        ),
    ),
    FeedPin(
        start=datetime(2026, 8, 2, 0, 0, 0),
        end=datetime(2026, 8, 2, 0, 5, 0),
        reason="a genuinely empty window: the feed's 'nothing happened' answer, a Sunday",
    ),
)
"""Feed windows the watch tests run on. Minutes rather than days on purpose: the endpoint
accepts `YYYY-MM-DDTHH:MM:SS` bounds, so a real page can be pinned at 65 KB instead of the
5 MB a full day of ~3,800 notifications would cost — untrimmed, Velocity garbage and all."""


class PinSet(BaseModel):
    """A committed list of generated pins, and the note saying what generated them."""

    model_config = ConfigDict(frozen=True)

    note: str = ""
    pins: tuple[Pin, ...] = ()


def read_extra_pins(path: Path) -> tuple[Pin, ...]:
    """Generated pins, if a generator has written any. A missing file is not an error."""
    if not path.is_file():
        return ()
    return PinSet.model_validate_json(path.read_bytes()).pins


def write_extra_pins(path: Path, pins: tuple[Pin, ...], *, note: str = "") -> None:
    """Write generated pins, sorted, so the file diffs readably in git."""
    payload = PinSet(note=note, pins=merge_pins((), pins)).model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_pins(base: tuple[Pin, ...], extra: tuple[Pin, ...]) -> tuple[Pin, ...]:
    """Union two pin lists, keeping the first reason given for a document, in sorted order."""
    seen: dict[tuple[str, str], Pin] = {}
    for pin in (*base, *extra):
        seen.setdefault((pin.celex, pin.version or ""), pin)
    return tuple(sorted(seen.values(), key=lambda pin: (pin.celex, pin.version or "")))
