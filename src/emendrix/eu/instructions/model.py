"""What an instruction parse is: one record, one miss, and the whole read of an act.

Split out of the walk that produces them (`read.py`) so the shape this signal publishes can
be read without reading the markup rules that fill it.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, ChangeType, ProvisionLocation, SignalClaim
from emendrix.eu.instructions.effect import EffectDateSource

__all__ = ["InstructionParse", "InstructionRecord", "UnreadInstruction"]


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

    def units(self, act: ActId) -> tuple[ProvisionLocation, ...]:
        seen = {record.unit.canonical: record.unit for record in self.for_act(act)}
        return tuple(sorted(seen.values(), key=lambda unit: unit.sort_key))
