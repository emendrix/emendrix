"""`emendrix explain` and `emendrix run --once` from the outside, offline, end to end.

`--fixture-dir` installs `FixtureResponseCache`, which has no code path to a socket, and
`CassetteMode.REPLAY` never constructs a provider client, so this is the whole shipped
command, argument parsing to JSON, with the network and the API key both physically absent.
That is how CI runs it.

**What the committed cassettes are.** Real exchanges with the pinned model, recorded by
`test_record_run_cassettes.py` and replayed here byte for byte. All nine changes pass the
citation gate on their first attempt, so there is no revision on disk and nothing falls back to
a quotation.

**What this file therefore does and does not prove.** It proves the shipped command produces the
artifact it claims to, offline, with every citation resolving against the two provision trees the
run already fetched. It proves nothing about whether the sentences are a *true* account of the
difference: that is faithfulness, it has no free ground truth, and it is measured and published
separately by the eval harness. A wrong sentence with a resolvable citation passes everything
below, exactly as designed.

The retry cycle and the verbatim fallback are tested against stub models that cite badly on
purpose, in `test_retry_cycle.py`. They belong there rather than here: a fallback that only
happens because the recorded model could not cite is a property of the recording, and it
disappears the day a re-recording cites correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.explain import Cassette, CassetteMiss
from emendrix.gate import GateOutcome
from eu_pins import AI_ACT, FIXTURE_DIR, OBSERVED_ON
from run_pins import RETRY_RECORDING, RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()

WINDOW = ("--since", "2026-08-05T10:00:00", "--until", "2026-08-05T10:05:00")


@pytest.fixture(autouse=True)
def _replay_from_the_run_cassettes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the explain stage at this file's cassette set, and at nothing else.

    Deleting the key as well is the belt-and-braces half: a run that reached for a provider
    would fail here rather than quietly succeed on someone's laptop and fail in CI.
    """
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")
    for _var in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(_var, raising=False)


def explain(*extra: str) -> str:
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
    return result.stdout  # the report alone; the summary line goes to stderr


def watchlist_file(tmp_path: Path, *celexes: str) -> Path:
    path = tmp_path / "watchlist.toml"
    path.write_text("".join(f'[[acts]]\ncelex = "{c}"\n' for c in celexes), encoding="utf-8")
    return path


# ------------------------------------------------------------------ emendrix explain


def test_the_manual_trigger_runs_the_whole_loop_offline() -> None:
    payload = json.loads(explain())
    assert len(payload["deltas"]) == 1
    emitted = payload["deltas"][0]
    assert emitted["from_version"] == TRANSITION.from_version
    assert emitted["to_version"] == TRANSITION.to_version
    assert len(emitted["changes"]) == TRANSITION.changes
    assert payload["skipped"] == []


def test_the_report_carries_the_disclaimer() -> None:
    assert json.loads(explain())["disclaimer"] == DISCLAIMER


def test_every_citation_resolves_and_every_change_still_ships() -> None:
    """What the gate is for: nothing shipped cites a provision this transition did not offer."""
    emitted = json.loads(explain())["deltas"][0]
    gate = emitted["gate"]

    assert gate["changes"] == TRANSITION.changes
    assert gate["passed_first"] == TRANSITION.changes
    assert gate["citations_rejected"] == 0
    assert gate["retries"] == 0, "nothing to send back"
    assert gate["fallback"] == 0, "and so nothing to quote in the model's place"
    assert gate["unexplained"] == 0
    assert len(emitted["changes"]) == TRANSITION.changes, "never drop a change"


def test_every_shipped_sentence_is_the_models_own_and_carries_a_rendered_link() -> None:
    """The sentences are the model's; the URLs are the adapter's. Nothing here invents either."""
    for change in json.loads(explain())["deltas"][0]["changes"]:
        assert change["outcome"] == GateOutcome.PASSED.value
        assert change["sentences"], "a change that passed the gate ships what it said"
        for sentence in change["sentences"]:
            assert sentence["fallback"] is False
            assert sentence["citations"], "every sentence carries at least one citation"
            for citation in sentence["citations"]:
                assert citation["url"].startswith(
                    "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:"
                )


def test_the_summary_line_goes_to_stderr_so_the_json_on_stdout_stays_parseable() -> None:
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
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["deltas"], "stdout is the report and nothing else"
    assert "gate: 9 changes" in result.stderr, "the counts a human reads first"
    assert "0 rejected" in result.stderr
    assert "0 sent back for revision" in result.stderr


