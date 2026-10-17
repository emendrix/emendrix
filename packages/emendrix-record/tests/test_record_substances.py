"""The record reads the site build's substance files beside its catalogue, and refuses to leave.

The files under `substances/` are written through the site build's own models over the toy
acts of the fixture and held to them by a contract test in the `emendrix` suite. Their numbers
are values the pipeline's committed table fixtures print, used only because their check digits
pass; the acts, rules and names around them are invented. They are copied beside a copy of the
fixture catalogue here, because the committed fixture tree is the writers' output byte for byte
and holds no substance file of its own.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from emendrix_record import DISCLAIMER
from emendrix_record.record import SUBSTANCES_FILE, Record, SubstanceRead, Unavailable
from emendrix_record.substances import SubstanceIndex

TESTS = Path(__file__).resolve().parent
CHANGELOGS = TESTS / "fixtures" / "changelogs"
CATALOGUE = TESTS / "fixtures" / "catalogue.json"
SUBSTANCES = TESTS / "substances"

CAS = "1333-74-0"


def site_with_substances(target: Path) -> Path:
    """A site `api/v1/` directory under `target`: the fixture catalogue and the substance files."""
    shutil.copytree(SUBSTANCES, target)
    shutil.copy(CATALOGUE, target / "catalogue.json")
    return target / "catalogue.json"


@pytest.fixture
def record(tmp_path: Path) -> Record:
    return Record(CHANGELOGS, site_with_substances(tmp_path / "v1"))


def test_a_number_reads_with_its_path_and_the_hash_of_its_bytes(record: Record) -> None:
    read = record.substance("cas", CAS)
    assert isinstance(read, SubstanceRead), read
    assert read.path == f"substances/cas-{CAS}.json"
    raw = (SUBSTANCES / read.path).read_bytes()
    assert read.sha256 == hashlib.sha256(raw).hexdigest()
    document = read.document
    assert document.disclaimer == DISCLAIMER
    assert (document.scheme, document.value) == ("cas", CAS)
    assert [(entry.act, entry.entry.key) for entry in document.entries] == [
        ("garden-rules", "7"),
        ("house-rules", "2"),
    ]
    assert [change.dated.isoformat() for change in document.history] == [
        "2026-08-09",
        "2026-08-06",
        "2026-08-06",
    ]


def test_the_list_reads_whole(record: Record) -> None:
    listed = record.substances()
    assert isinstance(listed, SubstanceIndex), listed
    assert [(row.scheme, row.value) for row in listed.substances] == [
        ("cas", CAS),
        ("ec", "215-605-7"),
        ("index", "001-001-00-9"),
    ]
    assert listed.substances[2].file == listed.substances[0].file


def test_a_number_with_no_file_is_unavailable(record: Record) -> None:
    missing = record.substance("cas", "309-00-2")
    assert isinstance(missing, Unavailable)
    assert missing.reason == (
        "substances/cas-309-00-2.json could not be read beside the site catalogue"
    )


@pytest.mark.parametrize(
    "value",
    ["../../catalogue", "x/../../../etc/passwd", "a\\b", "x\x00y"],
    ids=["climbs", "climbs-deep", "backslash", "nul"],
)
def test_a_path_that_leaves_the_directory_is_refused(record: Record, value: str) -> None:
    refused = record.substance("cas", value)
    assert isinstance(refused, Unavailable)
    assert refused.reason.startswith("refused the path")


def test_a_link_out_of_the_directory_is_refused(tmp_path: Path) -> None:
    catalogue = site_with_substances(tmp_path / "v1")
    outside = tmp_path / "outside.json"
    shutil.copy(SUBSTANCES / "substances" / f"cas-{CAS}.json", outside)
    (catalogue.parent / "substances" / "cas-50-00-0.json").symlink_to(outside)
    refused = Record(CHANGELOGS, catalogue).substance("cas", "50-00-0")
    assert isinstance(refused, Unavailable)
    assert refused.reason.startswith("refused the path")


def test_without_a_catalogue_nothing_is_read_and_the_reason_says_why() -> None:
    record = Record(CHANGELOGS, None)
    for read in (record.substance("cas", CAS), record.substances()):
        assert isinstance(read, Unavailable)
        assert "given no site catalogue" in read.reason


def test_a_file_that_does_not_parse_is_unavailable(tmp_path: Path) -> None:
    catalogue = site_with_substances(tmp_path / "v1")
    (catalogue.parent / "substances" / f"cas-{CAS}.json").write_text("{}", encoding="utf-8")
    (catalogue.parent / SUBSTANCES_FILE).write_text("[]", encoding="utf-8")
    record = Record(CHANGELOGS, catalogue)
    broken = record.substance("cas", CAS)
    assert isinstance(broken, Unavailable)
    assert "is not a substance file" in broken.reason
    listed = record.substances()
    assert isinstance(listed, Unavailable)
    assert "is not a list" in listed.reason
