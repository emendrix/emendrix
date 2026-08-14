"""The LangGraph wiring, and the only module in the project allowed to import `langgraph`.

Confining the framework to one file is the point of the file. Everything else in `graph/` is
ordinary Python that the tests call directly, so the dependency buys exactly three things
(typed state threading, a real cycle, resumable checkpoints) and cannot quietly become the way
the pipeline is written.

```
START ─ watch ─ fetch ─ delta ─ corroborate ─ explain ─ gate ─┬─ (pending, retries < 1) ─┐
                                                 ▲            └─ emit ─ END              │
                                                 └────────────────────────────────────────┘
```

One conditional edge, one cycle, bounded at a single revision by `MAX_GATE_RETRIES` — the
retry the gate is entitled to and nothing else. The
graph has no other branch: every stage runs on every act, and a run that cannot proceed carries
the reason in its own `ActRun` rather than being routed around, because "route around the
failure" is how a pipeline loses a change.

**Deliberately not used, and why.** No `Send` fan-out: per-change concurrency already exists
inside the explain stage's semaphore, and a second concurrency model would be two things to
reason about for one effect. No tools, no agent prebuilts, no interrupts: nothing here decides
anything, so there is nothing to interrupt for. No durable execution beyond the checkpointer.
If a feature cannot be justified in one sentence it is not here.

**The checkpointer.** `InMemorySaver` by default, injectable for anything else — a durable
saver (`langgraph-checkpoint-sqlite`) is a constructor argument and not a code change, which is
why that package is not a dependency of a tool whose runs are minutes long. Resumption is
exercised in `tests/graph/test_resume_cycle.py` against the in-memory saver: interrupt after
`delta`, re-enter with the same `thread_id`, and the finished report is byte-identical.

Pinned to **langgraph 1.2.10** (`pyproject.toml`, added 2026-08-06). Three names off its
stable core are used and no more: `StateGraph`, `add_conditional_edges`, and a checkpointer.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from emendrix.graph.deps import PipelineDeps
from emendrix.graph.nodes import PipelineNodes
from emendrix.graph.state import MAX_GATE_RETRIES, PipelineState

__all__ = [
    "DEFAULT_THREAD",
    "Pipeline",
    "after_gate",
    "build_pipeline",
    "resume_pipeline",
    "run_pipeline",
]

DEFAULT_THREAD = "emendrix"
"""The checkpoint thread a single-shot CLI run uses. One run, one thread, no history to mine."""

Pipeline = CompiledStateGraph[PipelineState, None, PipelineState, PipelineState]
"""The compiled loop. Named once so the rest of the package need not spell the four parameters."""

_LINEAR = ("fetch", "delta", "corroborate", "explain", "gate")


def after_gate(state: PipelineState) -> str:
    """The one decision the graph makes, and it is arithmetic: is a revision still owed?

    Not a judgement about content — `state.pending` is the gate's own verdict, computed
    deterministically in `gate/run.py`. This function only counts.
    """
    return "explain" if state.pending and state.retries < MAX_GATE_RETRIES else "emit"


def build_pipeline(
    deps: PipelineDeps,
    *,
    watch: bool = True,
    checkpointer: Checkpointer = None,
    interrupt_after: Sequence[str] = (),
) -> Pipeline:
    """The whole loop as a compiled graph. `watch=False` is the manual-trigger entry point.

    `emendrix explain <act> <a> <b>` is the same graph with the feed poll left out and the event
    supplied by the caller: one pipeline, two ways in, so the manual path cannot drift from the
    scheduled one.

    `interrupt_after` is how resumability is *exercised* rather than asserted: it stops the run
    after a named node so a test can drop the graph on the floor and re-enter the same thread.
    No CLI flag reaches it — a run that stops halfway is a thing this project does under test,
    not a mode it offers users.
    """
    nodes = PipelineNodes(deps)
    builder: StateGraph[PipelineState, None, PipelineState, PipelineState] = StateGraph(
        PipelineState
    )
    builder.add_node("watch", nodes.watch)
    builder.add_node("fetch", nodes.fetch)
    builder.add_node("delta", nodes.delta)
    builder.add_node("corroborate", nodes.corroborate)
    builder.add_node("explain", nodes.explain)
    builder.add_node("gate", nodes.gate)
    builder.add_node("emit", nodes.emit)

    builder.add_edge(START, "watch" if watch else "fetch")
    if watch:
        builder.add_edge("watch", "fetch")
    for source, target in pairwise(_LINEAR):
        builder.add_edge(source, target)
    builder.add_conditional_edges("gate", after_gate, {"explain": "explain", "emit": "emit"})
    builder.add_edge("emit", END)
    return builder.compile(
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
        interrupt_after=list(interrupt_after),
    )


async def run_pipeline(
    graph: Pipeline, state: PipelineState, *, thread: str = DEFAULT_THREAD
) -> PipelineState:
    """Run the graph to completion asynchronously, end to end.

    `ainvoke` all the way down rather than a sync driver with an event loop poked inside the
    explain node: one loop, owned by the caller, is the only arrangement that stays honest when
    the explain stage runs forty-five calls under a semaphore.
    """
    return _state(await graph.ainvoke(state, config={"configurable": {"thread_id": thread}}))


async def resume_pipeline(graph: Pipeline, *, thread: str = DEFAULT_THREAD) -> PipelineState:
    """Carry on where a checkpointed thread stopped. `None` input is LangGraph's resume signal.

    Nothing is re-fetched and nothing is re-explained: the completed nodes' writes are already
    in the checkpoint, so a resumed run costs only what was left to do.
    """
    return _state(await graph.ainvoke(None, config={"configurable": {"thread_id": thread}}))


def _state(returned: object) -> PipelineState:
    """LangGraph hands back the channel values as a mapping; validate them back into the model.

    The state schema is a pydantic model but `ainvoke` is typed loosely enough to return `Any`,
    and swallowing that with a `cast` would mean an output the type checker believes in and
    nobody has checked. Validating costs microseconds and turns a framework change into a
    failing test rather than an attribute error three lines later.
    """
    return PipelineState.model_validate(returned)
