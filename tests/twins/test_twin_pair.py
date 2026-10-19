"""Pairing by the word ratio: mutual best, the floor, ties, kinds, and children level by level."""

from __future__ import annotations

from twin_trees import node, text, words

from emendrix.twins.pair import (
    TWIN_FLOOR,
    TWIN_FLOOR_VERIFIED_ON,
    align_children,
    pair_nodes,
    word_ratio,
)


def test_the_floor_is_the_measured_one_with_its_date() -> None:
    assert (TWIN_FLOOR, TWIN_FLOOR_VERIFIED_ON) == (0.90, "2026-10-19")


def test_word_ratio_is_none_only_when_a_bound_falls_below_the_floor() -> None:
    same = words(20)
    assert word_ratio(same, same, floor=0.9) == 1.0
    one_off = text(20, change={5: "x"}).split()
    assert word_ratio(same, one_off, floor=0.9) == 0.95
    assert word_ratio(same, words(20, 100), floor=0.9) is None
    assert word_ratio(same, words(20, 100), floor=0.0) == 0.0


def test_units_pair_by_text_and_never_by_number() -> None:
    left = [node("AR 1", text(20)), node("AR 2", text(20, 100))]
    right = [node("AR 1", text(20, 100, change={3: "x"})), node("AR 2", text(20))]
    pairing = pair_nodes(left, right, floor=TWIN_FLOOR)
    assert [(pair.a.location.canonical, pair.b.location.canonical) for pair in pairing.pairs] == [
        ("AR 1", "AR 2"),
        ("AR 2", "AR 1"),
    ]
    assert [round(pair.ratio, 3) for pair in pairing.pairs] == [1.0, 0.95]
    assert pairing.unpaired_a == () and pairing.unpaired_b == ()


def test_a_pair_below_the_floor_is_no_pair_and_carries_no_best() -> None:
    # Three of twenty words differ: 2 * 17 / 40 = 0.85.
    left = [node("AR 1", text(20))]
    right = [node("AR 1", text(20, change={1: "x", 7: "y", 13: "z"}))]
    pairing = pair_nodes(left, right, floor=TWIN_FLOOR)
    assert pairing.pairs == ()
    assert [(row[0].location.canonical, row[1], row[2]) for row in pairing.unpaired_a] == [
        ("AR 1", None, None)
    ]
    assert pair_nodes(left, right, floor=0.85).pairs != ()


def test_a_tie_goes_to_the_lower_canonical_location_and_the_loser_keeps_its_best() -> None:
    left = [node("AR 1", text(20))]
    right = [node("AR 5", text(20)), node("AR 10", text(20))]
    pairing = pair_nodes(left, right, floor=TWIN_FLOOR)
    assert [(pair.a.location.canonical, pair.b.location.canonical) for pair in pairing.pairs] == [
        ("AR 1", "AR 10")
    ]
    [(unit, best, ratio)] = pairing.unpaired_b
    assert unit.location.canonical == "AR 5"
    assert best is not None and best.location.canonical == "AR 1"
    assert ratio == 1.0


def test_a_unit_whose_best_prefers_another_is_unpaired_with_that_best() -> None:
    left = [node("AR 1", text(20)), node("AR 2", text(20, change={4: "x"}))]
    right = [node("AR 1", text(20))]
    pairing = pair_nodes(left, right, floor=TWIN_FLOOR)
    assert [(pair.a.location.canonical, pair.b.location.canonical) for pair in pairing.pairs] == [
        ("AR 1", "AR 1")
    ]
    [(unit, best, ratio)] = pairing.unpaired_a
    assert (unit.location.canonical, best.location.canonical if best else None) == ("AR 2", "AR 1")
    assert ratio == 0.95


def test_an_article_is_never_paired_with_an_annex() -> None:
    pairing = pair_nodes([node("AR 1", text(20))], [node("AN I", text(20))], floor=TWIN_FLOOR)
    assert pairing.pairs == ()
    assert [row[1] for row in (*pairing.unpaired_a, *pairing.unpaired_b)] == [None, None]


def test_children_align_level_by_level_below_aligned_parents_only() -> None:
    a = node(
        "AR 1",
        "",
        node("AR 1 PA 1", text(20), node("AR 1 PA 1 PTA a", text(20, 200))),
        node("AR 1 PA 2", text(20, 100), node("AR 1 PA 2 PTA a", text(20, 300))),
    )
    b = node(
        "AR 1",
        "",
        # Its first paragraph is A's second, and its second A's first: alignment is by text.
        node("AR 1 PA 1", text(20, 100), node("AR 1 PA 1 PTA a", text(20, 300))),
        # A's PA 1 PTA a appears here under a paragraph that aligns with nothing.
        node("AR 1 PA 2", text(20, 500), node("AR 1 PA 2 PTA a", text(20, 200))),
        node("AR 1 PA 3", text(20), node("AR 1 PA 3 PTA a", text(20, 200))),
    )
    aligned = align_children(a, b, floor=TWIN_FLOOR)
    assert [(one.a.location.canonical, one.b.location.canonical) for one in aligned] == [
        ("AR 1 PA 1", "AR 1 PA 3"),
        ("AR 1 PA 1 PTA a", "AR 1 PA 3 PTA a"),
        ("AR 1 PA 2", "AR 1 PA 1"),
        ("AR 1 PA 2 PTA a", "AR 1 PA 1 PTA a"),
    ]
    assert align_children(node("AR 1", text(20)), b, floor=TWIN_FLOOR) == ()
