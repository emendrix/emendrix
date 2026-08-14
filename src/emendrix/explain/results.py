"""What an explain run produces, and what it cost.

Cost control is a stated goal of the project, so token usage is a first-class field rather than
a log line: every call carries its own `CallUsage`, every run sums them, and a replayed call
reports the usage of the exchange it replays with `requests=0`. The tokens were spent once, at
recording time, and counting them again on every CI run would be a lie about spend.

`ExplainedChange` is deliberately not a bare `Explanation`. A batch where one change failed
still ships the other forty-four (a change is never dropped), so the per-change result has to
be able to say *no explanation, and here is why* — and to say whether what it holds came from
a real model or a stub, which is the difference between a number the eval may publish and one
it may not.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from emendrix.core import ProvisionRef
from emendrix.explain.schema import Explanation, ExplanationUnavailable

__all__ = ["CallUsage", "ExplainRun", "ExplainedChange", "RunStats"]


class CallUsage(BaseModel):
    """Tokens and requests for one explain call. Zeroes are meaningful, not missing data."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    requests: int = Field(
        default=0, ge=0, description="Provider requests actually made. Zero on a replayed call."
    )
    schema_repairs: int = Field(
        default=0,
        ge=0,
        description="Extra requests pydantic-ai spent repairing a malformed structured output.",
    )

    def plus(self, other: CallUsage) -> CallUsage:
        return CallUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            requests=self.requests + other.requests,
            schema_repairs=self.schema_repairs + other.schema_repairs,
        )

    def cost_usd(self, *, input_per_mtok: float, output_per_mtok: float) -> float:
        """Spend at the caller's published rates. The rates live in `settings.py`, not here."""
        return (
            self.input_tokens * input_per_mtok + self.output_tokens * output_per_mtok
        ) / 1_000_000


class ExplainedChange(BaseModel):
    """One change, and either its explanation or the stated reason there is none."""

    model_config = ConfigDict(frozen=True)

    provision: ProvisionRef
    explanation: Explanation | None = None
    unavailable: ExplanationUnavailable | None = None
    usage: CallUsage = CallUsage()
    cassette_key: str = Field(
        default="",
        description="sha256 identity of the exchange, for audit. Empty when no call was made.",
    )
    replayed: bool = Field(default=False, description="Served from a committed cassette.")
    synthetic: bool = Field(
        default=False,
        description="Produced by a stub model, not the pinned one — never a quality claim.",
    )
    dropped_chars: int = Field(
        default=0, ge=0, description="Characters the prompt caps removed before the call."
    )
    no_evidence: bool = Field(
        default=False,
        description="The cap left the two texts identical, so no call was made. Never with prose.",
    )

    @model_validator(mode="after")
    def _exactly_one_outcome(self) -> Self:
        if (self.explanation is None) == (self.unavailable is None):
            raise ValueError(
                "an explained change carries exactly one of `explanation` or `unavailable`"
            )
        return self

    @model_validator(mode="after")
    def _no_evidence_carries_no_prose(self) -> Self:
        if self.no_evidence and self.explanation is not None:
            raise ValueError(
                "a change the prompt showed no difference for was never sent to the model, so it "
                "cannot carry an explanation"
            )
        return self

    @property
    def ok(self) -> bool:
        return self.explanation is not None


class RunStats(BaseModel):
    """What one `explain_delta` did, as counts. Published as measured, never curated."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    changes: int = Field(default=0, ge=0)
    explained: int = Field(default=0, ge=0)
    unavailable: int = Field(default=0, ge=0)
    replayed: int = Field(default=0, ge=0)
    synthetic: int = Field(default=0, ge=0)
    truncated: int = Field(
        default=0, ge=0, description="Calls whose prompt hit a character cap — visibly marked."
    )
    no_evidence: int = Field(
        default=0,
        ge=0,
        description="Changes whose capped texts were identical, so no call was made at all.",
    )
    usage: CallUsage = CallUsage()

    @classmethod
    def over(cls, model_id: str, results: tuple[ExplainedChange, ...]) -> Self:
        usage = CallUsage()
        for result in results:
            usage = usage.plus(result.usage)
        return cls(
            model_id=model_id,
            changes=len(results),
            explained=sum(1 for result in results if result.ok),
            unavailable=sum(1 for result in results if not result.ok),
            replayed=sum(1 for result in results if result.replayed),
            synthetic=sum(1 for result in results if result.synthetic),
            truncated=sum(1 for result in results if result.dropped_chars),
            no_evidence=sum(1 for result in results if result.no_evidence),
            usage=usage,
        )


class ExplainRun(BaseModel):
    """Every change of one delta, in the delta's order, with the run's accounting."""

    model_config = ConfigDict(frozen=True)

    results: tuple[ExplainedChange, ...] = ()
    stats: RunStats

    @property
    def explanations(self) -> tuple[Explanation | None, ...]:
        """The explanations alone, positionally aligned with the delta's changes."""
        return tuple(result.explanation for result in self.results)
