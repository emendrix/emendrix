"""Location parsing, against the location strings the corpus actually emits."""

from typing import Any

import pytest

from emendrix.core.location import ProvisionLocation, normalize_location
from emendrix.core.location_codes import LocationCode, LocationSegment, UnknownCode

# Every string below was read out of real modification annotations of three acts on
# 2026-08-05 (`scripts/validation/results/*-annotations.txt` and the branch notices they
# were computed from).
# They are copied verbatim, including the malformed ones: this is the observed set the
# parser must cover, not a tidied version of it.
OBSERVED = (
    # the ordinary shapes
    "AR 5",
    "AR 4a",
    "AR 75d",
    "AN III",
    "AN XIV",
    "AR 5 PA 1 ALN 1 PTA (bb)",
    "AR 113 PA 3 PTA (a)",
    "AR 99 PA 4 PTA (da)",
    "AR 3 PO 14a",
    "AR 57 PA 3a",
    "AN I SCT 10.4.3",
    "AN VI PRT C SCT 6.6.2",
    "AN XI SCT 3 SBS 3.2 PTA (a) PTI (ii)",
    "AN IX PO 8.6.2 COL 2 ALN 1 TIRE 2",
    "AN XIV TAB PO 4 COL 4 PTA (c)",
    "AN XIII PO 1.3 TIRE 3",
    "AN I PT 1.4.1 FR 2",
    "AN III PO (b) PO (ii)",
    "AN I SCT A PO 1",
    "AN XVII PO 50a",
    "AN VII SBS 7.14.a",
    "AN I SBS 0.11.a",
    # legacy long spellings
    "AR 1 PA 2 ALN 2 FR 1 TEXT",
    "AN I SECTION 3.2 PO 12",
    "AN XV SECTION II PO 1",
    "AN XVII APP 2 TABL TXT",
    # codes with no value at all
    "AR 65 TXT",
    "AR 122 PA 1 TIRE",
    "AN IX ALN",
    "AN XIV TAB NOTE",
    "AN XVII APP 6 TAB TXT",
    "AN XVII NOTE A",
    # arabic annexes, trailing dots, and other things the grammar did not promise
    "AN 17",
    "AN I.7",
    "AR 2.9",
    "AN VI SECTION 4.1.",
    "AN II PO 3.6.",
    "AN XVII P.62",
    # codes outside the vocabulary, and outright malformed values
    "AR 138 PA 1 L 1 FR 2",
    "AR 3 .20 PO B)",
    "TIT XI",
    "TIS IV",
    "CONSID 61",
    "A02P1LB",
    "N17PT19P4LB",
)

RAW_TEMPLATE = (
    "{AR|http://publications.europa.eu/resource/authority/fd_370/AR} 52 "
    "{PA|http://publications.europa.eu/resource/authority/fd_370/PA} 4"
)


@pytest.mark.parametrize("raw", OBSERVED)
def test_parse_round_trips(raw: str) -> None:
    assert ProvisionLocation.parse(raw).canonical == normalize_location(raw)


@pytest.mark.parametrize("raw", OBSERVED)
def test_canonical_is_a_fixed_point(raw: str) -> None:
    once = ProvisionLocation.parse(raw)
    assert ProvisionLocation.parse(once.canonical) == once


def test_normalize_strips_the_authority_template() -> None:
    assert normalize_location(RAW_TEMPLATE) == "AR 52 PA 4"
    assert ProvisionLocation.parse(RAW_TEMPLATE).canonical == "AR 52 PA 4"


def test_segments_are_typed() -> None:
    location = ProvisionLocation.parse("AR 5 PA 1 ALN 1 PTA (bb)")
    assert [segment.code for segment in location.segments] == [
        LocationCode.AR,
        LocationCode.PA,
        LocationCode.ALN,
        LocationCode.PTA,
    ]
    assert [segment.value for segment in location.segments] == ["5", "1", "1", "(bb)"]


def test_a_code_with_no_value_parses_as_a_segment() -> None:
    location = ProvisionLocation.parse("AN XIV TAB NOTE")
    assert [(str(s.code), s.value) for s in location.segments] == [
        ("AN", "XIV"),
        ("TAB", None),
        ("NOTE", None),
    ]


def test_unknown_codes_are_carried_not_rejected() -> None:
    location = ProvisionLocation.parse("AR 138 PA 1 L 1 FR 2")
    unknown = [s.code for s in location.segments if isinstance(s.code, UnknownCode)]
    assert unknown == [UnknownCode(raw="L")]
    assert location.canonical == "AR 138 PA 1 L 1 FR 2"


def test_a_wholly_malformed_value_is_one_unknown_segment() -> None:
    location = ProvisionLocation.parse("A02P1LB")
    assert location.segments[0].code == UnknownCode(raw="A02P1LB")
    assert location.segments[0].value is None


def test_legacy_spellings_are_preserved_but_fold_for_comparison() -> None:
    location = ProvisionLocation.parse("AN I SECTION 3.2 PO 12")
    code = location.segments[1].code
    assert code == LocationCode.SECTION
    assert isinstance(code, LocationCode)
    assert code.preferred is LocationCode.SCT
    assert location.canonical == "AN I SECTION 3.2 PO 12"


