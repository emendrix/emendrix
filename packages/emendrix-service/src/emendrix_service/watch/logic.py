"""What the watch pages say, as pure functions over the frozen views `db.watchlists` returns.

Every label, heading and date shown comes from `content` as the loader stored it, or from a
mechanical rule written down here. Nothing reads law text or guesses a location: a line that
is not one of the forms `emendrix_record.locations.parse_location` reads is shown back as
unresolved, and a location the record has never named is accepted and said to have no change
recorded yet, because the record lists only units that changed.
"""

from __future__ import annotations

import re
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.locations import human, parse_location, within
from emendrix_service.db.enums import Cadence
from emendrix_service.db.watchlists import ActView, ProvisionView, WatchItemView

__all__ = [
    "CADENCE_LABELS",
    "DATE_ALERTS_LABEL",
    "HEARTBEAT_LABEL",
    "NOTICES",
    "NO_CHANGE_YET",
    "WHAT_A_WATCH_DOES",
    "ItemLine",
    "canonical_sort_key",
    "coverage_line",
    "describe_item",
    "read_location",
    "readable",
    "resolve_paste",
    "roster_label",
    "sort_provisions",
    "watch_label",
]

CADENCE_LABELS: Final[dict[Cadence, str]] = {
    Cadence.INSTANT: "Every change, as it is recorded",
    Cadence.DAILY: "Daily digest (07:00 Brussels time, only when something changed)",
    Cadence.WEEKLY: "Weekly digest (Monday 07:00 Brussels time, only when something changed)",
    Cadence.NONE: "No email (feed only)",
}
DATE_ALERTS_LABEL: Final = "Flag changes that add or remove a date in the text"
HEARTBEAT_LABEL: Final = "A short note once a month when nothing changed"
NO_CHANGE_YET: Final = "no change recorded yet"
WHAT_A_WATCH_DOES: Final = (
    "You will get an email when a change to this provision appears in the record. The email "
    "repeats what the record says; it does not say whether the change affects you."
)

NOTICES: Final[dict[str, str]] = {
    "added": "Added to the watchlist.",
    "already": "The watchlist already holds that item, so nothing was added.",
    "created": "Watchlist created.",
    "saved": "Settings saved.",
    "deleted": "Watchlist deleted.",
    "removed": "Item removed.",
}
"""The sentence a page shows after a form posted and redirected, by the code in `?notice=`."""

ROLE_ORDER: Final = ("AR", "AN", "PA", "ALN", "PTA", "PTI", "IND")
"""Roles ranked in this order; any other role ranks after these, alphabetically."""

TEXT_LIMIT: Final = 120
"""The longest act key or location a form may name; anything longer names nothing stored."""

_NUMBER: Final = re.compile(r"^(\d{1,9})([a-z]*)$")
_NUMERAL: Final = re.compile(r"^([IVXLC]+)([a-z]*)$")
_ROMAN_VALUES: Final = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

SortKey = tuple[tuple[int, str, int, int, str], ...]


def _roman_value(numeral: str) -> int:
    total = 0
    for here, after in zip(numeral, [*numeral[1:], ""], strict=True):
        value = _ROMAN_VALUES[here]
        total += -value if after and _ROMAN_VALUES[after] > value else value
    return total


def canonical_sort_key(location: str) -> SortKey:
    """A mechanical order for canonical locations, compared token pair by token pair.

    Each `ROLE value` pair ranks first by role, in `ROLE_ORDER` (so every article comes before
    every annex), then by value: a number with an optional lower-case suffix compares by the
    number and then the suffix (`AR 6` < `AR 6a` < `AR 7` < `AR 60`); an annex numeral
    compares by its Roman value (`AN IV` < `AN IX` < `AN X`); any other value compares as text,
    after both. A location sorts directly before everything beneath it.
    """
    tokens = location.split(" ")
    pairs: list[tuple[int, str, int, int, str]] = []
    for at in range(0, len(tokens) - 1, 2):
        role, value = tokens[at], tokens[at + 1]
        rank = ROLE_ORDER.index(role) if role in ROLE_ORDER else len(ROLE_ORDER)
        number = _NUMBER.match(value)
        numeral = _NUMERAL.match(value) if role == "AN" else None
        if number:
            pairs.append((rank, role, 0, int(number.group(1)), number.group(2)))
        elif numeral:
            pairs.append((rank, role, 0, _roman_value(numeral.group(1)), numeral.group(2)))
        else:
            pairs.append((rank, role, 1, 0, value))
    return tuple(pairs)


def sort_provisions(provisions: list[ProvisionView]) -> list[ProvisionView]:
    """`provisions` in canonical order."""
    return sorted(provisions, key=lambda row: canonical_sort_key(row.unit))


