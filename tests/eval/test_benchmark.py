"""Scoring a judge against the committed hand review.

The load-bearing test is the last one: the labelled judge's committed verdicts, scored against
the committed sign-off, must reproduce the agreement two independent artifacts already imply. It
pins the join, the direction of every miss and both files at once, and it is worth more than any
assertion invented here.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix.eval_.benchmark import (
    BENCHMARK_CASSETTE_DIR,
    LABELLED_JUDGE_MODEL,
    LABELLED_SIGNOFF_PATH,
    AmbiguousJudgement,
    IncompleteBenchmark,
    JudgeScore,
    load_recorded,
    score,
)
from emendrix.eval_.benchmark_cli import benchmark_path, render_benchmark
from emendrix.eval_.cli import app
from emendrix.eval_.judge import Verdict, judge_model
from emendrix.eval_.judgements import (
    JUDGE_CASSETTE_DIR,
    RUBRIC_SHA,
    JudgeCassette,
    JudgeCassetteStore,
    judgement_key,
)
from emendrix.eval_.signoff import ReviewedEntry, ReviewSignoff, latest_signoff, load_signoff

runner = CliRunner()


def _sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _entry(index: int, *, faithful: bool, note: str = "") -> ReviewedEntry:
    return ReviewedEntry(
        slug=f"case AR {index}",
        prompt_sha=_sha(f"prompt {index}"),
        faithful=faithful,
        note=note,
    )


def _signoff(*entries: ReviewedEntry) -> ReviewSignoff:
    return ReviewSignoff(
        reviewed_on=date(2026, 8, 8),
        reviewer="A Reviewer",
        worksheet="reports/faithfulness-review-2026-08-08.md",
        sample_digest="deadbeef",
        summary="reviewed by hand",
        entries=entries,
    )


def _cassette(index: int, *, faithful: bool, issue: str | None = None) -> JudgeCassette:
    prompt = f"prompt {index}"
    return JudgeCassette(
        judge_model="m",
        key=judgement_key("m", prompt, rubric_sha=RUBRIC_SHA),
        synthetic=False,
        recorded_with="m",
        prompt=prompt,
        rubric_sha=RUBRIC_SHA,
        output=Verdict(faithful=faithful, issue=issue),
    )


def test_the_join_is_by_prompt_digest_and_not_by_the_name_of_the_change() -> None:
    """A slug names a change; a judgement is about one exact prompt. Re-explain the same
    article with another model and the slug is unchanged while the question is not."""
    signoff = _signoff(_entry(1, faithful=True))
    same_slug = _cassette(1, faithful=True).model_copy(update={"prompt": "a different prompt"})
    with pytest.raises(IncompleteBenchmark, match=re.escape("1. case AR 1")):
        score(signoff, (same_slug,), judge_model="m")


def test_a_judgement_that_maps_to_no_entry_is_counted_rather_than_dropped() -> None:
    signoff = _signoff(_entry(1, faithful=True))
    result = score(
        signoff, (_cassette(1, faithful=True), _cassette(9, faithful=False)), judge_model="m"
    )

    assert result.entries == 1
    assert result.unmapped == (_sha("prompt 9"),)


def test_lenient_and_strict_are_counted_in_the_directions_their_names_say() -> None:
    """Easy to invert and impossible to notice afterwards: a lenient judge inflates every
    faithfulness rate it produces, and a strict one only makes the project look worse."""
    signoff = _signoff(
        _entry(1, faithful=False, note="the reviewer failed it"),
        _entry(2, faithful=True),
        _entry(3, faithful=True),
    )
    recorded = (
        _cassette(1, faithful=True),  # judge passed what the reviewer failed: lenient
        _cassette(2, faithful=False),  # judge failed what the reviewer passed: strict
        _cassette(3, faithful=True),  # agreement
    )
    result = score(signoff, recorded, judge_model="m")

    assert (result.agreements, result.misses) == (1, 2)
    assert (result.lenient, result.strict) == (1, 1)
    assert result.agreement_rate == pytest.approx(1 / 3)
    assert [row.lenient for row in result.rows] == [True, False, False]
    assert [row.strict for row in result.rows] == [False, True, False]


def test_a_judge_missing_an_entry_is_refused_rather_than_scored_over_the_rest() -> None:
    """Nineteen of twenty is a curated number, and the missing one is never the easy one."""
    signoff = _signoff(_entry(1, faithful=True), _entry(2, faithful=False))
    with pytest.raises(IncompleteBenchmark) as raised:
        score(signoff, (_cassette(1, faithful=True),), judge_model="m")

    assert raised.value.missing == ("2. case AR 2",)
    assert "2. case AR 2" in str(raised.value)
    assert "not a benchmark" in str(raised.value)


def test_two_answers_to_one_prompt_are_refused_rather_than_silently_resolved() -> None:
    """A rubric edit files a second answer beside the first: the key carries the rubric, the
    prompt does not. Picking whichever hash sorts first would score a judge on an instruction
    nobody chose, and the difference between the two rubrics is the substance of the comparison.
    """
    signoff = _signoff(_entry(1, faithful=True))
    under_another_rubric = _cassette(1, faithful=False).model_copy(
        update={"rubric_sha": "0" * 64, "key": judgement_key("m", "prompt 1", rubric_sha="0" * 64)}
    )
    with pytest.raises(AmbiguousJudgement) as raised:
        score(signoff, (_cassette(1, faithful=True), under_another_rubric), judge_model="m")

    assert raised.value.rubric_shas == tuple(sorted(("0" * 64, RUBRIC_SHA)))
    assert "Delete the superseded recording" in str(raised.value)


def test_an_empty_score_divides_by_nothing_rather_than_by_zero() -> None:
    assert JudgeScore(judge_model="m").agreement_rate is None


def test_the_store_is_read_through_its_own_name_check(tmp_path: Path) -> None:
    """`load_recorded` goes through the cassette store, so an edited prompt is refused there."""
    store = JudgeCassetteStore(tmp_path)
    store.save(_cassette(1, faithful=True))
    assert [item.prompt for item in load_recorded(tmp_path, "m")] == ["prompt 1"]
    assert load_recorded(tmp_path, "another model") == ()


def test_the_report_renders_deterministically_and_carries_the_reviewers_note() -> None:
    signoff = _signoff(
        _entry(1, faithful=False, note="sentence 3 states an effect the texts do not show"),
        _entry(2, faithful=True),
    )
    labelled = score(
        signoff, (_cassette(1, faithful=True), _cassette(2, faithful=True)), judge_model="old"
    )
    challenger = score(
        signoff,
        (_cassette(1, faithful=False, issue="sentence 3"), _cassette(2, faithful=True)),
        judge_model="new",
    )
    rendered = render_benchmark(signoff, labelled, challenger, date(2026, 8, 8))

    assert rendered == render_benchmark(signoff, labelled, challenger, date(2026, 8, 8))
    assert rendered.startswith("# Judge benchmark — 2026-08-08")
    assert "sentence 3 states an effect the texts do not show" in rendered
    assert "| 1 | `case AR 1` | **not faithful** | faithful | **not faithful** |" in rendered
    assert "is **better** on this set" in rendered
    assert "Not legal advice" in rendered
    assert benchmark_path(date(2026, 8, 8), Path("reports")).name == (
        "judge-benchmark-2026-08-08.md"
    )


def test_a_table_cell_cannot_end_its_own_column() -> None:
    """A reviewer's note is prose a person typed, and one pipe in it would shift every column."""
    signoff = _signoff(_entry(1, faithful=False, note="a | b\nsecond line"))
    scored = score(signoff, (_cassette(1, faithful=False),), judge_model="m")
    rendered = render_benchmark(signoff, scored, scored, date(2026, 8, 8))

    assert "a \\| b second line |" in rendered


