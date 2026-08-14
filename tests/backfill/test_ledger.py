"""The resume record: what a second run of the same backfill is entitled to skip."""

from __future__ import annotations

from pathlib import Path

import pytest

from emendrix.backfill.ledger import (
    LEDGER_SCHEMA,
    Attempt,
    AttemptStatus,
    Ledger,
    LedgerBusy,
    ledger_lock,
    load_ledger,
    save_ledger,
)


def attempt(key: str, status: AttemptStatus = "emitted") -> Attempt:
    act, from_version, to_version = key.split("|")
    return Attempt(
        key=key,
        act=act,
        from_version=from_version,
        to_version=to_version,
        status=status,
    )


def test_an_absent_ledger_is_an_empty_one_rather_than_an_error(tmp_path: Path) -> None:
    loaded = load_ledger(tmp_path / "nothing.json")
    assert loaded.ledger.attempts == ()
    assert not loaded.existed
    assert "nothing.json" in loaded.detail


def test_a_ledger_round_trips_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    save_ledger(path, Ledger().record(attempt("eu:32017R0745|a|b")))
    loaded = load_ledger(path)
    assert loaded.existed
    assert [item.key for item in loaded.ledger.attempts] == ["eu:32017R0745|a|b"]
    assert loaded.ledger.schema_version == LEDGER_SCHEMA


def test_a_settled_transition_is_skipped_and_a_failed_one_is_retried() -> None:
    """Resume means resume: a failure is usually a network hiccup and is worth another go."""
    ledger = (
        Ledger()
        .record(attempt("act|a|b", "emitted"))
        .record(attempt("act|b|c", "skipped"))
        .record(attempt("act|c|d", "failed"))
    )
    assert ledger.done == frozenset({"act|a|b", "act|b|c"})


def test_recording_the_same_transition_twice_replaces_rather_than_appends() -> None:
    ledger = Ledger().record(attempt("act|a|b", "failed")).record(attempt("act|a|b", "emitted"))
    assert len(ledger.attempts) == 1
    assert ledger.attempts[0].status == "emitted"
    assert ledger.done == frozenset({"act|a|b"})


def test_re_recording_a_transition_counts_the_tries_it_has_cost() -> None:
    """A retry that never succeeds is money spent every run, so the count is kept, not implied."""
    ledger = Ledger().record(attempt("act|a|b", "failed"))
    assert ledger.attempts[0].tries == 1
    ledger = ledger.record(attempt("act|a|b", "failed")).record(attempt("act|a|b", "failed"))
    assert ledger.attempts[0].tries == 3


def test_a_transition_that_keeps_failing_is_given_up_on_at_the_limit() -> None:
    """Retrying forever is how a permanently broken act quietly bills an installation."""
    ledger = Ledger()
    for _ in range(3):
        ledger = ledger.record(attempt("act|a|b", "failed"))
    assert ledger.exhausted(3) == frozenset({"act|a|b"})
    assert ledger.exhausted(4) == frozenset()
    assert ledger.done == frozenset(), "exhausted is not done; it is given up on"


def test_a_limit_of_zero_never_gives_up() -> None:
    ledger = Ledger()
    for _ in range(9):
        ledger = ledger.record(attempt("act|a|b", "failed"))
    assert ledger.exhausted(0) == frozenset()


def test_a_transition_that_succeeds_after_failing_is_done_not_exhausted() -> None:
    ledger = Ledger()
    for _ in range(3):
        ledger = ledger.record(attempt("act|a|b", "failed"))
    ledger = ledger.record(attempt("act|a|b", "emitted"))
    assert ledger.done == frozenset({"act|a|b"})
    assert ledger.exhausted(3) == frozenset()
    assert ledger.attempts[0].tries == 4, "the count is history, not a failure count"


def test_a_second_run_against_one_ledger_is_refused_rather_than_racing(tmp_path: Path) -> None:
    """Two runs sharing a ledger do not corrupt it, they drop each other's finished work."""
    path = tmp_path / "ledger.json"
    with ledger_lock(path) as held:
        assert held.is_file()
        with pytest.raises(LedgerBusy) as caught, ledger_lock(path):
            pytest.fail("the second claim should not have been granted")
        assert str(held) in str(caught.value)
    assert not held.exists(), "leaving the lock behind would block every later run"


def test_the_lock_is_released_when_the_run_is_interrupted(tmp_path: Path) -> None:
    """Ctrl-C is the ordinary way a long backfill ends. It must not poison the next one."""
    path = tmp_path / "ledger.json"
    with pytest.raises(KeyboardInterrupt), ledger_lock(path):
        raise KeyboardInterrupt
    assert not (tmp_path / "ledger.json.lock").exists()


def test_a_lock_left_by_a_killed_process_is_named_so_it_can_be_cleared(tmp_path: Path) -> None:
    """Deciding a lock is stale needs a clock this project reads in one place. Say it instead."""
    path = tmp_path / "ledger.json"
    (tmp_path / "ledger.json.lock").write_text("4242\n", encoding="utf-8")
    with pytest.raises(LedgerBusy) as caught, ledger_lock(path):
        pytest.fail("a leftover lock is still a lock")
    assert "ledger.json.lock" in str(caught.value)
    assert "delete" in str(caught.value).lower()


def test_attempts_are_written_in_a_stable_order(tmp_path: Path) -> None:
    """A ledger a person may commit should diff cleanly, so ordering is not insertion order."""
    path = tmp_path / "ledger.json"
    save_ledger(path, Ledger().record(attempt("act|c|d")).record(attempt("act|a|b")))
    first = path.read_text(encoding="utf-8")
    save_ledger(path, Ledger().record(attempt("act|a|b")).record(attempt("act|c|d")))
    assert path.read_text(encoding="utf-8") == first


def test_an_unreadable_ledger_is_moved_aside_and_the_run_starts_over(tmp_path: Path) -> None:
    """Losing the record costs money. Losing it silently costs trust, so it is said out loud."""
    path = tmp_path / "ledger.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = load_ledger(path)
    assert loaded.ledger.attempts == ()
    assert loaded.recovered
    assert (tmp_path / "ledger.json.corrupt").is_file()
    assert "moved to" in loaded.detail


def test_a_read_only_load_reports_a_corrupt_ledger_but_leaves_it_in_place(tmp_path: Path) -> None:
    """A dry run consults the record and must not so much as rename it."""
    path = tmp_path / "ledger.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = load_ledger(path, set_aside=False)
    assert loaded.ledger.attempts == ()
    assert loaded.recovered
    assert path.is_file(), "the unreadable file was not touched"
    assert not (tmp_path / "ledger.json.corrupt").exists()


def test_a_ledger_from_another_schema_is_not_obeyed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text('{"schema_version": 99, "attempts": []}', encoding="utf-8")
    loaded = load_ledger(path)
    assert loaded.recovered
    assert "99" in loaded.detail


def test_saving_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    save_ledger(path, Ledger().record(attempt("act|a|b")))
    assert [item.name for item in tmp_path.iterdir()] == ["ledger.json"]
