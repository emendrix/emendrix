"""`emendrix backfill`, offline.

The dry run reads each act's tree notice and nothing else, so it runs against the pinned fixture
set with no network, no API key and no cassettes. That is also the mode an operator uses first,
which makes it the one worth testing hardest.

The two parsers at the bottom pin the output format, which is what makes this a test of the
command rather than of the packages under it: a `total: {n} selected across {m} acts` line, and
one indented line per selected transition beginning with its ledger key.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from emendrix.backfill import cli as backfill_cli
from emendrix.backfill.ledger import Attempt, Ledger, load_ledger, save_ledger
from emendrix.backfill.plan import Transition
from emendrix.backfill.runner import Outcome
from emendrix.cli import app
from run_pins import RUN_CASSETTE_DIR, TRANSITION

runner = CliRunner()

FIXTURES = Path("tests/fixtures/eu")
OBSERVED = "2026-08-08"

MDR = "eu:32017R0745"
TRANSITIONS = 7
"""The MDR fixture set publishes 8 dated, ENG-readable versions, so 7 consecutive pairs.
Verified 2026-08-09 by planning over `FixtureResponseCache(tests/fixtures/eu)`."""

WATCHLIST = """
[[acts]]
celex = "32017R0745"
name  = "Medical Devices Regulation"
"""


def watchlist(tmp_path: Path, body: str = WATCHLIST) -> Path:
    path = tmp_path / "watchlist.toml"
    path.write_text(body, encoding="utf-8")
    return path


def invoke(*args: str) -> Result:
    return runner.invoke(app, ["backfill", *args])


def text_of(result: Result) -> str:
    """stdout plus stderr, whichever way this click version splits them."""
    try:
        return result.output + result.stderr
    except (ValueError, AttributeError):
        return result.output


def test_a_dry_run_lists_the_transitions_and_writes_nothing(tmp_path: Path) -> None:
    result = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 0, result.output
    assert MDR in result.output
    assert f"total: {TRANSITIONS} selected across 1 acts" in result.output
    assert _selected(result.output) == TRANSITIONS
    assert not (tmp_path / "ledger.json").exists(), "a dry run records nothing"


def test_a_json_summary_is_one_line_of_stderr_a_collector_can_parse(tmp_path: Path) -> None:
    """The counts a tranche is judged by, in the shape the poll already emits."""
    result = invoke(
        "--dry-run",
        "--summary",
        "json",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 0, result.output
    line = [ln for ln in text_of(result).splitlines() if ln.startswith("{")][-1]
    payload = json.loads(line)
    assert payload["transitions_selected"] == TRANSITIONS
    assert payload["emitted"] == 0
    assert payload["failed"] == 0


def test_a_real_runs_json_summary_carries_what_it_emitted_and_what_it_spent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What a tranche spent must be readable from its one log line, not from nowhere.

    The run cassettes pin the MDR postponement pair, which sits second in the fixture's
    history behind the original-act transition, so `--since` cuts that first one off and
    `--limit 1` replays a real emission offline: the pinning `tests/graph/test_run_summary.py`
    uses. A replayed call reports `requests: 0`, the true count of provider requests made.
    """
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTE_DIR", str(RUN_CASSETTE_DIR))
    monkeypatch.setenv("EMENDRIX_EXPLAIN_CASSETTES", "replay")
    for var in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    result = invoke(
        "--limit",
        "1",
        "--since",
        "2020-01-01",
        "--summary",
        "json",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        TRANSITION.observed_on.isoformat(),
        "--ledger",
        str(tmp_path / "ledger.json"),
        "--output-repo",
        str(tmp_path / "out"),
    )
    assert result.exit_code == 0, text_of(result)
    line = [ln for ln in text_of(result).splitlines() if ln.startswith("{")][-1]
    payload = json.loads(line)
    assert payload["transitions_selected"] == 1
    assert payload["emitted"] == 1
    assert payload["failed"] == 0
    assert "requests" in payload["explain"], "the spend fields ride on every real summary"


