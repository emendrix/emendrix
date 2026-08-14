"""The diff on a corpus that is not law: the toy flat's house rules.

`emendrix.diff` imports `emendrix.core` and nothing else, so if it needed EU knowledge these
tests could not pass. They also carry the cases the real fixtures cannot: no renumbering
occurred in any of the seven traced transitions and no whole unit was ever deleted, so
deletion ordering and renumber detection are exercised on trees crafted here, which is
legitimate precisely because the toy corpus is not legal content.

One quirk of the toy worth knowing: its nodes are built with `ProvisionNode.from_plain_text`,
whose `comparison_text` covers the node's own text and *not* its children. The real parser
builds a unit's comparison form over the whole subtree. Nothing here depends on the
difference, but a toy sub-provision changing on its own would not move its unit.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import (
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    ChangeType,
    ProvisionNode,
    ProvisionTree,
    Signal,
    VersionId,
)
from emendrix.diff import RENUMBER_MIN_LENGTH, compute_delta
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED_ON = date(2026, 8, 6)

_LONG = (
    "Whoever last leaves the kitchen shall wipe the counter, empty the sink strainer and set "
    "the dishwasher running if it is full, and shall leave a note on the fridge for the next "
    "person if any of the three could not be done."
)
_LONG_EDITED = _LONG.replace("the fridge", "the door")
_UNRELATED = (
    "Bicycles are kept in the shed and not in the hallway, and the shed key lives on the hook "
    "beside the front door where everyone can reach it without asking anybody first at all."
)


@pytest.fixture
def toy() -> ToyCorpusAdapter:
    return ToyCorpusAdapter(observed_on=OBSERVED_ON)


def tree(adapter: ToyCorpusAdapter, version: VersionId) -> ProvisionTree:
    fetched = adapter.fetch_version(HOUSE_RULES, version)
    assert isinstance(fetched, ProvisionTree)
    return fetched


def crafted(version: VersionId, *units: tuple[str, str]) -> ProvisionTree:
    """A tree of top-level units built from `(location, text)` pairs, in the order given."""
    return ProvisionTree(
        act=HOUSE_RULES,
        version=version,
        language="ENG",
        roots=tuple(ProvisionNode.from_plain_text(location, text) for location, text in units),
    )


# ------------------------------------------------------------------ the toy transition


def test_the_toy_corpus_changes_come_out_exactly_typed_and_ordered(toy: ToyCorpusAdapter) -> None:
    """New-version document order, with the deleted rule at its old anchor between them."""
    delta = compute_delta(tree(toy, V1), tree(toy, V2))
    assert [(change.change_type, change.location.canonical) for change in delta.changes] == [
        (ChangeType.MODIFIED, "AR 2"),
        (ChangeType.DELETED, "AR 3"),
        (ChangeType.INSERTED, "AR 4"),
        (ChangeType.MODIFIED, "AN I"),
    ]
    assert delta.summary.unchanged_units == 1
    assert delta.summary.touched_units == 4


def test_the_texts_on_a_change_are_verbatim_and_the_versions_are_the_right_way_round(
    toy: ToyCorpusAdapter,
) -> None:
    """`before` keeps its irregular whitespace, and a deletion is referenced where it exists."""
    changes = {c.location.canonical: c for c in compute_delta(tree(toy, V1), tree(toy, V2)).changes}
    modified = changes["AR 2"]
    assert modified.before == "The bins go out on Tuesday evening."
    assert modified.after is not None and "evening,  and the recycling" in modified.after
    assert modified.provision.version == V2
    assert changes["AR 3"].provision.version == V1
    assert changes["AR 3"].after is None
    assert changes["AR 4"].before is None


def test_only_the_structural_signal_speaks_and_nothing_is_disputed_yet(
    toy: ToyCorpusAdapter,
) -> None:
    """The other two signals are `UNAVAILABLE` until corroboration, and that is not dissent."""
    for change in compute_delta(tree(toy, V1), tree(toy, V2)).changes:
        assert change.signals.observed_by == (Signal.STRUCTURAL_DIFF,)
        assert not change.disputed
    assert compute_delta(tree(toy, V1), tree(toy, V2)).summary.disputed == 0


def test_sub_provision_coordinates_ride_along_as_detail(toy: ToyCorpusAdapter) -> None:
    """The unit is the annex; `AN I SLOT 2` is where inside it the text moved."""
    changes = {c.location.canonical: c for c in compute_delta(tree(toy, V1), tree(toy, V2)).changes}
    within = [location.canonical for location in changes["AN I"].changed_within]
    assert within == ["AN I", "AN I SLOT 2"]
    assert changes["AR 2"].changed_within == (changes["AR 2"].location,)


def test_a_change_that_moves_no_date_says_so_rather_than_saying_unknown(
    toy: ToyCorpusAdapter,
) -> None:
    changes = {c.location.canonical: c for c in compute_delta(tree(toy, V1), tree(toy, V2)).changes}
    assert changes["AR 2"].applies_from == ApplicabilityUnchanged()
    assert isinstance(changes["AR 4"].applies_from, ApplicabilityUnknown)


def test_the_clock_that_the_diff_cannot_see_is_passed_in(toy: ToyCorpusAdapter) -> None:
    """`in_force` comes from the corpus's amendment metadata, never from a clock."""
    stamped = compute_delta(tree(toy, V1), tree(toy, V2), in_force=date(2026, 6, 1))
    assert {change.in_force for change in stamped.changes} == {date(2026, 6, 1)}
    assert {change.in_force for change in compute_delta(tree(toy, V1), tree(toy, V2)).changes} == {
        None
    }


