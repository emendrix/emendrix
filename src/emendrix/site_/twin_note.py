"""The line under a change, and on a provision page, naming the provision's textual twin.

A twin is a unit of another watched act whose text is textually similar to this one's by the
word ratio the committed twin map records, and nothing more: the note never says a provision
should change, is equivalent or has the same effect. It says four things, each read off a
committed file:

- **Where the twin is**: the aligned child of the deepest changed coordinate that has one,
  else the unit's own twin, linked to the sister act's provision page where the site wrote one,
  else to its public address in the version the pair was computed on.
- **How similar**: the committed ratio, or `identical text` where the comparison texts are
  equal, always under the words `textually similar`, in the visible text.
- **Which texts were paired**: the map pairs the two acts' newest stored versions, which need
  not be the event's own, so the note names their dates.
- **Whether the same amending act changed it**: `yes` when an event of the sister act
  attributed to this event's instrument has a change touching the twin, `no` when such an
  event touches other units only, and, when the record holds no such event, a sentence saying
  exactly that. It never says the act did not amend the twin: the record may simply not hold
  the event. An event no instrument is named for asks nothing, so it gets no answer.

Where the two texts differ, the note and the line link the pair's own page, which shows only
the differing passages. An identical pair has no such page, and nothing to compare.
"""

from __future__ import annotations

from emendrix.core import Change, ProvisionLocation
from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry
from emendrix.site_.amending import amending_keys
from emendrix.site_.clocks import human_date
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape
from emendrix.site_.outbound import external
from emendrix.site_.twin_inputs import TwinIndex, TwinSpot, TwinUnit
from emendrix.site_.urls import provision_href

__all__ = ["COMPARE", "SIMILAR", "twin_line", "twin_note"]

SIMILAR = "textually similar"
"""The gloss every mention of a twin carries, so the word never reads as a legal claim."""

COMPARE = "See where the two texts differ"
"""The words of every link to a twin page."""


def _parents(location: ProvisionLocation) -> list[ProvisionLocation]:
    """The location and every ancestor below its unit, deepest first."""
    return [
        ProvisionLocation(segments=location.segments[:depth])
        for depth in range(location.depth, 1, -1)
    ]


def _spot(change: Change, unit: TwinUnit) -> TwinSpot:
    """The partner of the deepest changed coordinate with one, else the unit's twin."""
    best: ProvisionLocation | None = None
    for changed in change.changed_within:
        for candidate in _parents(changed):
            if candidate.canonical in unit.children and (
                best is None or candidate.depth > best.depth
            ):
                best = candidate
    return unit.twin if best is None else unit.children[best.canonical]


def _touches(change: Change, location: ProvisionLocation) -> bool:
    """Whether a sister change touched the coordinate: its unit, and not only elsewhere in it."""
    if change.location != location.top_level:
        return False
    if location.depth == 1 or not change.changed_within:
        return True
    return any(c.contains(location) or location.contains(c) for c in change.changed_within)


def _answer(twins: TwinIndex, entry: ChangelogEntry, unit: TwinUnit, spot: TwinSpot) -> str:
    keys = amending_keys(entry)
    if not keys:
        return ""
    events = twins.events.get(str(unit.sister.act), {})
    named = [key for key in keys if key in events]
    if not named:
        return f" The record holds no {unit.sister.label} version made by the same amending act."
    location = ProvisionLocation.parse(spot.location)
    touched = any(_touches(change, location) for key in named for change in events[key])
    return f" The same amending act changed it: {'yes' if touched else 'no'}."


def _paired(twins: TwinIndex, unit: TwinUnit) -> str:
    def said(version: str) -> str:
        on = twins.dates.get(version)
        return version if on is None else human_date(on)

    here, there = said(unit.here), said(unit.there)
    if here == there:
        return f"paired on both acts' texts of {here}"
    return f"paired on this act's text of {here} and the {unit.sister.label} text of {there}"


def _lead(twins: TwinIndex, unit: TwinUnit, spot: TwinSpot, root: str) -> Html:
    """`Twin in IVDR: Art. 10(9), textually similar (0.973), paired on ...`, no full stop."""
    sister = unit.sister
    named = ProvisionLocation.parse(spot.location).human
    if unit.page:
        href = escape(root + provision_href(sister.slug, unit.twin.location))
        where = Html(f'<a href="{href}">{escape(named)}</a>')
    elif spot.url:
        where = external(spot.url, named)
    else:
        where = escape(named)
    score = "identical text" if spot.identical else f"{spot.ratio:.3f}"
    return Html(
        f"<strong>Twin in {escape(sister.label)}:</strong> {where}, "
        f"{escape(SIMILAR)} ({escape(score)}), {escape(_paired(twins, unit))}."
    )


def _compare(unit: TwinUnit, root: str) -> Html:
    if not unit.compare:
        return Html("")
    return Html(f' <a href="{escape(root + unit.compare)}">{escape(COMPARE)}</a>.')


def twin_note(
    site: SiteInputs, act: ActSite, entry: ChangelogEntry, emitted: EmittedChange, root: str
) -> list[Html]:
    """One line per sister act under a change whose unit has a twin; empty where none has."""
    change = emitted.change
    lines: list[Html] = []
    for unit in site.twins.twins(act.act, change.location.canonical):
        spot = _spot(change, unit)
        answer = _answer(site.twins, entry, unit, spot)
        lead = _lead(site.twins, unit, spot, root)
        compare = _compare(unit, root)
        lines.append(Html(f'<p class="small muted">{lead}{escape(answer)}{compare}</p>'))
    return lines


def twin_line(site: SiteInputs, act: ActSite, canonical: str, root: str) -> list[Html]:
    """A provision page's header line per sister act naming the unit's twin; empty for none."""
    return [
        Html(
            f'<p class="facts">{_lead(site.twins, unit, unit.twin, root)}{_compare(unit, root)}</p>'
        )
        for unit in site.twins.twins(act.act, canonical)
    ]
