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

`dates_named` reads the same pass a second way, by the date rather than by the coordinate. A
change carries the machine-readable dates its text stopped and started naming, and gathering
them under the act answers a question no one event page can: which dates does this legislation's
text name, and which amendment put each one there. It is a list of mentions and never a
schedule. Whether a provision applies from one of the dates in it is `Change.applies_from`'s
answer, stated on the change and nowhere else.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.inputs import ActSite
from emendrix.site_.urls import entry_anchors, location_slug

__all__ = ["DateMention", "ProvisionHistory", "ProvisionStep", "dates_named", "histories"]


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


class DateMention(BaseModel):
    """One machine-readable date one change moved, and everywhere a reader can go to see it.

    A mention, never an entry in a calendar: it says that a provision's text stopped or started
    naming this date, which is what the parser read. What the date does, and whether the
    provision applies from it, is `Change.applies_from`'s question and is answered on the change
    itself.
    """

    model_config = ConfigDict(frozen=True)

    on: date = Field(
        description="The date the text names, as the source's own date markup gave it."
    )
    added: bool = Field(description="True when the new text names it, False when the old text did.")
    location: ProvisionLocation = Field(description="The provision whose text moved it.")
    entry: ChangelogEntry = Field(description="The committed event the change came from.")
    anchor: str = Field(
        min_length=1, description="That change's fragment on the event page, as `ProvisionStep`."
    )


def dates_named(act: ActSite) -> tuple[DateMention, ...]:
    """Every date any change of this act added or removed, sorted by the date, then location.

    By the date first because that is the only order in which the list is about the act rather
    than about its events: a reader scanning it is asking which dates this legislation's text
    now names, and the events that moved them arrived in whatever order the corpus consolidated.
    Ties break on the provision and then on the change's own anchor, which is unique per change,
    so two events moving one date to one coordinate still come out in a fixed order and the page
    is byte-stable across builds.

    Read off `histories` rather than off the entries directly, so a mention carries the same
    anchor the provision page and the event page publish for the change that made it, and no
    second pass counts the coordinates an event touched twice.
    """
    mentions = [
        DateMention(
            on=on, added=added, location=history.location, entry=step.entry, anchor=step.anchor
        )
        for history in histories(act)
        for step in history.steps
        for on, added in (
            *((value, True) for value in step.change.dates_added),
            *((value, False) for value in step.change.dates_removed),
        )
    ]
    return tuple(
        sorted(mentions, key=lambda one: (one.on, one.location.sort_key, one.anchor, one.added))
    )
