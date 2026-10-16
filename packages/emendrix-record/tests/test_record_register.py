"""The record reads an act's register, and says plainly when an act has none.

The register under `registers/` is written by the `emendrix` writer over invented house rules
and held to it by a test in that suite; it is copied into a copy of the fixture repository here,
beside the act index it belongs to, because the committed fixture tree is the writers' output
byte for byte and holds no register of its own.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from emendrix_record import DISCLAIMER
from emendrix_record.models import Register
from emendrix_record.record import REGISTER_FILE, Record, Unavailable

TESTS = Path(__file__).resolve().parent
CHANGELOGS = TESTS / "fixtures" / "changelogs"
REGISTER = TESTS / "registers" / "toy" / "house-rules" / REGISTER_FILE


@pytest.fixture
def record(tmp_path: Path) -> Record:
    target = tmp_path / "changelogs"
    shutil.copytree(CHANGELOGS, target)
    shutil.copy(REGISTER, target / "toy" / "house-rules" / REGISTER_FILE)
    return Record(target, None)


def test_the_register_reads_whole_with_its_coverage(record: Record) -> None:
    register = record.register("toy", "house-rules")
    assert isinstance(register, Register), register
    assert register.disclaimer == DISCLAIMER
    assert (register.corpus, register.key, register.version) == ("toy", "house-rules", "v3")
    assert [(entry.key, entry.occurrence) for entry in register.entries] == [
        ("2", 1),
        ("10", 1),
        ("2", 2),
        (None, 1),
    ]
    assert register.entries[0].identifiers[0].value == "100-00-5"
    assert register.coverage.unkeyed_rows == 1
    assert [ref.key for ref in register.coverage.repeated_keys] == ["2"]
    assert [ref.unit for ref in register.unrecognised] == ["AN II"]


def test_an_act_without_a_register_is_unavailable_and_says_so(record: Record) -> None:
    missing = record.register("toy", "garden-rules")
    assert isinstance(missing, Unavailable)
    assert missing.reason == "the record holds no register for toy/garden-rules"


def test_an_act_the_record_does_not_hold_is_unavailable(record: Record) -> None:
    assert isinstance(record.register("toy", "attic-rules"), Unavailable)


def test_a_register_that_does_not_parse_is_unavailable(tmp_path: Path) -> None:
    target = tmp_path / "changelogs"
    shutil.copytree(CHANGELOGS, target)
    (target / "toy" / "house-rules" / REGISTER_FILE).write_text("{}", encoding="utf-8")
    broken = Record(target, None).register("toy", "house-rules")
    assert isinstance(broken, Unavailable)
    assert "is not a register" in broken.reason
