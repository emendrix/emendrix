"""The report: byte-stable, round-trippable, and honest about what it does not measure.

Built from a synthetic run rather than the corpus: rendering is not scoring, and a rendering
test that costs a minute of CI is a rendering test nobody runs.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from test_runner_toy import CHANGED, labels, tree

from emendrix.core import ProvisionLocation, Signal, SignalClaim, SignalReport
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.eval_.aggregate import aggregate
from emendrix.eval_.corpus import CorpusAct, CorpusSkip, EvalCorpus
from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.metric_rows import metric_rows
from emendrix.eval_.metrics import score
from emendrix.eval_.model_metrics import ModelMetrics
from emendrix.eval_.model_report import render_faithfulness, render_model_layer
from emendrix.eval_.prose import DISCLAIMER, KNOWN_CLASSES, MEANING, count
from emendrix.eval_.report import render_markdown, write_report
from emendrix.eval_.runner import EvalRun
from emendrix.eval_.thresholds import FLOORS, Floors, check
from emendrix.gate import GateStats

RUN_DATE = date(2026, 8, 6)


@pytest.fixture
def run() -> EvalRun:
    """One perfect toy transition and one where the reference set is missing a unit."""
    delta = compute_delta(tree("v1"), tree("v2"))
    thin = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=tuple(
            SignalClaim(location=ProvisionLocation.parse(unit), change_type=kind)
            for unit, kind in CHANGED.items()
            if unit != "AN I"
        ),
    )
    results = (
        score("toy@v2", corroborate(delta, metadata=labels())),
        score("toy@v2-thin", corroborate(delta, metadata=thin)),
    )
    return EvalRun(
        run_date=RUN_DATE,
        revision="deadbee",
        corpus_built_on=date(2026, 8, 5),
        corpus_transitions_possible=4,
        corpus_coverage=0.5,
        metrics=aggregate(results),
        cases=results,
    )


@pytest.fixture
def corpus() -> EvalCorpus:
    return EvalCorpus(
        built_on=date(2026, 8, 5),
        acts=(CorpusAct(celex="toy", transitions_possible=4, transitions_selected=2),),
        skips=(
            CorpusSkip(
                act="toy",
                version="v3",
                reason="consolidation_pending",
                detail="agreed at the June meeting, not yet written up",
            ),
        ),
    )


def test_two_renderings_of_one_run_are_byte_identical(run: EvalRun, corpus: EvalCorpus) -> None:
    assert render_markdown(run, corpus) == render_markdown(run, corpus)


def test_two_writes_of_one_run_are_byte_identical(
    run: EvalRun, corpus: EvalCorpus, tmp_path: Path
) -> None:
    first = [path.read_bytes() for path in write_report(run, corpus, tmp_path)]
    second = [path.read_bytes() for path in write_report(run, corpus, tmp_path)]
    assert first == second


def test_the_report_is_named_for_the_date_and_the_revision(
    run: EvalRun, corpus: EvalCorpus, tmp_path: Path
) -> None:
    markdown, payload = write_report(run, corpus, tmp_path)
    assert markdown.name == "2026-08-06-deadbee.md"
    assert payload.name == "2026-08-06-deadbee.json"


def test_the_json_round_trips_through_the_model(
    run: EvalRun, corpus: EvalCorpus, tmp_path: Path
) -> None:
    _, payload = write_report(run, corpus, tmp_path)
    restored = EvalRun.model_validate_json(payload.read_bytes())
    assert restored == run
    assert restored.metrics.localisation == run.metrics.localisation


def test_the_report_states_what_it_does_not_measure(run: EvalRun, corpus: EvalCorpus) -> None:
    """The rigour table is fixed text: it never softens because a number came out well."""
    rendered = render_markdown(run, corpus)
    assert MEANING in rendered
    assert KNOWN_CLASSES in rendered
    assert "it measures *citation validity*, not explanation quality" in rendered
    assert "**Never free.** Reported separately" in rendered


def test_every_report_carries_the_disclaimer(run: EvalRun, corpus: EvalCorpus) -> None:
    assert DISCLAIMER in render_markdown(run, corpus)
    assert "Not legal advice" in render_markdown(run, corpus)


def test_a_count_of_one_reads_as_one_in_the_published_rows() -> None:
    """These rows go to the README and to the methodology page, so a corpus of one must read.

    Every value in the committed report is well above one, so this asserts a property no
    current figure exercises. That is the point: the wording is fixed before a small corpus
    finds it, not after a reader does. `plural` is explicit because `entry` is the one noun
    these reports count that plus-`s` gets wrong.
    """
    assert count(1, "transition") == "1 transition"
    assert count(0, "transition") == "0 transitions"
    assert count(17, "transition") == "17 transitions"
    assert count(1, "change") == "1 change"
    assert count(1, "unit") == "1 unit"
    assert count(1, "entry", "entries") == "1 entry"
    assert count(20, "entry", "entries") == "20 entries"


def test_the_row_that_counts_transitions_agrees_the_noun(run: EvalRun) -> None:
    """The rows are what gets published, so the phrasing is asserted through them too."""
    rows = metric_rows(run)
    counted = [row.n for row in rows if row.n.endswith(("transition", "transitions"))]
    assert counted, "the localisation and instruction rows both count transitions"
    for value in counted:
        number = int(value.split(" ")[0])
        assert value.endswith("transition") == (number == 1), value


def test_the_unsupported_coordinate_count_is_published_as_a_floor() -> None:
    """The count ships beside the other gate counts, and its caveat rides in the same bullet.

    Two silent under-counts make the number a floor rather than a clearance: a mention the
    recogniser misses is never counted, and a coordinate readable on either shown side counts
    as supported however wrong the sentence naming it is. The rendering must say both, in the
    bullet itself, so the number cannot be quoted without them.
    """
    metrics = ModelMetrics(
        model_id="test:model",
        settled=GateStats(changes=2, passed_first=2, sentences=2, coordinates_unsupported=3),
        first_round=GateStats(changes=2, passed_first=2, sentences=2, citations=2),
    )
    rendered = "\n".join(render_model_layer(metrics))
    line = next(
        line
        for line in rendered.splitlines()
        if line.startswith("- **Coordinates named without support**")
    )
    assert "— 3;" in line
    assert "Counted per coordinate, not per sentence" in line
    assert "no sentence is dropped or rewritten for it" in line
    assert "floor" in line
    assert "a mention it misses is never counted" in line
    assert "visible on one shown side counts as supported" in line
    assert "A zero is a fact about this corpus, not about the check" in line
    assert "synthetic tests are what keep it able to fire" in line


def test_the_unexplained_count_is_published_with_its_reason_breakdown() -> None:
    """A change can ship without an explanation for three reasons, and the report must say
    which, because the three mean different things: a unit no text exists for, a cap the
    project chose, and a provider failing on a call that was made. One flat count reads as one
    phenomenon, and a model failure hiding inside a corpus artefact is exactly the kind of
    blur the metrics rules forbid. All three read zero over the pinned subset as it ships, so
    like the coordinate bullet above, the wording is fixed before a figure exercises it.
    """
    metrics = ModelMetrics(
        model_id="test:model",
        unexplained=4,
        no_evidence=1,
        model_failed=1,
        nothing_to_explain=2,
        settled=GateStats(changes=10, passed_first=6, unexplained=4, sentences=6),
        first_round=GateStats(changes=10, passed_first=6, sentences=6, citations=6),
    )
    rendered = "\n".join(render_model_layer(metrics))
    line = next(
        line
        for line in rendered.splitlines()
        if line.startswith("- **Changes shipped without an explanation**")
    )
    assert "4 of 10" in line
    assert "2 had nothing to explain" in line
    assert "1 were the cap's refusal" in line
    assert "1 were model failures" in line
    assert "stated reason" in line


def _judge_line(judge: str, explainer: str) -> str:
    """The one bullet naming the judge, out of a rendered faithfulness section."""
    report = FaithfulnessReport(judge_model=judge, sampled=1, judged=1, faithful=1)
    rendered = render_faithfulness(report, explainer)
    return next(line for line in rendered if line.startswith("- **Judge**"))


def test_what_the_judge_pairing_buys_is_read_off_the_two_model_ids() -> None:
    """A hand-written independence caveat outlives the configuration that made it true, and goes
    on claiming a shared vendor after the judge has moved to another one. Deriving it from the
    two model ids is what stops that."""
    shared = _judge_line("openrouter:anthropic/claude-opus-5", "openrouter:anthropic/x")
    assert "same vendor, same lineage" in shared

    cross = _judge_line("openrouter:openai/gpt-5.6-sol", "openrouter:anthropic/claude-sonnet-5")
    assert "A different vendor as well" in cross
    assert "still not independence" in cross, "a different vendor is not independence"
    assert "same vendor" not in cross


def test_an_id_with_no_vendor_segment_claims_nothing_about_vendors() -> None:
    """A reviewer pointing the judge at a bare model name must not be told a lineage story."""
    for judge, explainer in (("j", "openrouter:anthropic/x"), ("openrouter:openai/y", "e")):
        line = _judge_line(judge, explainer)
        assert "a second model reading the same English" in line
        assert "vendor" not in line


def test_the_report_publishes_the_disagreement_and_the_skip(
    run: EvalRun, corpus: EvalCorpus
) -> None:
    rendered = render_markdown(run, corpus)
    assert "`AN I` | seen by structural_diff, not by corpus_metadata" in rendered
    assert "consolidation_pending" in rendered
    assert "agreed at the June meeting, not yet written up" in rendered


def test_a_run_with_no_disagreement_says_so(corpus: EvalCorpus) -> None:
    delta = compute_delta(tree("v1"), tree("v2"))
    result = score("toy@v2", corroborate(delta, metadata=labels()))
    clean = EvalRun(
        run_date=RUN_DATE, corpus_built_on=RUN_DATE, metrics=aggregate((result,)), cases=(result,)
    )
    assert "## Disagreements, verbatim\n\nEvery unit" in render_markdown(clean, corpus)
    assert "None.\n" in render_markdown(clean, corpus)


# ------------------------------------------------------------------- the floors


def test_a_number_that_falls_breaches_its_floor(run: EvalRun) -> None:
    floors = FLOORS.model_copy(update={"localisation_micro_f1": 0.99, "cases_scored": 2})
    breached = check(run.metrics, floors)
    assert [item.metric for item in breached] == ["localisation micro F1"]
    assert "floor 0.990" in str(breached[0])


def test_a_number_that_rises_does_not(run: EvalRun) -> None:
    floors = Floors(
        source="synthetic",
        localisation_micro_f1=0.5,
        localisation_micro_recall=0.5,
        localisation_macro_f1=0.5,
        classification_accuracy=0.5,
        cases_scored=2,
        max_parser_unknown_elements=0,
        max_documents_unreadable=0,
    )
    assert check(run.metrics, floors) == ()


def test_a_metric_that_was_never_measured_is_a_breach_not_a_pass() -> None:
    """An eval that stopped computing a number must fail, not quietly report nothing."""
    breached = check(aggregate(()))
    assert {item.metric for item in breached} >= {"localisation micro F1", "transitions scored"}
    assert all(item.measured is None or item.measured == 0.0 for item in breached)
