"""The rows the loader builds are the record's own facts, keyed and flattened as the record keys
them; nothing here touches a database."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from emendrix_record.links import entry_anchors
from emendrix_record.models import ActIndex
from emendrix_record.payload import (
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    ChangeRecord,
    Payload,
    Sentence,
)
from emendrix_record.reads import Unavailable
from emendrix_record.record import Record, entry_key
from emendrix_service.load.models import ChangeLoad, StoredUnitChange
from emendrix_service.load.rows import (
    applies_from,
    change_loads,
    event_key,
    filed_rows,
    provision_loads,
    sentences_json,
)

FIXTURE = Path(__file__).resolve().parents[2] / "emendrix-record" / "tests" / "fixtures"

RECORD = Record(FIXTURE / "changelogs", FIXTURE / "catalogue.json")


def act(name: str) -> ActIndex:
    index = RECORD.act(name)
    assert not isinstance(index, Unavailable), index
    return index


def loads_of(name: str, version: str) -> tuple[Payload, tuple[ChangeLoad, ...]]:
    index = act(name)
    event = RECORD.event(index, version)
    assert not isinstance(event, Unavailable)
    read = RECORD.payload(event.path, event.sha256)
    assert not isinstance(read, Unavailable)
    key = event_key(index.corpus, index.key, event.to_version)
    rows = filed_rows(index, event, read.payload)
    return read.payload, change_loads(key, entry_key(event), read.payload, rows)


EVENTS = [("garden-rules", "v2"), ("house-rules", "v2"), ("house-rules", "v3")]


@pytest.mark.parametrize(("name", "version"), EVENTS)
def test_svc_load_anchors_and_occurrences_follow_the_site_rule(name: str, version: str) -> None:
    payload, loads = loads_of(name, version)
    locations = [change.change.provision.location for change in payload.changes]
    assert [load.location for load in loads] == locations
    assert tuple(load.anchor for load in loads) == entry_anchors(version, locations)
    for load in loads:
        expected = locations[: loads.index(load) + 1].count(load.location)
        assert load.occurrence == expected
        assert load.event_key == f"toy/{name}@{version}"


@pytest.mark.parametrize(("name", "version"), EVENTS)
def test_svc_load_every_change_takes_the_index_row_it_is_filed_under(
    name: str, version: str
) -> None:
    _, loads = loads_of(name, version)
    index = act(name)
    for load in loads:
        rows = [row for row in index.provisions[load.unit] if row.version == version]
        row = rows[load.occurrence - 1]
        assert (load.disputed, load.dispute_reason) == (row.disputed, row.dispute_reason)
        assert load.applies_from == row.applies_from
        assert load.amending_acts == row.amending_acts
        assert load.changed_within == row.changed_within
        assert (load.change_type, load.outcome) == (row.change_type, row.outcome)


def test_svc_load_a_payload_without_a_stored_reason_takes_the_index_rows() -> None:
    payload, loads = loads_of("garden-rules", "v2")
    stored = {change.change.provision.location: change.change for change in payload.changes}
    assert stored["AR 9"].dispute_reason is None
    (load,) = [load for load in loads if load.location == "AR 9"]
    assert (load.disputed, load.dispute_reason) == (True, "textless_metadata_only")


def test_svc_load_applies_from_is_flattened_as_the_index_flattens_it() -> None:
    payload, _ = loads_of("house-rules", "v2")
    record = payload.changes[0]

    def with_value(value: date | ApplicabilityUnknown | ApplicabilityUnchanged) -> ChangeRecord:
        change = record.change.model_copy(update={"applies_from": value})
        return record.model_copy(update={"change": change})

    assert applies_from(with_value(date(2027, 12, 2))) == "2027-12-02"
    assert applies_from(with_value(ApplicabilityUnknown(reason="not read"))) == "unknown"
    assert applies_from(with_value(ApplicabilityUnchanged())) == "unchanged"


def test_svc_load_sentences_keep_text_fallback_and_citations_then_the_note() -> None:
    payload, loads = loads_of("house-rules", "v2")
    record = payload.changes[0]
    (citation,) = record.sentences[0].citations
    sentence = {
        "text": record.sentences[0].text,
        "fallback": record.sentences[0].fallback,
        "citations": [{"label": citation.label, "url": citation.url}],
    }
    assert loads[0].sentences == (sentence,)
    note = Sentence(text="The date in the text changed.", fallback=True)
    noted = record.model_copy(update={"applicability_note": note})
    assert sentences_json(noted) == (
        sentence,
        {"text": note.text, "fallback": True, "citations": [], "note": True},
    )


def test_svc_load_provision_rows_take_the_newest_change() -> None:
    def stored(
        unit: str, version: str, heading: str | None, location: str = ""
    ) -> StoredUnitChange:
        return StoredUnitChange(
            unit=unit, to_version=version, location=location or unit, occurrence=1, heading=heading
        )

    rows = provision_loads(
        "toy",
        "house-rules",
        (
            stored("AR 2", "v2", "Bins"),
            stored("AR 2", "v3", "Bins and recycling"),
            stored("AR 2", "v3", "A paragraph", location="AR 2 PA 1"),
            stored("AN I", "v2", "Cleaning rota"),
        ),
    )
    assert [(row.unit, row.heading, row.newest_version, row.changes) for row in rows] == [
        ("AN I", "Cleaning rota", "v2", 1),
        ("AR 2", "Bins and recycling", "v3", 3),
    ]