def test_a_cutoff_reduces_the_selection_it_reports(tmp_path: Path) -> None:
    wide = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    narrow = invoke(
        "--dry-run",
        "--since",
        "2024-01-01",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert wide.exit_code == 0 and narrow.exit_code == 0
    assert _selected(narrow.output) < _selected(wide.output)
    assert _selected(narrow.output) > 0
    assert "before the cutoff" in narrow.output, "what a cutoff left out is counted, not dropped"


def test_a_dry_run_counts_what_the_ledger_already_settled(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    plain = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(ledger_path),
    )
    first_key = _first_key(plain.output)
    save_ledger(
        ledger_path,
        Ledger().record(
            Attempt(
                key=first_key,
                act=MDR,
                from_version="x",
                to_version="y",
                status="emitted",
            )
        ),
    )
    resumed = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(ledger_path),
    )
    assert _selected(resumed.output) == _selected(plain.output) - 1
    assert "1 already done" in resumed.output


def test_a_limit_runs_one_tranche_and_says_how_many_are_waiting(tmp_path: Path) -> None:
    """History is read in tranches, and a cap nobody printed reads as "that was all of it"."""
    result = invoke(
        "--dry-run",
        "--limit",
        "3",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 0, result.output
    assert _selected(result.output) == 3
    assert f"{TRANSITIONS - 3} more are outstanding" in result.output


def test_a_limit_bigger_than_the_selection_leaves_nothing_waiting(tmp_path: Path) -> None:
    result = invoke(
        "--dry-run",
        "--limit",
        str(TRANSITIONS + 5),
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 0, result.output
    assert _selected(result.output) == TRANSITIONS
    assert "outstanding" not in result.output


def test_a_dry_run_skips_a_transition_the_output_repository_already_holds(tmp_path: Path) -> None:
    """The idempotence that survives a container: the entry on disk is the record of the work.

    The ledger is working-directory relative and a deployment need not keep it, so a run whose
    ledger is gone must still not pay a second time for a transition already in the changelog.
    """
    repo = tmp_path / "out"
    plain = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
        "--output-repo",
        str(repo),
    )
    version = _first_key(plain.output).split("|")[2]
    payload = repo / "eu" / "32017R0745" / "changes" / f"{version}.json"
    payload.parent.mkdir(parents=True)
    payload.write_text("{}", encoding="utf-8")

    resumed = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
        "--output-repo",
        str(repo),
    )
    assert _selected(resumed.output) == _selected(plain.output) - 1
    assert "1 of them already in the output repository" in resumed.output


