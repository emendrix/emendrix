"""CAS, EC and Index numbers by check digit, over values cut from the committed fixtures.

No value here is typed from memory: each is read off a fixture excerpt under
`tests/fixtures/eu/tables/` or the committed REACH package of 2026-05-11, and the first test
checks that the fixtures still print them. The derived values (a digit changed, a zero
prefixed, a hyphen swapped) are those fixture values altered in the one stated way.
"""

from __future__ import annotations

import zipfile

from emendrix.core import Identifier
from emendrix.eu.substances import SCHEMES, cas, ec, identifiers_in, index, read_identifier
from eu_pins import FIXTURE_DIR

TABLES = FIXTURE_DIR / "tables"

HYDROGEN_CAS = "1333-74-0"
HYDROGEN_EC = "215-605-7"
HYDROGEN_INDEX = "001-001-00-9"
SODIUM_HYDRIDE_INDEX = "001-003-00-X"
"""The first rows of CLP Annex VI Table 3 (`02008R1272-20200501_AN-VI_t1.xml`)."""

EC_REMAINDER_TEN = "418-070-1"
"""CLP Annex VI Table 3, row 80 excerpt: its weighted sum leaves 10, written `1`."""

ALDRIN_CAS = "309-00-2"
"""PIC Annex V Part 1 (`02012R0649-20261001_AN-V_t1.xml`)."""

MERCURY_EC = "231-106-7"
LEAD_EC = "231-100-4"
"""Batteries Annex I (`02023R1542-20250731_AN-I_t1.xml`)."""

BENZOIC_CELL = "65-85-0\n532-32-1"
"""Cosmetics Annex V entry 1's CAS cell: two numbers in one cell."""

FRUCTOSE_EC = "200-233-3"
"""REACH Annex IV, the one EC-shaped value in the corpus whose remainder is 10 and that does not
end in `1`: it fails."""

REACH_EC_TEN = "424-550-1"
APP_13_CELL = "15110-84-6,\n14110-84-6"
"""REACH Annex XVII Appendix 13: a key cell with a valid and an invalid CAS number."""


def test_the_fixtures_still_print_every_value_used_here() -> None:
    clp = (TABLES / "02008R1272-20200501_AN-VI_t1.xml").read_text(encoding="utf-8")
    for value in (
        HYDROGEN_CAS,
        HYDROGEN_EC,
        HYDROGEN_INDEX,
        SODIUM_HYDRIDE_INDEX,
        EC_REMAINDER_TEN,
    ):
        assert value in clp
    assert ALDRIN_CAS in (TABLES / "02012R0649-20261001_AN-V_t1.xml").read_text(encoding="utf-8")
    batteries = (TABLES / "02023R1542-20250731_AN-I_t1.xml").read_text(encoding="utf-8")
    assert MERCURY_EC in batteries and LEAD_EC in batteries
    cosmetics = (TABLES / "02009R1223-20150716_AN-V_t1.xml").read_text(encoding="utf-8")
    assert all(part in cosmetics for part in BENZOIC_CELL.split("\n"))
    with zipfile.ZipFile(FIXTURE_DIR / "consolidation_2006R1907_20260511.ENG.fmx4.zip") as reach:
        text = "".join(
            reach.read(name).decode("utf-8") for name in reach.namelist() if name.endswith(".xml")
        )
    assert FRUCTOSE_EC in text and REACH_EC_TEN in text
    assert all(part in text for part in APP_13_CELL.replace(",", "").split("\n"))


def test_cas_check_digit_accepts_the_printed_value_and_rejects_a_changed_digit() -> None:
    assert cas(HYDROGEN_CAS) == Identifier(scheme="cas", value=HYDROGEN_CAS)
    assert cas(ALDRIN_CAS) == Identifier(scheme="cas", value=ALDRIN_CAS)
    assert cas(HYDROGEN_CAS[:-1] + "1") is None
    assert cas(HYDROGEN_EC) is None, "an EC-shaped token is not a CAS number"


