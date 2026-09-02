"""Which clock dates an event, and which clock orders a list. They are not one thing.

Three dates can describe one amendment event: the day its changes came into force (clock 1,
the corpus's own answer), the day emendrix first saw it, and the day the consolidated version
it produced speaks as of. Mixing them in one key is how the front page once ranked a
years-old transition, detected that day by a backfill, above the newest real amendment: a
detection date and an in-force date compare cleanly and mean nothing compared. So the
vocabulary keeps the jobs apart: `sort_date` orders every newest-first list, `event_dated`
stamps timestamps and is the stated fallback, and `EventDate` carries a date together with
its clock for anything a reader sees.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, VersionId
from emendrix.output import ChangelogEntry

__all__ = ["EventDate", "VersionDates", "event_date", "event_dated", "sort_date"]


def event_dated(entry: ChangelogEntry) -> date:
    """When an event took effect: clock 1 if the changes carry it, else when it was seen.

    A bare date, for machine timestamps and as `sort_date`'s fallback: it drops which clock
    answered. A page printing the date under words reads `ActSite.dated`, which keeps the
    clock, and no newest-first list orders by this alone, because its fallback compares a
    detection date against in-force dates as if they measured one thing.
    """
    return max(entry.in_force) if entry.in_force else entry.detected_on


VersionDates = Mapping[tuple[ActId, VersionId], date]
"""The date each version speaks as of, for the events whose corpus resolved one.

Resolved at the CLI boundary, where a corpus may be named and a version tag read; this module
only looks entries up. Keyed by act and tag together rather than the tag alone, because a tag
is corpus-scoped and nothing stops two corpora minting the same string.
"""


def sort_date(entry: ChangelogEntry, version_dates: VersionDates) -> date:
    """The clock every newest-first list on the site shares.

    The consolidated version's own date where the corpus resolved one, else `event_dated`.
    The version date is a fact about the legislation and the detection date a fact about
    when emendrix ran; the module docstring holds the incident that keeps them out of one
    key. Feeds' `<updated>` and the sitemap's `<lastmod>` answer when a page changed rather
    than what is newest, and read `event_dated` on purpose.
    """
    resolved = version_dates.get((entry.act, entry.to_version))
    return resolved if resolved is not None else event_dated(entry)


class EventDate(BaseModel):
    """A date and the clock that produced it, inseparable.

    The corpus's own in-force date and the day emendrix first saw an event are different
    claims, and a page that has only the date cannot help labelling one as the other.
    The acts index once printed the fallback under "last amended", which told a reader
    the act moved on a day emendrix merely ran; carrying the clock in the value makes
    that misreading impossible to write by accident.
    """

    model_config = ConfigDict(frozen=True)

    on: date
    in_force: bool = Field(
        description="True for clock 1, the corpus's own answer; False when `on` is the "
        "date the event was first seen."
    )

    @property
    def words(self) -> str:
        """The clock and the date, in the words every dated line on the site uses.

        Rendered here once and imported rather than restated, for the reason `act_event`
        gives: two renderings of one fact that describe it differently are how a caveat
        gets softened in one of them.
        """
        clock = "in force" if self.in_force else "detected"
        return f"{clock} {self.on.isoformat()}"


def event_date(entry: ChangelogEntry) -> EventDate:
    """One event's date with its clock: the one place a page's dated words are built from.

    The act header, the home card, the acts index row and the event page title all print the
    same fact, and each once built it by hand from `in_force` and `detected_on`. One builder
    means the clock a page names is decided once, and a line that says "in force" over a
    detection date cannot be written by a renderer that forgot the second branch.
    """
    return EventDate(on=event_dated(entry), in_force=bool(entry.in_force))
