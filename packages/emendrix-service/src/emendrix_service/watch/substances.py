"""Watching a CAS or EC number: reading one from a link or a paste, and what the tab says of it.

A number is read by `emendrix_record.identifiers.parse_identifier`, the reader's copy of the
check-digit rules the pipeline recognises numbers in table rows by, and never re-implemented
here. Only CAS and EC numbers are watchable, because those are what a table row's identifiers
carry across acts; a CLP Index No keys one row of one table, so a page that is given one says so
and points at the numbers that row carries. A number is said to *appear in* an entry, never to
be regulated: many entries name a group of substances and print no number at all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.identifiers import parse_identifier
from emendrix_record.locations import human
from emendrix_service.notify.matching import row_name, substance_label
from emendrix_service.watch.views import EntryStamp, WatchItemView

__all__ = [
    "INDEX_NOT_WATCHED",
    "NOT_PRINTED_YET",
    "SUBSTANCES_HEADING",
    "WATCHABLE",
    "WHAT_A_NUMBER_WATCH_DOES",
    "Reading",
    "SubstanceRow",
    "address",
    "entry_line",
    "landing_path",
    "newest_entry",
    "read_substance",
    "readings_of",
    "substance_page",
    "substance_rows",
]

WATCHABLE: Final = ("cas", "ec")
"""The schemes a watch item may name."""

SUBSTANCES_HEADING: Final = "Substances"
INDEX_NOT_WATCHED: Final = "watch a CAS or EC number that its entry prints instead."
NOT_PRINTED_YET: Final = "No recorded change to an entry printing this number yet."
WHAT_A_NUMBER_WATCH_DOES: Final = (
    "You will get an email when the record shows a table entry printing this number added, "
    "removed or amended, in any act it holds. Many entries name a group of substances and print "
    "no number, so a change to one of those does not reach you through a number. The email "
    "repeats what the record says; it does not say whether the change affects you."
)

_PREFIX: Final = re.compile(r"^(cas|ec|index)[-:\s]", re.IGNORECASE)
_DIGITS: Final = re.compile(r"\d+")


class Reading(BaseModel):
    """What a `?substance=` value reads as."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["watchable", "ambiguous", "index", "invalid"] = Field(
        description="One number to watch, two readings to choose from, an Index No, or none."
    )
    shown: str = Field(description="The value as given, trimmed and cut to 80 characters.")
    identifiers: tuple[str, ...] = Field(
        default=(), description="`scheme:value` of each watchable reading."
    )
    index: str | None = Field(default=None, description="The Index No, when it read as one.")
    reason: str | None = Field(default=None, description="Why it is no number, when invalid.")


class SubstanceRow(BaseModel):
    """One watched number as the Watching tab lists it, under "Substances"."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="The item's id.")
    label: str = Field(description="`CAS 50-00-0`.")
    page: str | None = Field(description="Its substance page, once a stored change names it.")
    latest_text: str = Field(description="Its newest entry change, or that there is none.")
    latest_url: str | None = Field(description="That change on its event page, when it has one.")


def readings_of(text: str) -> tuple[tuple[str, ...], str | None, str | None]:
    """The watchable readings of `text`, the Index No it reads as, and why it reads as none.

    `parse_identifier` offers every reading whose check passes: a hyphenless value of 7 digits
    may pass as both a CAS and an EC number, and both come back.
    """
    parsed = parse_identifier(text)
    if isinstance(parsed, str):
        return (), None, parsed
    watchable = tuple(f"{scheme}:{value}" for scheme, value in parsed if scheme in WATCHABLE)
    index = next((value for scheme, value in parsed if scheme == "index"), None)
    return watchable, index, None


def read_substance(text: str) -> Reading:
    """A `?substance=` value: `cas-50-00-0` as the site's link writes it, or a number alone.

    A scheme prefix keeps only the readings of that scheme, so `cas-200-001-8` is refused rather
    than watched as the EC number it is.
    """
    shown = " ".join(text.split())[:80]
    prefix = _PREFIX.match(text.strip())
    scheme = prefix.group(1).lower() if prefix else None
    body = text.strip()[prefix.end() :] if prefix else text
    watchable, index, reason = readings_of(body)
    if scheme is not None:
        watchable = tuple(found for found in watchable if found.startswith(f"{scheme}:"))
        index = index if scheme == "index" else None
        if not watchable and index is None and reason is None:
            named = {"cas": "a CAS number", "ec": "an EC number", "index": "an Index No"}[scheme]
            reason = f"{body.strip()!r} is not {named}."
    if index is not None and not watchable:
        return Reading(outcome="index", shown=shown, index=index)
    if len(watchable) == 1:
        return Reading(outcome="watchable", shown=shown, identifiers=watchable)
    if watchable:
        return Reading(outcome="ambiguous", shown=shown, identifiers=watchable)
    return Reading(outcome="invalid", shown=shown, reason=reason or f"{shown!r} is no number.")


def address(identifier: str) -> str:
    """`cas:50-00-0` as a site address writes it: `cas-50-00-0`."""
    return identifier.replace(":", "-", 1)


def substance_page(site_url: str, identifier: str) -> str:
    """The number's page on the site."""
    return f"{site_url}/substances/{address(identifier)}/"


