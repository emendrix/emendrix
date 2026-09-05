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

`cross_act_mentions` reads that same pass once more, across every act at once, because the
question "which of these dates has not arrived yet" is the one question no single act's list
can answer. It adds exactly one fact per mention that the per-act list does not carry: whether
a later committed change of the same act took that date back out of the same provision. That
fold is a statement about the committed record and never about the law, and the record it reads
begins at each act's first committed version, which `DateCoverage`'s own counters state.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Change, ProvisionLocation
from emendrix.output import ChangelogEntry
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.urls import entry_anchors, location_slug

__all__ = [
    "IS_NOT_A_SCHEDULE",
    "MOVED",
    "CrossActMention",
    "DateMention",
    "ProvisionHistory",
    "ProvisionStep",
    "ahead",
    "cross_act_mentions",
    "dates_named",
    "histories",
    "passed_within",
]

IS_NOT_A_SCHEDULE: Final = (
    "This is a list of dates the text contains. Whether a provision applies from one of them "
    'is stated for each change under "applies from", and nowhere else.'
)
"""The disclaimer both date lists carry, in one place so neither can be softened alone.

A list of dates under a heading is read as a schedule unless the page says otherwise, and this
project may not publish one: a date in a provision's text is a date the parser read off the
source's own date markup, and what it governs is prose nothing here parses. So the sentence
says what the list is not, and points at the one line on the site that answers the other
question. It lives here rather than on either page because the two pages may not import each
other, and a wording that lived on one of them would be reworded on one surface and not the
next.
"""

MOVED: Final = {True: "added to", False: "removed from"}
"""Which direction the date moved, in the two words `DateMention.added` distinguishes."""


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


def _in_act_order(act: ActSite) -> tuple[DateMention, ...]:
    """Every mention of this act, coordinate by coordinate, newest change of each one first.

    The order `histories` publishes, kept rather than sorted, because the supersession fold
    needs to know which change of a coordinate is the latest one and the sorted list has
    thrown that away. Read off `histories` rather than off the entries directly, so a mention
    carries the same anchor the provision page and the event page publish for the change that
    made it, and no second pass counts the coordinates an event touched twice.
    """
    return tuple(
        DateMention(
            on=on, added=added, location=history.location, entry=step.entry, anchor=step.anchor
        )
        for history in histories(act)
        for step in history.steps
        for on, added in (
            *((value, True) for value in step.change.dates_added),
            *((value, False) for value in step.change.dates_removed),
        )
    )


def dates_named(act: ActSite) -> tuple[DateMention, ...]:
    """Every date any change of this act added or removed, sorted by the date, then location.

    By the date first because that is the only order in which the list is about the act rather
    than about its events: a reader scanning it is asking which dates this legislation's text
    now names, and the events that moved them arrived in whatever order the corpus consolidated.
    Ties break on the provision and then on the change's own anchor, which is unique per change,
    so two events moving one date to one coordinate still come out in a fixed order and the page
    is byte-stable across builds.
    """
    return tuple(
        sorted(
            _in_act_order(act),
            key=lambda one: (one.on, one.location.sort_key, one.anchor, one.added),
        )
    )


class CrossActMention(BaseModel):
    """One act's mention, carried with its act and with whatever later change took it back out.

    The unit of a list that spans acts. A bare date is not it: two acts that both name
    31 December named it independently, and a row gathering them would assert a relationship
    the corpus does not hold. A change is not it either, since one change can move eight dates
    and cannot be sorted by any of them. The mention is what the comparison actually produced,
    and it keeps every address a reader needs to check it against the verbatim text.
    """

    model_config = ConfigDict(frozen=True)

    act: ActSite = Field(description="The act whose text moved the date.")
    mention: DateMention
    superseded_by: DateMention | None = Field(
        default=None,
        description="The later committed change that removed this date from this provision, "
        "when the newest change of the pair removed it; None otherwise.",
    )


def cross_act_mentions(site: SiteInputs) -> tuple[CrossActMention, ...]:
    """Every act's mentions in one list, each carrying whatever later change took it back out.

    The fold is deliberately narrow: for one act, one coordinate and one date, take every
    committed change that added or removed it and look at the newest. If that newest change
    removed the date, every added mention of the pair is marked and linked to it. It says that
    a later amendment took the date out of that provision's text, which is a statement about
    the committed record; whether anything still applies from that date is a question this
    package does not ask anywhere.

    "Newest" is the act's own published order, `clocks.sort_date`, the same order its timeline
    and every newest-first list on the site read. A build handed no version dates falls back to
    the in-force dates, which is a coarser order and can leave a mention unmarked; that is the
    one order this project has, and a second one computed here would be a second answer to a
    question the site already answers everywhere else.

    The order is total and explicit, because byte stability may not rest on a property of one
    corpus: the date first, since the list exists to be read forward, then the act in the
    roster's own order, then the coordinate in the order the act page lists provisions, then
    the change's own anchor and its direction, which no two rows of one act can share.
    """
    found: list[CrossActMention] = []
    for act in site.acts:
        mentions = _in_act_order(act)
        newest: dict[tuple[str, date], DateMention] = {}
        for one in mentions:
            newest.setdefault((one.location.canonical, one.on), one)
        for one in mentions:
            head = newest[(one.location.canonical, one.on)]
            found.append(
                CrossActMention(
                    act=act,
                    mention=one,
                    superseded_by=head if one.added and not head.added else None,
                )
            )
    return tuple(
        sorted(
            found,
            key=lambda one: (
                one.mention.on,
                one.act.label.casefold(),
                one.act.act.key,
                one.mention.location.sort_key,
                one.mention.anchor,
                one.mention.added,
            ),
        )
    )


def ahead(mentions: tuple[CrossActMention, ...], on: date) -> tuple[CrossActMention, ...]:
    """The mentions dated after `on`, in the order they arrived.

    `on` is the build's own date, passed down from the command line, and the comparison is
    strict: a date equal to it has arrived and is therefore not ahead. No clock is read here or
    anywhere below it, so two builds of one corpus on one date split the list identically.
    """
    return tuple(one for one in mentions if one.mention.on > on)


def passed_within(
    mentions: tuple[CrossActMention, ...], on: date, days: int
) -> tuple[CrossActMention, ...]:
    """The mentions dated in the `days` before `on`, inclusive of both ends."""
    first = on - timedelta(days=days)
    return tuple(one for one in mentions if first <= one.mention.on <= on)
