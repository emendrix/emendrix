"""The whole loop, end to end, on a corpus that is not law: `tests/toy_corpus.py`.

This is the seam's strongest test. WATCH → FETCH → DELTA → CORROBORATE → EXPLAIN → GATE → EMIT
runs unchanged over a flat's house rules, with no CELEX, no Formex, no network and no signal
source, which is only possible because every node reads `CorpusAdapter` and core types. If a
future change makes the graph reach for something EU-shaped, this file stops importing.

The model is a stub (`stub_engine.py`) driven through the real `ExplainEngine`, so what is
asserted is state flow, output shape and counts. Nothing here is evidence about explanations.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime

import pytest

from emendrix import DISCLAIMER
from emendrix.core import ChangeType, ProvisionTree, VersionId
from emendrix.gate import GateOutcome
from emendrix.graph import (
    ActRun,
    PipelineDeps,
    PipelineState,
    RunReport,
    build_pipeline,
    run_pipeline,
)
from emendrix.watch.events import AmendmentEvent, PollResult, PollStats, PollWindow
from emendrix.watch.state import WatchState
from stub_engine import citing_offered, engine
from toy_corpus import HOUSE_RULES, V1, V2, V3_PENDING, ToyCorpusAdapter

OBSERVED = date(2026, 8, 6)
WINDOW = PollWindow(start=datetime(2026, 8, 1), end=datetime(2026, 8, 6), observed_on=OBSERVED)


def event(
    *, new: str | None = str(V2), previous: str | None = str(V1), target: str | None = str(V2)
) -> AmendmentEvent:
    return AmendmentEvent(
        act=HOUSE_RULES,
        target_version=None if target is None else VersionId(target),
        new_version=None if new is None else VersionId(new),
        previous_version=None if previous is None else VersionId(previous),
        trigger="toy:test",
        observed_on=OBSERVED,
    )


class StubWatcher:
    """A `WatchSource` that answers from a list. The graph never learns where events come from."""

    def __init__(self, *events: AmendmentEvent) -> None:
        self.events = events
        self.windows: list[PollWindow] = []

    def poll(self, window: PollWindow) -> PollResult:
        self.windows.append(window)
        return PollResult(
            events=self.events,
            state=WatchState(),
            stats=PollStats(entries=7, matched=len(self.events)),
        )


def deps(*, watcher: StubWatcher | None = None) -> PipelineDeps:
    return PipelineDeps(
        adapter=ToyCorpusAdapter(observed_on=OBSERVED),
        engine=engine(citing_offered()),
        observed_on=OBSERVED,
        watcher=watcher,
    )


@pytest.fixture
def report() -> RunReport:
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(),)),
        )
    )
    assert final.report is not None
    return final.report


# ------------------------------------------------------------------ the flow


def test_the_manual_path_runs_the_whole_loop_and_emits_a_report(report: RunReport) -> None:
    assert len(report.deltas) == 1
    emitted = report.deltas[0]
    assert emitted.act == HOUSE_RULES
    assert (emitted.from_version, emitted.to_version) == (V1, V2)
    assert emitted.summary.touched_units == 4
    assert report.skipped == ()
    assert report.observed_on == OBSERVED


def test_every_change_the_diff_found_reaches_the_output(report: RunReport) -> None:
    """The invariant the whole package is built around, checked at the far end of it."""
    emitted = report.deltas[0]
    kinds = {change.change.change_type for change in emitted.changes}
    assert kinds == {ChangeType.MODIFIED, ChangeType.INSERTED, ChangeType.DELETED}
    assert len(emitted.changes) == emitted.summary.touched_units
    assert emitted.gate.changes == len(emitted.changes)
    assert emitted.gate.settled == emitted.gate.changes


def test_a_grounded_stub_passes_the_gate_on_the_first_attempt(report: RunReport) -> None:
    gate = report.deltas[0].gate
    assert gate.passed_first == gate.changes
    assert gate.passed_on_retry == 0
    assert gate.fallback == 0
    assert gate.retries == 0
    assert gate.citations_rejected == 0
    assert all(item.outcome is GateOutcome.PASSED for item in report.deltas[0].changes)


def test_citation_keys_become_the_corpus_own_urls_only_on_the_way_out(
    report: RunReport,
) -> None:
    """The model saw opaque tokens; the gate checked tokens; only EMIT renders a link, and only
    through the adapter, so nothing upstream can invent one."""
    for change in report.deltas[0].changes:
        for sentence in change.sentences:
            assert sentence.citations, "every sentence carries at least one citation"
            for citation in sentence.citations:
                assert citation.url.startswith("https://example.invalid/house-rules/")
                assert citation.ref.act == HOUSE_RULES


def test_the_report_carries_the_disclaimer_as_a_field(report: RunReport) -> None:
    """A field rather than a rendering step, so no output path can forget it."""
    assert report.disclaimer == DISCLAIMER
    assert DISCLAIMER in report.model_dump_json()


def test_the_run_is_byte_stable_across_two_identical_runs() -> None:
    """Changelogs are diffed in git, so two runs of the same inputs must produce one file."""
    first = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(),)),
        )
    )
    second = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(),)),
        )
    )
    assert first.report is not None and second.report is not None
    assert first.report.model_dump_json(indent=2) == second.report.model_dump_json(indent=2)


# ------------------------------------------------------------------ the watch entry


def test_the_watch_node_supplies_the_events_and_its_own_counts() -> None:
    watcher = StubWatcher(event())
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(watcher=watcher), watch=True),
            PipelineState(observed_on=OBSERVED, window=WINDOW),
        )
    )
    assert watcher.windows == [WINDOW], "the window is handed in, never asked for"
    assert final.report is not None
    assert final.report.poll is not None
    assert final.report.poll.entries == 7
    assert len(final.report.deltas) == 1


def test_a_watch_run_with_no_watcher_simply_finds_nothing() -> None:
    """Not an error: a graph built to poll and given nothing to poll had an empty day."""
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=True),
            PipelineState(observed_on=OBSERVED, window=WINDOW),
        )
    )
    assert final.report is not None
    assert final.report.deltas == ()
    assert final.report.skipped == ()


# ------------------------------------------------------------------ what cannot proceed


def test_a_pending_consolidation_is_reported_rather_than_raised() -> None:
    """A consolidated text lags the act that amended it, so this state is routine, not an error.

    `ConsolidationPending` is a value that flows to the output and is re-checked until it
    resolves; `core/states.py` carries the measured lag.
    """
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(
                observed_on=OBSERVED,
                events=(event(new=str(V3_PENDING), target=str(V3_PENDING)),),
            ),
        )
    )
    assert final.report is not None
    assert final.report.deltas == ()
    assert len(final.report.skipped) == 1
    skipped = final.report.skipped[0]
    assert skipped.act == HOUSE_RULES
    assert "consolidation_pending" in skipped.reason
    assert "not yet written up" in skipped.reason


def test_an_event_with_no_earlier_version_says_so_instead_of_diffing_against_nothing() -> None:
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(previous=None),)),
        )
    )
    assert final.report is not None
    assert final.report.deltas == ()
    assert "no earlier version" in final.report.skipped[0].reason


def test_an_event_carrying_no_version_at_all_is_still_a_result() -> None:
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(new=None, target=None),)),
        )
    )
    assert final.report is not None
    assert len(final.report.skipped) == 1
    assert final.report.skipped[0].reason


def test_english_unavailable_reaches_the_report_as_the_state_it_is() -> None:
    """The toy corpus refuses every language but English; ask for another and it says so."""
    alien = PipelineDeps(
        adapter=ToyCorpusAdapter(observed_on=OBSERVED, language="LAV"),
        engine=engine(citing_offered()),
        observed_on=OBSERVED,
    )
    final = asyncio.run(
        run_pipeline(
            build_pipeline(alien, watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(),)),
        )
    )
    assert final.report is not None
    assert "english_unavailable" in final.report.skipped[0].reason


# ------------------------------------------------------------------ the state itself


def test_the_state_is_serialisable_all_the_way_through() -> None:
    """LangGraph checkpoints it, so a field that cannot round-trip breaks resume, not a test."""
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps(), watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(),)),
        )
    )
    payload = final.model_dump_json()
    restored = PipelineState.model_validate_json(payload)
    assert restored.model_dump_json() == payload
    assert restored.report == final.report


def test_an_act_run_says_why_it_stopped_or_says_nothing() -> None:
    """`blocked` is the report's reason string, and it is empty exactly when a delta exists."""
    run = ActRun(event=event())
    assert run.blocked == "no delta was computed"
    assert not run.fetched
    assert run.pending == ()


def test_the_adapter_really_is_the_only_thing_the_loop_knows_about_the_corpus() -> None:
    """The toy adapter has no signal source and no feed, and the loop runs anyway."""
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    assert isinstance(adapter.fetch_version(HOUSE_RULES, V2), ProvisionTree)
    minimal = PipelineDeps(adapter=adapter, engine=engine(citing_offered()), observed_on=OBSERVED)
    assert minimal.signals is None
    assert minimal.watcher is None
    final = asyncio.run(
        run_pipeline(
            build_pipeline(minimal, watch=False),
            PipelineState(observed_on=OBSERVED, events=(event(),)),
        )
    )
    assert final.report is not None
    emitted = final.report.deltas[0]
    assert emitted.corroboration is not None
    assert emitted.summary.disputed == 0, "silence from the other signals is never dissent"
