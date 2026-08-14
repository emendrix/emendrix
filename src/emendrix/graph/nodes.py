"""The seven nodes. Each one is an adapter: read the state, call a stage, return the update.

There is no logic in this file and there must not be. A node's whole job is to know which field
of the state a stage reads and which field it writes; the moment one of them starts *deciding*
something, the graph has stopped being orchestration and become agency, which is exactly what
this package forbids. The test for it is blunt: every function below fits on a screen and none
of them contains a rule you could disagree with.

Dependencies are captured by the class rather than threaded through the state, so the state
stays a serialisable document (see `deps.py`). LangGraph is not imported here at all — these
are ordinary functions, and `tests/graph/` calls most of them directly, which is the cheap way
to keep the framework at arm's length.

The determinism invariant, per node: only `watch` and `fetch` may reach the (cached) corpus,
only `explain` may await a model, and none of them reads a clock — `observed_on` and the poll
window arrive in the initial state from the CLI.
"""

from __future__ import annotations

from typing import Any

from emendrix.graph import stages
from emendrix.graph.deps import PipelineDeps
from emendrix.graph.state import ActRun, PipelineState

__all__ = ["PipelineNodes"]

Update = dict[str, Any]
"""A partial state update, which is what LangGraph merges into the channels."""


class PipelineNodes:
    """The loop's nodes, bound to one set of dependencies."""

    def __init__(self, deps: PipelineDeps) -> None:
        self.deps = deps

    def watch(self, state: PipelineState) -> Update:
        """WATCH: one window of the change feed → events. Requires a `WatchSource`."""
        if self.deps.watcher is None or state.window is None:
            return {}
        result = self.deps.watcher.poll(state.window)
        return {"events": result.events, "poll": result.stats}

    def fetch(self, state: PipelineState) -> Update:
        """FETCH: one `ActRun` per event, each holding two trees or the state that blocked it."""
        return {"runs": tuple(stages.fetch(self.deps, event) for event in state.events)}

    def delta(self, state: PipelineState) -> Update:
        """DELTA: the structural diff of every fetched pair."""
        return {"runs": tuple(stages.localise(run) for run in state.runs)}

    def corroborate(self, state: PipelineState) -> Update:
        """CORROBORATE: merge the corpus's other signals into every delta."""
        return {"runs": tuple(stages.corroborate_run(self.deps, run) for run in state.runs)}

    async def explain(self, state: PipelineState) -> Update:
        """EXPLAIN, entered once or twice: the batch, then the gate's one revision.

        `state.gated` is the whole of the distinction — it is false before the gate has run and
        true after, so the second entry can only ever be the revision the gate asked for.
        """
        if state.gated:
            runs = tuple([await stages.revise(self.deps, run) for run in state.runs])
            return {"runs": runs, "retries": state.retries + 1}
        return {"runs": tuple([await stages.explain(self.deps, run) for run in state.runs])}

    def gate(self, state: PipelineState) -> Update:
        """GATE: check every citation. Already-settled runs pass through untouched."""
        return {"runs": tuple(self._gate(run) for run in state.runs)}

    def emit(self, state: PipelineState) -> Update:
        """EMIT: assemble the typed report. Rendering to Markdown and git happens in `output/`."""
        return {"report": stages.emit(self.deps, state)}

    # --------------------------------------------------------------- adaptation

    def _gate(self, run: ActRun) -> ActRun:
        """First entry checks; the second rules on the revisions the explain node parked."""
        if run.gated is not None:
            return stages.settle(self.deps, run)
        return stages.gate(self.deps, run)
