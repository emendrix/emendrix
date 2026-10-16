"""The entry table a change block shows: its three states, its counts, its rows and its caps.

Every delta here is built from invented keys and cell text (`toy_table_entries.py`), because
the renderer reads only the delta and a typed legal row would be content nobody fetched.
"""

from __future__ import annotations

import re

from helpers import text_of
from toy_table_entries import TABLE, added, amended, delta, removed, unpaired

from emendrix.core import EntryGaps
from emendrix.site_.entry_table import LISTED, OPEN, entry_table
from emendrix.site_.markup import join

_HREF = "../../../api/v1/eu/k/changes/v2.json"
_EN_DASHED_B = "a\u2013b"
_EN_DASHED_C = "a\u2013c"


def _html(*args: object, **kwargs: object) -> str:
    return join(entry_table(delta(*args, **kwargs), _HREF))  # type: ignore[arg-type]


def _count(html: str) -> str:
    match = re.search(r'<p class="entries-count">(.*?)</p>', html)
    assert match is not None
    return match.group(1)


def test_a_change_that_read_no_table_shows_nothing() -> None:
    assert entry_table(None, _HREF) == []


def test_a_table_read_with_nothing_moved_says_so_and_points_at_the_text() -> None:
    html = _html()
    assert _count(html) == (
        "No keyed table entry changed between these two versions. "
        "The text below shows where the provision did change."
    )
    assert "<table" not in html


def test_the_count_line_counts_each_kind_and_says_entry_for_one() -> None:
    html = _html(added("k1"), added("k2"), amended("k3", ("a",), ("b",)))
    assert _count(html) == "2 entries added, 1 amended, 0 removed."
    assert _count(_html(added("k1"))) == "1 entry added, 0 amended, 0 removed."


def test_the_count_line_names_the_typography_and_the_whitespace_it_set_aside() -> None:
    html = _html(
        amended("k1", ("a",), ("b",)),
        amended("k2", ("a-b",), (_EN_DASHED_B,), typography=True),
        amended("k3", ("a-c",), (_EN_DASHED_C,), typography=True),
        whitespace_only=4,
    )
    assert _count(html) == (
        "0 entries added, 3 amended, 0 removed (2 of the amended differ only in spacing, dash "
        "forms or accents). 4 more changed only in whitespace and are not listed."
    )
    one = _html(amended("k2", ("a-b",), (_EN_DASHED_B,), typography=True), whitespace_only=1)
    assert "(1 of the amended differs only in" in _count(one)
    assert _count(one).endswith("1 more changed only in whitespace and is not listed.")


def test_the_gap_sentence_names_only_the_gaps_that_are_there() -> None:
    assert '<p class="small muted">' not in _html(added("k1"))
    same = _html(
        added("k1"), gaps_before=EntryGaps(unkeyed_rows=3), gaps_after=EntryGaps(unkeyed_rows=3)
    )
    assert "3 rows carry no key and are not compared." in same
    differing = _html(
        added("k1"),
        gaps_before=EntryGaps(unkeyed_rows=1),
        gaps_after=EntryGaps(unkeyed_rows=2, unrecognised_tables=1),
    )
    assert (
        "1 row in the previous version and 2 in this one carry no key and are not compared; "
        "0 tables in the previous version and 1 in this one could not be recognised and are "
        "not read."
    ) in differing
    keys = _html(added("k1"), unpaired_keys=(unpaired("k9"),))
    assert "1 key printed a different number of times in the two versions is not compared." in keys


def test_an_amended_entry_shows_both_sides_and_marks_only_the_cells_that_differ() -> None:
    html = _html(amended("k1", ("k1", "same", "old words", "z"), ("k1", "same", "new words", "z")))
    assert '<td class="side">Before</td>' in html and '<td class="side">After</td>' in html
    assert '<td class="differs"><del>old</del> words</td>' in html
    assert '<td class="differs"><ins>new</ins> words</td>' in html
    assert "<td>same</td>" in html
    assert html.count('class="differs"') == 2


def test_the_header_rows_are_the_table_s_own_with_their_spans_and_every_header_has_scope() -> None:
    html = _html(added("k1"))
    assert '<th scope="col" rowspan="2">Entry</th>' in html
    assert '<th scope="col" rowspan="2">Name</th>' in html
    assert '<th scope="col" colspan="2">Limits</th>' in html
    assert '<th scope="col">low</th><th scope="col">high</th>' in html
    assert '<th scope="col" rowspan="2">Identifiers</th>' in html
    assert all("scope=" in tag for tag in re.findall(r"<th\b[^>]*>", html))


def test_an_entry_names_its_key_and_its_identifiers_and_a_name_key_its_name() -> None:
    html = _html(added("k1"))
    assert "<span>Entry k1</span><span>CAS k1-cas</span>" in html
    named = TABLE.model_copy(update={"key_label": None})
    change = added("k2").model_copy(
        update={"after": added("k2").after.model_copy(update={"name": "Name Two"})}  # type: ignore[union-attr]
    )
    assert "<span>Name Two</span>" in join(entry_table(delta(change, table=named), _HREF))


def test_typography_only_amendments_sit_closed_under_the_amended_table() -> None:
    html = _html(
        amended("k1", ("a",), ("b",)), amended("k2", ("a-b",), (_EN_DASHED_B,), typography=True)
    )
    closed = '<details class="typography"><summary>1 entry differs only in spacing, dash forms '
    assert closed + "or accents</summary>" in html
    assert html.index("Entry k1") < html.index(closed) < html.index("Entry k2")


def test_fifty_open_then_a_counted_fold_to_two_hundred_then_keys_and_the_file() -> None:
    changes = [added(f"k{index}") for index in range(1, 251)]
    html = _html(*changes)
    fold = html.index("<details><summary>150 more added entries</summary>")
    assert html[:fold].count("<tbody>") == OPEN
    assert html.count("<tbody>") == LISTED
    assert "50 more added entries, by key only:" in html
    assert "<li>Entry k201, CAS k201-cas</li>" in html and "<li>Entry k250," in html
    assert "Entry k250</span>" not in html
    assert (
        f'Their rows are in this change\'s file: <a href="{_HREF}">api/v1/eu/k/changes/v2.json</a>.'
    ) in html


def test_cells_are_escaped_and_keep_their_line_breaks() -> None:
    html = _html(added("k1", ("k1", "a <b> & c", "first\nsecond", "z")))
    assert "<td>a &lt;b&gt; &amp; c</td>" in html
    assert "<td>first\nsecond</td>" in html
    assert "<b>" not in text_of(html.replace("&lt;b&gt;", ""))


def test_a_cell_covered_by_a_span_in_the_rows_is_merged_not_printed_empty() -> None:
    html = _html(added("k1", ("k1", "shared", "x", "y"), ("k1", None, "z", "w")))
    assert '<td rowspan="2">shared</td>' in html


def test_the_rendering_is_byte_stable_and_carries_no_inline_style() -> None:
    changes = (added("k2"), amended("k1", ("a",), ("b",)), removed("k3"))
    assert _html(*changes) == _html(*changes)
    assert "style=" not in _html(*changes)


def test_a_short_row_s_missing_cells_are_empty_rather_than_spanned() -> None:
    html = _html(added("k1", ("k1", "only")))
    assert "<td>k1</td><td>only</td><td></td><td></td></tr>" in html
