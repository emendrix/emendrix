"""The model layer, measured: citation grounding, the one retry, and the quote fallback.

Rows 3 and 4 of the rigour table (`prose.py`) are different questions and this module answers
only the third. **Grounding measures citation validity, not explanation quality.** A sentence
that is factually wrong about the law and cites a provision that resolves passes this gate, and
it is supposed to: whether a sentence *follows from the texts* is faithfulness, measured
separately and more weakly in `judge.py` and `faithfulness.py`. Publishing one number for both
would be the single most flattering thing this project could do and the one that would make every
other number worthless.

What is measured, over the pinned subset (`subset.py`) in cassette replay:

- **grounding**, changes whose first explanation passed the gate with no retry, over the changes
  that had an explanation to check;
- **retry recovery**, of the changes the gate sent back, how many came back grounded;
- **fallback**, how many ended up carrying the gate's own verbatim quotation instead;
- **schema repairs**, malformed structured outputs pydantic-ai had to ask again for;
- and the per-change breakdown all four are derived from, so a rate can be traced to a unit.

The pipeline is the shipped one, called through `graph.stages`: explain → gate → revise →
settle. Nothing here re-implements the retry policy, because a harness that measures its own
copy of the pipeline measures nothing.

**The `synthetic` count is the number to read first.** A cassette recorded from a stub model is
a complete test of the machinery and no evidence at all about the pinned model; every rate below
is honest about the *gate*, and about the model only when `synthetic` is zero.

No clock and no network: the observation date is passed in and every document comes from the
committed fixtures, exactly as the deterministic layer's runner does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ChangeType
from emendrix.explain import CallUsage, RunStats, rate_for
from emendrix.gate import GateOutcome, GateStats

__all__ = [
    "SUBSET_CASSETTE_DIR",
    "ChangeOutcome",
    "ModelCaseResult",
    "ModelMetrics",
    "pool",
]

SUBSET_CASSETTE_DIR: Final = Path(__file__).resolve().parents[3] / "tests" / "cassettes-eval"
"""Where the subset's recorded exchanges live: `tests/cassettes-eval/`, committed and replayed.

Kept apart from the four pinned prompt shapes (`tests/cassettes/`) and the one whole
transition (`tests/cassettes-run/`) because the three sets answer different questions and a
shared directory would make "which of these does CI actually need?" unanswerable. Resolved from
this file rather than the working directory, like `explain.DEFAULT_CASSETTE_DIR`.
"""


class ChangeOutcome(BaseModel):
    """One change through explain and gate — the row every rate below is summed from."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    unit: str
    change_type: ChangeType
    outcome: GateOutcome
    sentences: int = Field(default=0, ge=0)
    citations: int = Field(default=0, ge=0)
    citations_rejected: int = Field(default=0, ge=0)
    fallback_sentences: int = Field(default=0, ge=0)
    retried: bool = False
    replayed: bool = Field(default=False, description="Answered from a committed cassette.")
    synthetic: bool = Field(default=False, description="A stub model produced the sentences.")
    reason: str = Field(default="", description="Why there was no explanation, when there is none.")


class ModelCaseResult(BaseModel):
    """One transition's contribution to the model layer, or the state that stopped it."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    act: str
    units: int = Field(default=0, ge=0, description="Units the subset pins for this transition.")
    missing_units: tuple[str, ...] = Field(
        default=(), description="Pinned units this run's delta no longer contains."
    )
    scored: bool = True
    state: str | None = None
    detail: str = ""
    first_round: GateStats = GateStats()
    settled: GateStats = GateStats()
    explain: RunStats | None = None
    outcomes: tuple[ChangeOutcome, ...] = ()


class ModelMetrics(BaseModel):
    """The pooled model layer. Rates are properties, so the counts stay the published thing."""

    model_config = ConfigDict(frozen=True)

    model_id: str = ""
    cases: tuple[ModelCaseResult, ...] = ()
    changes: int = Field(default=0, ge=0)
    explained: int = Field(default=0, ge=0)
    unexplained: int = Field(default=0, ge=0)
    replayed: int = Field(default=0, ge=0)
    synthetic: int = Field(default=0, ge=0)
    truncated: int = Field(default=0, ge=0, description="Prompts a character cap trimmed.")
    no_evidence: int = Field(
        default=0,
        ge=0,
        description="Changes a character cap left with two identical texts, never sent.",
    )
    model_failed: int = Field(
        default=0,
        ge=0,
        description="Changes whose live call failed and shipped the stated reason instead.",
    )
    nothing_to_explain: int = Field(
        default=0,
        ge=0,
        description="Changes another signal named that the diff saw no text for.",
    )
    schema_repairs: int = Field(default=0, ge=0)
    missing_units: int = Field(default=0, ge=0)
    first_round: GateStats = GateStats()
    settled: GateStats = GateStats()
    usage: CallUsage = CallUsage()
    recording_cost_usd: float | None = Field(
        default=None,
        description="What the recorded exchanges cost at the published rate. None = unpriced.",
    )

    @property
    def checked(self) -> int:
        """Changes the gate had an explanation to rule on — the denominator of every rate."""
        return self.settled.changes - self.settled.unexplained

    @property
    def grounding_rate(self) -> float | None:
        """Share of checked changes that passed the gate first time, with no retry."""
        return None if self.checked == 0 else self.settled.passed_first / self.checked

    @property
    def retry_recovery_rate(self) -> float | None:
        """Share of the changes the gate sent back that came back grounded."""
        retried = self.settled.retries
        return None if retried == 0 else self.settled.passed_on_retry / retried

    @property
    def fallback_rate(self) -> float | None:
        """Share of checked changes that shipped the gate's verbatim quotation instead."""
        return None if self.checked == 0 else self.settled.fallback / self.checked

    @property
    def citation_validity(self) -> float | None:
        """Share of first-round citation keys that resolved. Keys, not sentences."""
        offered = self.first_round.citations
        if offered == 0:
            return None
        return (offered - self.first_round.citations_rejected) / offered

    @property
    def settled_all(self) -> bool:
        """Every change left the gate with a final answer. False is a bug, not a metric."""
        return all(case.settled.settled == case.settled.changes for case in self.cases)


def pool(model_id: str, cases: tuple[ModelCaseResult, ...]) -> ModelMetrics:
    """Sum the cases. Counts first; every rate is derived from them, never stored."""
    first = GateStats()
    settled = GateStats()
    usage = CallUsage()
    stats = [case.explain for case in cases if case.explain is not None]
    for case in cases:
        first = first.plus(case.first_round)
        settled = settled.plus(case.settled)
    for item in stats:
        usage = usage.plus(item.usage)
    rate = rate_for(model_id)
    return ModelMetrics(
        model_id=model_id,
        cases=cases,
        changes=sum(item.changes for item in stats),
        explained=sum(item.explained for item in stats),
        unexplained=sum(item.unavailable for item in stats),
        replayed=sum(item.replayed for item in stats),
        synthetic=sum(item.synthetic for item in stats),
        truncated=sum(item.truncated for item in stats),
        no_evidence=sum(item.no_evidence for item in stats),
        model_failed=sum(item.model_failed for item in stats),
        nothing_to_explain=sum(item.nothing_to_explain for item in stats),
        schema_repairs=usage.schema_repairs,
        missing_units=sum(len(case.missing_units) for case in cases),
        first_round=first,
        settled=settled,
        usage=usage,
        recording_cost_usd=None
        if rate is None
        else usage.cost_usd(
            input_per_mtok=rate.input_per_mtok, output_per_mtok=rate.output_per_mtok
        ),
    )
