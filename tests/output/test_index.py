"""The change index: every value read off committed payloads, in a total order, with no text.

The index is what a consumer reads before deciding which payload to fetch, so the tests are
about the contract a consumer relies on: one row per change carrying the payload's own facts,
`dispute_reason` as the model computes it whether or not the file stores it, hashes of the
bytes as committed, and the same bytes whatever order the payloads were written in.
"""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

import pytest
from index_entries import (
    DISTINCTIVE_TEXT,
    SECOND_EVENT_ON,
    as_schema_1_0,
    at_version,
    repaired,
    with_units,
    without_dispute_reason,
    write_payload,
)
from toy_entries import OBSERVED_ON, disputed_entry, explained_entry, toy_entry

from emendrix import DISCLAIMER
from emendrix.output import (
    INDEX_FILE,
    INDEX_SCHEMA,
    ActIndex,
    ChangelogEntry,
    act_index,
    index_files,
    render_index,
    root_index,
)
from emendrix.site_.urls import change_anchor, entry_anchors

_ACT_DIR = "toy/house-rules"


def _one(tmp_path: Path, entry: ChangelogEntry, text: str | None = None) -> ActIndex:
    write_payload(tmp_path, entry, text)
    return act_index(tmp_path, _ACT_DIR)


def test_one_entry_indexes_to_one_event_and_one_row_per_change(tmp_path: Path) -> None:
    entry = toy_entry()
    index = _one(tmp_path, entry)
    assert (index.corpus, index.key, index.title) == ("toy", "house-rules", entry.title)
    (event,) = index.events
    assert event.path == f"{_ACT_DIR}/changes/{entry.key}.json"
    assert event.counts == entry.counts
    assert event.diff_only is True
    rows = [row for rows in index.provisions.values() for row in rows]
    assert len(rows) == len(entry.changes)
    assert list(index.provisions) == sorted(index.provisions)
    for emitted in entry.changes:
        (row,) = index.provisions[emitted.change.unit.canonical]
        expected = {
            (True, True): "both",
            (True, False): "before",
            (False, True): "after",
            (False, False): "none",
        }[(emitted.change.before is not None, emitted.change.after is not None)]
        assert row.text == expected
        assert row.change_type == emitted.change.change_type.value
        assert row.outcome == "unexplained"
        assert row.occurrence == 1
    assert {row.text for row in rows} >= {"both", "before", "after"}


def test_a_disputed_entry_carries_its_reason_and_the_signals_as_stored(tmp_path: Path) -> None:
    index = _one(tmp_path, disputed_entry())
    (row,) = index.provisions["AR 9"]
    assert row.disputed is True
    assert row.dispute_reason == "textless_metadata_only"
    assert row.text == "none"
    assert row.signals.structural_diff == "absent"
    assert row.signals.corpus_metadata == "observed"
    assert row.signals.instruction_parse == "unavailable"
    others = [other for key, rows in index.provisions.items() if key != "AR 9" for other in rows]
    assert others and not any(other.disputed for other in others)


def test_a_payload_without_the_stored_reason_indexes_the_reason_its_signals_give(
    tmp_path: Path,
) -> None:
    entry = disputed_entry()
    text = without_dispute_reason(entry)
    assert '"dispute_reason"' not in text
    stored = _one(tmp_path, entry, text)
    assert stored.provisions["AR 9"][0].dispute_reason == "textless_metadata_only"


def test_event_rows_name_the_units_only_one_signal_names(tmp_path: Path) -> None:
    plain = toy_entry()
    named = with_units(
        at_version(plain, "v3", SECOND_EVENT_ON),
        metadata_only=("AR 9",),
        instruction_only=("AR 12", "AN II"),
    )
    write_payload(tmp_path, plain)
    write_payload(tmp_path, named)
    newest, oldest = act_index(tmp_path, _ACT_DIR).events
    assert newest.to_version == "v3"
    assert newest.metadata_only_units == ("AR 9",)
    assert newest.instruction_only_units == ("AR 12", "AN II")
    assert plain.corroboration is None
    assert (oldest.metadata_only_units, oldest.instruction_only_units) == ((), ())


def test_the_order_payloads_are_written_in_does_not_move_a_byte(tmp_path: Path) -> None:
    entries = [at_version(toy_entry(), f"v{number}", OBSERVED_ON) for number in (2, 3, 4, 5, 6, 7)]
    built: list[dict[str, str]] = []
    for seed in (1, 2, 3):
        repo = tmp_path / str(seed)
        shuffled = list(entries)
        random.Random(seed).shuffle(shuffled)
        for entry in shuffled:
            write_payload(repo, entry)
        built.append(index_files(repo))
    assert built[0] == built[1] == built[2]
    assert index_files(tmp_path / "1") == built[0]
    index = act_index(tmp_path / "1", _ACT_DIR)
    assert [event.to_version for event in index.events] == ["v7", "v6", "v5", "v4", "v3", "v2"]
    assert [row.version for row in index.provisions["AR 2"]] == ["v7", "v6", "v5", "v4", "v3", "v2"]


