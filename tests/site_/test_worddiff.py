"""The deterministic word diff behind the unified track-changes view.

Verbatim means verbatim applies to *storage*; this module is a comparison-time rendering,
so collapsing whitespace between tokens here is the same licence `core`'s comparison
functions already use. The floor exists because a rewrite with almost nothing in common
renders as a wall of struck-through text, which is worse than showing the two texts whole.
"""

from __future__ import annotations

from emendrix.site_.worddiff import (
    LINE_TOKEN_CEILING,
    SIMILARITY_FLOOR,
    DiffSpan,
    compare,
    similarity,
    word_diff,
)


def test_a_small_edit_yields_equal_deleted_inserted_spans() -> None:
    spans = word_diff("pay within one month of receipt", "pay within two weeks of receipt")
    assert spans == (
        DiffSpan(kind="equal", text="pay within", sep=" "),
        DiffSpan(kind="deleted", text="one month", sep=" "),
        DiffSpan(kind="inserted", text="two weeks", sep=" "),
        DiffSpan(kind="equal", text="of receipt", sep=""),
    )


def test_identical_texts_are_one_equal_span() -> None:
    assert word_diff("same text", "same text") == (
        DiffSpan(kind="equal", text="same text", sep=""),
    )


def test_whitespace_between_tokens_does_not_count_as_a_change() -> None:
    """The matcher sees words. How much whitespace stood between them is not a change.

    The rendering keeps the line break the source had, which is a separate question and the
    subject of the tests below: what changed and how it reads are decided independently.
    """
    spans = word_diff("a  b\nc", "a b c")
    assert [span.kind for span in spans] == ["equal"]
    assert spans[0].text == "a b\nc"


def test_a_line_break_is_kept_where_the_source_had_one() -> None:
    """Stored text breaks at every block boundary, and the view must not flatten it."""
    before = "Article 59\nDerogation\n1. By way of derogation from Article 52"
    after = "Article 59\nDerogation\n1. By way of derogation from Article 53"
    rendered = "".join(span.text + span.sep for span in word_diff(before, after))
    assert rendered.startswith("Article 59\nDerogation\n1. By way")
    assert rendered.count("\n") == 2


def test_the_separator_after_a_span_is_the_one_the_source_had() -> None:
    """The boundary between two spans is a boundary between two texts, so it is carried."""
    spans = word_diff("title\nold body", "title\nnew body")
    assert spans[0] == DiffSpan(kind="equal", text="title", sep="\n")
    assert [span.kind for span in spans] == ["equal", "deleted", "inserted", "equal"]


def test_a_removal_and_its_replacement_are_separated_by_a_space() -> None:
    """They are alternatives shown side by side, not consecutive text, whatever followed."""
    spans = word_diff("in Article 30\nthe information", "in Article 27\nthe information")
    deleted = next(span for span in spans if span.kind == "deleted")
    inserted = next(span for span in spans if span.kind == "inserted")
    assert deleted.sep == " "
    assert inserted.sep == "\n"


def test_a_line_break_never_becomes_a_reported_change() -> None:
    """Reflowing a text must move no span: the matcher is built from words alone."""
    flat = "one two three four five"
    broken = "one two\nthree\nfour five"
    assert [span.kind for span in word_diff(flat, broken)] == ["equal"]
    assert similarity(flat, broken) == 1.0


def test_deletion_only_and_insertion_only_edits() -> None:
    assert word_diff("a b c", "a c") == (
        DiffSpan(kind="equal", text="a", sep=" "),
        DiffSpan(kind="deleted", text="b", sep=" "),
        DiffSpan(kind="equal", text="c", sep=""),
    )
    assert word_diff("a c", "a b c") == (
        DiffSpan(kind="equal", text="a", sep=" "),
        DiffSpan(kind="inserted", text="b", sep=" "),
        DiffSpan(kind="equal", text="c", sep=""),
    )


def test_similarity_is_one_for_identical_and_zero_for_disjoint_texts() -> None:
    assert similarity("a b c", "a b c") == 1.0
    assert similarity("a b c", "x y z") == 0.0


def test_the_floor_separates_a_small_edit_from_a_rewrite() -> None:
    small = similarity("pay within one month of receipt", "pay within two weeks of receipt")
    rewrite = similarity(
        "the controller shall keep records of processing activities",
        "member states may adopt stricter national measures by decree",
    )
    assert small > SIMILARITY_FLOOR > rewrite


def test_two_calls_produce_identical_output() -> None:
    a = "the quick brown fox jumps over the lazy dog " * 40
    b = "the slow brown fox leaps over the lazy cat " * 40
    assert word_diff(a, b) == word_diff(a, b)


# ------------------------------------------------------------------ line granularity


def _big(lines: int, width: int = 12) -> str:
    """A text with more tokens than `LINE_TOKEN_CEILING`, laid out one row per line."""
    return "\n".join(" ".join(f"r{row}c{col}" for col in range(width)) for row in range(lines))


def test_a_text_within_the_ceiling_is_compared_word_by_word() -> None:
    assert compare("pay within one month", "pay within two weeks").granularity == "word"


def test_a_text_over_the_ceiling_is_compared_line_by_line() -> None:
    before = _big(3000)
    assert len(before.split()) > LINE_TOKEN_CEILING
    assert compare(before, before).granularity == "line"


def test_line_granularity_reports_the_row_that_changed_and_no_other() -> None:
    before = _big(3000)
    after = before.replace("r1500c0", "CHANGED", 1)
    result = compare(before, after)
    assert result.granularity == "line"
    changed = [span for span in result.spans if span.kind != "equal"]
    assert len(changed) == 2
    assert "CHANGED" in changed[1].text
    assert "r1500c0" in changed[0].text
    # the whole row is the unit, so the untouched columns ride along with it
    assert "r1500c11" in changed[0].text and "r1500c11" in changed[1].text


def test_line_granularity_leaves_untouched_rows_in_equal_spans() -> None:
    before = _big(3000)
    after = before.replace("r1500c0", "CHANGED", 1)
    equal_text = "\n".join(s.text for s in compare(before, after).spans if s.kind == "equal")
    assert "r0c0" in equal_text and "r2999c11" in equal_text


def test_identical_large_texts_are_one_equal_span_and_ratio_one() -> None:
    before = _big(3000)
    result = compare(before, before)
    assert result.ratio == 1.0
    assert len(result.spans) == 1 and result.spans[0].kind == "equal"


def test_compare_is_deterministic_at_line_granularity() -> None:
    before = _big(3000)
    after = before.replace("r10c0", "CHANGED", 1)
    assert compare(before, after) == compare(before, after)


def test_similarity_and_word_diff_agree_with_compare_on_a_large_text() -> None:
    before = _big(3000)
    after = before.replace("r10c0", "CHANGED", 1)
    result = compare(before, after)
    assert similarity(before, after) == result.ratio
    assert word_diff(before, after) == result.spans