def test_a_worse_result_is_reported_as_worse() -> None:
    """The one reading that must not be softened: publishing it is the point of measuring it."""
    signoff = _signoff(_entry(1, faithful=True), _entry(2, faithful=True))
    labelled = score(
        signoff, (_cassette(1, faithful=True), _cassette(2, faithful=True)), judge_model="old"
    )
    challenger = score(
        signoff, (_cassette(1, faithful=True), _cassette(2, faithful=False)), judge_model="new"
    )
    rendered = render_benchmark(signoff, labelled, challenger, date(2026, 8, 8))

    assert "is **worse** on this set by 1 entry" in rendered
    assert "published as measured" in rendered


def test_the_label_set_is_pinned_to_the_review_the_recordings_answer() -> None:
    """Sign-offs accumulate and publication takes the newest; this benchmark must not.

    Every committed judgement in either directory answers a prompt of the sample one person read
    on 2026-08-08. Following the newest review here would score both judges against twenty
    prompts neither has ever been asked, which is a refusal rather than a measurement.
    """
    labelled = load_signoff(LABELLED_SIGNOFF_PATH)
    assert labelled is not None
    assert labelled.worksheet == "reports/faithfulness-review-2026-08-08.md"

    newest = latest_signoff()
    assert newest is not None
    assert newest.worksheet != labelled.worksheet, "a later review must not re-point the labels"