# ------------------------------------------------------------------------ renumbering


def test_a_provision_that_only_moved_is_one_renumbering_not_a_delete_and_an_insert() -> None:
    before = crafted(V1, ("AR 1", "Short."), ("AR 5", _LONG))
    after = crafted(V2, ("AR 1", "Short."), ("AR 6", _LONG))
    (change,) = compute_delta(before, after).changes
    assert change.change_type is ChangeType.RENUMBERED
    assert change.location.canonical == "AR 6"
    assert change.previous_location is not None
    assert change.previous_location.canonical == "AR 5"
    # Empty `changed_within` is how a renumbering records that the text itself is unchanged.
    assert change.changed_within == ()


def test_a_provision_that_moved_and_was_edited_slightly_is_still_one_renumbering() -> None:
    before = crafted(
        V1,
        ("AR 5", _LONG),
    )
    after = crafted(
        V2,
        ("AR 6", _LONG_EDITED),
    )
    (change,) = compute_delta(before, after).changes
    assert change.change_type is ChangeType.RENUMBERED
    assert change.changed_within != ()


def test_a_provision_that_moved_and_was_rewritten_stays_a_deletion_and_an_insertion() -> None:
    """Past the v0.1 cap: corroboration gets to flag the pair, not this module."""
    before = crafted(V1, ("AR 5", _LONG))
    after = crafted(V2, ("AR 6", _UNRELATED))
    assert [c.change_type for c in compute_delta(before, after).changes] == [
        ChangeType.DELETED,
        ChangeType.INSERTED,
    ]


def test_short_provisions_are_matched_by_exact_text_only() -> None:
    """Boilerplate is 0.97-similar to its neighbours, so similarity is not evidence there."""
    short = "The bins go out on Tuesday evening."
    assert len(short) < RENUMBER_MIN_LENGTH
    moved = compute_delta(crafted(V1, ("AR 2", short)), crafted(V2, ("AR 3", short)))
    assert [c.change_type for c in moved.changes] == [ChangeType.RENUMBERED]
    edited = compute_delta(
        crafted(V1, ("AR 2", short)), crafted(V2, ("AR 3", short.replace("Tuesday", "Thursday")))
    )
    assert [c.change_type for c in edited.changes] == [ChangeType.DELETED, ChangeType.INSERTED]


# --------------------------------------------------------------------------- ordering


def test_a_deletion_with_no_surviving_predecessor_is_emitted_first() -> None:
    before = crafted(V1, ("AR 1", "Gone."), ("AR 2", "Kept."))
    after = crafted(V2, ("AR 2", "Kept."), ("AR 3", "New."))
    assert [
        (c.change_type, c.location.canonical) for c in compute_delta(before, after).changes
    ] == [
        (ChangeType.DELETED, "AR 1"),
        (ChangeType.INSERTED, "AR 3"),
    ]


def test_deletions_sharing_an_anchor_keep_the_old_versions_order() -> None:
    before = crafted(V1, ("AR 1", "Kept."), ("AR 2", "Gone."), ("AR 3", "Also gone."))
    after = crafted(V2, ("AR 1", "Kept."))
    assert [c.location.canonical for c in compute_delta(before, after).changes] == ["AR 2", "AR 3"]


# ----------------------------------------------------------------------- determinism


def test_two_runs_produce_identical_bytes(toy: ToyCorpusAdapter) -> None:
    """Changelogs are diffed in git; a delta that reorders itself between runs is a defect."""
    first = compute_delta(tree(toy, V1), tree(toy, V2))
    second = compute_delta(tree(toy, V1), tree(toy, V2))
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_diffing_two_different_acts_is_a_programming_error_not_a_state() -> None:
    other = ProvisionTree(act=HOUSE_RULES.model_copy(update={"key": "other"}), version=V1)
    with pytest.raises(ValueError, match="different acts"):
        compute_delta(other, crafted(V2, ("AR 1", "Anything.")))