def test_a_real_run_without_an_output_repository_is_refused_before_any_fetch(
    tmp_path: Path,
) -> None:
    """The product of a backfill is a committed changelog. Without one there is nothing to do."""
    result = invoke(
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 2
    assert "--output-repo" in text_of(result)
    assert not (tmp_path / "ledger.json.lock").exists(), "refused before it claimed anything"


def test_a_polite_delay_the_environment_got_wrong_is_a_configuration_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backfill is the workload that turns the delay up; a typo in it must not read as a default."""
    monkeypatch.setenv("EMENDRIX_POLITE_DELAY_S", "slowly")
    result = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 2
    assert "EMENDRIX_POLITE_DELAY_S" in text_of(result)


def test_an_unknown_act_on_the_watchlist_is_a_configuration_error(tmp_path: Path) -> None:
    result = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path, '[[acts]]\ncelex = "not-a-celex"\n')),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
    )
    assert result.exit_code == 2


def test_an_act_filter_narrows_the_watchlist_and_never_extends_it(tmp_path: Path) -> None:
    """The watchlist stays the single answer to which acts this installation cares about."""
    unwatched = invoke(
        "--dry-run",
        "--act",
        "32024R1689",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert unwatched.exit_code == 0, unwatched.output
    assert _selected(unwatched.output) == 0

    garbage = invoke(
        "--dry-run",
        "--act",
        "not-a-celex",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert garbage.exit_code == 2
    assert "not a CELEX number" in text_of(garbage)


def test_a_transition_that_has_used_its_retries_is_dropped_and_said_so(tmp_path: Path) -> None:
    """Retrying a permanently broken act forever is how an installation quietly pays twice."""
    ledger_path = tmp_path / "ledger.json"
    plain = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(ledger_path),
    )
    first_key = _first_key(plain.output)
    ledger = Ledger()
    for _ in range(3):
        ledger = ledger.record(
            Attempt(
                key=first_key,
                act=MDR,
                from_version="x",
                to_version="y",
                status="failed",
                detail="the endpoint hung up",
            )
        )
    save_ledger(ledger_path, ledger)

    resumed = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(ledger_path),
    )
    assert _selected(resumed.output) == _selected(plain.output) - 1
    assert "given up" in resumed.output, "an abandoned transition is never dropped in silence"

    forced = invoke(
        "--dry-run",
        "--retry-limit",
        "0",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(ledger_path),
    )
    assert _selected(forced.output) == _selected(plain.output), "--retry-limit 0 never gives up"


def test_a_real_run_is_refused_while_another_run_holds_the_ledger(tmp_path: Path) -> None:
    """Two runs on one ledger drop each other's finished transitions and pay for them twice."""
    (tmp_path / "ledger.json.lock").write_text("4242\n", encoding="utf-8")
    result = invoke(
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
        "--output-repo",
        str(tmp_path / "out"),
    )
    assert result.exit_code == 2
    assert "ledger.json.lock" in text_of(result)
    assert (tmp_path / "ledger.json.lock").is_file(), "a refusal never clears somebody else's lock"


def test_a_dry_run_is_not_blocked_by_a_lock_it_never_needed(tmp_path: Path) -> None:
    """Checking what a running backfill has left to do is the obvious thing to want."""
    (tmp_path / "ledger.json.lock").write_text("4242\n", encoding="utf-8")
    result = invoke(
        "--dry-run",
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(tmp_path / "ledger.json"),
    )
    assert result.exit_code == 0, result.output


def test_an_interruption_reports_what_it_earned_and_leaves_the_lock_clear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A long backfill ends with Ctrl-C more often than it ends by finishing.

    The loop itself is stubbed: what is under test is the command's response to an interruption,
    not the graph, and this keeps the test offline and free.
    """
    ledger_path = tmp_path / "ledger.json"

    def one_then_stop(
        deps: object, transitions: Sequence[Transition], *, observed_on: date
    ) -> Iterator[Outcome]:
        yield Outcome(transition=transitions[0], status="skipped", detail="nothing to diff")
        raise KeyboardInterrupt

    monkeypatch.setattr(backfill_cli, "run_transitions", one_then_stop)
    result = invoke(
        "--watchlist",
        str(watchlist(tmp_path)),
        "--fixture-dir",
        str(FIXTURES),
        "--observed-on",
        OBSERVED,
        "--ledger",
        str(ledger_path),
        "--output-repo",
        str(tmp_path / "out"),
    )
    assert result.exit_code == 130, result.output
    assert "[1/" in result.output and "%]" in result.output, "progress carries a percentage"
    assert "1 skipped" in result.output, "the totals it earned, not a traceback"
    assert "interrupted" in text_of(result)
    kept = load_ledger(ledger_path).ledger
    assert [item.status for item in kept.attempts] == ["skipped"], (
        "what finished was recorded; what was in flight was not, and runs again"
    )
    assert not (tmp_path / "ledger.json.lock").exists(), "Ctrl-C must not block the next run"


def _selected(output: str) -> int:
    """The `selected` total the summary line prints."""
    for line in output.splitlines():
        if line.startswith("total:"):
            return int(line.split()[1])
    raise AssertionError(f"no total line in:\n{output}")


def _first_key(output: str) -> str:
    """The ledger key of the first transition the dry run listed."""
    for line in output.splitlines():
        if line.startswith("  eu:"):
            return line.strip().split()[0]
    raise AssertionError(f"no transition line in:\n{output}")
