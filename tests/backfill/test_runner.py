"""The backfill loop, over a corpus that is not law.

`tests/toy_corpus.py` publishes three versions: two readable and one with no text in any
language. So a backfill over it is exactly one transition, which is enough to assert the
loop's contract: an outcome per transition, a report on the ones that produced a delta, and a
recorded failure rather than a raised one when a transition cannot be computed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pytest

import emendrix.backfill.runner as runner_module
from emendrix.backfill.plan import Transition, plan_transitions
from emendrix.backfill.runner import TRIGGER, run_transitions
from emendrix.core import ActId, ConsolidationPending, ProvisionTree, Unavailable, VersionId
from emendrix.graph import PipelineDeps, PipelineState, RunReport
from stub_engine import citing_offered, engine
from toy_corpus import HOUSE_RULES, V1, V2, V3_PENDING, ToyCorpusAdapter

OBSERVED = date(2026, 8, 8)


def deps(adapter: ToyCorpusAdapter | None = None) -> PipelineDeps:
    return PipelineDeps(
        adapter=adapter if adapter is not None else ToyCorpusAdapter(observed_on=OBSERVED),
        engine=engine(citing_offered()),
        observed_on=OBSERVED,
    )


def toy_transitions() -> Sequence[Transition]:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    return plan_transitions(HOUSE_RULES, adapter.discover_versions(HOUSE_RULES)).transitions


def test_the_toy_corpus_offers_one_readable_transition() -> None:
    """v3 has no text in any language, so it is not an endpoint. The plan says so before the run."""
    planned = toy_transitions()
    assert len(planned) == 1
    assert (planned[0].from_version, planned[0].to_version) == (V1, V2)


def test_every_transition_produces_exactly_one_outcome() -> None:
    outcomes = list(run_transitions(deps(), toy_transitions(), observed_on=OBSERVED))
    assert len(outcomes) == 1
    assert outcomes[0].status == "emitted"
    report = outcomes[0].report
    assert report is not None
    assert len(report.deltas) == 1


def test_the_event_says_which_command_asserted_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A backfilled entry must not read as though a poll had found it.

    Read off the state the runner hands to the graph rather than off the report: `EmittedDelta`
    carries the act and the two versions, not the event that asked for them, so the trigger is
    only observable where the runner writes it.
    """
    captured: list[PipelineState] = []

    def spying_execute(deps: PipelineDeps, state: PipelineState, *, watch: bool) -> RunReport:
        captured.append(state)
        return RunReport(observed_on=OBSERVED)

    monkeypatch.setattr(runner_module, "execute", spying_execute)
    list(run_transitions(deps(), toy_transitions(), observed_on=OBSERVED))
    assert captured[0].events[0].trigger == TRIGGER
    assert captured[0].events[0].previous_version == V1
    assert captured[0].events[0].new_version == V2


def test_an_outcome_becomes_the_ledger_attempt_that_records_it() -> None:
    outcome = next(iter(run_transitions(deps(), toy_transitions(), observed_on=OBSERVED)))
    attempt = outcome.attempt
    assert attempt.key == outcome.transition.key
    assert attempt.act == str(HOUSE_RULES)
    assert attempt.status == "emitted"


def test_a_transition_the_loop_cannot_compute_is_skipped_rather_than_emitted() -> None:
    """`ConsolidationPending` and friends are answers. They settle the transition, with a reason."""

    class Pending(ToyCorpusAdapter):
        def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
            found = super().fetch_version(act, V3_PENDING)
            # `Unavailable` is an annotated union, so the concrete class is what `isinstance`
            # can be asked about.
            assert isinstance(found, ConsolidationPending)
            return found

    outcomes = list(
        run_transitions(
            deps(Pending(observed_on=OBSERVED)), toy_transitions(), observed_on=OBSERVED
        )
    )
    assert outcomes[0].status == "skipped"
    assert outcomes[0].detail
    assert outcomes[0].report is not None


def test_a_transition_that_raises_is_recorded_and_the_run_continues() -> None:
    """One act's bad afternoon must not end a three-hundred-transition run."""

    class Broken(ToyCorpusAdapter):
        def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
            raise OSError("the endpoint hung up")

    planned = list(toy_transitions()) * 2
    outcomes = list(
        run_transitions(deps(Broken(observed_on=OBSERVED)), planned, observed_on=OBSERVED)
    )
    assert len(outcomes) == 2, "the second transition still ran"
    assert all(item.status == "failed" for item in outcomes)
    assert "the endpoint hung up" in outcomes[0].detail
    assert outcomes[0].report is None


def test_no_transitions_is_no_outcomes_and_no_error() -> None:
    assert list(run_transitions(deps(), [], observed_on=OBSERVED)) == []


def test_an_interrupted_run_stops_rather_than_recording_a_failure() -> None:
    """Ctrl-C is an instruction, not a fault.

    `KeyboardInterrupt` derives from `BaseException`, so the loop's `except Exception` lets it
    through. That is the whole point: catching it would turn one keypress into three hundred
    recorded failures and a ledger full of transitions nobody wanted retried.
    """

    class Interrupted(ToyCorpusAdapter):
        def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable:
            raise KeyboardInterrupt

    planned = list(toy_transitions()) * 2
    with pytest.raises(KeyboardInterrupt):
        list(
            run_transitions(deps(Interrupted(observed_on=OBSERVED)), planned, observed_on=OBSERVED)
        )
