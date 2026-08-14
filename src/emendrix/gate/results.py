"""What the gate decides, as types. No policy here — only the shape of a verdict.

The gate answers one question about one sentence: **does every key it cites resolve to a
provision that was actually offered for this change?** It has no opinion about whether the
sentence is true, useful or well written. That separation is not fastidiousness; it is the
line between *citation grounding*, which is measured
here and is a property of the pipeline, and *faithfulness*, which is measured by a different
layer against a different reference and may never be quietly folded into this number.

Three failure reasons, and they mean different things:

- `UNKNOWN_KEY` — the key was never offered. This is the anti-hallucination invariant:
  citing outside the retrieved context is structurally impossible to do correctly, so it is
  rejected without judging content.
- `UNRESOLVED` — the key was offered, but the provision it names is not in that version's
  tree. In a healthy pipeline this cannot happen, because the offered set is built from the
  trees; it fires when a caller mints its own keys, which is exactly when it should.
- `UNCHECKABLE` — no tree for that version was on hand. The gate does not pass what it cannot
  check, and it says which of the two it was.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ProvisionRef
from emendrix.explain import CitedSentence, Explanation, ExplanationUnavailable

__all__ = [
    "APPLICABILITY_NOTE",
    "CitationFailure",
    "FailureReason",
    "GateOutcome",
    "GateResult",
    "GateStats",
    "GatedChange",
    "GatedDelta",
    "GatedExplanation",
    "GatedSentence",
    "Resolution",
    "SentenceFailure",
]

APPLICABILITY_NOTE: Final = -1
"""The slot index of `Explanation.applicability_note`, which has no ordinal of its own."""


class FailureReason(StrEnum):
    UNKNOWN_KEY = "unknown_key"
    UNRESOLVED = "unresolved"
    UNCHECKABLE = "uncheckable"


class Resolution(StrEnum):
    """What a resolver found when asked whether a provision exists in a version."""

    PRESENT = "present"
    ABSENT = "absent"
    UNCHECKABLE = "uncheckable"


class GateOutcome(StrEnum):
    """How one change left the gate. Every change leaves it — that is the point.

    `RETRY_REQUESTED` is transient: it exists only between the two halves of the one retry
    cycle, and no run may finish holding one.
    """

    PASSED = "passed"
    PASSED_ON_RETRY = "passed_on_retry"
    FALLBACK = "fallback"
    RETRY_REQUESTED = "retry_requested"
    UNEXPLAINED = "unexplained"


class CitationFailure(BaseModel):
    """One citation key the gate rejected, and precisely why."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    reason: FailureReason
    detail: str = Field(min_length=1, description="Reader-facing sentence naming the fault.")


