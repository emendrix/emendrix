"""`emendrix watch --once`, run end to end against the pinned fixtures, with no network.

The window is the five pinned minutes of 2026-08-05, so what this exercises is the real feed,
the real AI Act tree notice and the real state file, with only the clock supplied by the test.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from emendrix import DISCLAIMER
from emendrix.cli import app
from emendrix.watch.source import DEFAULT_LOOKBACK_DAYS, OVERLAP, window_start
from emendrix.watch.state import load_state
from eu_pins import AI_ACT, AI_ACT_V1, AI_ACT_V2, FIXTURE_DIR

runner = CliRunner()

WINDOW = ("--since", "2026-08-05T10:00:00", "--until", "2026-08-05T10:05:00")


def watchlist_file(tmp_path: Path, *celexes: str) -> Path:
    path = tmp_path / "watchlist.toml"
    path.write_text(
        "".join(f'[[acts]]\ncelex = "{value}"\n' for value in celexes), encoding="utf-8"
    )
    return path


def run(tmp_path: Path, *extra: str, celexes: tuple[str, ...] = (AI_ACT,)) -> str:
    """The whole command, offline. Returns its output; a non-zero exit is a test failure."""
    result = runner.invoke(
        app,
        [
            "watch",
            "--once",
            "--watchlist",
            str(watchlist_file(tmp_path, *celexes)),
            "--state-file",
            str(tmp_path / "state.json"),
            "--fixture-dir",
            str(FIXTURE_DIR),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    return result.output


def test_the_flagship_amendment_is_found_offline(tmp_path: Path) -> None:
    output = run(tmp_path, *WINDOW)
    assert "46 notifications · 4 naming a watched act" in output
    assert f"+ new version   eu:{AI_ACT} {AI_ACT_V1} -> {AI_ACT_V2}" in output
    assert DISCLAIMER in output


def test_the_state_is_written_and_the_second_run_says_nothing_new(tmp_path: Path) -> None:
    """Idempotency, through the file: the same window twice reports once."""
    run(tmp_path, *WINDOW)

    state = load_state(tmp_path / "state.json").state
    assert state.last_window_end == datetime(2026, 8, 5, 10, 5)
    assert len(state.seen) == 46
    assert [row.key for row in state.emitted] == [f"eu:{AI_ACT}@{AI_ACT_V2}"]

    second = run(tmp_path, *WINDOW)
    assert "nothing new." in second
    assert "0 events" in second


def test_an_empty_window_advances_the_cursor(tmp_path: Path) -> None:
    output = run(tmp_path, "--since", "2026-08-02T00:00:00", "--until", "2026-08-02T00:05:00")
    assert "0 notifications" in output
    assert load_state(tmp_path / "state.json").state.last_window_end == datetime(2026, 8, 2, 0, 5)


def test_json_output_is_the_serialised_result(tmp_path: Path) -> None:
    payload = json.loads(run(tmp_path, *WINDOW, "--json"))
    assert payload["events"][0]["new_version"] == AI_ACT_V2
    assert payload["stats"]["matched"] == 4


def test_a_corrupt_state_file_is_reported_and_the_poll_still_runs(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text("{ not json", encoding="utf-8")
    output = run(tmp_path, *WINDOW)
    assert "state recovered:" in output
    assert f"-> {AI_ACT_V2}" in output


def test_a_second_watched_act_the_window_never_mentions_costs_nothing(tmp_path: Path) -> None:
    """No fixture is pinned for the DSA, and none is needed: it is never looked up."""
    assert "(2 watched)" in run(tmp_path, *WINDOW, celexes=(AI_ACT, "32022R2065"))


def test_a_bad_watchlist_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    """It is the one hand-written input in the system, so it gets a hand-written answer."""
    missing = runner.invoke(app, ["watch", "--once", "--watchlist", str(tmp_path / "gone.toml")])
    assert missing.exit_code == 2
    assert "copy watchlist.example.toml" in missing.output
    assert missing.exception is None or isinstance(missing.exception, SystemExit)

    bad = tmp_path / "watchlist.toml"
    bad.write_text('[[acts]]\ncelex = "nonsense"\n', encoding="utf-8")
    invalid = runner.invoke(app, ["watch", "--once", "--watchlist", str(bad)])
    assert invalid.exit_code == 2
    assert "not a CELEX" in invalid.output


def test_the_window_start_prefers_the_flag_then_the_cursor_then_a_fortnight() -> None:
    """`--since` wins; otherwise resume with an hour of deliberate overlap."""
    end = datetime(2026, 8, 6, 0, 0)
    explicit = datetime(2026, 1, 1, 0, 0)
    assert window_start(explicit, datetime(2026, 8, 5), end) == explicit
    assert window_start(None, datetime(2026, 8, 5), end) == datetime(2026, 8, 5) - OVERLAP
    assert window_start(None, None, end) == end - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    # A cursor ahead of the window end never produces a backwards window.
    assert window_start(None, datetime(2026, 9, 1), end) == end


def test_the_observation_date_is_stamped_on_the_states_it_writes(tmp_path: Path) -> None:
    """Not asserted against a fixed date: the point is that it is *a* date, passed in."""
    payload = json.loads(run(tmp_path, *WINDOW, "--json"))
    stamped = date.fromisoformat(payload["events"][0]["observed_on"])
    assert stamped.year >= 2026
