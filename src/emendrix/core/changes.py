"""The vocabulary a change is described in: its kind, the signals that saw it, its two clocks.

`SignalSet` records which of the three independent signals saw a change, so a disagreement
ships as `disputed` instead of being silently dropped or merged away. `Applicability` is
clock two: a date only when deterministically readable, otherwise a stated non-answer.

The `Change` and `Delta` these describe live in `emendrix.core.delta`.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Applicability",
    "ApplicabilityUnchanged",
    "ApplicabilityUnknown",
    "ChangeType",
    "Signal",
    "SignalObservation",
    "SignalSet",
    "SignalStatus",
]


class ChangeType(StrEnum):
    """How a provision changed. Assigned by the diff and its classification, never by a model.

    `RENUMBERED` and `DEFERRED` are carried from the first commit so the schema never
    migrates, even though no trace has yet produced a renumbering: none occurred in the seven
    end-to-end traces under `scripts/validation/results/`, and no role code plausibly meaning
    "renumbered" appears in the 540 annotations they inventory.
    """

    INSERTED = "INSERTED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENUMBERED = "RENUMBERED"
    DEFERRED = "DEFERRED"


class Signal(StrEnum):
    """The three independent signals corroboration merges."""

    STRUCTURAL_DIFF = "structural_diff"
    CORPUS_METADATA = "corpus_metadata"
    INSTRUCTION_PARSE = "instruction_parse"


class SignalStatus(StrEnum):
    """Whether a signal saw this change, did not see it, or could not have.

    `UNAVAILABLE` is not a disagreement: a corpus that publishes no modification metadata
    cannot dissent. Only `OBSERVED` against `ABSENT` is a dispute.
    """

    OBSERVED = "observed"
    ABSENT = "absent"
    UNAVAILABLE = "unavailable"


class SignalObservation(BaseModel):
    """One signal's verdict on one change, with whatever detail that signal carries.

    `change_types` is what this signal said the change *was*, at the top-level unit
    granularity: a set, because one signal can name a unit more than once and in more than one
    way (the AI Act's Article 5 carries both inserted points and replaced ones). Two signals
    disagree on kind when their sets do not intersect; a signal that names no kind never disagrees.
    """

    model_config = ConfigDict(frozen=True)

    status: SignalStatus = SignalStatus.UNAVAILABLE
    detail: str | None = None
    change_types: tuple[ChangeType, ...] = ()

    @property
    def observed(self) -> bool:
        return self.status is SignalStatus.OBSERVED


class SignalSet(BaseModel):
    """The three verdicts on one change.

    The structural diff is the primary shipped signal, and the only one carrying actual text.
    Corpus metadata is the evaluation reference set, and it is *not* an oracle: a blanket
    amendment is annotated once and its 30 landing sites are not enumerated (measured
    2026-08-05).
    """

    model_config = ConfigDict(frozen=True)

    structural_diff: SignalObservation = SignalObservation()
    corpus_metadata: SignalObservation = SignalObservation()
    instruction_parse: SignalObservation = SignalObservation()

    @property
    def observations(self) -> tuple[tuple[Signal, SignalObservation], ...]:
        return (
            (Signal.STRUCTURAL_DIFF, self.structural_diff),
            (Signal.CORPUS_METADATA, self.corpus_metadata),
            (Signal.INSTRUCTION_PARSE, self.instruction_parse),
        )

    @property
    def observed_by(self) -> tuple[Signal, ...]:
        return tuple(signal for signal, seen in self.observations if seen.observed)

    @property
    def disagreement(self) -> bool:
        """True when the signals disagree about *presence* or about *kind*.

        Presence: one signal saw the change and another applicable one did not. Kind: two
        signals both saw it and named kinds with nothing in common. `UNAVAILABLE` is never a
        disagreement, and neither is an observation that names no kind at all.
        """
        statuses = {seen.status for _, seen in self.observations}
        if SignalStatus.OBSERVED in statuses and SignalStatus.ABSENT in statuses:
            return True
        claimed = [
            frozenset(seen.change_types)
            for _, seen in self.observations
            if seen.observed and seen.change_types
        ]
        return bool(claimed) and not frozenset.intersection(*claimed)


class ApplicabilityUnknown(BaseModel):
    """The applicability date could not be read deterministically, which is the honest answer.

    Attaching a date to a provision set is prose, with exceptions and conditions. Many
    unknowns is the correct outcome; the model never fills one in.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["unknown"] = "unknown"
    reason: str | None = None


class ApplicabilityUnchanged(BaseModel):
    """The change does not move the date this provision applies from."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["unchanged"] = "unchanged"


Applicability = date | ApplicabilityUnknown | ApplicabilityUnchanged
"""Clock 2: a date only when deterministically readable, otherwise a stated non-answer."""
