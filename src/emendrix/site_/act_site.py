"""One act as the site shows it: its names, its addresses and its committed events, resolved.

Split out of `inputs` at the boundary between one act's resolved view and the whole build's
inputs: everything here is about a single act and reads nothing site-wide, while `inputs`
gathers the acts with the deployment facts and the report into what a build renders. `inputs`
re-exports `ActSite`, so a renderer may import it from either module.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId
from emendrix.output import ChangelogEntry
from emendrix.output.json_out import slug
from emendrix.site_.attribution import unattributed
from emendrix.site_.clocks import EventDate, event_date

__all__ = ["ActSite"]


class ActSite(BaseModel):
    """One act as the site shows it: its label, its grouping, and every committed event."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    label: str = Field(min_length=1)
    long_name: str = Field(default="", description="The watchlist's long form, or ''.")
    domain: str = Field(default="", description="Index grouping; empty lands under 'Other'.")
    aliases: tuple[str, ...] = ()
    eurlex_url: str = Field(default="", description="Resolved at the CLI boundary; '' = none.")
    published_url: str = Field(default="", description="The act as published; '' = none.")
    entries: tuple[ChangelogEntry, ...] = Field(
        default=(), description="Newest first by `sort_date`."
    )

    @property
    def slug(self) -> str:
        """The act's path segment: its own key, made filesystem-safe."""
        return slug(self.act.key)

    @property
    def headline(self) -> str:
        """What the page's H1 says: the long form when the watchlist gives one, else the label."""
        return self.long_name or self.label

    @property
    def newest_amendment(self) -> ChangelogEntry | None:
        """The newest event an amending act is named for; None when there is no such event.

        Newest by `sort_date`, the order `entries` arrives in. An event no amending act is
        named for is never the answer: this backs every "newest amendment" line the site
        prints, and one of those answered by such an event would dress it as an amendment. So
        `None` has two readings, told apart by `entries`, and each caller says which in words:
        nothing was ever seen, or everything seen names no amending act.
        """
        for entry in self.entries:
            if not unattributed(entry):
                return entry
        return None

    @property
    def dated(self) -> EventDate | None:
        """That event's date with its clock, or None. The clock is that entry's own, a true
        statement about it even when another entry carries a later detection date."""
        entry = self.newest_amendment
        return None if entry is None else event_date(entry)
