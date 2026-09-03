"""The evidence block: unified where legible, stacked verbatim where not, and its size.

The size travels with the markup because it has to be the size of *that* markup's comparison,
so the tests below compute the expected counts from `compare` rather than writing a number
down: what is asserted is that the block reports the comparison it was built from.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import Change, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.diffview import render_texts
from emendrix.site_.worddiff import compare
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED = date(2026, 8, 9)


def _entry() -> ChangelogEntry:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(before, ProvisionTree) and isinstance(after, ProvisionTree)
    return diff_only_entry(compute_delta(before, after), detected_on=OBSERVED)


def _change(kind: str) -> tuple[Change, ChangelogEntry]:
    entry = _entry()
    for emitted in entry.changes:
        if emitted.change.change_type.value == kind:
            return emitted.change, entry
    raise AssertionError(f"no {kind} change in the toy delta")


def test_a_modified_provision_renders_as_a_unified_diff_when_similar_enough() -> None:
    change, entry = _change("MODIFIED")
    rendered = render_texts(change, entry).html
    assert '<p class="diff">' in rendered
    assert "<del>" in rendered or "<ins>" in rendered


def test_a_rewrite_below_the_floor_falls_back_to_stacked_verbatim() -> None:
    change, entry = _change("MODIFIED")
    rewritten = change.model_copy(
        update={"after": "entirely different words with nothing shared at all whatsoever"}
    )
    rendered = render_texts(rewritten, entry).html
    assert "texts differ too much for an inline diff" in rendered
    assert rendered.count('<pre class="verbatim"') == 2
    assert "<del>" not in rendered


def test_an_insertion_shows_the_whole_new_text_marked_inserted() -> None:
    change, entry = _change("INSERTED")
    rendered = render_texts(change, entry).html
    assert 'class="verbatim ins"' in rendered
    assert "<del>" not in rendered


def test_markup_in_legal_text_cannot_open_a_tag() -> None:
    change, entry = _change("MODIFIED")
    hostile = change.model_copy(update={"after": str(change.before) + ' <script>"x"'})
    assert "<script>" not in render_texts(hostile, entry).html


def test_verbatim_blocks_preserve_stored_whitespace() -> None:
    change, entry = _change("MODIFIED")
    spaced = change.model_copy(
        update={"before": "line one\n  indented line", "after": "unrelated replacement text"}
    )
    rendered = render_texts(spaced, entry).html
    assert "line one\n  indented line" in rendered


# ------------------------------------------------------------------ eliding unchanged rows


def _table(rows: int) -> str:
    """A text past `LINE_TOKEN_CEILING`, one row per line, so the diff runs line by line."""
    return "\n".join(" ".join(f"r{row}c{col}" for col in range(12)) for row in range(rows))


def _texts(before: str, after: str) -> tuple[Change, ChangelogEntry]:
    """A real MODIFIED change with its two texts replaced by the ones under test."""
    change, entry = _change("MODIFIED")
    return change.model_copy(update={"before": before, "after": after}), entry


def test_a_line_diff_elides_long_runs_of_unchanged_rows() -> None:
    before = _table(3000)
    after = before.replace("r1500c0", "CHANGED", 1)
    html = render_texts(*_texts(before, after)).html
    assert "compared line by line" in html
    assert "unchanged lines" in html
    # the changed row and its neighbours survive, as do the head and tail of the run
    assert "CHANGED" in html and "r1499c0" in html and "r1501c0" in html
    assert "r0c0" in html and "r2999c0" in html
    # what goes is the bulk in between, which is the whole point
    assert "r800c0" not in html and "r2200c0" not in html


def test_eliding_keeps_the_page_a_small_fraction_of_the_text() -> None:
    before = _table(3000)
    after = before.replace("r1500c0", "CHANGED", 1)
    html = render_texts(*_texts(before, after)).html
    assert len(html) < len(before) // 10


def test_a_word_diff_is_never_elided() -> None:
    html = render_texts(*_texts("pay within one month", "pay within two weeks")).html
    assert "unchanged lines" not in html
    assert "compared line by line" not in html


def test_the_unified_block_is_labelled_with_both_version_tags_above_it() -> None:
    """The label is a row of its own above the block, so a reader knows which direction the
    marked text runs in without reading the surrounding page."""
    change, entry = _change("MODIFIED")
    rendered = render_texts(change, entry).html
    label = (
        f'<p class="lbl"><code>{entry.from_version}</code> → <code>{entry.to_version}</code></p>'
    )
    assert label in rendered
    assert rendered.index(label) < rendered.index('<p class="diff">')


# ------------------------------------------------------------------ the size of the difference


def test_a_two_sided_change_counts_the_characters_of_the_comparison_it_shows() -> None:
    """The count is the rendered comparison's own, which is the property the page depends on.

    Computed here from `compare` rather than typed in, so the assertion is that the block
    reports what the comparison it was built from says, not that two people agreed on a number.
    """
    change, entry = _change("MODIFIED")
    before, after = change.before, change.after
    assert before is not None and after is not None
    comparison = compare(before, after)
    rendered = render_texts(change, entry)
    assert rendered.inserted == sum(
        len(span.text) for span in comparison.spans if span.kind == "inserted"
    )
    assert rendered.deleted == sum(
        len(span.text) for span in comparison.spans if span.kind == "deleted"
    )
    assert rendered.inserted and rendered.deleted
    assert rendered.granularity == "word"


def test_a_stacked_rewrite_still_reports_the_comparison_that_was_made() -> None:
    """Below the similarity floor the page stacks the texts; the comparison still happened."""
    change, entry = _change("MODIFIED")
    rewritten = change.model_copy(
        update={"after": "entirely different words with nothing shared at all whatsoever"}
    )
    rendered = render_texts(rewritten, entry)
    assert "shown separately" in rendered.html
    assert rendered.inserted and rendered.deleted
    assert rendered.granularity == "word"


def test_an_insertion_counts_the_whole_new_text_and_a_deletion_the_whole_old_one() -> None:
    """One side is not a comparison, so the count is the stored text and no unit is named."""
    change, entry = _change("INSERTED")
    after = change.after
    assert after is not None
    inserted = render_texts(change, entry)
    assert (inserted.inserted, inserted.deleted) == (len(after), 0)
    assert inserted.granularity is None

    removed = render_texts(change.model_copy(update={"before": after, "after": None}), entry)
    assert (removed.inserted, removed.deleted) == (0, len(after))
    assert removed.granularity is None


def test_a_unit_with_no_text_on_either_side_counts_nothing() -> None:
    change, entry = _change("MODIFIED")
    rendered = render_texts(change.model_copy(update={"before": None, "after": None}), entry)
    assert (rendered.inserted, rendered.deleted, rendered.granularity) == (0, 0, None)


def test_a_line_comparison_says_so_and_counts_whole_lines() -> None:
    """Above the token ceiling a line is the unit, so one changed word costs a whole row."""
    before = _table(3000)
    after = before.replace("r1500c0", "CHANGED", 1)
    rendered = render_texts(*_texts(before, after))
    assert rendered.granularity == "line"
    row = before.split("\n")[1500]
    assert rendered.deleted == len(row)
    assert rendered.inserted == len(row.replace("r1500c0", "CHANGED", 1))


def test_eliding_an_unchanged_run_never_moves_the_count() -> None:
    """`_kept` shortens `equal` runs only, so what is hidden is never what is counted."""
    before = _table(3000)
    after = before.replace("r1500c0", "CHANGED", 1)
    rendered = render_texts(*_texts(before, after))
    assert "unchanged lines" in rendered.html
    assert rendered.inserted + rendered.deleted < len(rendered.html)
