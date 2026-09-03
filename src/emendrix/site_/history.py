"""One provision read down the act's history: every event that touched it, newest first.

The pipeline's unit is a version transition, so a committed document is one event and the
changes it holds are that event's. The reader's unit is the provision: what has Annex XVII done
over time? This module is that inversion, and it is nothing more. A step exists because a
committed change names that coordinate; the order is the order the act's own timeline already
publishes; and no step is merged, deduplicated or reconciled with another.

Two consequences of that, both deliberate:

- **A coordinate touched twice inside one event is two steps.** One event can carry two changes
  at one location, and the anchor scheme already tells them apart (`urls.entry_anchors` counts
  occurrences and suffixes the second). Collapsing them would drop a change from a page whose
  whole purpose is to hold every change to that provision.
- **Annex numerals are not reconciled.** The corpus writes `AN 4` for one act's annex and
  `AN IV` for another's, and both spellings appear in the committed data for annexes of the same
  act read through different signals. They are two units in the data and each keeps its own
  history, because merging them by roman value would be this package deciding what a corpus
  meant (`docs/limitations.md`).

The anchors ride along rather than being recomputed by whoever renders a step: a provision page
uses them as its step ids, so a link minted for an event page keeps working on the provision
page and the reader can move between the two without either side running its own counter.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.inputs import ActSite
from emendrix.site_.urls import entry_anchors, location_slug

__all__ = ["ProvisionHistory", "ProvisionStep", "histories"]


class ProvisionStep(BaseModel):
    """One event's change to one provision: the change, its entry, and its event-page anchor."""

    model_config = ConfigDict(frozen=True)

    entry: ChangelogEntry = Field(description="The committed event this change came from.")
    index: int = Field(
        ge=0,
        description="Position in `entry.changes`; the text cache is keyed "
        "by it, so a caller reads the evidence back positionally.",
    )
    anchor: str = Field(
        min_length=1,
        description="The fragment the event page publishes for "
        "this change, reused as the provision page's step id.",
    )

    @property
    def change(self) -> Change:
        """The change itself, read back from the entry rather than stored twice."""
        return self.entry.changes[self.index].change


class ProvisionHistory(BaseModel):
    """One coordinate and every committed change to it, in the act's own order."""

    model_config = ConfigDict(frozen=True)

    location: ProvisionLocation
    steps: tuple[ProvisionStep, ...] = Field(
        min_length=1, description="Newest first, the act's entry order; never empty."
    )


def histories(act: ActSite) -> tuple[ProvisionHistory, ...]:
    """Every provision this act's events touched, sorted by `ProvisionLocation.sort_key`.

    Sorted by the sort key rather than by the canonical string, so `AR 10` follows `AR 9` and
    `AN II` follows `AN I`, which is the order the act page's index already lists them in. The
    steps inside a history are left in the order the entries arrived, which `collect_site`
    guarantees is newest first.

    Two coordinates whose slugs collide are refused rather than written, for the reason
    `instruments.amended_by` refuses two instruments that would share a path: a page written
    twice is a page the tree lists once and serves as the other. `location_slug` documents the
    one shape that can do it, a lettered point written without its parentheses, and no change
    location in the committed corpus is one.
    """
    found: dict[str, list[ProvisionStep]] = {}
    locations: dict[str, ProvisionLocation] = {}
    paths: dict[str, str] = {}
    for entry in act.entries:
        anchors = entry_anchors(
            entry.key, [emitted.change.location.canonical for emitted in entry.changes]
        )
        for index, anchor in enumerate(anchors):
            location = entry.changes[index].change.location
            key = location.canonical
            if key not in locations:
                locations[key] = location
                path = location_slug(key)
                if paths.setdefault(path, key) != key:
                    raise ValueError(
                        f"provisions {paths[path]} and {key} share the URL path {path!r}"
                    )
            found.setdefault(key, []).append(ProvisionStep(entry=entry, index=index, anchor=anchor))
    return tuple(
        ProvisionHistory(location=locations[key], steps=tuple(steps))
        for key, steps in sorted(found.items(), key=lambda item: locations[item[0]].sort_key)
    )
