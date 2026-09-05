"""The two events whose counts say less than a sentence does, on every surface that says them.

One matched every unit and has nothing to report; the other has rows to report and no text in
any of them. Both keep every count they ever carried, and neither drops a row.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from site_entries import (
    some_textless_entry,
    textless_entry,
    unattributed_entry,
    untouched_entry,
)

from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry
from emendrix.site_.feeds import render_feed
from emendrix.site_.inputs import SiteInputs, collect_site
from emendrix.site_.pages.act import render_act
from emendrix.site_.untouched import (
    UNTOUCHED_SENTENCE,
    all_textless,
    textless_note,
    textless_words,
    untouched,
    untouched_note,
)

REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO / "reports" / "eval"
ATOM = "{http://www.w3.org/2005/Atom}"


def _site(entry: ChangelogEntry) -> SiteInputs:
    return collect_site(
        generated_on=entry.detected_on,
        run=EvalRun.model_validate_json(latest_report(REPORTS).read_bytes()),
        report=Path("r.json"),
        entries=(entry,),
        site_url="https://example.invalid/site",
    )


def test_zero_touched_is_the_class_and_a_touched_event_is_not() -> None:
    assert untouched(untouched_entry())
    assert not untouched(unattributed_entry())


def test_the_note_carries_the_number_of_units_the_comparison_read() -> None:
    entry = untouched_entry()
    assert str(entry.summary.unchanged_units) in untouched_note(entry)


def test_the_act_page_states_the_finding_in_words_not_as_a_row_of_zeros() -> None:
    entry = untouched_entry()
    rendered = render_act(_site(entry), _site(entry).acts[0])
    assert UNTOUCHED_SENTENCE in rendered
    assert untouched_note(entry) in rendered
    assert "0 provisions touched" not in rendered
    assert "0 substantive" not in rendered


def test_a_touched_event_keeps_its_count_line() -> None:
    entry = unattributed_entry()
    rendered = render_act(_site(entry), _site(entry).acts[0])
    assert UNTOUCHED_SENTENCE not in rendered
    assert "touched — " in rendered


def test_the_feed_summary_states_the_finding_and_keeps_the_entry_whole() -> None:
    entry = untouched_entry()
    site = _site(entry)
    root = ElementTree.fromstring(render_feed(site, None))
    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == 1
    summary = entries[0].findtext(f"{ATOM}summary")
    assert summary is not None
    assert UNTOUCHED_SENTENCE in summary
    assert "0 provisions touched" not in summary


def test_every_unit_with_no_text_is_the_class_and_a_mixed_event_is_not() -> None:
    """The predicate is all or nothing, so an event with one text-carrying unit is outside it,
    and an event that touched nothing is outside it too: there is no row to say this of."""
    assert all_textless(textless_entry())
    assert not all_textless(some_textless_entry())
    assert not all_textless(untouched_entry())


def test_the_note_says_what_named_the_rows_and_that_none_was_dropped() -> None:
    entry = textless_entry()
    note = textless_note(entry)
    assert str(entry.counts.touched) in note
    assert "marked disputed" in note and "none was dropped" in note


def test_the_act_page_keeps_both_counts_and_replaces_only_the_split() -> None:
    entry = textless_entry()
    rendered = render_act(_site(entry), _site(entry).acts[0])
    assert "2 provisions touched — none with text to show" in rendered
    assert "<strong>2 disputed</strong>" in rendered
    assert textless_note(entry) in rendered
    assert "0 substantive" not in rendered


def test_a_mixed_event_prints_the_split_three_ways() -> None:
    """The clause is unconditional otherwise, `0 with no text` included: a line that changed
    shape between two events is a line a reader has to read twice."""
    entry = some_textless_entry()
    rendered = render_act(_site(entry), _site(entry).acts[0])
    assert "5 provisions touched — 4 substantive, 0 date-only, 1 with no text" in rendered
    assert textless_note(entry) not in rendered


def test_the_title_fragment_names_the_count_and_what_it_is_a_count_of() -> None:
    assert textless_words(textless_entry()) == "2 provisions named with no text to show"
