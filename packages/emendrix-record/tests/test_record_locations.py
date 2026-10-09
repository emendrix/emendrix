"""Canonical-location containment, the typed forms read as a location, and the human form."""

from __future__ import annotations

import pytest

from emendrix_record.locations import ANNEX_LIMIT, human, parse_location, within


@pytest.mark.parametrize(
    ("inner", "outer", "expected"),
    [
        ("AR 6", "AR 6", True),
        ("AR 6 PA 1", "AR 6", True),
        ("AR 6 PA 1 ALN 1 PTA (a)", "AR 6 PA 1", True),
        ("AR 6", "AR 6 PA 1", False),
        ("AR 60", "AR 6", False),
        ("AR 6", "AR 60", False),
        ("AR 6a", "AR 6", False),
        ("AN I", "AN II", False),
        ("AN II", "AN I", False),
        ("AN I", "AN I", True),
        ("AN I", "AR 1", False),
    ],
)
def test_containment_is_by_whole_tokens(inner: str, outer: str, expected: bool) -> None:
    assert within(inner, outer) is expected


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("AR 6", "AR 6"),
        ("AN I", "AN I"),
        ("AR 6 PA 1", "AR 6 PA 1"),
        ("AR 5 PA 1 ALN 1 PTA (bb)", "AR 5 PA 1 ALN 1 PTA (bb)"),
        ("  AR   6  PA 1 ", "AR 6 PA 1"),
        ("Article 6", "AR 6"),
        ("article 6", "AR 6"),
        ("Art. 6", "AR 6"),
        ("Article 6a", "AR 6a"),
        ("Article 75d", "AR 75d"),
        ("Article 6(1)", "AR 6 PA 1"),
        ("Article 6(1a)", "AR 6 PA 1a"),
        ("Art. 6(2)", "AR 6 PA 2"),
        ("Annex I", "AN I"),
        ("Annex 1", "AN I"),
        ("Annex IV", "AN IV"),
        ("Annex 4", "AN IV"),
        ("annex iv", "AN IV"),
        ("Annex XVII", "AN XVII"),
        ("Annex 17", "AN XVII"),
        (f"Annex {ANNEX_LIMIT}", "AN XXXIX"),
    ],
)
def test_each_form_read_gives_its_canonical_location(text: str, canonical: str) -> None:
    assert parse_location(text) == canonical


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "Article",
        "Art 6 bis",
        "Article6",
        "Art. 6 bis",
        "the transparency obligations for chatbots",
        "Article 6(1)(a)",
        "Article 6(1)(a)(i)",
        "Annex 0",
        "Annex 01",
        f"Annex {ANNEX_LIMIT + 1}",
        "Annex IIII",
        "Annex XL",
        "Annex",
        "AR",
        "AR 6 pa 1",
        "PA 1",
        "Recital 12",
    ],
)
def test_anything_else_is_refused_rather_than_guessed(text: str) -> None:
    assert parse_location(text) is None


@pytest.mark.parametrize(
    ("canonical", "spelled"),
    [
        ("AR 6", "Article 6"),
        ("AR 6a", "Article 6a"),
        ("AN IV", "Annex IV"),
        ("AR 6 PA 1", "Article 6(1)"),
    ],
)
def test_the_human_form_reads_back_as_the_same_location(canonical: str, spelled: str) -> None:
    assert human(canonical) == spelled
    assert parse_location(spelled) == canonical


@pytest.mark.parametrize(
    "canonical", ["AR 5 PA 1 ALN 1 PTA (bb)", "AR 6 PA 1 PTA (a)", "AN IV PA 1", "AR 6 PO 2"]
)
def test_any_other_location_is_shown_as_it_is(canonical: str) -> None:
    assert human(canonical) == canonical
