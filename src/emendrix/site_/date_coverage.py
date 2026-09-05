"""How much of the committed corpus carries a date at all, counted before any of it is shown.

The forward list of dates is a view of a small corner of the corpus, and a page that showed
only that corner without saying how small it is would be selecting rather than publishing. So
every figure the panel prints is counted here, over the committed entries one build renders,
and the page prints what this returns and nothing it worked out for itself.

Two questions, kept apart because they are not one. `Change.dates_added` and
`Change.dates_removed` say which machine-readable dates a provision's text stopped and started
naming; `Change.applies_from` is clock 2, read deterministically from a date change in the act's
own application article, and it is the only field in this project that says a provision applies
from a date. The counters for the two are separate fields here and separate blocks on the page.

`ApplicabilityUnknown` is a value that flows to the output and gets counted, never a silence, so
its reasons are published in the corpus's own words with the block that records none named
rather than dropped: a breakdown that listed only the reasons that exist would not add up to its
own total.

The corpus totals come from `SiteInputs.corpus`, the same rollup the methodology page publishes
its rates from, so one denominator carries every share on the site. No clock, no network, no
model: two builds of one repository state count the same numbers.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ApplicabilityUnchanged, ApplicabilityUnknown
from emendrix.site_.history import CrossActMention, ProvisionStep, ahead, histories
from emendrix.site_.inputs import ActSite, SiteInputs

__all__ = ["DateCoverage", "applies_ahead", "coverage"]

NO_REASON: Final = "no reason recorded"
"""What an `ApplicabilityUnknown` carrying no reason is called in the published breakdown."""


class DateCoverage(BaseModel):
    """Everything the coverage panel prints, counted off the committed entries this build holds.

    A frozen model rather than loose locals, so a test can assert that the page prints the
    numbers this module returned and no others.
    """

    model_config = ConfigDict(frozen=True)

    events: int = Field(default=0, ge=0, description="Committed events this build renders.")
    changes: int = Field(default=0, ge=0, description="Changes across those events.")
    textless: int = Field(default=0, ge=0, description="Changes with no text on either side.")
    without_a_date: int = Field(
        default=0, ge=0, description="Changes whose text moved no machine-readable date."
    )
    applies_dated: int = Field(
        default=0, ge=0, description="Changes whose `applies_from` resolves to a date."
    )
    applies_unchanged: int = Field(
        default=0, ge=0, description="Changes stating that the date they apply from did not move."
    )
    applies_unknown: int = Field(
        default=0, ge=0, description="Changes stating that no such date could be read."
    )
    unknown_reasons: tuple[tuple[str, int], ...] = Field(
        default=(),
        description="Why, in the corpus's own words, biggest block first; ties by the wording.",
    )
    dated_ahead: int = Field(
        default=0, ge=0, description="Of the resolved dates, those falling after the build date."
    )
    mentions: int = Field(default=0, ge=0, description="Dates added or removed, over the corpus.")
    mentions_ahead: int = Field(default=0, ge=0, description="Of those, dated after the build.")
    superseded_ahead: int = Field(
        default=0, ge=0, description="Of those, added and later removed from the same provision."
    )
    acts_ahead: int = Field(default=0, ge=0, description="Acts supplying a mention ahead.")
    acts_with_events: int = Field(default=0, ge=0, description="Acts with a committed event.")
    earliest: date | None = Field(default=None, description="The oldest reading, or None.")
    latest: date | None = Field(default=None, description="The newest reading, or None.")
    gaps: int = Field(
        default=0,
        ge=0,
        description="Beyond each act's own opening, events reaching back to a version no "
        "other event of that act produced.",
    )

    @property
    def with_a_date(self) -> int:
        """Changes whose text moved at least one machine-readable date."""
        return self.changes - self.without_a_date

    @property
    def mentions_behind(self) -> int:
        """Mentions dated on or before the build date, so not in the forward list."""
        return self.mentions - self.mentions_ahead

    @property
    def acts_with_nothing_ahead(self) -> int:
        """Acts holding a committed event and no date after the build date."""
        return self.acts_with_events - self.acts_ahead


def _reason(change_applies: ApplicabilityUnknown) -> str:
    """The stated reason, or the name the page gives the block that states none."""
    return change_applies.reason or NO_REASON


def _gaps(site: SiteInputs) -> int:
    """Events whose earlier version is not one any other committed event of the act produced.

    Every act has exactly one such event legitimately, the oldest one the corpus holds, since
    nothing precedes an act's first committed version; that one is subtracted and the rest are
    the holes. Read off the set of versions rather than off consecutive pairs, so the answer is
    a property of what the corpus holds and not of the order a build happens to list it in.
    Counted rather than described, because the caveat this feeds is about how much of an act's
    history is here, and a caveat carrying a number a reader can check is worth more than one
    hedging in general terms.
    """
    found = 0
    for act in site.acts:
        produced = {entry.to_version for entry in act.entries}
        unreached = sum(1 for entry in act.entries if entry.from_version not in produced)
        found += max(unreached - 1, 0)
    return found


def coverage(site: SiteInputs, mentions: tuple[CrossActMention, ...]) -> DateCoverage:
    """The panel's numbers, counted once so the page cannot print a figure it did not compute.

    `mentions` is the fold the page renders, passed in rather than rebuilt, so the count of
    what is on screen and the count in the panel cannot come apart.
    """
    counts = site.corpus
    reasons: Counter[str] = Counter()
    without = dated = unchanged = unknown = dated_ahead = 0
    for _, entry in site.recent:
        for emitted in entry.changes:
            change = emitted.change
            if not change.dates_added and not change.dates_removed:
                without += 1
            if isinstance(change.applies_from, date):
                dated += 1
                if change.applies_from > site.generated_on:
                    dated_ahead += 1
            elif isinstance(change.applies_from, ApplicabilityUnchanged):
                unchanged += 1
            else:
                unknown += 1
                reasons[_reason(change.applies_from)] += 1
    forward = ahead(mentions, site.generated_on)
    days = [one.mention.on for one in mentions]
    return DateCoverage(
        events=counts.events,
        changes=counts.changes,
        textless=counts.textless,
        without_a_date=without,
        applies_dated=dated,
        applies_unchanged=unchanged,
        applies_unknown=unknown,
        unknown_reasons=tuple(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
        dated_ahead=dated_ahead,
        mentions=len(mentions),
        mentions_ahead=len(forward),
        superseded_ahead=sum(1 for one in forward if one.superseded_by is not None),
        acts_ahead=len({one.act.act.key for one in forward}),
        acts_with_events=sum(1 for act in site.acts if act.entries),
        earliest=min(days, default=None),
        latest=max(days, default=None),
        gaps=_gaps(site),
    )


def applies_ahead(site: SiteInputs) -> tuple[tuple[ActSite, ProvisionStep, date], ...]:
    """Every change whose `applies_from` resolves to a date later than the build date.

    Read off `histories` like the mentions are, so a row carries the anchor the event page
    publishes for the change that moved the date and lands on the block a reader can check it
    in. Ordered on the same key the mentions are, so the two blocks read in one direction.
    """
    found: list[tuple[ActSite, ProvisionStep, date]] = []
    for act in site.acts:
        for history in histories(act):
            for step in history.steps:
                applies = step.change.applies_from
                if isinstance(applies, date) and applies > site.generated_on:
                    found.append((act, step, applies))
    return tuple(
        sorted(
            found,
            key=lambda row: (
                row[2],
                row[0].label.casefold(),
                row[0].act.key,
                row[1].change.location.sort_key,
                row[1].anchor,
            ),
        )
    )
