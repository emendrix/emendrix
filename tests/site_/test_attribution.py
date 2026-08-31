"""The no-amending-act class: derived from the committed document, all four checks real."""

from __future__ import annotations

from datetime import date

from site_entries import IN_FORCE, attributed_entry, unattributed_entry

from emendrix.site_.attribution import unattributed


def test_both_signals_unavailable_is_the_class() -> None:
    assert unattributed(unattributed_entry())


def test_a_zero_change_entry_with_both_signals_unavailable_is_still_the_class() -> None:
    """Two of the committed class members carry no changes at all; the predicate must not
    read an empty change list as evidence either way."""
    entry = unattributed_entry()
    empty = entry.model_copy(update={"changes": ()})
    assert unattributed(empty)


def test_a_diff_only_entry_never_qualifies() -> None:
    """No corroboration ran, so there is no window to have named an act, and nothing to say."""
    entry = unattributed_entry().model_copy(update={"corroboration": None})
    assert not unattributed(entry)


def test_an_available_metadata_signal_disqualifies() -> None:
    assert not unattributed(attributed_entry())


def test_a_named_amending_act_disqualifies_even_against_the_signals() -> None:
    """The check is asserted against the document, not derived from the availability flags:
    a change naming an act under unavailable signals is a state the pipeline cannot write,
    and the predicate refuses to classify it rather than trusting the flags over the bytes."""
    entry = unattributed_entry()
    attributed = attributed_entry()
    contradictory = entry.model_copy(update={"changes": attributed.changes})
    assert not unattributed(contradictory)


def test_an_in_force_date_disqualifies_even_against_the_signals() -> None:
    entry = unattributed_entry().model_copy(update={"in_force": (date(2026, 6, 1),)})
    assert not unattributed(entry)


def test_the_attributed_fixture_carries_what_its_name_claims() -> None:
    """The disqualifying fixture disqualifies for the stated reason, not by accident."""
    entry = attributed_entry()
    assert entry.in_force == (IN_FORCE,)
    assert all(emitted.change.amending_acts for emitted in entry.changes)
