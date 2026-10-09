"""What an email says, as frozen values, before any template turns it into text or HTML.

Every field is a stored fact or a phrase built from one by a rule written in `compose`; nothing
here carries provision text. The feed reuses `ChangeLine`, so the email and the feed state each
change in the same words.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.notify.facts import Citation

__all__ = ["ChangeLine", "Digest", "DigestKind", "EventBlock", "Heartbeat", "SentenceLine"]

DigestKind = Literal["instant", "daily", "weekly"]

_FROZEN = ConfigDict(frozen=True)


class SentenceLine(BaseModel):
    """One stored sentence, unaltered, with the words that say what kind of sentence it is."""

    model_config = _FROZEN

    text: str = Field(description="The sentence as stored.")
    prefix: str = Field(default="", description="What kind of sentence it is, or ''.")
    citations: tuple[Citation, ...] = Field(default=(), description="What it cites, as stored.")


class ChangeLine(BaseModel):
    """One watched change, as one line of an email and one entry of the feed."""

    model_config = _FROZEN

    location: str = Field(description="The change's location in human form, `Article 6`.")
    title: str = Field(description="The act label and the location, `AI Act Article 113`.")
    heading: str | None = Field(default=None, description="The stored heading.")
    change_type: str = Field(description="The change type, lower-cased.")
    disputed: bool = Field(default=False, description="Whether the signals disagree.")
    dispute: str | None = Field(default=None, description="`disputed: ` and its reason sentence.")
    date_alert: bool = Field(default=False, description="Flagged as a date change.")
    dates_removed: tuple[date, ...] = Field(default=(), description="Dates the old text named.")
    dates_added: tuple[date, ...] = Field(default=(), description="Dates the new text names.")
    dates: str | None = Field(default=None, description="The dates removed and added, in words.")
    applies: str = Field(description="What the record read of the application date.")
    sentences: tuple[SentenceLine, ...] = Field(default=(), description="The stored prose.")
    unexplained: str | None = Field(default=None, description="`no explanation: <reason>`.")
    link: str = Field(description="The change on its event page.")
    why: str = Field(description="Which watch item matched, and how.")


class EventBlock(BaseModel):
    """One event of one act, and the watched changes it made."""

    model_config = _FROZEN

    act_label: str = Field(description="The catalogue's label for the act.")
    from_version: str = Field(description="The version compared from.")
    to_version: str = Field(description="The version compared to.")
    in_force: tuple[date, ...] = Field(default=(), description="The event's in-force dates.")
    amending_acts: tuple[str, ...] = Field(default=(), description="Keys of the amending acts.")
    url: str = Field(description="The event's page.")
    lines: tuple[ChangeLine, ...] = Field(description="One line per watched change.")


class Digest(BaseModel):
    """One email of watched changes: an instant one about one event, or a daily or weekly one."""

    model_config = _FROZEN

    kind: DigestKind = Field(description="Which delivery the email is.")
    watchlist_name: str = Field(description="The watchlist's name.")
    events: tuple[EventBlock, ...] = Field(description="The events, oldest first.")
    date_alert_count: int = Field(default=0, description="Lines flagged as a date change.")
    why: tuple[str, ...] = Field(default=(), description="Each distinct reason, in order.")

    @property
    def lines(self) -> tuple[ChangeLine, ...]:
        """Every line of every event, in order."""
        return tuple(line for event in self.events for line in event.lines)


class Heartbeat(BaseModel):
    """The monthly note: still watching, and nothing was sent last month."""

    model_config = _FROZEN

    watchlist_name: str = Field(description="The watchlist's name.")
    month: str = Field(description="The quiet month's name, `October`.")
    watched: tuple[str, ...] = Field(description="What the watchlist watches, in words.")