def test_json_out_writes_the_same_document_to_a_file(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.json"
    explain("--json-out", str(target))
    written = json.loads(target.read_text(encoding="utf-8"))
    assert len(written["deltas"][0]["changes"]) == TRANSITION.changes
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_two_runs_produce_the_same_bytes() -> None:
    """Committed changelogs are diffed in git, so the document may not wobble."""
    assert explain() == explain()


def test_the_verbatim_texts_reach_the_output_untouched() -> None:
    """The changelog quotes the `Change`, not the model, so `before`/`after` must be there."""
    changes = json.loads(explain())["deltas"][0]["changes"]
    with_text = [c for c in changes if c["change"]["before"] is not None]
    assert with_text, "the MDR pair has text on both sides of every change"
    for change in with_text:
        assert change["change"]["after"] is not None


# ------------------------------------------------------------------ emendrix run --once


def test_run_once_polls_persists_and_emits_on_a_day_with_no_watched_amendment(
    tmp_path: Path,
) -> None:
    """The whole command with nothing to do, which is most days, and still a result.

    The MDR is watched, the pinned window names only the AI Act, so the poll reads 46
    notifications, matches none, advances its cursor and emits an empty report.
    """
    state = tmp_path / "state.json"
    result = runner.invoke(
        app,
        [
            "run",
            "--once",
            "--watchlist",
            str(watchlist_file(tmp_path, TRANSITION.celex)),
            "--state-file",
            str(state),
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--observed-on",
            OBSERVED_ON.isoformat(),
            *WINDOW,
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    payload = json.loads(result.stdout)
    assert payload["deltas"] == []
    assert payload["skipped"] == []
    assert payload["poll"]["entries"] == 46
    assert payload["poll"]["matched"] == 0
    assert payload["disclaimer"] == DISCLAIMER
    assert state.is_file(), "the cursor is persisted, so the next poll does not rescan"


def test_run_once_reaches_the_explain_stage_with_the_real_flagship_delta(
    tmp_path: Path,
) -> None:
    """Watching the AI Act over the pinned window drives the whole loop on 45 real changes.

    No cassettes are committed for that transition (45 changes is ten times the bytes needed
    to prove the wiring), so replay does what replay is designed to do and fails loudly naming
    the exchange it wanted. Reaching that failure *through the command* is the assertion: the
    poll matched, both versions were fetched, the diff ran, corroboration ran, and EXPLAIN was
    entered. A `--cassettes live` run with a key finishes it.
    """
    result = runner.invoke(
        app,
        [
            "run",
            "--once",
            "--watchlist",
            str(watchlist_file(tmp_path, AI_ACT)),
            "--state-file",
            str(tmp_path / "state.json"),
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--observed-on",
            OBSERVED_ON.isoformat(),
            *WINDOW,
        ],
    )
    assert isinstance(result.exception, CassetteMiss)
    assert "record and live" in str(result.exception), "the error says how to fix itself"


def test_a_bad_watchlist_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    """It is the one hand-written input in the system, so it gets a hand-written answer."""
    missing = runner.invoke(app, ["run", "--once", "--watchlist", str(tmp_path / "gone.toml")])
    assert missing.exit_code == 2
    assert "copy watchlist.example.toml" in missing.output


def test_the_loop_flag_says_what_to_use_instead_of_pretending_to_schedule(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app, ["run", "--loop", "--watchlist", str(watchlist_file(tmp_path, AI_ACT))]
    )
    assert result.exit_code == 2
    assert "cron" in result.output


# ------------------------------------------------------------------ the cassettes


def test_the_committed_run_cassettes_are_one_real_exchange_per_change() -> None:
    """No revision on disk, because none was asked for: every committed exchange is accounted
    for by a pinned transition, nine for the postponement and three for the retry recording."""
    files = sorted(RUN_CASSETTE_DIR.rglob("*.json"))
    assert len(files) == TRANSITION.changes + RETRY_RECORDING.changes
    for path in files:
        cassette = Cassette.model_validate_json(path.read_text(encoding="utf-8"))
        assert not cassette.synthetic, f"{path.name} was recorded from a stub"
        assert cassette.recorded_with == cassette.model_id
        assert "REJECTED BY THE CITATION GATE" not in cassette.user


def test_the_run_cassettes_are_byte_stable_when_rewritten() -> None:
    """Committed artifacts are diffed in git, so serialisation may not wobble."""
    for path in sorted(RUN_CASSETTE_DIR.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert Cassette.model_validate_json(text).to_json() == text
