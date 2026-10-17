"""`find_substance` over the record fixture and the toy substance files beside its catalogue.

The substance files (see `test_record_substances.py` in the `emendrix-record` member) give one
CAS number, `1333-74-0`, an entry in each of the two toy acts and three recorded changes; its EC
number has a file of its own and its Index No lands on the CAS page. The numbers are values the
pipeline's committed table fixtures print, used only because their check digits pass.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.tools_substance import ABSENCE, SubstanceAnswer, find_substance
from emendrix_record.models import ActIndex, EventRow
from emendrix_record.record import Record, SubstanceRead

RECORD_TESTS = Path(__file__).resolve().parents[2] / "emendrix-record" / "tests"
CHANGELOGS = RECORD_TESTS / "fixtures" / "changelogs"

CAS = "1333-74-0"
EC = "215-605-7"
INDEX = "001-001-00-9"
EC_REMAINDER_TEN = "418-070-1"

FORBIDDEN = (
    "restricted",
    "banned",
    "prohibited",
    "permitted",
    "allowed",
    "approved",
    "authorised",
    "regulated",
    "compliant",
    "safe",
    "hazardous",
    "listed as",
    "classified as",
    "not found in",
    "not covered by",
)
"""Words the answer's own prose never uses about a number: it says where one appears."""


@pytest.fixture
def record(tmp_path: Path) -> Record:
    site = tmp_path / "v1"
    shutil.copytree(RECORD_TESTS / "substances", site)
    shutil.copy(RECORD_TESTS / "fixtures" / "catalogue.json", site / "catalogue.json")
    return Record(CHANGELOGS, site / "catalogue.json")


def _prose(answer: SubstanceAnswer) -> list[str]:
    """Every sentence the tool writes, not the rows it quotes."""
    return [answer.sentence, *(reading.sentence for reading in answer.readings)]


def test_a_number_is_found_in_both_acts_with_its_rows(record: Record) -> None:
    answer = find_substance(record, CAS)
    assert answer.unavailable == ()
    (reading,) = answer.readings
    assert (reading.scheme, reading.value, reading.lands_on) == ("cas", CAS, None)
    assert [(entry.act, entry.entry.key, entry.key_label) for entry in reading.entries] == [
        ("garden-rules", "7", "No"),
        ("house-rules", "2", "No"),
    ]
    assert reading.entries[1].entry.rows[0][2] == CAS
    assert reading.sentence.startswith(f"CAS {CAS} appears in 2 entries of 2 acts")


def test_the_history_is_newest_first_with_the_acts_each_change_names(record: Record) -> None:
    (reading,) = find_substance(record, CAS).readings
    history = [traced.change for traced in reading.history]
    assert [(c.act, c.version, c.kind, c.dated.isoformat()) for c in history] == [
        ("house-rules", "v3", "amended", "2026-08-09"),
        ("garden-rules", "v2", "added", "2026-08-06"),
        ("house-rules", "v2", "added", "2026-08-06"),
    ]
    assert [c.amending_acts for c in history] == [("toy-amendment-2",), (), ("toy-amendment-1",)]
    assert history[0].before is not None and history[0].after is not None
    assert history[0].event == "https://example.org/acts/house-rules/v3/#v3-an-i"


def test_every_change_names_its_payload_and_that_payloads_hash(record: Record) -> None:
    (reading,) = find_substance(record, CAS).readings
    for traced in reading.history:
        index = record.act(f"toy/{traced.change.act}")
        assert isinstance(index, ActIndex)
        event = Record.event(index, traced.change.version)
        assert isinstance(event, EventRow)
        assert (traced.payload, traced.payload_sha256) == (event.path, event.sha256)
        assert traced.payload_unavailable is None


def test_the_answer_names_the_file_it_read_and_its_hash(record: Record) -> None:
    (reading,) = find_substance(record, CAS).readings
    read = record.substance("cas", CAS)
    assert isinstance(read, SubstanceRead)
    assert (reading.file, reading.sha256) == (read.path, read.sha256)
    assert reading.page == "https://example.org/substances/cas-1333-74-0/"


