"""The model layer's arithmetic, and the layered report it lands in.

The rates are computed from `GateStats` counts, so they are tested from synthetic counts with
known answers: a metric whose only test is "it produced a number over the corpus" is not tested.
The last two tests then run the real subset offline and assert the properties that must hold
whatever the cassettes contain: every change settles, every explanation is replayed, and no
pinned unit went missing.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import ChangeType
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eval_.corpus import EvalCorpus, load_corpus
from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.metrics import CaseResult
from emendrix.eval_.model_metrics import ChangeOutcome, ModelCaseResult, ModelMetrics, pool
from emendrix.eval_.report import render_markdown
from emendrix.eval_.runner import CorpusReader, EvalRun, prepare_case, run_corpus
from emendrix.eval_.subset import restrict, select_subset
from emendrix.eval_.thresholds import MODEL_FLOORS, check_model
from emendrix.explain import RunStats
from emendrix.gate import GateOutcome, GateStats
from eu_pins import FIXTURE_DIR, OBSERVED_ON

RUN_DATE = date(2026, 8, 6)


def _case(case_id: str, first: GateStats, settled: GateStats) -> ModelCaseResult:
    return ModelCaseResult(
        case_id=case_id, act="X", units=settled.changes, first_round=first, settled=settled
    )


def test_the_rates_are_the_counts_and_nothing_else() -> None:
    """Ten changes: six passed, two recovered on retry, one quoted, one had nothing to explain."""
    settled = GateStats(
        changes=10,
        passed_first=6,
        passed_on_retry=2,
        fallback=1,
        unexplained=1,
        retries=3,
        sentences=20,
        citations=25,
        citations_rejected=5,
    )
    first = GateStats(
        changes=10, passed_first=6, retries=3, sentences=12, citations=15, citations_rejected=5
    )
    metrics = pool("m", (_case("a", first, settled),))

    assert metrics.checked == 9  # the unexplained change is not in any denominator
    assert metrics.grounding_rate == pytest.approx(6 / 9)
    assert metrics.retry_recovery_rate == pytest.approx(2 / 3)
    assert metrics.fallback_rate == pytest.approx(1 / 9)
    assert metrics.citation_validity == pytest.approx(10 / 15)
    assert metrics.settled_all is True


def test_a_layer_that_measured_nothing_answers_none_rather_than_zero() -> None:
    """`None` and `0.000` are different claims: one is "not measured", the other is "measured"."""
    metrics = pool("m", ())
    assert metrics.checked == 0
    assert metrics.grounding_rate is None
    assert metrics.retry_recovery_rate is None
    assert metrics.fallback_rate is None
    assert metrics.citation_validity is None


def test_a_change_that_never_settled_is_a_bug_and_says_so() -> None:
    settled = GateStats(changes=4, passed_first=1, retries=3)
    metrics = pool("m", (_case("a", settled, settled),))
    assert metrics.settled_all is False
    breaches = [str(item) for item in check_model(metrics)]
    assert any("settled" in item for item in breaches)


def test_a_judgements_breach_names_the_judge_it_looked_for() -> None:
    """The usual cause is a judge nothing was recorded against, so the breach has to say which.

    A floor that reports `measured 0.000` and names no model reads as a lost cassette directory
    rather than as a configuration override, which is what `EMENDRIX_JUDGE_MODEL` pointing at an
    unrecorded model produced on 2026-08-08.
    """
    settled = GateStats(changes=55, passed_first=55, sentences=55, citations=55)
    metrics = pool("m", (_case("a", settled, settled),))
    unjudged = FaithfulnessReport(judge_model="openrouter:vendor/nothing-recorded", sampled=20)
    breaches = [str(item) for item in check_model(metrics, unjudged)]

    assert any(
        item.startswith("faithfulness judgements recorded (openrouter:vendor/nothing-recorded):")
        for item in breaches
    )
    unnamed = [str(item) for item in check_model(metrics, None)]
    assert any(item.startswith("faithfulness judgements recorded:") for item in unnamed)


def test_the_floors_catch_a_shrunken_subset() -> None:
    thin = pool(
        "m",
        (_case("a", GateStats(changes=1, passed_first=1), GateStats(changes=1, passed_first=1)),),
    )
    assert [str(item) for item in check_model(thin)] != []


def test_pooling_sums_both_rounds_and_keeps_the_cases() -> None:
    left = GateStats(changes=2, passed_first=2, sentences=4, citations=4)
    right = GateStats(changes=3, passed_first=3, sentences=6, citations=6)
    metrics = pool("m", (_case("a", left, left), _case("b", right, right)))
    assert metrics.settled.changes == 5
    assert metrics.first_round.citations == 10
    assert [case.case_id for case in metrics.cases] == ["a", "b"]


def test_the_counts_a_run_carries_pool_across_cases() -> None:
    """`no_evidence` sums like `truncated` does. A count that stops at one case reaches nothing."""
    left = _case("a", GateStats(), GateStats()).model_copy(
        update={
            "explain": RunStats(model_id="m", changes=3, explained=2, truncated=2, no_evidence=1)
        }
    )
    right = _case("b", GateStats(), GateStats()).model_copy(
        update={
            "explain": RunStats(model_id="m", changes=2, explained=1, truncated=1, no_evidence=1)
        }
    )
    metrics = pool("m", (left, right))
    assert (metrics.changes, metrics.explained) == (5, 3)
    assert metrics.truncated == 3
    assert metrics.no_evidence == 2


def test_an_outcome_row_carries_where_it_came_from() -> None:
    row = ChangeOutcome(
        case_id="c",
        unit="AR 5",
        change_type=ChangeType.MODIFIED,
        outcome=GateOutcome.FALLBACK,
        sentences=1,
        citations=1,
        citations_rejected=2,
        fallback_sentences=1,
        retried=True,
        synthetic=True,
    )
    assert row.model_dump()["outcome"] == "fallback"
    assert row.synthetic is True


@pytest.fixture(scope="module")
def corpus() -> EvalCorpus:
    return load_corpus()


def test_the_committed_subset_is_the_one_the_rule_selects(corpus: EvalCorpus) -> None:
    """The subset is generated, not curated, so re-running the rule must reproduce it."""
    subset = corpus.explain_subset
    assert subset is not None
    http = CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR))
    reader = CorpusReader(CellarClient(http, observed_on=OBSERVED_ON))
    deltas = []
    for case in corpus.cases:
        prepared = prepare_case(reader, case)
        if isinstance(prepared, CaseResult):
            continue
        deltas.append((case.id, prepared.corroboration.delta))
    assert select_subset(deltas) == subset


def test_restricting_a_delta_reports_a_unit_it_no_longer_holds(corpus: EvalCorpus) -> None:
    http = CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR))
    reader = CorpusReader(CellarClient(http, observed_on=OBSERVED_ON))
    case = corpus.case("32017R0745@20200424")
    assert case is not None
    prepared = prepare_case(reader, case)
    assert not isinstance(prepared, CaseResult)
    kept, missing = restrict(prepared.corroboration.delta, ("AR 59", "AR 99999"))
    assert [change.location.canonical for change in kept.changes] == ["AR 59"]
    assert missing == ("AR 99999",)


def test_the_report_keeps_grounding_and_faithfulness_in_separate_sections(
    corpus: EvalCorpus,
) -> None:
    """Layered sections, and the two model rows never share a heading (honesty rule 2)."""
    settled = GateStats(changes=2, passed_first=1, fallback=1, retries=1)
    metrics = ModelMetrics(
        model_id="m",
        cases=(_case("a", settled, settled),),
        changes=2,
        first_round=settled,
        settled=settled,
    )
    http = CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR))
    reader = CorpusReader(CellarClient(http, observed_on=OBSERVED_ON))
    run: EvalRun = run_corpus(
        reader, corpus, run_date=RUN_DATE, revision="test", only="32017R0745@20230311"
    )
    faithfulness = FaithfulnessReport(judge_model="j", sampled=2, judged=2, faithful=2)
    markdown = render_markdown(
        run.model_copy(update={"model": metrics, "faithfulness": faithfulness}), corpus
    )
    grounding = markdown.index("## Model layer — citation grounding")
    quality = markdown.index("## Model layer — explanation faithfulness")

    assert markdown.index("## Headline") < grounding < quality
    section = markdown[grounding:quality]
    assert "Not explanation quality." in section
    assert "faithful" not in section.lower().replace("faithfulness, measured further down", "")
    assert "**Faithful: 2 of 2** (1.000)" in markdown[quality:]


def test_the_floors_are_the_ones_the_committed_report_measured() -> None:
    """A floor is the value a report named, not an aspiration. `source` says which report."""
    assert MODEL_FLOORS.source.startswith("reports/eval/")
    assert MODEL_FLOORS.subset_changes == 55
    assert MODEL_FLOORS.max_missing_units == 0