class SentenceFailure(BaseModel):
    """One sentence that carried at least one rejected citation."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(
        description=f"Position in `sentences`, or {APPLICABILITY_NOTE} for the note."
    )
    text: str = Field(min_length=1, description="The rejected sentence, kept for the report.")
    citations: tuple[CitationFailure, ...] = Field(min_length=1)

    @property
    def label(self) -> str:
        if self.index == APPLICABILITY_NOTE:
            return "the applicability note"
        return f"sentence {self.index + 1}"


class GateResult(BaseModel):
    """The verdict on one explanation: what failed, and how much was looked at."""

    model_config = ConfigDict(frozen=True)

    failures: tuple[SentenceFailure, ...] = ()
    sentences: int = Field(default=0, ge=0)
    citations: int = Field(default=0, ge=0)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def rejected_citations(self) -> int:
        return sum(len(failure.citations) for failure in self.failures)

    @property
    def complaint(self) -> str:
        """The specific failure handed to `ExplainEngine.revise` — deterministic, ordered.

        It names the sentence and every bad key with its reason. It deliberately does *not*
        repeat the offered set: `explain.revision_note` already re-prints that, and saying it
        twice in one prompt is how a retry turns into a negotiation.
        """
        return "; ".join(
            f"{failure.label} cites {item.detail}"
            for failure in self.failures
            for item in failure.citations
        )


class GatedSentence(BaseModel):
    """A sentence that has been through the gate, and whether the gate wrote it.

    `fallback` is on *this* type and not on `explain.CitedSentence` on purpose. The model's
    output schema is the model's interface, and a provenance flag inside it would be a field the
    model could set, letting an invented sentence claim to be a verbatim quotation. The flag
    therefore lives where it is minted: on the gate's own value, which no model ever fills in.
    """

    model_config = ConfigDict(frozen=True)

    sentence: CitedSentence
    fallback: bool = Field(
        default=False, description="Written by the gate as a verbatim quotation, not by the model."
    )

    @property
    def text(self) -> str:
        return self.sentence.text

    @property
    def citations(self) -> tuple[str, ...]:
        return self.sentence.citations


class GatedExplanation(BaseModel):
    """An explanation after the gate: every sentence in it is grounded, by check or by quote."""

    model_config = ConfigDict(frozen=True)

    sentences: tuple[GatedSentence, ...] = Field(min_length=1)
    applicability_note: GatedSentence | None = None

    @classmethod
    def accepted(cls, explanation: Explanation) -> Self:
        """The explanation exactly as the model wrote it, having passed."""
        note = explanation.applicability_note
        return cls(
            sentences=tuple(GatedSentence(sentence=item) for item in explanation.sentences),
            applicability_note=None if note is None else GatedSentence(sentence=note),
        )

    @property
    def fallbacks(self) -> int:
        return sum(1 for item in self.sentences if item.fallback)


class GatedChange(BaseModel):
    """One change, and what shipped for it. Exactly one of the two outcomes is present."""

    model_config = ConfigDict(frozen=True)

    provision: ProvisionRef
    outcome: GateOutcome
    explanation: GatedExplanation | None = None
    unavailable: ExplanationUnavailable | None = None
    failures: tuple[SentenceFailure, ...] = Field(
        default=(), description="Everything the gate rejected for this change, both rounds."
    )
    complaint: str = Field(default="", description="What was sent back to the model, if anything.")


class GateStats(BaseModel):
    """What one gate run did, as counts. Published as measured."""

    model_config = ConfigDict(frozen=True)

    changes: int = Field(default=0, ge=0)
    passed_first: int = Field(default=0, ge=0)
    passed_on_retry: int = Field(default=0, ge=0)
    fallback: int = Field(default=0, ge=0)
    unexplained: int = Field(default=0, ge=0, description="No explanation existed to check.")
    retries: int = Field(default=0, ge=0, description="Changes sent back for the one revision.")
    sentences: int = Field(default=0, ge=0)
    citations: int = Field(default=0, ge=0)
    citations_rejected: int = Field(default=0, ge=0)
    notes_dropped: int = Field(
        default=0, ge=0, description="Applicability notes the gate dropped as non-verbatim."
    )
    coordinates_unsupported: int = Field(
        default=0,
        ge=0,
        description="Coordinates a shipped sentence names that neither the diff localised "
        "nor the capped evidence contains. Per coordinate naming, not per sentence: one "
        "sentence naming two counts two. Counted only; nothing is dropped for it.",
    )

    def plus(self, other: GateStats) -> GateStats:
        return GateStats(
            changes=self.changes + other.changes,
            passed_first=self.passed_first + other.passed_first,
            passed_on_retry=self.passed_on_retry + other.passed_on_retry,
            fallback=self.fallback + other.fallback,
            unexplained=self.unexplained + other.unexplained,
            retries=self.retries + other.retries,
            sentences=self.sentences + other.sentences,
            citations=self.citations + other.citations,
            citations_rejected=self.citations_rejected + other.citations_rejected,
            notes_dropped=self.notes_dropped + other.notes_dropped,
            coordinates_unsupported=self.coordinates_unsupported + other.coordinates_unsupported,
        )

    @property
    def settled(self) -> int:
        """Changes with a final answer. Must equal `changes` once the cycle has finished."""
        return self.passed_first + self.passed_on_retry + self.fallback + self.unexplained


class GatedDelta(BaseModel):
    """Every change of one delta after the gate, in the delta's order, with the counts.

    Positional alignment with `Delta.changes` is a contract, exactly as it is for
    `ExplainRun.results`: `changes[i]` is `delta.changes[i]`, retried, fallen back or skipped.
    """

    model_config = ConfigDict(frozen=True)

    changes: tuple[GatedChange, ...] = ()
    stats: GateStats = GateStats()

    @property
    def pending(self) -> tuple[int, ...]:
        """Indices awaiting the one revision — empty on a settled round."""
        return tuple(
            index
            for index, change in enumerate(self.changes)
            if change.outcome is GateOutcome.RETRY_REQUESTED
        )
