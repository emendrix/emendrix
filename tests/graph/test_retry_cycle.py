"""The one cycle in the graph: gate → explain → gate, and never a third time.

This is the edge that makes a graph framework worth the dependency, so it is tested at
the level a reader would want to defend it: the conditional edge fires exactly when the gate
has pending work, the second attempt is a *revision* carrying the gate's own complaint, and the
run cannot revolve again no matter how badly the model behaves.

Three stubs, three outcomes, from `stub_engine.py`:

- `citing_offered`        → passes first, the cycle never fires;
- `citing_badly_then_well`→ fails, is told exactly what was wrong, passes on retry;
- `citing_nothing_real`   → fails twice, and the verbatim quotation ships instead.

In all three the change count out equals the change count in. That is the promise, and it is
what every assertion here is ultimately about.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from pydantic_ai.models.function import FunctionModel

from emendrix.core import VersionId
from emendrix.gate import GateOutcome
from emendrix.graph import (
    MAX_GATE_RETRIES,
    PipelineDeps,
    PipelineState,
    RunReport,
    after_gate,
    build_pipeline,
    run_pipeline,
)
from emendrix.watch.events import AmendmentEvent
from stub_engine import (
    INVENTED_KEY,
    citing_badly_then_well,
    citing_nothing_real,
    citing_offered,
    engine,
    recording,
    revision_count,
)
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED = date(2026, 8, 6)

EVENT = AmendmentEvent(
    act=HOUSE_RULES,
    target_version=V2,
    new_version=V2,
    previous_version=V1,
    trigger="toy:retry",
    observed_on=OBSERVED,
)


def report_from(model: FunctionModel) -> RunReport:
    deps = PipelineDeps(
        adapter=ToyCorpusAdapter(observed_on=OBSERVED),
        engine=engine(model),
        observed_on=OBSERVED,
    )
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps, watch=False),
            PipelineState(observed_on=OBSERVED, events=(EVENT,)),
        )
    )
    assert final.report is not None
    return final.report


@pytest.fixture
def touched() -> int:
    """How many changes the toy transition has; every assertion below is relative to it."""
    return report_from(citing_offered()).deltas[0].summary.touched_units


# ------------------------------------------------------------------ the edge itself


def test_the_conditional_edge_is_arithmetic_and_not_a_judgement() -> None:
    """`after_gate` counts; it does not look at a sentence. That is the constraint, in code."""
    idle = PipelineState(observed_on=OBSERVED)
    assert after_gate(idle) == "emit", "nothing pending, so nothing to ask again"
    assert MAX_GATE_RETRIES == 1


def test_a_first_attempt_that_passes_never_enters_the_cycle(touched: int) -> None:
    prompts: list[str] = []
    report = report_from(recording(citing_offered(), prompts))
    gate = report.deltas[0].gate

    assert gate.passed_first == touched
    assert gate.retries == 0
    assert revision_count(prompts) == 0, "no revision prompt was ever built"
    assert len(prompts) == touched, "one call per change, and no more"


# ------------------------------------------------------------------ passing on retry


def test_a_bad_citation_is_sent_back_once_and_the_second_answer_passes(touched: int) -> None:
    prompts: list[str] = []
    report = report_from(recording(citing_badly_then_well(), prompts))
    gate = report.deltas[0].gate

    assert gate.passed_on_retry == touched
    assert gate.passed_first == 0
    assert gate.fallback == 0
    assert gate.retries == touched
    assert gate.settled == gate.changes
    assert revision_count(prompts) == touched
    assert len(prompts) == touched * 2, "exactly two calls per change: the attempt and the retry"


def test_the_retry_carries_the_gates_own_complaint_and_the_offered_keys(touched: int) -> None:
    """A retry that did not say what was wrong would be a second guess, not a correction."""
    prompts: list[str] = []
    report_from(recording(citing_badly_then_well(), prompts))
    revisions = [prompt for prompt in prompts if "REJECTED BY THE CITATION GATE" in prompt]

    assert revisions
    for prompt in revisions:
        assert INVENTED_KEY in prompt, "the specific bad key is named"
        assert "not offered for this change" in prompt
        assert "OFFERED CITATION KEYS" in prompt, "the legal keys are still in front of the model"


def test_the_change_that_passed_on_retry_ships_the_corrected_sentence(touched: int) -> None:
    report = report_from(citing_badly_then_well())
    for change in report.deltas[0].changes:
        assert change.outcome is GateOutcome.PASSED_ON_RETRY
        assert [sentence.text for sentence in change.sentences] == [
            "Corrected on the second attempt."
        ]
        assert not any(sentence.fallback for sentence in change.sentences)


# ------------------------------------------------------------------ falling back


def test_a_model_that_fails_twice_falls_back_and_the_change_still_ships(touched: int) -> None:
    prompts: list[str] = []
    report = report_from(recording(citing_nothing_real(), prompts))
    emitted = report.deltas[0]
    gate = emitted.gate

    assert gate.fallback == touched
    assert gate.passed_first == 0 and gate.passed_on_retry == 0
    assert gate.retries == touched
    assert len(emitted.changes) == touched, "never drop a change"
    assert len(prompts) == touched * 2, "one revision, and no third attempt"
    assert revision_count(prompts) == touched


def test_the_fallback_sentence_is_the_provisions_own_text_and_says_so(touched: int) -> None:
    report = report_from(citing_nothing_real())
    for change in report.deltas[0].changes:
        assert change.outcome is GateOutcome.FALLBACK
        assert len(change.sentences) == 1
        sentence = change.sentences[0]
        assert sentence.fallback, "the flag is minted by the gate, never by the model"
        assert sentence.text != "A confident sentence about nothing."
        quoted = change.change.after or change.change.before
        assert quoted is not None
        assert " ".join(str(quoted).split())[:40] in sentence.text
        assert sentence.citations, "even the gate's own sentence carries a citation"


def test_no_ungrounded_sentence_reaches_the_output_by_any_route(touched: int) -> None:
    """The other half of the promise, over all three stub behaviours at once."""
    for model in (citing_offered(), citing_badly_then_well(), citing_nothing_real()):
        report = report_from(model)
        emitted = report.deltas[0]
        assert len(emitted.changes) == touched
        for change in emitted.changes:
            assert change.sentences, f"{change.change.location.canonical} shipped with nothing"
            for sentence in change.sentences:
                assert sentence.citations
                if not sentence.fallback:
                    assert INVENTED_KEY not in [
                        c.ref.location.canonical for c in sentence.citations
                    ]


def test_the_rejected_citations_are_counted_rather_than_forgotten(touched: int) -> None:
    """Published as measured: a run that had to fall back on everything says so in its numbers."""
    gate = report_from(citing_nothing_real()).gate
    assert gate.citations_rejected == touched * 2, "both rounds' rejections are counted"
    assert gate.citations >= gate.citations_rejected
    assert gate.changes == touched


def test_the_toy_versions_are_the_pair_these_assertions_assume() -> None:
    assert VersionId("v1") == V1
    assert VersionId("v2") == V2