def test_the_labelled_judge_scores_what_two_committed_artifacts_already_agree_on() -> None:
    """The self-test of the whole join, and of both artifacts it reads.

    Measured 2026-08-08: `openrouter:anthropic/claude-sonnet-5`, judging the prose recorded that
    day, agreed with the reviewer on 15 of the 20 sampled entries, and every one of the five
    misses was lenient. Neither the transcription nor this mapping is checkable on its own; that
    they produce this number together is what makes both trustworthy. A future edit to either
    file lands here.
    """
    signoff = load_signoff(LABELLED_SIGNOFF_PATH)
    assert signoff is not None and len(signoff.entries) == 20
    scored = score(
        signoff,
        load_recorded(JUDGE_CASSETTE_DIR, LABELLED_JUDGE_MODEL),
        judge_model=LABELLED_JUDGE_MODEL,
    )

    assert (scored.entries, scored.agreements, scored.misses) == (20, 15, 5)
    assert (scored.lenient, scored.strict) == (5, 0)
    assert [row.number for row in scored.rows if not row.agrees] == [2, 3, 5, 17, 18]
    assert scored.unmapped == ()
    assert scored.rubric_shas == ("",), "these predate the rubric entering the cassette key"


def test_the_challenger_answered_every_labelled_prompt_under_the_rubric_in_git() -> None:
    """The committed benchmark set is the current judge's answers to the same twenty prompts.

    Kept apart from `tests/cassettes-judge/`, which holds the current faithfulness sample: these
    rule on prose recorded on 2026-08-08, which is not the prose that ships, so a shared
    directory would make it unanswerable which of the two the published rate replays.

    Measured 2026-08-09: `openrouter:openai/gpt-5.6-sol`, under the rubric in git (the one that
    admits the pipeline header as evidence), agreed with the reviewer on 15 of the 20 with 1
    lenient miss and 4 strict ones, against the labelled judge's 15 with 5 lenient. One
    agreement fewer than the same judge scored under the 2026-08-08 rubric (16 with 1 lenient
    and 3 strict), so the rubric change cost an agreement on this label set and that is
    published as measured. Pinned here because a published comparison whose numbers nothing
    checks is a paragraph, not a measurement.
    """
    signoff = load_signoff(LABELLED_SIGNOFF_PATH)
    assert signoff is not None
    challenger = judge_model({})
    recorded = load_recorded(BENCHMARK_CASSETTE_DIR, challenger)
    scored = score(signoff, recorded, judge_model=challenger)

    assert scored.entries == 20
    assert scored.unmapped == ()
    assert scored.rubric_shas == (RUBRIC_SHA,)
    assert all(not cassette.synthetic for cassette in recorded), (
        "a stub's verdict is a test of the recorder and no evidence about a judge"
    )
    assert (scored.agreements, scored.lenient, scored.strict) == (15, 1, 4)
    assert [row.number for row in scored.rows if not row.agrees] == [2, 6, 8, 10, 19]


def test_the_command_writes_the_dated_comparison_and_names_both_judges(tmp_path: Path) -> None:
    """The composition root, over the committed artifacts, with the date passed in."""
    result = runner.invoke(
        app, ["judge-benchmark", "--report-dir", str(tmp_path), "--date", "2026-08-08"]
    )
    assert result.exit_code == 0, result.output

    written = benchmark_path(date(2026, 8, 8), tmp_path).read_text(encoding="utf-8")
    assert "| `openrouter:anthropic/claude-sonnet-5` |" in written
    assert written.count("15 / 20 (0.750)") == 2, "both judges score 15 of 20 on this label set"


def test_the_command_refuses_a_review_that_carries_no_per_entry_verdicts(tmp_path: Path) -> None:
    """A summary line is not a label set: there is nothing for a judge to be scored against."""
    empty = tmp_path / "signoff.json"
    empty.write_text(_signoff().model_dump_json(), encoding="utf-8")
    result = runner.invoke(app, ["judge-benchmark", "--signoff", str(empty), "--no-write"])

    assert result.exit_code == 1
    assert "no hand review with per-entry verdicts" in result.output
