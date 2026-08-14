"""The state the graph threads through the loop. One pydantic model, serialisable throughout.

Everything a node reads and everything it writes lives here, which is the first of the three
things a graph framework is bought for: the pipeline stops passing tuples of half-results
between functions and starts having a *shape* that can be checkpointed, inspected mid-run and
resumed. That the shape is a pydantic model rather than a `TypedDict` is deliberate — LangGraph
validates it on every node boundary, so a node that writes nonsense fails at the node instead of
three stages later.

**One list, not a fan-out.** A poll can name several acts, so the state carries a tuple of
`ActRun`s and every node maps over it. Per-change concurrency stays inside the explain stage's
own semaphore rather than becoming graph-level `Send` fan-out: same effect, one graph
a reader can hold in their head, and no second concurrency model to reason about.

**What it costs, stated plainly:** an `ActRun` holds two whole provision trees, so a checkpoint
of a real transition is megabytes. That is the price of being able to resume after the fetch
without re-fetching, and it is the honest reading of "resumability" for this pipeline.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, Delta, ProvisionTree, Unavailable
from emendrix.corroborate import CorroborationReport
from emendrix.explain import ExplainedChange, ExplainRun
from emendrix.gate import GatedDelta
from emendrix.graph.report import RunReport
from emendrix.watch.events import AmendmentEvent, PollStats, PollWindow

__all__ = ["MAX_GATE_RETRIES", "ActRun", "PipelineState"]

MAX_GATE_RETRIES = 1
"""The one revision the gate allows. Not a knob, a policy."""


class ActRun(BaseModel):
    """One act's transition, accumulating through the loop. Every stage adds one field.

    A run that cannot proceed says why and stops: `unavailable` for a first-class corpus state,
    `note` for a run that is well-formed and simply has nothing to compare. Neither is an error
    and both reach the report, because a watched act nobody could diff is a *result*.
    """

    model_config = ConfigDict(frozen=True)

    event: AmendmentEvent
    unavailable: Unavailable | None = None
    note: str = Field(default="", description="Why this run stopped, when no state covers it.")
    before: ProvisionTree | None = None
    after: ProvisionTree | None = None
    delta: Delta | None = None
    corroboration: CorroborationReport | None = None
    explained: ExplainRun | None = None
    gated: GatedDelta | None = None
    revisions: tuple[tuple[int, ExplainedChange], ...] = Field(
        default=(),
        description="Answers to the gate's one retry, parked here until the gate rules on them.",
    )

    @property
    def act(self) -> ActId:
        return self.event.act

    @property
    def fetched(self) -> bool:
        """Both sides in hand — the precondition of every stage after FETCH."""
        return self.before is not None and self.after is not None

    @property
    def pending(self) -> tuple[int, ...]:
        """Change indices the gate sent back for their one revision."""
        return () if self.gated is None else self.gated.pending

    @property
    def blocked(self) -> str:
        """A reader-facing reason this run produced no delta, or `""` if it produced one."""
        if self.delta is not None:
            return ""
        if self.unavailable is not None:
            return f"{self.unavailable.state}: {self.unavailable.detail}".rstrip(": ")
        return self.note or "no delta was computed"


class PipelineState(BaseModel):
    """Everything the graph knows, at any point between two nodes.

    `observed_on` and `window` are values handed in at the CLI boundary — no node reads a clock,
    which is what makes a resumed run produce the same bytes as the run it resumed.
    """

    model_config = ConfigDict(frozen=True)

    observed_on: date
    window: PollWindow | None = None
    poll: PollStats | None = None
    events: tuple[AmendmentEvent, ...] = ()
    runs: tuple[ActRun, ...] = ()
    retries: int = Field(default=0, ge=0, description="Gate→explain cycles taken. Capped at 1.")
    report: RunReport | None = None

    @property
    def gated(self) -> bool:
        """True once the gate has seen these runs — the explain node's "am I revising?" test."""
        return any(run.gated is not None for run in self.runs)

    @property
    def pending(self) -> bool:
        """True while some change is waiting for its one revision."""
        return any(run.pending for run in self.runs)
