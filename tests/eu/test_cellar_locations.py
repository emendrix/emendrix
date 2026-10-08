"""CELLAR location codes read as the units the markup names, and containers kept apart."""

from __future__ import annotations

import pytest

from emendrix.eu.cellar_locations import (
    ROMAN_LIMIT,
    ContainerKey,
    ContainerKind,
    UnconvertedAnnex,
    gap_note,
    roman,
    unit_code,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AN 4", "AN IV"),
        ("AN 5", "AN V"),
        ("AN 17", "AN XVII"),
        ("AN 4 PO 2", "AN IV PO 2"),
        ("AR 3.1", "AR 3"),
        ("AR 3.20", "AR 3"),
        ("AR 10a.2", "AR 10a"),
        ("AR 3.1 PA 2 PTA (b)", "AR 3 PA 2 PTA (b)"),
        ("{AN|http://publications.europa.eu/resource/authority/fd_370/AN} 11", "AN XI"),
    ],
)
def test_a_notation_is_rewritten_to_the_markups_spelling(raw: str, expected: str) -> None:
    assert unit_code(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "AN IV",
        "AN I PO 1.3.1 PA 2",
        "AN I.7",
        "AR 5 PA 1 ALN 1 PTA (bb)",
        "AR 77 TIT",
        "AR 4a",
        "AR 3 .20 PO B)",
        "APP 1",
    ],
)
def test_a_code_already_in_the_markups_spelling_is_left_as_written(raw: str) -> None:
    assert unit_code(raw) == raw


def test_the_mapping_is_idempotent_on_what_it_rewrote() -> None:
    once = unit_code("AN 4 PO 2")
    assert isinstance(once, str)
    assert unit_code(once) == once


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("PRT 2", ContainerKind.PART),
        ("CHA III", ContainerKind.CHAPTER),
        ("TIT XI", ContainerKind.TITLE),
        ("TIS IV", ContainerKind.SUBTITLE),
        ("SCT 2", ContainerKind.SECTION),
        ("SECTION 3", ContainerKind.SECTION_LONG),
        ("P 2", ContainerKind.P),
        ("CONSID 61", ContainerKind.RECITAL),
        ("AN", ContainerKind.UNNUMBERED_ANNEX),
        ("AN PO 3", ContainerKind.UNNUMBERED_ANNEX),
        ("TIT", ContainerKind.TITLE),
        ("CHA 1 AR 5", ContainerKind.CHAPTER),
    ],
)
def test_a_container_or_recital_is_a_counted_gap_not_a_unit(raw: str, kind: ContainerKind) -> None:
    assert unit_code(raw) == ContainerKey(kind=kind, raw=raw)


def test_an_arabic_annex_beyond_the_converter_is_refused_not_guessed() -> None:
    assert unit_code(f"AN {ROMAN_LIMIT}") == "AN L"
    assert unit_code(f"AN {ROMAN_LIMIT + 1}") == UnconvertedAnnex(raw=f"AN {ROMAN_LIMIT + 1}")
    assert unit_code("AN 0") == UnconvertedAnnex(raw="AN 0")


def test_the_roman_converter_over_its_whole_range() -> None:
    assert [roman(n) for n in (1, 4, 9, 14, 19, 40, 44, 49, 50)] == [
        "I",
        "IV",
        "IX",
        "XIV",
        "XIX",
        "XL",
        "XLIV",
        "XLIX",
        "L",
    ]
    assert roman(0) is None
    assert roman(ROMAN_LIMIT + 1) is None
    assert len({roman(n) for n in range(1, ROMAN_LIMIT + 1)}) == ROMAN_LIMIT


def test_an_empty_code_is_returned_empty_for_the_caller_to_count() -> None:
    assert unit_code("   ") == ""


def test_the_note_names_the_gaps_and_is_untouched_without_them() -> None:
    note = "3 annotations in (2008-10-12, 2009-01-20]"
    assert gap_note(note, (None, None)) == note
    assert gap_note(None, ()) is None
    chapter = ContainerKey(kind=ContainerKind.CHAPTER, raw="CHA III")
    assert gap_note(note, (None, chapter, chapter)) == (
        f"{note}; 2 annotations named a part, chapter, title or recital "
        "and are not counted as units"
    )
    assert gap_note(None, (UnconvertedAnnex(raw="AN 51"),)) == (
        "1 annotations named an annex by a number not converted"
    )