@pytest.mark.parametrize("typed", ["1333740", "0" + CAS, f" {CAS.replace('-', chr(0x2011))} "])
def test_a_number_typed_without_hyphens_or_loosely_is_read(record: Record, typed: str) -> None:
    answer = find_substance(record, typed)
    assert [(one.scheme, one.value) for one in answer.readings] == [("cas", CAS)]
    assert len(answer.readings[0].entries) == 2


def test_an_ec_number_reads_its_own_file(record: Record) -> None:
    (reading,) = find_substance(record, EC.replace("-", "")).readings
    assert (reading.scheme, reading.value, reading.file) == ("ec", EC, f"substances/ec-{EC}.json")


def test_an_index_no_is_answered_with_the_page_its_entry_lands_on(record: Record) -> None:
    (reading,) = find_substance(record, INDEX).readings
    assert (reading.scheme, reading.value) == ("index", INDEX)
    assert reading.lands_on is not None
    assert (reading.lands_on.scheme, reading.lands_on.value) == ("cas", CAS)
    assert reading.file == f"substances/cas-{CAS}.json"
    assert reading.sentence.startswith(f"Index No {INDEX} (CAS {CAS}) appears in 2 entries")


def test_an_index_no_with_no_page_says_why(record: Record) -> None:
    (reading,) = find_substance(record, "001-003-00-X").readings
    assert reading.entries == () and reading.file is None
    assert reading.sentence == (
        "Index No 001-003-00-X lands on no CAS or EC page: no entry in the record prints it "
        "beside a CAS or EC number, and an Index No has no page of its own."
    )


def test_absence_is_said_in_the_one_sentence(record: Record) -> None:
    answer = find_substance(record, "309-00-2")
    (reading,) = answer.readings
    assert reading.entries == () and reading.history == ()
    assert reading.sentence == f"CAS 309-00-2: {ABSENCE}"
    assert ABSENCE == (
        "No entry in the record prints this number. Many entries name a group of substances and "
        "print no number, so absence here is not absence from the law."
    )
    assert answer.unavailable == ()


def test_an_ec_whose_remainder_is_ten_is_accepted(record: Record) -> None:
    (reading,) = find_substance(record, EC_REMAINDER_TEN).readings
    assert (reading.scheme, reading.value) == ("ec", EC_REMAINDER_TEN)
    assert ABSENCE in reading.sentence


def test_a_failed_check_digit_is_answered_with_the_reason(record: Record) -> None:
    answer = find_substance(record, "1333-74-1")
    assert answer.readings == ()
    assert answer.sentence == (
        "'1333-74-1' is not a CAS, EC or Index No: read as CAS, its CAS check digit is 1 where "
        "its other digits give 0. Nothing was looked up."
    )


def test_a_value_that_is_no_number_is_answered_with_the_shapes(record: Record) -> None:
    answer = find_substance(record, "formaldehyde")
    assert answer.readings == ()
    assert "is not shaped like a CAS number" in answer.sentence


def test_seven_digits_answer_every_reading_that_passes(record: Record) -> None:
    answer = find_substance(record, "2311004")
    assert [(one.scheme, one.value) for one in answer.readings] == [
        ("cas", "2311-00-4"),
        ("ec", "231-100-4"),
    ]
    assert answer.sentence.startswith("'2311004' reads as more than one number, each answered.")


def test_without_a_catalogue_nothing_is_said_and_the_reason_is_given() -> None:
    answer = find_substance(Record(CHANGELOGS, None), CAS)
    assert answer.disclaimer == DISCLAIMER
    assert answer.unavailable and "given no site catalogue" in answer.unavailable[0]
    assert ABSENCE not in answer.sentence
    assert answer.readings[0].entries == ()


@pytest.mark.parametrize(
    "typed", [CAS, EC, INDEX, "001-003-00-X", "309-00-2", "1333-74-1", "x", "2311004"]
)
def test_every_answer_carries_the_disclaimer_and_none_of_the_forbidden_words(
    record: Record, typed: str
) -> None:
    answer = find_substance(record, typed)
    assert answer.model_dump()["disclaimer"] == DISCLAIMER
    for sentence in _prose(answer):
        for word in FORBIDDEN:
            assert not re.search(rf"\b{word}\b", sentence, re.IGNORECASE), (typed, word)
    for reading in answer.readings:
        if reading.entries:
            assert reading.file is not None and reading.sha256 is not None
