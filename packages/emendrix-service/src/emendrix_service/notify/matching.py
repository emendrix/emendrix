"""Which watch items a change matches, and how: a set intersection over canonical locations.

An `act` item matches every change of its act. A `provision` item at `L` matches a change by the
first rule that holds:

1. `at`: the change is at `L` or beneath it;
2. `inside`: a `changed_within` coordinate lies inside `L`, or `L` inside it;
3. `container`: the change names no `changed_within` coordinate and `L` lies inside the changed
   unit, so the record says the unit moved and not which part of it.

Containment is `emendrix_record.locations.within`, token-prefix containment, so `AR 60` is never
inside `AR 6`. Nothing here reads text or guesses at a coordinate the record does not state.

A `substance` item names a CAS or EC number and no act. It matches a change of any act, by the
rule `entry`, when a table row the change added, removed or amended carries the number on either
side, as the loader stored it in the change's table hits. An amendment only in spacing, dash
forms or accents does not match; the row is still labelled amended on every page and in the
payload, and is only left out of what the service sends.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.identifiers import SCHEME_NAMES
from emendrix_record.locations import human, within
from emendrix_service.db.enums import ItemKind
from emendrix_service.notify.facts import ChangeFacts, ItemFacts, RowHit

__all__ = [
    "NAME_LIMIT",
    "RANK",
    "Hit",
    "HitReason",
    "best",
    "is_date_alert",
    "match",
    "phrase",
    "row_name",
    "rule",
    "substance_label",
    "substance_rule",
]

HitReason = Literal["act", "at", "inside", "container", "entry"]

RANK: Final[dict[HitReason, int]] = {"at": 0, "inside": 1, "container": 2, "entry": 3, "act": 4}
"""Which reason says most about a change, when several items of one watchlist match it."""


class Hit(BaseModel):
    """One item that matches one change, and the rule it matched by."""

    model_config = ConfigDict(frozen=True)

    item_id: UUID = Field(description="The item that matched.")
    reason: HitReason = Field(description="The rule that matched it.")


NAME_LIMIT: Final = 60
"""The most characters of a row's name a reason quotes before cutting it at a word."""


def substance_rule(item: ItemFacts, hits: Sequence[RowHit]) -> RowHit | None:
    """The first of `hits` carrying the item's number, skipping typography-only amendments."""
    return next(
        (hit for hit in hits if hit.identifier == item.identifier and not hit.typography_only),
        None,
    )


def rule(change: ChangeFacts, item: ItemFacts) -> HitReason | None:
    """The first rule by which `item` matches `change`, or `None`.

    The caller has already narrowed an act or provision item to the change's act; a substance
    item is matched against a change of any act.
    """
    if item.kind == ItemKind.SUBSTANCE:
        return "entry" if substance_rule(item, change.table_hits) is not None else None
    if item.kind == ItemKind.ACT or item.location is None:
        return "act"
    watched = item.location
    if within(change.location, watched):
        return "at"
    if any(within(w, watched) or within(watched, w) for w in change.changed_within):
        return "inside"
    if not change.changed_within and within(watched, change.location):
        return "container"
    return None


def match(change: ChangeFacts, items: Sequence[ItemFacts]) -> tuple[Hit, ...]:
    """Every item of `items` that matches `change`, in the order given, one hit per item."""
    hits: list[Hit] = []
    for item in items:
        reason = rule(change, item)
        if reason is not None:
            hits.append(Hit(item_id=item.item_id, reason=reason))
    return tuple(hits)


def best(hits: Sequence[Hit]) -> Hit | None:
    """The hit whose reason says most; the first given among equals."""
    return min(hits, key=lambda hit: RANK[hit.reason], default=None)


def is_date_alert(change: ChangeFacts) -> bool:
    """Whether the change adds or removes a date in the text, or is a deferral."""
    return bool(change.dates_added or change.dates_removed) or (
        change.change_type.lower() == "deferred"
    )


def substance_label(identifier: str) -> str:
    """`cas:50-00-0` as a sentence names it: `CAS 50-00-0`."""
    scheme, _, value = identifier.partition(":")
    return f"{SCHEME_NAMES.get(scheme, scheme.upper())} {value}"


def row_name(name: str) -> str:
    """A row's name cut at its first `;`, then at a word within `NAME_LIMIT` characters."""
    text = name.split(";", 1)[0].strip()
    if len(text) <= NAME_LIMIT:
        return text
    space = text.rfind(" ", 0, NAME_LIMIT + 1)
    cut = text[:space] if space > 0 else text[:NAME_LIMIT]
    return cut.rstrip(" ,") + "\u2026"


def _entry_phrase(row: RowHit, item: ItemFacts, act_label: str) -> str:
    where = f"in {act_label} {human(row.unit)} was {row.kind}"
    watched = f"you watch {substance_label(item.identifier or '')}"
    if row.key_label is None:
        return f"{watched}; the entry for {row_name(row.name or row.row_key)} {where}"
    label = "entry" if row.key_label == "Entry" else row.key_label
    return f"{watched}; {label} {row.row_key} {where}"


def phrase(hit: Hit, item: ItemFacts, change: ChangeFacts, act_label: str) -> str:
    """Why the change reached the reader, in the words of the rule that matched."""
    if hit.reason == "entry":
        row = substance_rule(item, change.table_hits)
        if row is not None:
            return _entry_phrase(row, item, act_label)
        return f"you watch {substance_label(item.identifier or '')}"
    if hit.reason == "act" or item.location is None:
        return f"you watch {act_label}"
    watched = f"{act_label} {human(item.location)}"
    if hit.reason == "container":
        return (
            f"you watch {watched}; this change is to {human(change.location)}, and the record "
            "does not say which part of it moved"
        )
    return f"you watch {watched}"
