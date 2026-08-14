"""Resumability, exercised rather than claimed: the third thing the dependency buys.

`docs/architecture.md` says a graph framework earns its place partly because a run that dies
after the expensive fetch can be picked up where it stopped. That is a testable claim, so it is
tested: compile with `interrupt_after=["delta"]`, run until it stops, throw the in-flight run
away, re-enter the same `thread_id` with `None`, and require the finished report to be
**byte-identical** to the report an uninterrupted run produces.

Byte-identical is the strong form and it is the right one. It only holds because no node reads
a clock and no stage carries a timing, a duration or an iteration order, the same property
that lets a changelog be diffed in git. If this test ever starts flapping, the leak it found is
real and the fix is upstream, not here.

The checkpointer is `InMemorySaver`, injected. A durable one (`langgraph-checkpoint-sqlite`) is
a constructor argument, not a code change, so it is not a dependency of a tool whose runs are
minutes long, and the resume path being exercised is the same path either way.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from emendrix.core import ActId, ProvisionTree, Unavailable, VersionId
from emendrix.graph import (
    PipelineDeps,
    PipelineState,
    build_pipeline,
    resume_pipeline,
    run_pipeline,
)
from emendrix.graph.build import Pipeline
from emendrix.watch.events import AmendmentEvent
from stub_engine import citing_badly_then_well, citing_offered, engine
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED = date(2026, 8, 6)
THREAD = "resume-test"

EVENT = AmendmentEvent(
    act=HOUSE_RULES,
    target_version=V2,
    new_version=V2,
    previous_version=V1,
    trigger="toy:resume",
    observed_on=OBSERVED,
)


def deps(*, grounded: bool = True) -> PipelineDeps:
    return PipelineDeps(
        adapter=ToyCorpusAdapter(observed_on=OBSERVED),
        engine=engine(citing_offered() if grounded else citing_badly_then_well()),
        observed_on=OBSERVED,
    )


def graph(*, stop_after: str | None = None, grounded: bool = True) -> Pipeline:
    return build_pipeline(
        deps(grounded=grounded),
        watch=False,
        checkpointer=InMemorySaver(),
        interrupt_after=() if stop_after is None else (stop_after,),
    )


def start() -> PipelineState:
    return PipelineState(observed_on=OBSERVED, events=(EVENT,))


def straight_through(*, grounded: bool = True) -> PipelineState:
    return asyncio.run(run_pipeline(graph(grounded=grounded), start(), thread=THREAD))


@pytest.mark.parametrize("stop_after", ["fetch", "delta", "corroborate", "explain"])
def test_a_run_interrupted_mid_loop_resumes_to_the_identical_report(stop_after: str) -> None:
    """Killed after each stage in turn; each time the finished output is byte for byte the same."""
    interrupted = graph(stop_after=stop_after)
    halfway = asyncio.run(run_pipeline(interrupted, start(), thread=THREAD))
    assert halfway.report is None, f"the run did not stop after {stop_after}"

    resumed = asyncio.run(resume_pipeline(interrupted, thread=THREAD))
    assert resumed.report is not None
    assert resumed.report.model_dump_json(indent=2) == _reference()


def test_the_interrupt_really_stops_where_it_says_it_does() -> None:
    """A guard on the guard: if `interrupt_after` silently stopped working, every resume test
    above would pass by running straight through and prove nothing."""
    after_fetch = asyncio.run(run_pipeline(graph(stop_after="fetch"), start(), thread=THREAD))
    assert len(after_fetch.runs) == 1
    assert after_fetch.runs[0].fetched, "FETCH ran"
    assert after_fetch.runs[0].delta is None, "DELTA did not"

    after_delta = asyncio.run(run_pipeline(graph(stop_after="delta"), start(), thread=THREAD))
    assert after_delta.runs[0].delta is not None
    assert after_delta.runs[0].explained is None


def test_resuming_does_not_redo_the_work_that_was_already_checkpointed() -> None:
    """The point of resuming: the fetched trees are in the checkpoint, so nothing refetches.

    Counted at the adapter, which is the only thing in the loop that can be expensive.
    """
    adapter = _CountingAdapter(observed_on=OBSERVED)
    pipeline = build_pipeline(
        PipelineDeps(adapter=adapter, engine=engine(citing_offered()), observed_on=OBSERVED),
        watch=False,
        checkpointer=InMemorySaver(),
        interrupt_after=("delta",),
    )
    asyncio.run(run_pipeline(pipeline, start(), thread=THREAD))
    fetches_before_the_crash = adapter.fetches
    assert fetches_before_the_crash == 2, "both sides of the transition"

    final = asyncio.run(resume_pipeline(pipeline, thread=THREAD))
    assert final.report is not None
    assert adapter.fetches == fetches_before_the_crash, "a resumed run refetches nothing"


def test_a_run_interrupted_inside_the_retry_cycle_still_finishes_it() -> None:
    """The cycle is the interesting checkpoint: stopping between the two halves of one retry
    must not leave a change parked as `RETRY_REQUESTED` forever.

    `explain` is entered twice on a run that fails the gate once, and a static interrupt fires
    on *every* visit, so this run stops twice and is resumed twice. That is LangGraph behaving
    correctly, and asserting it here is cheaper than being surprised by it later.
    """
    pipeline = graph(stop_after="explain", grounded=False)
    after_first_attempt = asyncio.run(run_pipeline(pipeline, start(), thread=THREAD))
    assert after_first_attempt.report is None
    assert after_first_attempt.retries == 0, "stopped before the gate saw anything"

    after_revision = asyncio.run(resume_pipeline(pipeline, thread=THREAD))
    assert after_revision.report is None, "stopped again, on the second visit to explain"
    assert after_revision.retries == 1, "the one revision was asked for and answered"

    resumed = asyncio.run(resume_pipeline(pipeline, thread=THREAD))
    assert resumed.report is not None
    assert resumed.pending is False, "nothing may be left waiting for a revision"
    gate = resumed.report.deltas[0].gate
    assert gate.settled == gate.changes
    assert gate.passed_on_retry == gate.changes


def test_two_threads_do_not_see_each_others_checkpoints() -> None:
    """One run, one thread (`DEFAULT_THREAD`). A shared saver must still keep them apart."""
    saver = InMemorySaver()
    pipeline = build_pipeline(deps(), watch=False, checkpointer=saver, interrupt_after=("delta",))
    asyncio.run(run_pipeline(pipeline, start(), thread="first"))
    second = asyncio.run(run_pipeline(pipeline, start(), thread="second"))
    assert second.report is None, "the second thread starts from the beginning, not from the first"

    finished = asyncio.run(resume_pipeline(pipeline, thread="first"))
    assert finished.report is not None


class _CountingAdapter(ToyCorpusAdapter):
    """The toy adapter, counting fetches. Nothing else about it differs."""

    def __init__(self, *, observed_on: date) -> None:
        super().__init__(observed_on=observed_on)
        self.fetches = 0

    def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
        self.fetches += 1
        return super().fetch_version(act, version)


def _reference() -> str:
    """What an uninterrupted run of the same inputs produces. Computed once per test, cheaply."""
    final = straight_through()
    assert final.report is not None
    return final.report.model_dump_json(indent=2)
