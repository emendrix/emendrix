"""Every tool over the committed fixture: what it selects, how it pages, what it carries.

The fixture holds two toy acts and three events (see `test_record_reader.py` in the
`emendrix-record` member). Its texts are short, so paging is exercised with a small
`max_chars`; its one disputed change per act has the reason `textless_metadata_only`, and the
garden act's payload stores no `dispute_reason`.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.resources import methodology
from emendrix_mcp.tools import ChangeRow
from emendrix_mcp.tools_event import describe_act, get_event, list_disputed, provision_history
from emendrix_mcp.tools_read import changes_since, find_provisions, list_acts
from emendrix_mcp.tools_text import (
    LEADING_MARKER,
    MAX_CHARS_LIMIT,
    TRUNCATION_MARKER,
    TextPage,
    get_change,
    page,
)
from emendrix_record.reads import PERMALINK_UNAVAILABLE
from emendrix_record.reasons import REASON_SENTENCES
from emendrix_record.record import Record

FIXTURES = Path(__file__).resolve().parents[2] / "emendrix-record" / "tests" / "fixtures"
CHANGELOGS = FIXTURES / "changelogs"
CATALOGUE = FIXTURES / "catalogue.json"

HOUSE = "house-rules"
GARDEN = "garden-rules"
EARLY = date(2026, 1, 1)


@pytest.fixture
def record() -> Record:
    return Record(CHANGELOGS, CATALOGUE)


def _raw(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _index(act: str) -> Any:
    return _raw(CHANGELOGS / "toy" / act / "index.json")


def _catalogue(act: str) -> Any:
    return next(row for row in _raw(CATALOGUE)["acts"] if row["key"] == act)


def _rows(result: BaseModel) -> list[ChangeRow]:
    """Every `ChangeRow` anywhere in a result."""
    found: list[ChangeRow] = []

    def walk(value: object) -> None:
        if isinstance(value, ChangeRow):
            found.append(value)
        elif isinstance(value, BaseModel):
            for name in type(value).model_fields:
                walk(getattr(value, name))
        elif isinstance(value, tuple | list):
            for item in value:
                walk(item)

    walk(result)
    return found


def _every_result(record: Record) -> list[BaseModel]:
    return [
        list_acts(record),
        find_provisions(record, HOUSE, ""),
        changes_since(record, EARLY),
        provision_history(record, HOUSE, "AR 2"),
        get_change(record, HOUSE, "v3", "AR 9"),
        get_event(record, HOUSE, "v3"),
        list_disputed(record),
        describe_act(record, HOUSE),
    ]


# --- changes_since --------------------------------------------------------------------------


def test_changes_since_compares_the_basis_it_is_told(record: Record) -> None:
    updated = changes_since(record, date(2026, 8, 10), basis="updated_on")
    assert {(row.key, row.event.to_version) for row in updated.rows} == {(HOUSE, "v3")}
    detected = changes_since(record, date(2026, 8, 10), basis="detected_on")
    assert detected.rows == ()
    detected = changes_since(record, date(2026, 8, 9), basis="detected_on")
    assert {(row.key, row.event.to_version) for row in detected.rows} == {(HOUSE, "v3")}
    assert changes_since(record, EARLY, basis="in_force").rows == ()


def test_changes_since_in_force_reads_the_row_date(tmp_path: Path) -> None:
    copy = tmp_path / "changelogs"
    shutil.copytree(CHANGELOGS, copy)
    path = copy / "toy" / HOUSE / "index.json"
    index = _raw(path)
    index["provisions"]["AR 2"][1]["in_force"] = "2026-09-01"
    path.write_text(json.dumps(index), encoding="utf-8")
    result = changes_since(Record(copy, None), date(2026, 9, 1), basis="in_force")
    assert [(row.key, row.location, row.event.to_version) for row in result.rows] == [
        (HOUSE, "AR 2", "v2")
    ]
    assert changes_since(Record(copy, None), date(2026, 9, 2), basis="in_force").rows == ()


def test_excluding_disputed_drops_exactly_the_disputed_rows(record: Record) -> None:
    every = changes_since(record, EARLY).rows
    kept = changes_since(record, EARLY, include_disputed=False).rows
    assert [row for row in every if not row.row.disputed] == list(kept)
    assert len(every) - len(kept) == 2


def test_limit_keeps_the_newest_rows_and_counts_the_rest(record: Record) -> None:
    every = changes_since(record, EARLY, limit=500)
    assert len(every.rows) == 14 and every.omitted == 0
    dates = [row.event.updated_on for row in every.rows]
    assert dates == sorted(dates, reverse=True)
    short = changes_since(record, EARLY, limit=3)
    assert short.rows == every.rows[:3] and short.omitted == 11


def test_an_act_the_record_does_not_hold_is_said_in_words(record: Record) -> None:
    result = changes_since(record, EARLY, acts=("attic-rules", HOUSE))
    assert result.unavailable == ("the record holds no act 'attic-rules'",)
    assert {row.key for row in result.rows} == {HOUSE}


# --- provision_history and find_provisions --------------------------------------------------


def test_an_untouched_provision_has_no_rows_and_the_window_in_words(record: Record) -> None:
    result = provision_history(record, HOUSE, "AR 1")
    assert result.rows == () and result.window is not None
    assert result.sentence.startswith("No recorded change to AR 1 of toy/house-rules")
    assert result.window.sentence in result.sentence
    assert (result.window.from_version, result.window.to_version) == ("v1", "v3")
    assert result.sentence.endswith("returns nothing here.")
    assert not provision_history(record, HOUSE, "AR 2").sentence.endswith("returns nothing here.")


def test_a_touched_provision_lists_its_stored_rows_newest_first(record: Record) -> None:
    result = provision_history(record, HOUSE, "AR 2")
    assert [row.row.model_dump(mode="json") for row in result.rows] == _index(HOUSE)["provisions"][
        "AR 2"
    ]


def test_find_provisions_matches_names_and_headings_only(record: Record) -> None:
    by_heading = find_provisions(record, HOUSE, "bins")
    assert [(match.location, match.heading) for match in by_heading.provisions] == [
        ("AR 2", "Bins")
    ]
    assert by_heading.provisions[0].heading_version == "v3"
    by_code = find_provisions(record, HOUSE, "ar ")
    assert [match.location for match in by_code.provisions] == ["AR 2", "AR 3", "AR 4", "AR 9"]
    assert find_provisions(record, HOUSE, "recycling").provisions == ()


def test_list_acts_filters_by_name_and_by_the_catalogue_sector(record: Record) -> None:
    assert [act.row.key for act in list_acts(record, query="garden").acts] == [GARDEN]
    assert len(list_acts(record, domain="housing").acts) == 2
    assert list_acts(record, domain="energy").acts == ()
    blind = list_acts(Record(CHANGELOGS, None), domain="housing")
    assert blind.acts == () and len(blind.unavailable) == 2


# --- get_change -----------------------------------------------------------------------------


def test_the_markers_are_fixed_text() -> None:
    assert TRUNCATION_MARKER == (
        "\n[… {omitted} characters omitted, continue with offset={next_offset}]"
    )
    assert LEADING_MARKER == "[… {offset} characters before this page, from offset=0]\n"


def _unmarked(text_page: TextPage) -> str:
    body = text_page.text
    if text_page.offset:
        body = body.removeprefix(LEADING_MARKER.format(offset=text_page.offset))
    if text_page.next_offset is not None:
        omitted = text_page.total_chars - text_page.next_offset
        marker = TRUNCATION_MARKER.format(omitted=omitted, next_offset=text_page.next_offset)
        assert body.endswith(marker)
        body = body.removesuffix(marker)
    return body


def test_a_long_side_is_cut_at_max_chars_and_marked(record: Record) -> None:
    stored = _raw(CHANGELOGS / "toy" / HOUSE / "changes" / "v2.json")["changes"][0]["change"]
    result = get_change(record, HOUSE, "v2", "AR 2", max_chars=10)
    assert result.change is not None and result.change.after is not None
    first = result.change.after
    marker = TRUNCATION_MARKER.format(omitted=len(stored["after"]) - 10, next_offset=10)
    assert first.text == stored["after"][:10] + marker
    assert (first.returned_chars, first.total_chars, first.next_offset) == (
        10,
        len(stored["after"]),
        10,
    )


@pytest.mark.parametrize("max_chars", [1, 7, 10, 35, 1000])
def test_paging_by_offset_loses_and_repeats_nothing(record: Record, max_chars: int) -> None:
    stored = _raw(CHANGELOGS / "toy" / HOUSE / "changes" / "v2.json")["changes"][0]["change"]
    for side in ("before", "after"):
        pieces: list[str] = []
        offset: int | None = 0
        while offset is not None:
            result = get_change(record, HOUSE, "v2", "AR 2", max_chars=max_chars, offset=offset)
            assert result.change is not None
            text_page = getattr(result.change, side)
            assert isinstance(text_page, TextPage) and text_page.offset == offset
            pieces.append(_unmarked(text_page))
            offset = text_page.next_offset
        assert "".join(pieces) == stored[side]


def test_max_chars_and_offset_are_clamped() -> None:
    assert page("abc", 0, 0).returned_chars == 1
    assert page("x" * (MAX_CHARS_LIMIT + 5), 0, 10**9).returned_chars == MAX_CHARS_LIMIT
    assert page("abc", -4, 2).offset == 0
    past = page("abc", 99, 2)
    assert (past.offset, past.returned_chars, past.next_offset) == (3, 0, None)
    assert page("abc", 0, 3).text == "abc"


def test_the_reason_comes_from_the_index_row_when_the_payload_lacks_it(record: Record) -> None:
    result = get_change(record, GARDEN, "v2", "AR 9")
    assert result.change is not None and result.change.row is not None
    assert result.change.row.dispute_reason == "textless_metadata_only"
    assert result.change.reason_sentence == REASON_SENTENCES["textless_metadata_only"]
    assert result.change.before is None and result.change.after is None


def test_get_change_returns_the_stored_facts_unaltered(record: Record) -> None:
    raw = _raw(CHANGELOGS / "toy" / HOUSE / "changes" / "v2.json")["changes"][0]
    result = get_change(record, HOUSE, "v2", "AR 2")
    assert result.change is not None
    dumped = result.change.model_dump(mode="json")
    for name in ("change_type", "heading", "changed_within", "signals", "applies_from"):
        assert dumped[name] == raw["change"][name], name
    assert dumped["sentences"] == raw["sentences"]
    assert dumped["before"]["text"] == raw["change"]["before"]
    assert result.change.sentences[0].citations[0].url == raw["sentences"][0]["citations"][0]["url"]
    assert result.change.provision_url == _catalogue(HOUSE)["provisions"]["AR 2"]


def test_an_unknown_change_is_said_in_words(record: Record) -> None:
    result = get_change(record, HOUSE, "v3", "AR 77")
    assert result.change is None and "'AR 77'" in result.unavailable[0]
    assert result.disclaimer == DISCLAIMER


# --- get_event and list_disputed ------------------------------------------------------------


def test_get_event_names_the_units_only_one_signal_names(record: Record) -> None:
    result = get_event(record, HOUSE, "v3")
    assert result.event is not None and result.event.corroboration is not None
    assert result.event.view.event.instruction_only_units == ("AR 7",)
    assert result.event.view.event.metadata_only_units == ("AR 9",)
    assert result.event.corroboration.instruction_only_units == ("AR 7",)
    assert "AR 7" not in {row.location for row in result.event.rows}
    assert result.event.matches_index
    assert result.event.view.url == _catalogue(HOUSE)["events"]["v3"]


def test_list_disputed_groups_by_reason_with_the_published_sentence(record: Record) -> None:
    result = list_disputed(record)
    assert [(group.reason, group.sentence) for group in result.groups] == [
        ("textless_metadata_only", REASON_SENTENCES["textless_metadata_only"])
    ]
    assert [(row.key, row.location) for row in result.groups[0].rows] == [
        (GARDEN, "AR 9"),
        (HOUSE, "AR 9"),
    ]
    assert len(list_disputed(record, act=HOUSE).groups[0].rows) == 1
    assert list_disputed(record, reason="kind_mismatch").groups == ()
    unknown = list_disputed(record, reason="no_such_code")
    assert unknown.groups == () and "no_such_code" in unknown.unavailable[0]


# --- what every result carries --------------------------------------------------------------


def test_permalinks_are_the_catalogue_values(record: Record) -> None:
    rows = _rows(changes_since(record, EARLY, limit=500))
    for row in rows:
        listing = _catalogue(row.key)
        assert row.provision_url == listing["provisions"][row.location]
        assert row.event.url == listing["events"][row.event.to_version]
    assert list_acts(record).acts[0].url == _catalogue(GARDEN)["url"]


def test_without_a_catalogue_every_permalink_is_unavailable() -> None:
    blind = Record(CHANGELOGS, None)
    rows = [row for result in _every_result(blind) for row in _rows(result)]
    assert rows
    for row in rows:
        assert row.provision_url is None and row.event.url is None
        assert row.provision_url_unavailable == PERMALINK_UNAVAILABLE
        assert row.event.url_unavailable == PERMALINK_UNAVAILABLE
    act = list_acts(blind).acts[0]
    assert act.url is None and act.url_unavailable == PERMALINK_UNAVAILABLE
    assert act.label is None and act.row.title == "Garden Rules of Flat 3B"
    assert PERMALINK_UNAVAILABLE in methodology(blind)


def test_every_result_carries_the_disclaimer_and_stored_rows(record: Record) -> None:
    stored = {
        (act, location, row["version"], row["occurrence"]): row
        for act in (HOUSE, GARDEN)
        for location, rows in _index(act)["provisions"].items()
        for row in rows
    }
    for result in _every_result(record):
        assert result.model_dump()["disclaimer"] == DISCLAIMER
        for row in _rows(result):
            dumped = row.row.model_dump(mode="json")
            assert set(dumped["signals"]) == {
                "structural_diff",
                "corpus_metadata",
                "instruction_parse",
            }
            assert dumped == stored[(row.key, row.location, row.row.version, row.row.occurrence)]
            assert row.reason_sentence == (
                REASON_SENTENCES[dumped["dispute_reason"]] if dumped["disputed"] else None
            )


def test_the_methodology_names_no_figure(record: Record) -> None:
    text = methodology(record)
    assert DISCLAIMER in text
    assert not any(character.isdigit() for character in text)
