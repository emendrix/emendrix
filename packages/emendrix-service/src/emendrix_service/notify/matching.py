"""Which watch items a change matches, and how: a set intersection over canonical locations.

An `act` item matches every change of its act. A `provision` item at `L` matches a change by the
first rule that holds:

1. `at`: the change is at `L` or beneath it;
2. `inside`: a `changed_within` coordinate lies inside `L`, or `L` inside it;
3. `container`: the change names no `changed_within` coordinate and `L` lies inside the changed
   unit, so the record says the unit moved and not which part of it.

Containment is `emendrix_record.locations.within`, token-prefix containment, so `AR 60` is never
inside `AR 6`. Nothing here reads text or guesses at a coordinate the record does not state.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.locations import human, within
from emendrix_service.db.enums import ItemKind
from emendrix_service.notify.facts import ChangeFacts, ItemFacts

__all__ = ["RANK", "Hit", "HitReason", "best", "is_date_alert", "match", "phrase", "rule"]

HitReason = Literal["act", "at", "inside", "container"]

RANK: Final[dict[HitReason, int]] = {"at": 0, "inside": 1, "container": 2, "act": 3}
"""Which reason says most about a change, when several items of one watchlist match it."""


class Hit(BaseModel):
    """One item that matches one change, and the rule it matched by."""

    model_config = ConfigDict(frozen=True)

    item_id: UUID = Field(description="The item that matched.")
    reason: HitReason = Field(description="The rule that matched it.")


def rule(change: ChangeFacts, item: ItemFacts) -> HitReason | None:
    """The first rule by which `item` matches `change`, or `None`.

    The caller has already narrowed `item` to the change's act.
    """
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


def phrase(hit: Hit, item: ItemFacts, change: ChangeFacts, act_label: str) -> str:
    """Why the change reached the reader, in the words of the rule that matched."""
    if hit.reason == "act" or item.location is None:
        return f"you watch {act_label}"
    watched = f"{act_label} {human(item.location)}"
    if hit.reason == "container":
        return (
            f"you watch {watched}; this change is to {human(change.location)}, and the record "
            "does not say which part of it moved"
        )
    return f"you watch {watched}"
