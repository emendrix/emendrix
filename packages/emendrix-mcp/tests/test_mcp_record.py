"""The record reads the committed fixture into the server's models and refuses what it must.

The fixture under `fixtures/` is written by the `emendrix` writers and held to them by a test
in that suite: two toy acts, three events, one disputed change in each act, one event naming
units by name only, and one payload written without the stored `dispute_reason`. Tests that
need to damage it copy it first.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.models import ActIndex, RootIndex
from emendrix_mcp.record import (
    PERMALINK_UNAVAILABLE,
    ChangeRead,
    PayloadRead,
    Record,
    Unavailable,
    _row,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CHANGELOGS = FIXTURES / "changelogs"
CATALOGUE = FIXTURES / "catalogue.json"

HOUSE = "house-rules"
GARDEN = "garden-rules"


@pytest.fixture
def record() -> Record:
    return Record(CHANGELOGS, CATALOGUE)


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    target = tmp_path / "changelogs"
    shutil.copytree(CHANGELOGS, target)
    return target


def _act(record: Record, act: str) -> ActIndex:
    index = record.act(act)
    assert isinstance(index, ActIndex), index
    return index


def _change(record: Record, act: str, version: str, location: str, n: int = 1) -> ChangeRead:
    read = record.change(act, version, location, n)
    assert isinstance(read, ChangeRead), read
    return read


def test_the_root_lists_both_acts_with_the_disclaimer(record: Record) -> None:
    root = record.root()
    assert isinstance(root, RootIndex)
    assert root.disclaimer == DISCLAIMER
    assert [(row.corpus, row.key) for row in root.acts] == [("toy", GARDEN), ("toy", HOUSE)]


def test_every_act_index_and_every_payload_reads_and_matches_its_hash(record: Record) -> None:
    root = record.root()
    assert isinstance(root, RootIndex)
    payloads = 0
    for row in root.acts:
        index = _act(record, row.key)
        assert (index.corpus, index.key) == (row.corpus, row.key)
        assert _act(record, f"{row.corpus}/{row.key}") == index
        for event in index.events:
            read = record.payload(event.path, event.sha256)
            assert isinstance(read, PayloadRead), read
            assert read.matches_index and read.sha256 == event.sha256
            assert read.payload.to_version == event.to_version
            assert read.payload.disclaimer == DISCLAIMER
            payloads += 1
    assert payloads == 3


def test_change_selects_by_location_and_occurrence_with_its_index_row(record: Record) -> None:
    read = _change(record, HOUSE, "v3", "AR 9")
    assert read.change.change.provision.location == "AR 9"
    assert read.change.change.disputed
    assert read.row is not None and read.row.dispute_reason == "textless_metadata_only"
    assert read.event.to_version == "v3"
    assert read.matches_index
    assert _change(record, HOUSE, "v2", "AR 2").change.change.after is not None


def test_an_unknown_change_is_a_value_naming_what_was_asked(record: Record) -> None:
    for asked, names in [
        (record.change(HOUSE, "v3", "AR 9", 2), "occurrence 2"),
        (record.change(HOUSE, "v3", "AR 77"), "'AR 77'"),
        (record.change(HOUSE, "v9", "AR 2"), "'v9'"),
        (record.change("attic-rules", "v2", "AR 2"), "'attic-rules'"),
        (record.change(HOUSE, "v3", "AR 9", 0), "occurrence 0"),
    ]:
        assert isinstance(asked, Unavailable), asked
        assert names in asked.reason


@pytest.mark.parametrize(
    "path", ["../index.json", "toy/../../index.json", "/etc/passwd", "C:\\index.json", ""]
)
def test_a_path_leaving_the_repository_is_refused(record: Record, path: str) -> None:
    read = record.payload(path, "0" * 64)
    assert isinstance(read, Unavailable)
    assert "refused" in read.reason


def test_a_link_leaving_the_repository_is_refused(copy: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (copy / "toy" / "escape.json").symlink_to(outside)
    read = Record(copy, None).payload("toy/escape.json", "0" * 64)
    assert isinstance(read, Unavailable) and "refused" in read.reason


def test_a_payload_edited_after_indexing_is_reported_as_a_hash_mismatch(copy: Path) -> None:
    payload = copy / "toy" / HOUSE / "changes" / "v3.json"
    payload.write_bytes(payload.read_bytes() + b"\n")
    record = Record(copy, None)
    read = _change(record, HOUSE, "v3", "AR 9")
    assert not read.matches_index
    assert read.sha256 != read.event.sha256
    index = _act(record, HOUSE)
    whole = record.payload(index.events[0].path, index.events[0].sha256)
    assert isinstance(whole, PayloadRead)
    assert not whole.matches_index and whole.indexed_sha256 == index.events[0].sha256


def test_a_payload_without_a_stored_dispute_reason_reads_and_the_row_gives_it(
    record: Record,
) -> None:
    raw = json.loads((CHANGELOGS / "toy" / GARDEN / "changes" / "v2.json").read_text())
    assert all("dispute_reason" not in emitted["change"] for emitted in raw["changes"])
    read = _change(record, GARDEN, "v2", "AR 9")
    assert read.change.change.disputed
    assert read.change.change.dispute_reason is None
    assert read.row is not None and read.row.dispute_reason == "textless_metadata_only"


def test_an_unreadable_payload_is_a_value(copy: Path) -> None:
    (copy / "toy" / HOUSE / "changes" / "v3.json").write_text("not json", encoding="utf-8")
    read = Record(copy, None).change(HOUSE, "v3", "AR 9")
    assert isinstance(read, Unavailable) and "v3.json" in read.reason


def test_permalinks_are_read_from_the_catalogue(record: Record) -> None:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    house = next(act for act in catalogue["acts"] if act["key"] == HOUSE)
    index = _act(record, HOUSE)
    assert record.act_url(index) == house["url"]
    assert record.event_url(index, index.events[0]) == house["events"]["v3"]
    assert record.provision_url(index, "AR 9") == house["provisions"]["AR 9"]
    assert isinstance(record.provision_url(index, "AR 77"), Unavailable)


def test_without_a_catalogue_every_permalink_is_unavailable_and_none_is_built() -> None:
    record = Record(CHANGELOGS, None)
    index = _act(record, HOUSE)
    for answer in (
        record.catalogue(),
        record.act_url(index),
        record.event_url(index, index.events[0]),
        record.provision_url(index, "AR 2"),
    ):
        assert answer == Unavailable(reason=PERMALINK_UNAVAILABLE)
        assert "http" not in answer.reason


def test_a_catalogue_that_cannot_be_read_is_unavailable_too(tmp_path: Path) -> None:
    record = Record(CHANGELOGS, tmp_path / "missing.json")
    answer = record.act_url(_act(record, HOUSE))
    assert isinstance(answer, Unavailable)
    assert answer.reason.startswith("permalink unavailable")


def test_a_sub_provision_change_finds_the_row_filed_under_its_unit(record: Record) -> None:
    """The index files rows by top-level unit, in payload order, whatever the change's own depth.

    No fixture change sits below top level, so the shapes are made here from fixture rows: two
    changes under `AR 2`, one at `AR 2 PA 1` and one at `AR 2`, each its own location's first.
    """
    index = _act(record, HOUSE)
    event = index.events[1]
    first, *_ = index.provisions["AR 2"]
    rows = (
        first.model_copy(update={"version": event.to_version, "change_type": "MODIFIED"}),
        first.model_copy(update={"version": event.to_version, "change_type": "INSERTED"}),
    )
    shaped = index.model_copy(update={"provisions": {"AR 2": rows}})
    read = record.payload(event.path, event.sha256)
    assert isinstance(read, PayloadRead)
    template = read.payload.changes[0]
    deeper = template.change.provision.model_copy(update={"location": "AR 2 PA 1"})
    changes = (
        template.model_copy(
            update={"change": template.change.model_copy(update={"provision": deeper})}
        ),
        template,
    )
    assert _row(shaped, event, changes, 0) == rows[0]
    assert _row(shaped, event, changes, 1) == rows[1]


def test_a_path_holding_a_nul_is_refused_not_raised(record: Record) -> None:
    read = record.payload("toy/\x00.json", "0" * 64)
    assert isinstance(read, Unavailable) and "refused" in read.reason
