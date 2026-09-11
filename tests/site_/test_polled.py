"""The poller's record as the site reads it: a document, never an import.

`site_/polled.py` declares its own partial shape of the state file rather than importing the
poller's model, because the site is a rendering of documents and may not depend on the package
that writes them. The first test below is the other half of that rule: it builds a real
`WatchState`, serialises it the way `save_state` does, and holds the site's reader to it, so
the two shapes cannot drift apart unnoticed. Importing the poller here is allowed and is the
point; importing it in `site_/` is not.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from emendrix.site_.polled import PolledState, read_polled
from emendrix.watch.state import PendingConsolidation, WatchState

WINDOW_END = datetime(2026, 9, 11, 0, 0, 0)


def _pending(act: str, first_seen: date) -> PendingConsolidation:
    return PendingConsolidation(
        act_key=f"eu:{act}",
        celex=act,
        version=f"0{act}-20260719",
        first_seen=first_seen,
        last_checked=WINDOW_END.date(),
        checks=2,
    )


def _write(path: Path, state: WatchState) -> Path:
    path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def test_the_reader_answers_over_a_state_file_the_poller_itself_wrote(tmp_path: Path) -> None:
    """The contract, against the real model rather than against a hand-written fixture."""
    state = WatchState(
        last_window_end=WINDOW_END,
        pending=(
            _pending("32017R0745", date(2026, 9, 3)),
            _pending("32006R1907", date(2026, 9, 7)),
        ),
    )
    polled = read_polled(_write(tmp_path / "watch-state.json", state))
    assert polled == PolledState(
        checked_through=date(2026, 9, 11), waiting=2, waiting_since=date(2026, 9, 3)
    )


def test_an_empty_pending_list_reads_zero_and_no_date(tmp_path: Path) -> None:
    """A corpus with nothing waiting is the normal state, and it still has a cursor to report."""
    polled = read_polled(_write(tmp_path / "s.json", WatchState(last_window_end=WINDOW_END)))
    assert polled == PolledState(checked_through=date(2026, 9, 11), waiting=0, waiting_since=None)


def test_no_path_at_all_is_no_record(tmp_path: Path) -> None:
    """The flag is optional, so its absence is the normal build and never an error."""
    assert read_polled(None) is None


def test_a_path_that_does_not_exist_is_no_record(tmp_path: Path) -> None:
    """A deployment that mounts the state volume late still builds a site."""
    assert read_polled(tmp_path / "nothing-here.json") is None


def test_a_file_that_is_not_json_is_no_record(tmp_path: Path) -> None:
    """Better a page that says nothing than a build that fails over a courtesy."""
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    assert read_polled(path) is None


def test_a_file_of_another_schema_is_no_record(tmp_path: Path) -> None:
    """The fields are named in schema 1. Guessing at a later layout is how a page starts
    printing a number that means something else."""
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"schema_version": 2, "last_window_end": "2026-09-11T00:00:00"}))
    assert read_polled(path) is None


def test_a_poller_that_has_never_closed_a_window_reports_no_date(tmp_path: Path) -> None:
    """A state file exists from the first run, and until a window closes it has no cursor."""
    polled = read_polled(_write(tmp_path / "s.json", WatchState()))
    assert polled is not None
    assert polled.checked_through is None


def test_a_row_with_an_unreadable_first_seen_is_counted_and_not_dated(tmp_path: Path) -> None:
    """Counting a waiting consolidation and dating it are two answers, and one can fail alone."""
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "last_window_end": "2026-09-11T00:00:00",
                "pending": [{"act_key": "eu:32017R0745", "first_seen": "soon"}],
            }
        )
    )
    polled = read_polled(path)
    assert polled == PolledState(checked_through=date(2026, 9, 11), waiting=1, waiting_since=None)
