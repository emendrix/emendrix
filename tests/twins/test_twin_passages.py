"""The caps on what a twin pair may show: context, the cut, the count and the withheld share."""

from __future__ import annotations

from twin_trees import text, words

from emendrix.twins.passages import (
    CONTEXT_WORDS,
    CUT,
    MAX_PASSAGES,
    PASSAGE_CHARS,
    WITHHELD_SHARE,
    excerpt,
)


def test_the_caps_are_the_published_ones() -> None:
    assert (CONTEXT_WORDS, PASSAGE_CHARS, MAX_PASSAGES, WITHHELD_SHARE, CUT) == (
        6,
        400,
        12,
        0.30,
        "[…]",
    )


def test_identical_texts_show_nothing_and_withhold_nothing() -> None:
    shown = excerpt(text(50), text(50))
    assert (shown.passages, shown.omitted, shown.withheld) == ((), 0, False)


def test_a_passage_carries_six_words_of_context_either_side() -> None:
    a, b = text(100), text(100, change={50: "x"})
    [passage] = excerpt(a, b).passages
    assert passage.a == " ".join(words(13, 44))
    assert passage.b == " ".join([*words(6, 44), "x", *words(6, 51)])
    assert passage.cut is False


def test_context_stops_at_the_edges_and_an_insertion_shows_context_alone_on_one_side() -> None:
    a = text(100)
    b = " ".join(["x", *words(100)])
    [passage] = excerpt(a, b).passages
    assert passage.a == " ".join(words(6))
    assert passage.b == " ".join(["x", *words(6)])


def test_each_side_is_cut_at_the_character_cap_with_a_visible_mark() -> None:
    a = text(1000)
    b = " ".join([*words(400), *words(100, stem="y"), *words(500, 500)])
    [passage] = excerpt(a, b).passages
    assert passage.cut is True
    assert len(passage.a) == PASSAGE_CHARS + len(CUT) and passage.a.endswith(CUT)
    assert len(passage.b) == PASSAGE_CHARS + len(CUT) and passage.b.endswith(CUT)
    short = excerpt(text(1000), text(1000, change={500: "x"})).passages[0]
    assert short.cut is False and CUT not in short.a


def test_at_most_twelve_passages_are_shown_and_the_rest_are_counted() -> None:
    changed = {offset: f"x{offset}" for offset in range(25, 1000, 50)}
    shown = excerpt(text(1000), text(1000, change=changed))
    assert len(changed) == 20
    assert (len(shown.passages), shown.omitted, shown.withheld) == (MAX_PASSAGES, 8, False)


def test_passages_over_the_share_of_either_text_are_withheld_whole() -> None:
    a, b = text(100), text(100, change={10: "x", 30: "y", 50: "z"})
    # Three passages of 13 words, 39 of 100: over 30% of either side.
    shown = excerpt(a, b)
    assert (shown.passages, shown.omitted, shown.withheld) == ((), 0, True)
    kept = excerpt(text(100), text(100, change={10: "x", 50: "z"}))
    assert kept.withheld is False and len(kept.passages) == 2