def landing_path(identifier: str) -> str:
    """The watch landing for the number, as a local path."""
    return f"/account/watch?substance={address(identifier)}"


def _dated(stamp: EntryStamp) -> tuple[date, str]:
    return (stamp.in_force or stamp.detected_on, stamp.event_key)


def newest_entry(identifier: str, stamps: Sequence[EntryStamp]) -> EntryStamp | None:
    """The newest stored change to a row carrying `identifier`, by in-force date, else the day
    its event was detected, then by event key, so the choice never depends on read order."""
    found = [stamp for stamp in stamps if stamp.identifier == identifier]
    return max(found, key=_dated, default=None)


def entry_line(stamp: EntryStamp) -> str:
    """`Index No 605-001-00-5 in CLP Annex VI was amended in the version in force 2025-09-01`.

    The key is named as the act names it, `Entry` lower-cased in running text, and a row keyed by
    its name is named by that name, cut as the email cuts it.
    """
    where = f"in {stamp.act_label} {human(stamp.unit)} was {stamp.kind}"
    if stamp.key_label is None:
        line = f"The entry for {row_name(stamp.name or stamp.row_key)} {where}"
    else:
        line = f"{stamp.key_label} {stamp.row_key} {where}"
    if stamp.in_force is not None:
        return f"{line} in the version in force {stamp.in_force.isoformat()}"
    return f"{line} in the version recorded {stamp.detected_on.isoformat()}"


def _order(identifier: str) -> tuple[str, tuple[int, ...], str]:
    scheme, _, value = identifier.partition(":")
    return scheme, tuple(int(part) for part in _DIGITS.findall(value)), value


def substance_rows(
    items: Sequence[WatchItemView], stamps: Sequence[EntryStamp], *, site_url: str
) -> tuple[SubstanceRow, ...]:
    """The substance items of `items`, by scheme and then by number, each with its newest change.

    A number no stored change names may still be printed by an entry that has never changed,
    which the service cannot see, so its row links no page and says only what is recorded.
    """
    found = [item for item in items if item.identifier is not None]
    rows: list[SubstanceRow] = []
    for item in sorted(found, key=lambda item: _order(item.identifier or "")):
        identifier = item.identifier or ""
        stamp = newest_entry(identifier, stamps)
        rows.append(
            SubstanceRow(
                id=str(item.id),
                label=substance_label(identifier),
                page=substance_page(site_url, identifier) if stamp is not None else None,
                latest_text=entry_line(stamp) if stamp is not None else NOT_PRINTED_YET,
                latest_url=f"{stamp.url}#{stamp.anchor}" if stamp and stamp.url else None,
            )
        )
    return tuple(rows)
