"""What an instruction parse is: one record, one miss, and the whole read of an act.

Split out of the walk that produces them (`read.py`) so the shape this signal publishes can
be read without reading the markup rules that fill it.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, ChangeType, ProvisionLocation, SignalClaim
from emendrix.eu.instructions.effect import EffectDateSource

__all__ = [
    "InstructionParse",
    "InstructionRecord",
    "UnreadInstruction",
    "Window",
    "WindowedInstructions",
]

type Window = tuple[date | None, date]
"""One consolidation's window, `(after, until]`, exactly as `eu/signals.py` computes it.

A value passed down from the composition root, never a clock read. `None` for the lower bound
is the act as published, where everything up to the later version belongs to the pair.
"""


class InstructionRecord(BaseModel):
    """One instruction, as read: what it points at, what it orders, and where it was said."""

    model_config = ConfigDict(frozen=True)

    location: ProvisionLocation
    change_type: ChangeType
    source_ref: str = Field(description="Where the instruction sits, e.g. `AR 1 (7)(a)`.")
    amended_act: ActId | None = Field(
        default=None, description="The act its instruction article names, where it names one."
    )
    from_quotation: bool = Field(
        default=False, description="True when the identifier came from the quoted provision."
    )
    effect_date: date | None = Field(
        default=None,
        description="When this instruction takes effect, read from its own act's text.",
    )
    effect_source: EffectDateSource = Field(
        default=EffectDateSource.UNREAD,
        description="Which of the act's own statements the date came from, `unread` for none.",
    )

    @property
    def unit(self) -> ProvisionLocation:
        return self.location.top_level

    def claimed_in(self, window: Window | None) -> bool:
        """Whether this instruction belongs to `(after, until]`, the window's own convention.

        A record the act dated nowhere belongs to every window: the reader that could not date
        it is a counted gap, and dropping a claim on the strength of a date nobody read would
        be guessing in the one direction that loses a finding.
        """
        if window is None or self.effect_date is None:
            return True
        after, until = window
        return (after is None or after < self.effect_date) and self.effect_date <= until

    def to_claim(self, *, amending_act: ActId | None = None) -> SignalClaim:
        """The corroboration-shaped claim. `amending_act` is the document this was parsed from.

        Not `self.amended_act`, which is the act the instruction *targets*. The record cannot
        supply it, so it is passed in by the caller that read the document.
        """
        return SignalClaim(
            location=self.location,
            change_type=self.change_type,
            source=self.source_ref,
            amending_act=amending_act,
        )


class UnreadInstruction(BaseModel):
    """A clause that looks like an instruction and produced no record. Counted, never guessed."""

    model_config = ConfigDict(frozen=True)

    source_ref: str
    clause: str
    reason: str


class WindowedInstructions(BaseModel):
    """The records one consolidation claims from an act, and what claiming them cost.

    Both counts are published in the signal's note, so a reader of the payload can tell an
    empty signal from a scoped one without leaving the payload. Both are counts over the
    records, not statements about the caller, which is why the unbounded window reports the
    zero it measured rather than a phrase about having no dates.
    """

    model_config = ConfigDict(frozen=True)

    records: tuple[InstructionRecord, ...] = ()
    excluded: int = Field(
        default=0,
        description="Records this act dates outside the window. No window excludes nothing.",
    )
    undated: int = Field(
        default=0, description="Claimed records the act's own text left with no effect date."
    )

    @property
    def summary(self) -> str:
        """The note's own second half: what the window left out and what it could not date."""
        return f"{self.excluded} dated outside the window, {self.undated} undated and claimed"


class InstructionParse(BaseModel):
    """Every instruction of one amending act, and every one it could not read.

    `matched` and `unread` together are the coverage statistic this signal is published with:
    a parser whose recall is a rumour is worth nothing as a cross-check. `dated` and `undated`
    are the second such statistic, over the effect date each record carries (`effect.py`).
    """

    model_config = ConfigDict(frozen=True)

    act: ActId
    records: tuple[InstructionRecord, ...] = ()
    unread: tuple[UnreadInstruction, ...] = ()
    targets: tuple[ActId, ...] = Field(
        default=(), description="The acts its instruction articles name, in document order."
    )
    scoped: bool = Field(
        default=True, description="False when no article named an act and every one was read."
    )

    @property
    def matched(self) -> int:
        return len(self.records)

    @property
    def coverage(self) -> float:
        """Matched instructions over instruction-looking clauses. `1.0` when nothing was unread."""
        total = self.matched + len(self.unread)
        return 1.0 if total == 0 else self.matched / total

    @property
    def dated(self) -> int:
        """Records whose effect date the act's own text yielded."""
        return sum(1 for record in self.records if record.effect_date is not None)

    @property
    def undated(self) -> int:
        """The counted gap: records the four-tier read left with no date. Never an error."""
        return self.matched - self.dated

    @property
    def effect_date_coverage(self) -> float:
        """Dated records over records. `1.0` when there was nothing to date."""
        return 1.0 if self.matched == 0 else self.dated / self.matched

    def for_act(self, act: ActId) -> tuple[InstructionRecord, ...]:
        """The records aimed at one amended act — all of them when the act named none."""
        if not self.scoped:
            return self.records
        return tuple(record for record in self.records if record.amended_act == act)

    def in_window(self, act: ActId, window: Window | None) -> WindowedInstructions:
        """One act's records as one consolidation may claim them, with the two counts.

        An amending act's instruction set is one document and is read once; which of it belongs
        to a given consolidation is this. Without it the same instructions are claimed again in
        every window the act touches, years after the one they took effect in.

        `None` is the unbounded window and claims the act whole, which is what a caller holding
        no dates can honestly say. It excludes nothing, and the count says so.
        """
        wanted = self.for_act(act)
        claimed = tuple(record for record in wanted if record.claimed_in(window))
        return WindowedInstructions(
            records=claimed,
            excluded=len(wanted) - len(claimed),
            undated=sum(1 for record in claimed if record.effect_date is None),
        )

    def units(self, act: ActId) -> tuple[ProvisionLocation, ...]:
        seen = {record.unit.canonical: record.unit for record in self.for_act(act)}
        return tuple(sorted(seen.values(), key=lambda unit: unit.sort_key))