def test_a_repair_moves_updated_on_and_is_listed_by_its_own_kind(tmp_path: Path) -> None:
    entry = repaired(toy_entry(), "signals", date(2026, 10, 8))
    (event,) = _one(tmp_path, entry).events
    assert event.detected_on == OBSERVED_ON
    assert event.updated_on == date(2026, 10, 8)
    assert [(row.kind, row.repaired_on) for row in event.repairs] == [
        ("signals", date(2026, 10, 8))
    ]


def test_an_edited_byte_moves_its_own_hash_and_the_act_hash_and_nothing_else(
    tmp_path: Path,
) -> None:
    first = toy_entry()
    second = at_version(first, "v3", SECOND_EVENT_ON)
    write_payload(tmp_path, first)
    path = write_payload(tmp_path, second)
    before_act = act_index(tmp_path, _ACT_DIR)
    before_root = root_index([before_act])
    text = path.read_text(encoding="utf-8")
    marker = '"unexplained": "diff-only mode'
    assert marker in text
    path.write_text(text.replace(marker, marker.replace('"diff', '" diff'), 1), encoding="utf-8")
    after_act = act_index(tmp_path, _ACT_DIR)
    after_root = root_index([after_act])

    assert after_act.events[0].sha256 != before_act.events[0].sha256
    assert after_act.events[1] == before_act.events[1]
    assert after_act.model_copy(update={"events": before_act.events}) == before_act
    assert after_root.acts[0].index_sha256 != before_root.acts[0].index_sha256
    assert (
        after_root.acts[0].model_copy(update={"index_sha256": before_root.acts[0].index_sha256})
        == before_root.acts[0]
    )


def test_a_schema_1_0_document_indexes_as_one(tmp_path: Path) -> None:
    (event,) = _one(tmp_path, explained_entry(), as_schema_1_0(explained_entry())).events
    assert event.schema_version == "1.0"
    assert event.evidence is False


def test_a_repeated_location_counts_occurrences_as_the_site_anchors_do(tmp_path: Path) -> None:
    base = toy_entry()
    first, second, *_ = base.changes
    entry = base.model_copy(update={"changes": (first, second, first, *base.changes[2:], first)})
    index = _one(tmp_path, entry)
    unit = first.change.unit.canonical
    assert [row.occurrence for row in index.provisions[unit]] == [1, 2, 3]

    anchors = entry_anchors(
        entry.key, [emitted.change.location.canonical for emitted in entry.changes]
    )
    remaining = {key: list(rows) for key, rows in index.provisions.items()}
    for emitted, anchor in zip(entry.changes, anchors, strict=True):
        row = remaining[emitted.change.unit.canonical].pop(0)
        assert change_anchor(entry.key, emitted.change.location.canonical, row.occurrence) == anchor


def test_a_bare_applicability_date_renders_as_its_iso_string(tmp_path: Path) -> None:
    base = toy_entry()
    first, *rest = base.changes
    dated = first.model_copy(
        update={"change": first.change.model_copy(update={"applies_from": date(2027, 12, 2)})}
    )
    index = _one(tmp_path, base.model_copy(update={"changes": (dated, *rest)}))
    assert index.provisions[first.change.unit.canonical][0].applies_from == "2027-12-02"
    assert {row.applies_from for rows in index.provisions.values() for row in rows} >= {
        "unknown",
        "unchanged",
    }


def test_a_payload_that_does_not_validate_is_refused_by_name(tmp_path: Path) -> None:
    path = write_payload(tmp_path, toy_entry(), '{"schema_version": "9.9"}\n')
    with pytest.raises(ValueError, match=str(path)):
        act_index(tmp_path, _ACT_DIR)
    with pytest.raises(ValueError, match=str(path)):
        index_files(tmp_path)


def test_every_file_carries_the_disclaimer_and_no_provision_text(tmp_path: Path) -> None:
    entry = explained_entry()
    assert DISTINCTIVE_TEXT in entry.to_json()
    write_payload(tmp_path, entry)
    write_payload(tmp_path, at_version(disputed_entry(), "v3", SECOND_EVENT_ON))
    files = index_files(tmp_path)
    assert list(files) == [INDEX_FILE, f"{_ACT_DIR}/{INDEX_FILE}"]
    for text in files.values():
        payload = json.loads(text)
        assert payload["disclaimer"] == DISCLAIMER
        assert payload["index_schema"] == INDEX_SCHEMA
        assert DISTINCTIVE_TEXT not in text
        assert text.endswith("}\n")
    act = act_index(tmp_path, _ACT_DIR)
    assert files[f"{_ACT_DIR}/{INDEX_FILE}"] == render_index(act)
    (row,) = root_index([act]).acts
    assert row.index == f"{_ACT_DIR}/{INDEX_FILE}"
    assert (row.events, row.changes, row.disputed) == (2, 9, 1)
    assert row.provisions == len(act.provisions)
    assert row.newest_version == "v3"
    assert (row.first_detected_on, row.updated_on) == (OBSERVED_ON, SECOND_EVENT_ON)
