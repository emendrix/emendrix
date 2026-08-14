"""The evidence block: unified where legible, stacked verbatim where not."""

from __future__ import annotations

from datetime import date

from emendrix.core import Change, ProvisionTree
from emendrix.diff import compute_delta
from emendrix.output import ChangelogEntry, diff_only_entry
from emendrix.site_.diffview import render_texts
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
    rendered = render_texts(change, entry)
    assert '<p class="diff">' in rendered
    assert "<del>" in rendered or "<ins>" in rendered


def test_a_rewrite_below_the_floor_falls_back_to_stacked_verbatim() -> None:
    change, entry = _change("MODIFIED")
    rewritten = change.model_copy(
        update={"after": "entirely different words with nothing shared at all whatsoever"}
    )
    rendered = render_texts(rewritten, entry)
    assert "texts differ too much for an inline diff" in rendered
    assert rendered.count('<pre class="verbatim"') == 2
    assert "<del>" not in rendered


def test_an_insertion_shows_the_whole_new_text_marked_inserted() -> None:
    change, entry = _change("INSERTED")
    rendered = render_texts(change, entry)
    assert 'class="verbatim ins"' in rendered
    assert "<del>" not in rendered


def test_markup_in_legal_text_cannot_open_a_tag() -> None:
    change, entry = _change("MODIFIED")
    hostile = change.model_copy(update={"after": str(change.before) + ' <script>"x"'})
    assert "<script>" not in render_texts(hostile, entry)


def test_verbatim_blocks_preserve_stored_whitespace() -> None:
    change, entry = _change("MODIFIED")
    spaced = change.model_copy(
        update={"before": "line one\n  indented line", "after": "unrelated replacement text"}
    )
    rendered = render_texts(spaced, entry)
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
    html = str(render_texts(*_texts(before, after)))
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
    html = str(render_texts(*_texts(before, after)))
    assert len(html) < len(before) // 10


def test_a_word_diff_is_never_elided() -> None:
    html = str(render_texts(*_texts("pay within one month", "pay within two weeks")))
    assert "unchanged lines" not in html
    assert "compared line by line" not in html
