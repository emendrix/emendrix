"""A typed number is read by shape and check digit, or answered with the reason it is none.

The values are ones the pipeline's committed table fixtures print, held there by its own tests;
a contract test in the `emendrix` suite holds every reading here to the pipeline's.
"""

from __future__ import annotations

import pytest

from emendrix_record.identifiers import parse_identifier

HYDROGEN_CAS = "1333-74-0"
HYDROGEN_EC = "215-605-7"
HYDROGEN_INDEX = "001-001-00-9"
SODIUM_HYDRIDE_INDEX = "001-003-00-X"
EC_REMAINDER_TEN = "418-070-1"
LEAD_EC = "231-100-4"


@pytest.mark.parametrize(
    ("typed", "reading"),
    [
        (HYDROGEN_CAS, ("cas", HYDROGEN_CAS)),
        (HYDROGEN_EC, ("ec", HYDROGEN_EC)),
        (HYDROGEN_INDEX, ("index", HYDROGEN_INDEX)),
        (SODIUM_HYDRIDE_INDEX, ("index", SODIUM_HYDRIDE_INDEX)),
        (EC_REMAINDER_TEN, ("ec", EC_REMAINDER_TEN)),
        ("0" + HYDROGEN_CAS, ("cas", HYDROGEN_CAS)),
        (HYDROGEN_CAS.replace("-", chr(0x2011)), ("cas", HYDROGEN_CAS)),
        (f"  {HYDROGEN_EC} ", ("ec", HYDROGEN_EC)),
        ("1333740", ("cas", HYDROGEN_CAS)),
    ],
)
def test_a_number_with_a_passing_check_is_read_canonically(
    typed: str, reading: tuple[str, str]
) -> None:
    assert parse_identifier(typed) == (reading,)


def test_seven_digits_are_offered_as_every_reading_that_passes() -> None:
    assert parse_identifier(LEAD_EC.replace("-", "")) == (("cas", "2311-00-4"), ("ec", LEAD_EC))


def test_an_ec_whose_remainder_is_ten_is_written_one() -> None:
    assert parse_identifier(EC_REMAINDER_TEN) == (("ec", EC_REMAINDER_TEN),)
    reason = parse_identifier(EC_REMAINDER_TEN[:-1] + "0")
    assert isinstance(reason, str)
    assert "EC check digit is 0 where its first six digits give 1" in reason


def test_a_failed_check_names_the_digit_and_what_the_digits_give() -> None:
    reason = parse_identifier(HYDROGEN_CAS[:-1] + "1")
    assert reason == (
        "'1333-74-1' is not a CAS, EC or Index No: read as CAS, its CAS check digit is 1 where "
        "its other digits give 0."
    )
    index = parse_identifier(SODIUM_HYDRIDE_INDEX.lower())
    assert isinstance(index, str) and "not shaped like" in index


def test_a_hyphenless_value_says_how_each_reading_failed() -> None:
    reason = parse_identifier(HYDROGEN_EC.replace("-", "")[:-1] + "9")
    assert isinstance(reason, str)
    assert "read as CAS 2156-05-9" in reason and "read as EC 215-605-9" in reason


@pytest.mark.parametrize("typed", ["hydrogen", "12", "", "50-00", "12345678901"])
def test_anything_else_is_answered_with_the_shapes_it_does_not_have(typed: str) -> None:
    reason = parse_identifier(typed)
    assert isinstance(reason, str)
    assert "is not shaped like a CAS number" in reason
