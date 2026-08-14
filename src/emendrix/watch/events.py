"""The typed vocabulary of the WATCH stage: what a poll is asked, and what it answers with.

Separated from `watch/poll.py` for the same reason `core/` is separated from `diff/`: the
algorithm is one thing to read and the shapes it moves between are another. The graph imports
these; it has no reason to import the loop.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, Unavailable, VersionDescriptor, VersionId
from emendrix.watch.state import WatchState

__all__ = [
    "AmendmentEvent",
    "PollResult",
    "PollStats",
    "PollWindow",
    "VersionSource",
]


class VersionSource(Protocol):
    """The one thing the poller needs from a corpus: what versions an act has now.

    Deliberately the `CorpusAdapter` method rather than anything EU-shaped — `EuCorpusAdapter`
    satisfies it as it stands, and so does a three-line test double.
    """

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]: ...


class PollWindow(BaseModel):
    """The slice of time a poll asks the feed about, and the date it stamps states with."""

    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime
    observed_on: date


class AmendmentEvent(BaseModel):
    """One thing worth telling somebody about: a new version, or the state that blocks it.

    Exactly one of `new_version` and `unavailable` is set. An event carrying `unavailable` is
    not a failure — `ConsolidationPending` and `EnglishUnavailable` are answers: they are
    rendered, they are counted, and they are re-checked until they resolve.
    """

    model_config = ConfigDict(frozen=True)

    act: ActId
    target_version: VersionId | None = Field(
        default=None, description="The version this event is about, fetchable or not."
    )
    new_version: VersionId | None = None
    previous_version: VersionId | None = None
    version_date: date | None = None
    unavailable: Unavailable | None = None
    trigger: str = Field(default="", description="The feed identifier that surfaced this.")
    observed_on: date

    @property
    def ready(self) -> bool:
        """True when there is text to diff — i.e. the downstream pipeline can run."""
        return self.new_version is not None

    @property
    def key(self) -> str:
        """The dedupe identity: what was reported, about which version of which act."""
        if self.new_version is not None:
            return f"{self.act}@{self.new_version}"
        state = self.unavailable.state if self.unavailable is not None else "unknown"
        return f"{self.act}@{state}:{self.target_version or 'latest'}"


class PollStats(BaseModel):
    """What the poll saw, including everything it deliberately did nothing about."""

    model_config = ConfigDict(frozen=True)

    entries: int = 0
    duplicates: int = Field(default=0, description="Entries already seen in an earlier window.")
    matched: int = Field(default=0, description="Entries naming a watched act.")
    suppressed: int = Field(default=0, description="Matches whose event had already been sent.")
    pending_checked: int = 0
    pending_resolved: int = 0
    truncated: bool = Field(
        default=False,
        description="The window was not read to its end; the cursor stopped where the feed did.",
    )


class PollResult(BaseModel):
    """The events, the state to persist, and the numbers behind both."""

    model_config = ConfigDict(frozen=True)

    events: tuple[AmendmentEvent, ...] = ()
    state: WatchState
    stats: PollStats = PollStats()