def test_empty_location_is_rejected() -> None:
    with pytest.raises(ValueError, match="segments"):
        ProvisionLocation.parse("   ")


def test_containment() -> None:
    article = ProvisionLocation.parse("AR 5")
    paragraph = ProvisionLocation.parse("AR 5 PA 1")
    other = ProvisionLocation.parse("AR 50")

    assert article.contains(paragraph)
    assert paragraph.is_within(article)
    assert article.contains(article)
    assert not paragraph.contains(article)
    assert not article.contains(other)
    assert not other.is_within(article)


def test_top_level_is_the_unit_of_change() -> None:
    assert ProvisionLocation.parse("AR 5 PA 1 ALN 1 PTA (bb)").top_level.canonical == "AR 5"
    assert ProvisionLocation.parse("AN VI PRT C SCT 6.6.2").top_level.canonical == "AN VI"
    assert ProvisionLocation.parse("TIT XI").top_level.canonical == "TIT XI"


def test_child_extends_a_path() -> None:
    child = ProvisionLocation.parse("AR 5").child(LocationCode.PA, "1")
    assert child.canonical == "AR 5 PA 1"
    assert child.is_within(ProvisionLocation.parse("AR 5"))


def test_ordering_is_numeric_then_alphabetic() -> None:
    raw = ["AR 10", "AR 4a", "AR 9", "AR 4", "AR 100"]
    ordered = sorted(ProvisionLocation.parse(value) for value in raw)
    assert [location.canonical for location in ordered] == [
        "AR 4",
        "AR 4a",
        "AR 9",
        "AR 10",
        "AR 100",
    ]


def test_annexes_order_by_roman_value() -> None:
    raw = ["AN XIV", "AN I", "AN IX", "AN III", "AN V"]
    ordered = sorted(ProvisionLocation.parse(value) for value in raw)
    assert [location.canonical for location in ordered] == [
        "AN I",
        "AN III",
        "AN V",
        "AN IX",
        "AN XIV",
    ]


def test_articles_sort_before_annexes() -> None:
    ordered = sorted(ProvisionLocation.parse(value) for value in ["AN I", "AR 100"])
    assert [location.canonical for location in ordered] == ["AR 100", "AN I"]


def test_a_provision_sorts_before_its_own_sub_provisions() -> None:
    raw = ["AR 5 PA 2", "AR 5", "AR 5 PA 1", "AR 6"]
    ordered = sorted(ProvisionLocation.parse(value) for value in raw)
    assert [location.canonical for location in ordered] == [
        "AR 5",
        "AR 5 PA 1",
        "AR 5 PA 2",
        "AR 6",
    ]


def test_human_rendering() -> None:
    assert ProvisionLocation.parse("AR 5 PA 1 PTA (bb)").human == "Art. 5(1)(bb)"
    assert ProvisionLocation.parse("AN III").human == "Annex III"
    assert ProvisionLocation.parse("AN VI PRT C SCT 6.6.2").human == "Annex VI part C section 6.6.2"
    assert ProvisionLocation.parse("AR 65 TXT").human == "Art. 65 text"
    assert ProvisionLocation.parse("TIS IV").human == "TIS IV"


def test_a_head_with_no_number_reads_as_its_word() -> None:
    """A change keyed to a whole annex or title is a real form, and its code is not a word.

    Eight committed changes carry such a head (counted 2026-09-03), and until then they
    rendered as the raw metadata code, which reached readers as a search label. A code the
    vocabulary has no reading for keeps the spelling the corpus used, because capitalising it
    would be a guess at a reading and the vocabulary is empirical.
    """
    assert ProvisionLocation.parse("AN").human == "Annex"
    assert ProvisionLocation.parse("TIT").human == "Title"
    assert ProvisionLocation.parse("TIT XI").human == "Title XI"
    assert ProvisionLocation.parse("PRT I").human == "Part I"
    assert ProvisionLocation.parse("AR").human == "Article"
    assert ProvisionLocation.parse("CHA 1").human == "CHA 1"
    assert ProvisionLocation.parse("PA 1").human == "PA 1"


def test_locations_are_hashable_and_live_in_sets() -> None:
    first = ProvisionLocation.parse("AR 5 PA 1")
    second = ProvisionLocation.parse("AR 5 PA 1")
    assert first == second
    assert len({first, second, ProvisionLocation.parse("AR 5")}) == 2


def test_json_round_trip_is_the_canonical_string() -> None:
    location = ProvisionLocation.parse("AR 5 PA 1 ALN 1 PTA (bb)")
    # A location serialises to its canonical string, so the JSON output stays readable and
    # byte-stable; `model_dump`'s declared return type does not know that.
    dumped: Any = location.model_dump()
    assert dumped == "AR 5 PA 1 ALN 1 PTA (bb)"
    assert ProvisionLocation.model_validate(dumped) == location


def test_json_round_trip_keeps_unknown_codes() -> None:
    location = ProvisionLocation.parse("CONSID 61")
    assert ProvisionLocation.model_validate(location.model_dump()) == location


def test_a_segment_value_cannot_smuggle_in_another_segment() -> None:
    """A value with a space would re-parse into a different path, breaking round-trip."""
    with pytest.raises(ValueError, match="pattern"):
        LocationSegment(code=LocationCode.AR, value="5 PA 1")
