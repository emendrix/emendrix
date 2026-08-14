"""The run summary as a log collector receives it, rather than as a person reads it.

A deployment's stdout is a log pipeline's input. The full `RunReport` is unsuitable for that
and not marginally so: one real transition of nine changes serialises to roughly 180 kB, and a
collector that reassembles container lines and parses one JSON object per line does one of two
unhelpful things with it. Pretty-printed, it arrives as some thirty fragments whose messages are
`}` and `    "notes_dropped": 0,`. Compacted onto one line, it exceeds the line cap collectors
impose (fluent-bit's default is 32 kB, with `Skip_Long_Lines On`) and is dropped whole, which is
worse, because fragments at least look wrong.

So the thing that goes to a log stream is the summary, and it has to be bounded by the number of
acts watched rather than by the number of changes found. That is the property these tests hold
down: the shape is one line, and its size does not follow the report's.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from emendrix.cli import app
from eu_pins import FIXTURE_DIR, OBSERVED_ON
from run_pins import RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()


@pytest.fixture(autouse=True)
def _replay_from_the_run_cassettes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same offline pinning `test_run_cli.py` uses: cassettes only, and no key present."""
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")
    for _var in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(_var, raising=False)


def explain(*extra: str) -> tuple[str, str]:
    """The pinned transition through the shipped command; stdout and stderr kept apart."""
    result = runner.invoke(
        app,
        [
            "explain",
            TRANSITION.celex,
            TRANSITION.from_version,
            TRANSITION.to_version,
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--observed-on",
            OBSERVED_ON.isoformat(),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    return result.stdout, result.stderr


def test_the_json_summary_is_a_single_parseable_line() -> None:
    """One line, because a collector's unit of ingestion is a line and nothing smaller."""
    _, stderr = explain("--summary", "json")
    lines = [line for line in stderr.splitlines() if line.strip()]
    assert len(lines) == 1, f"the summary must be one line, got {len(lines)}"
    json.loads(lines[0])


def test_the_json_summary_carries_the_counts_the_panels_are_built_from() -> None:
    """Gate outcomes and touched units per act: what "did this run do" is answered with."""
    _, stderr = explain("--summary", "json")
    payload = json.loads(stderr.strip())
    assert payload["observed_on"] == OBSERVED_ON.isoformat()
    assert payload["gate"]["changes"] == TRANSITION.changes
    act = payload["acts"][0]
    assert act["from_version"] == TRANSITION.from_version
    assert act["to_version"] == TRANSITION.to_version
    assert act["summary"]["touched_units"] == TRANSITION.changes
    assert act["gate"]["changes"] == TRANSITION.changes


def test_the_json_summary_is_bounded_by_acts_and_not_by_changes() -> None:
    """The whole point. Nine changes make a ~180 kB report; the summary must not follow it.

    The bound asserted here is deliberately far below any collector's line cap rather than
    equal to one, so that this fails while there is still room to fix it.
    """
    report, stderr = explain("--summary", "json")
    summary = stderr.strip()
    assert len(summary.encode()) < 4096, "a run summary that needs 4 kB is carrying prose"
    assert len(summary) * 10 < len(report), "the summary is not tracking the report's size"


def test_the_json_summary_carries_no_explanation_prose() -> None:
    """Size is the symptom; carrying sentences is the cause, so name the cause too.

    `gate.sentences` is a count and stays: what may not appear is a sentence's text.
    """
    report, stderr = explain("--summary", "json")
    payload = json.loads(stderr.strip())
    assert "changes" not in payload["acts"][0], "per-change detail belongs in the report"
    shipped = [
        sentence["text"]
        for delta in json.loads(report)["deltas"]
        for change in delta["changes"]
        for sentence in change["sentences"]
    ]
    assert shipped, "the pinned transition ships prose, or this test proves nothing"
    for text in shipped:
        assert text not in stderr, "an explanation sentence reached the log line"


def test_the_text_summary_is_still_what_a_person_gets_by_default() -> None:
    """The default may not change: a person at a terminal is the commoner reader."""
    _, stderr = explain()
    assert f"gate: {TRANSITION.changes} changes" in stderr
    assert "0 sent back for revision" in stderr
