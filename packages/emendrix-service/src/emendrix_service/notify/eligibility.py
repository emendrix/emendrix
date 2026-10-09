"""Whether a newly seen event may alert anyone: judged once, by its key, and never again.

The rules, in order, the first that holds deciding:

1. `bootstrap`: the notifier has judged nothing yet, so everything already in the record is
   history, and going live sends none of it.
2. `before_live`: the event was detected before the installation went live.
3. `stale_in_force`: its newest in-force date is more than `FRESHNESS` before it was detected,
   which is what a backfill of an old consolidation looks like.
4. `fresh`: otherwise. An event with no in-force date is fresh, because nothing says it is old.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.notify.facts import EventFacts

__all__ = ["FRESHNESS", "Judgement", "Reason", "judge"]

FRESHNESS: Final = timedelta(days=60)
"""How far an event's newest in-force date may lie before its detection and still alert.

The consolidation lag measured against CELLAR is 10 to 17 days between an amendment's entry into
force and the consolidated text that carries it, so 60 days passes every real poll with margin
and still refuses a backfill, whose consolidations are months or years old.
"""

Reason = Literal["bootstrap", "before_live", "stale_in_force", "fresh"]


class Judgement(BaseModel):
    """What the notifier decided about one event, and why."""

    model_config = ConfigDict(frozen=True)

    eligible: bool = Field(description="Whether the event is matched against watchlists.")
    reason: Reason = Field(description="The rule that decided.")
    gap_days: int | None = Field(
        default=None, description="For `stale_in_force`, days from newest in-force to detection."
    )

    def stored(self) -> str:
        """The reason as `notify.announced` keeps it: the code, and the gap after a colon."""
        return self.reason if self.gap_days is None else f"{self.reason}:{self.gap_days}"


def judge(event: EventFacts, *, live_since: date, bootstrap: bool) -> Judgement:
    """The judgement of `event` under the rules of this module."""
    if bootstrap:
        return Judgement(eligible=False, reason="bootstrap")
    if event.detected_on < live_since:
        return Judgement(eligible=False, reason="before_live")
    if event.in_force:
        gap = event.detected_on - max(event.in_force)
        if gap > FRESHNESS:
            return Judgement(eligible=False, reason="stale_in_force", gap_days=gap.days)
    return Judgement(eligible=True, reason="fresh")
