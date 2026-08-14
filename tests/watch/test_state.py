"""The state store: atomic, bounded, and unwilling to die on a bad file.

This is the module the "assume the process died mid-run" requirement lands on, so the tests
are about the ugly cases rather than the happy one.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from emendrix.watch.state import (
    EMITTED_RETENTION_DAYS,
    SEEN_RETENTION_DAYS,
    STATE_SCHEMA,
    EmittedEvent,
    PendingConsolidation,
    SeenEntry,
    WatchState,
    default_state_path,
    load_state,
    prune,
    save_state,
)

TODAY = date(2026, 8, 6)


def a_state() -> WatchState:
    return WatchState(
        last_window_end=datetime(2026, 8, 6, 0, 0),
        seen=(SeenEntry(entry_id="cellar:a@t1", on=TODAY),),
        emitted=(EmittedEvent(key="eu:32024R1689@02024R1689-20260727", on=TODAY),),
        pending=(
            PendingConsolidation(
                act_key="eu:32017R0745",
                celex="32017R0745",
                version="02017R0745-20260801",
                first_seen=date(2026, 8, 1),
                last_checked=TODAY,
            ),
        ),
    )


def test_a_saved_state_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "watch-state.json"
    save_state(path, a_state())
    loaded = load_state(path)
    assert (loaded.existed, loaded.recovered) == (True, False)
    assert loaded.state == a_state()


def test_the_state_directory_is_created_on_first_write(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "watch-state.json"
    save_state(path, WatchState())
    assert path.is_file()


def test_a_crash_between_write_and_rename_leaves_the_old_state_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of write-tmp-and-rename: a reader never sees a half-written file."""
    path = tmp_path / "watch-state.json"
    save_state(path, a_state())
    before = path.read_bytes()

    def die(source: object, target: object) -> None:
        raise OSError("killed mid-write")

    monkeypatch.setattr(os, "replace", die)
    with pytest.raises(OSError, match="killed mid-write"):
        save_state(path, WatchState())

    assert path.read_bytes() == before
    assert load_state(path).state == a_state()
    assert list(tmp_path.glob("*.tmp")) == []


def test_a_missing_state_file_is_an_empty_state_not_a_crash(tmp_path: Path) -> None:
    loaded = load_state(tmp_path / "absent.json")
    assert (loaded.state, loaded.existed, loaded.recovered) == (WatchState(), False, False)


def test_a_corrupt_state_file_is_set_aside_and_the_poll_starts_over(tmp_path: Path) -> None:
    """Truncated JSON, half a write from an older build: start from `--since`, never die."""
    path = tmp_path / "watch-state.json"
    path.write_text('{"seen": [{"entry_id": "a", ', encoding="utf-8")
    loaded = load_state(path)
    assert loaded.recovered is True
    assert loaded.state == WatchState()
    assert (tmp_path / "watch-state.json.corrupt").is_file()
    assert not path.exists()


def test_a_state_from_another_schema_is_not_guessed_at(tmp_path: Path) -> None:
    path = tmp_path / "watch-state.json"
    save_state(path, a_state().model_copy(update={"schema_version": STATE_SCHEMA + 1}))
    loaded = load_state(path)
    assert loaded.recovered is True
    assert "schema" in loaded.detail
    assert loaded.state.seen == ()


def test_the_rolling_windows_are_bounded_and_asymmetric() -> None:
    """Entry identities age out in 60 days; what they resolved to is kept far longer."""
    old_seen = TODAY - timedelta(days=SEEN_RETENTION_DAYS + 1)
    old_emitted = TODAY - timedelta(days=EMITTED_RETENTION_DAYS + 1)
    state = WatchState(
        seen=(
            SeenEntry(entry_id="stale", on=old_seen),
            SeenEntry(entry_id="fresh", on=TODAY),
            SeenEntry(entry_id="edge", on=TODAY - timedelta(days=SEEN_RETENTION_DAYS)),
        ),
        emitted=(
            EmittedEvent(key="ancient", on=old_emitted),
            EmittedEvent(key="kept", on=old_seen),
        ),
    )
    pruned = prune(state, on=TODAY)
    assert [entry.entry_id for entry in pruned.seen] == ["fresh", "edge"]
    assert [entry.key for entry in pruned.emitted] == ["kept"]


def test_pruning_takes_the_horizon_as_a_value() -> None:
    """No clock read anywhere below the CLI: the window end is what "now" means here."""
    state = WatchState(seen=(SeenEntry(entry_id="a", on=TODAY),))
    assert prune(state, on=TODAY + timedelta(days=SEEN_RETENTION_DAYS + 1)).seen == ()


def test_the_default_path_is_user_data_not_the_cache() -> None:
    """Losing this file loses work; losing the cache loses bytes. They are different places."""
    path = default_state_path()
    assert path.name == "watch-state.json"
    assert "emendrix" in str(path)