def watch_label(act: ActView, location: str | None) -> str:
    """`Annex I of House Rules`, or the act's label alone for the whole act."""
    return f"{human(location)} of {act.label}" if location else act.label


def roster_label(act: ActView) -> str:
    """An act as the roster offers it: its label, then its long name and aliases."""
    other = [name for name in (act.long_name, *act.aliases) if name and name != act.label]
    return f"{act.label} ({', '.join(other)})" if other else act.label


class ItemLine(BaseModel):
    """One watch item as the account page lists it."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="The item's id.")
    act_label: str = Field(description="The act's label, or its key once the catalogue drops it.")
    act_url: str | None = Field(description="The act's page, when the catalogue lists the act.")
    where: str = Field(description="`Article 6(1)`, or `The whole act`.")
    location: str | None = Field(description="The canonical location, None for the whole act.")
    unit: str | None = Field(description="The stored unit containing the location, human form.")
    heading: str | None = Field(description="That unit's stored heading, when it has one.")
    note: str | None = Field(description="`no change recorded yet`, or None.")


def describe_item(
    item: WatchItemView, act: ActView | None, provisions: list[ProvisionView]
) -> ItemLine:
    """How one item reads: what it names, and the heading of the stored unit holding it.

    A location no stored unit contains (`within`) has no change recorded yet; neither has a
    whole act with no stored unit at all.
    """
    holder = None
    if item.location is not None:
        holder = next((row for row in provisions if within(item.location, row.unit)), None)
        unknown = holder is None
    else:
        unknown = not provisions
    return ItemLine(
        id=item.id,
        act_label=act.label if act is not None else item.act_key,
        act_url=act.url if act is not None else None,
        where=human(item.location) if item.location else "The whole act",
        location=item.location,
        unit=human(holder.unit) if holder is not None else None,
        heading=holder.heading if holder is not None else None,
        note=NO_CHANGE_YET if unknown else None,
    )


def readable(text: str) -> bool:
    """Whether `text` may reach a query: short enough, and free of control characters."""
    return len(text) <= TEXT_LIMIT and not any(ord(char) < 32 for char in text)


def read_location(text: str) -> str | None:
    """`parse_location`, refusing text that `readable` refuses."""
    return parse_location(text) if readable(text) else None


def _without_act_name(line: str, act: ActView) -> str:
    for name in sorted(
        {act.label, act.long_name, act.act_key, *act.aliases}, key=len, reverse=True
    ):
        if name and line.lower().startswith(f"{name.lower()} "):
            return line[len(name) + 1 :]
    return line


def resolve_paste(text: str, act: ActView) -> tuple[list[str], list[str]]:
    """The canonical locations a pasted block names, and the lines that name none.

    One location per non-blank line. A line may begin with the act's label, long name, key or
    one of its aliases, followed by a space; that name is dropped when it matches as written,
    ignoring case, and the rest must be a form `parse_location` reads. Resolved locations keep
    their first order and repeat once only.
    """
    resolved: list[str] = []
    unresolved: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        canonical = read_location(_without_act_name(line, act))
        if canonical is None:
            unresolved.append(line)
        elif canonical not in resolved:
            resolved.append(canonical)
    return resolved, unresolved


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


def coverage_line(act: ActView) -> str:
    """How far the record has read an act, and what was announced that it cannot read yet.

    `checked_through` is the end of the last window the poller read, not when it ran, so the
    sentence says "published up to". A waiting row in state `english_unavailable` is a version
    offered in no English text; every other waiting row is a consolidation announced and
    waiting for its text. Nothing here says whether that is good or bad.
    """
    if act.checked_through is None:
        lines = ["The record does not yet say how far this act has been checked for changes."]
    else:
        lines = [f"Checked for changes published up to {act.checked_through.isoformat()}."]
    english = [row for row in act.waiting if row.state == "english_unavailable"]
    pending = [row for row in act.waiting if row.state != "english_unavailable"]
    if pending:
        alone = len(pending) == 1
        seen = sorted(row.first_seen for row in pending if row.first_seen is not None)
        sentence = _count(len(pending), "consolidation", "consolidations") + (
            " has been announced and is waiting for its text"
            if alone
            else " have been announced and are waiting for their text"
        )
        if seen:
            sentence += f"; {'it' if alone else 'the oldest'} was first seen on {seen[0]}"
        lines.append(f"{sentence}.")
    if english:
        verb = "is" if len(english) == 1 else "are"
        lines.append(
            f"{_count(len(english), 'version', 'versions')} {verb} not offered in English."
        )
    return " ".join(lines)
