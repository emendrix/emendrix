"""What an instruction parse is: one record, one miss, and the whole read of an act.

Split out of the walk that produces them (`read.py`) so the shape this signal publishes can
be read without reading the markup rules that fill it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, ChangeType, ProvisionLocation, SignalClaim

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
    a parser whose recall is a rumour is worth nothing as a cross-check.
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

    def for_act(self, act: ActId) -> tuple[InstructionRecord, ...]:
        """The records aimed at one amended act — all of them when the act named none."""
        if not self.scoped:
            return self.records
        return tuple(record for record in self.records if record.amended_act == act)

    def units(self, act: ActId) -> tuple[ProvisionLocation, ...]:
        seen = {record.unit.canonical: record.unit for record in self.for_act(act)}
        return tuple(sorted(seen.values(), key=lambda unit: unit.sort_key))
