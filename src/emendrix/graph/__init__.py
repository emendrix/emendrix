"""`emendrix.graph` — the loop, assembled. Orchestration, and deliberately not agency.

WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT, wired as a LangGraph
`StateGraph`. Every node except `explain` is deterministic Python, and every node is an
*adapter*: it reads a field of the state, calls a function that already existed before this
package did, and writes the result back. Nothing in here decides anything about a document.

That constraint is what makes the framework defensible on a near-linear pipeline. What it buys
is three things, argued out in `docs/architecture.md`: one typed state instead of a growing
tuple of half-results, one real cycle (the gate's single revision, which a straight-line
function would have to special-case), and checkpointed resume across the expensive fetch. What
it costs is a dependency and a vocabulary a reader has to learn before they can follow the
control flow — which is why `langgraph` is imported in exactly one module, `build.py`, and
`tests/test_architecture.py` fails the build if that ever stops being true.

Layout:

- `deps.py`   — what the loop needs from outside: the adapter, the engine, two capabilities.
- `state.py`  — the one pydantic state the graph threads, and what a single act's run holds.
- `stages.py` — one function per stage, all logic delegated to the package that owns it.
- `nodes.py`  — the seven node adapters. No logic, by rule, and grep-checked for length.
- `report.py` — the EMIT stage's typed document, citations rendered on the way out.
- `build.py`  — the wiring, the one conditional edge, the checkpointer. The only langgraph import.
- `cli.py`    — two commands, `emendrix run --once` and `emendrix explain`; the wiring they
  share with the rest of the project lives in `emendrix.session`.
"""

from emendrix.graph.build import (
    DEFAULT_THREAD,
    Pipeline,
    after_gate,
    build_pipeline,
    resume_pipeline,
    run_pipeline,
)
from emendrix.graph.deps import PipelineDeps, WatchSource
from emendrix.graph.nodes import PipelineNodes
from emendrix.graph.report import (
    EmittedChange,
    EmittedDelta,
    EmittedSentence,
    RunReport,
    SkippedAct,
    build_delta_report,
)
from emendrix.graph.state import MAX_GATE_RETRIES, ActRun, PipelineState

__all__ = [
    "DEFAULT_THREAD",
    "MAX_GATE_RETRIES",
    "ActRun",
    "EmittedChange",
    "EmittedDelta",
    "EmittedSentence",
    "Pipeline",
    "PipelineDeps",
    "PipelineNodes",
    "PipelineState",
    "RunReport",
    "SkippedAct",
    "WatchSource",
    "after_gate",
    "build_delta_report",
    "build_pipeline",
    "resume_pipeline",
    "run_pipeline",
]