def test_ec_remainder_ten_is_written_one_and_valid() -> None:
    assert ec(HYDROGEN_EC) == Identifier(scheme="ec", value=HYDROGEN_EC)
    assert ec(EC_REMAINDER_TEN) == Identifier(scheme="ec", value=EC_REMAINDER_TEN)
    assert ec(REACH_EC_TEN) == Identifier(scheme="ec", value=REACH_EC_TEN)
    assert ec(FRUCTOSE_EC) is None
    assert ec(HYDROGEN_EC[:-1] + "8") is None


def test_index_check_character_weights_one_to_eight_with_ten_written_x() -> None:
    assert index(HYDROGEN_INDEX) == Identifier(scheme="index", value=HYDROGEN_INDEX)
    assert index(SODIUM_HYDRIDE_INDEX) == Identifier(scheme="index", value=SODIUM_HYDRIDE_INDEX)
    assert index(HYDROGEN_INDEX[:-1] + "8") is None
    assert index(SODIUM_HYDRIDE_INDEX[:-1] + "0") is None


def test_a_leading_zero_is_dropped_from_the_canonical_cas() -> None:
    assert cas("0" + HYDROGEN_CAS) == Identifier(scheme="cas", value=HYDROGEN_CAS)
    found, failed = identifiers_in("0" + HYDROGEN_CAS, ("cas",))
    assert found == (Identifier(scheme="cas", value=HYDROGEN_CAS),)
    assert failed == 0


def test_a_non_ascii_hyphen_reads_as_a_hyphen() -> None:
    odd = HYDROGEN_CAS.replace("-", chr(0x2011))
    assert cas(odd) == Identifier(scheme="cas", value=HYDROGEN_CAS)
    assert read_identifier(HYDROGEN_EC.replace("-", chr(0x2013))) == (
        Identifier(scheme="ec", value=HYDROGEN_EC),
    )


def test_a_cell_with_two_numbers_yields_both_in_order() -> None:
    found, failed = identifiers_in(BENZOIC_CELL, SCHEMES)
    assert found == (
        Identifier(scheme="cas", value="65-85-0"),
        Identifier(scheme="cas", value="532-32-1"),
    )
    assert failed == 0
    found, failed = identifiers_in(APP_13_CELL, ("cas",))
    assert found == (Identifier(scheme="cas", value="15110-84-6"),)
    assert failed == 1, "14110-84-6 fails its check digit and is counted, not returned"


def test_dash_cells_hold_nothing() -> None:
    for text in ("", "-", chr(0x2013), chr(0x2014), "/", "and others"):
        assert identifiers_in(text, SCHEMES) == ((), 0)


def test_only_the_asked_schemes_are_read_and_duplicates_collapse() -> None:
    cell = f"{HYDROGEN_CAS} {HYDROGEN_EC} {HYDROGEN_CAS}"
    assert identifiers_in(cell, ("cas",)) == ((Identifier(scheme="cas", value=HYDROGEN_CAS),), 0)
    assert identifiers_in(cell, ("ec",)) == ((Identifier(scheme="ec", value=HYDROGEN_EC),), 0)
    assert identifiers_in(cell, ("index",)) == ((), 0)


def test_hyphenless_input_offers_every_passing_reading() -> None:
    digits = HYDROGEN_CAS.replace("-", "")
    assert read_identifier(digits) == (Identifier(scheme="cas", value=HYDROGEN_CAS),)
    # Lead's EC number also passes as a CAS number once the hyphens are placed the CAS way.
    both = read_identifier(LEAD_EC.replace("-", ""))
    assert both == (
        Identifier(scheme="cas", value="2311-00-4"),
        Identifier(scheme="ec", value=LEAD_EC),
    )
    # Hydrogen's EC number passes only as an EC number.
    assert read_identifier(HYDROGEN_EC.replace("-", "")) == (
        Identifier(scheme="ec", value=HYDROGEN_EC),
    )
    assert read_identifier(" " + HYDROGEN_INDEX + " ") == (
        Identifier(scheme="index", value=HYDROGEN_INDEX),
    )
    assert read_identifier("12") == ()
    assert read_identifier("hydrogen") == ()
    assert read_identifier(FRUCTOSE_EC) == ()
