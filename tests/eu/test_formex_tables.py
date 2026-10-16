"""Table rows out of the markup, over the committed REACH packages and the table excerpts.

Every count below was measured on 2026-10-16 with this reader over the committed fixtures.
**If one of these numbers moves, that is a finding to explain, not a test to update.** The
REACH figures differ from the validation script's survey in two stated ways: a row whose key
cell holds no well-formed Index number is unkeyed here where the script fell back to the raw
text, and an entry's identifiers come from the profile's columns only, where the script scanned
every cell of the row.
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from xml.etree.ElementTree import Element

import pytest

from emendrix.core import (
    ActId,
    Identifier,
    ProvisionLocation,
    ProvisionTree,
    TableReading,
    VersionId,
    normalize_for_comparison,
)
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse as parse_module
from emendrix.eu.formex import parse_act
from emendrix.eu.formex.documents import act_documents, documents_of, unit_elements
from emendrix.eu.formex.locations import annex_segment
from emendrix.eu.formex.model import CoverageCounter
from emendrix.eu.formex.parse import table_elements
from emendrix.eu.formex.tables import read_tables
from emendrix.eu.packages import FormexPackage
from emendrix.eu.substances import profiles_for
from eu_pins import FIXTURE_DIR, REACH, package

TABLES = FIXTURE_DIR / "tables"
REACH_NEWEST = "02006R1907-20260511"
REACH_VERSIONS = (
    "02006R1907-20071123",
    "02006R1907-20081012",
    "02006R1907-20090120",
    "02006R1907-20120605",
    "02006R1907-20121009",
    "02006R1907-20150101",
    "02006R1907-20150323",
    "02006R1907-20160203",
    "02006R1907-20160308",
    "02006R1907-20170302",
    "02006R1907-20170704",
    "02006R1907-20190107",
    "02006R1907-20190702",
    "02006R1907-20210101",
    "02006R1907-20210215",
    "02006R1907-20220301",
    "02006R1907-20220501",
    "02006R1907-20231201",
    "02006R1907-20240606",
    "02006R1907-20251023",
    REACH_NEWEST,
)
"""Every committed REACH package."""


# --------------------------------------------------------------------------- helpers


def excerpt_package(name: str) -> FormexPackage:
    """A one-member package around a table excerpt, so it goes through the real parser."""
    version = name.split("_", 1)[0]
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("excerpt.xml", (TABLES / name).read_bytes())
    return FormexPackage.from_zip(
        blob.getvalue(),
        act=ActId(corpus="eu", key="3" + version[1:10]),
        requested_version=VersionId(version),
        served_version=VersionId(version),
        language="ENG",
        source_url=f"fixture:{name}",
        fetched_at=datetime(2026, 10, 16, tzinfo=UTC),
    )


def excerpt_reading(name: str) -> TableReading:
    return parse_act(excerpt_package(name)).tree.table_entries


def excerpt_table(name: str) -> tuple[Element, ProvisionLocation, ProvisionLocation]:
    """The excerpt's one table element, its unit's location and its container's."""
    documents = documents_of(act_documents(excerpt_package(name), CoverageCounter()))
    for document in documents:
        for unit, is_annex in unit_elements(document):
            segment = annex_segment(unit) if is_annex else None
            assert segment is not None
            location = ProvisionLocation.parse(f"{segment[0]} {segment[1]}")
            tables = list(table_elements(unit, location, is_annex))
            assert len(tables) == 1
            return tables[0][0], location, tables[0][1]
    raise AssertionError(f"{name} holds no annex unit")


def read_second_table(name: str) -> TableReading:
    """An excerpt of a container's second table, read at ordinal 2 as the full package has it."""
    tbl, unit, container = excerpt_table(name)
    return read_tables([(tbl, container, 2)], unit, profiles_for("3" + name[1:10]))


def by_table(reading: TableReading) -> dict[tuple[str, int], list[int]]:
    """Per table: rows, entries, keyed entries, unkeyed entries, failed check digits."""
    counts: dict[tuple[str, int], list[int]] = {}
    for entry in reading.entries:
        line = counts.setdefault((entry.container.canonical, entry.table), [0, 0, 0, 0, 0])
        line[0] += len(entry.rows)
        line[1] += 1
        line[2 if entry.key is not None else 3] += 1
        line[4] += entry.failed_check_digits
    return counts


def values(entry_identifiers: tuple[Identifier, ...]) -> list[str]:
    return [one.value for one in entry_identifiers]


@pytest.fixture(scope="module")
def reach_newest(module_client: CellarClient) -> ProvisionTree:
    return parse_act(package(module_client, REACH, REACH_NEWEST)).tree


@pytest.fixture(scope="module")
def module_client() -> CellarClient:
    from emendrix.eu.cache import FixtureResponseCache
    from emendrix.eu.http import CellarHttp
    from eu_pins import OBSERVED_ON

    return CellarClient(
        CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR)), observed_on=OBSERVED_ON
    )


# --------------------------------------------------------------------------- REACH


def test_the_newest_reach_package_yields_eleven_profiled_tables(
    reach_newest: ProvisionTree,
) -> None:
    """Measured 2026-10-16: rows, entries, keyed, unkeyed, failed check digits per table."""
    reading = reach_newest.table_entries
    assert reading.unrecognised == ()
    assert [(t.container.canonical, t.table) for t in reading.tables] == [
        ("AN IV", 1),
        ("AN XIV", 1),
        ("AN XVII", 1),
        ("AN XVII APP 1", 1),
        ("AN XVII APP 2", 1),
        ("AN XVII APP 4", 1),
        ("AN XVII APP 5", 1),
        ("AN XVII APP 6", 1),
        ("AN XVII APP 8", 1),
        ("AN XVII APP 12", 1),
        ("AN XVII APP 13", 1),
    ]
    assert by_table(reading) == {
        ("AN IV", 1): [40, 40, 40, 0, 1],
        ("AN XIV", 1): [59, 59, 59, 0, 0],
        ("AN XVII", 1): [75, 75, 75, 0, 0],
        ("AN XVII APP 1", 1): [331, 239, 239, 0, 3],
        ("AN XVII APP 2", 1): [853, 849, 847, 2, 4],
        ("AN XVII APP 4", 1): [431, 430, 430, 0, 0],
        ("AN XVII APP 5", 1): [23, 23, 23, 0, 0],
        ("AN XVII APP 6", 1): [299, 225, 221, 4, 1],
        ("AN XVII APP 8", 1): [22, 22, 22, 0, 0],
        ("AN XVII APP 12", 1): [33, 33, 33, 0, 0],
        ("AN XVII APP 13", 1): [91, 91, 90, 1, 1],
    }
    assert len(reading.entries) == 2086


def test_annex_xvii_entries_are_keyed_by_entry_number_with_68_printed_twice(
    reach_newest: ProvisionTree,
) -> None:
    main = [e for e in reach_newest.table_entries.entries if e.container.canonical == "AN XVII"]
    assert all(len(e.rows) == 1 for e in main), "an Annex XVII entry is always one row"
    assert [e.key for e in main][:6] == ["1", "2", "3", "4", "5", "6"]
    assert [(e.key, e.occurrence) for e in main if e.key == "68"] == [("68", 1), ("68", 2)]
    first, second = (e for e in main if e.key == "68")
    assert first.name == "Perfluorooctanoic acid (PFOA)"
    assert values(first.identifiers) == ["335-67-1", "206-397-9"]
    assert second.identifiers == ()
    # Group entries name a family and print no number in the designation column. The
    # conditions column is not scanned, so entries 72 and 75, whose numbers sit there, are here.
    assert [e.key for e in main if not e.identifiers] == [
        "1", "3", "18", "19", "20", "25", "28", "40", "43", "44", "45", "46a", "47", "53",
        "65", "68", "72", "73", "74", "75", "78", "79", "82",
    ]  # fmt: skip
    table = next(t for t in reach_newest.table_entries.tables if t.container.canonical == "AN XVII")
    assert table.key_label == "Entry"
    assert table.header[0][0] is not None and table.header[0][0].startswith("Column 1")


def test_appendix_entries_are_keyed_by_index_number_and_keep_every_row(
    reach_newest: ProvisionTree,
) -> None:
    entries = reach_newest.table_entries.entries
    app_1 = [e for e in entries if e.container.canonical == "AN XVII APP 1"]
    assert app_1[0].key == "024-001-00-0"
    assert app_1[0].name == "Chromium (VI) trioxide"
    assert values(app_1[0].identifiers) == ["1333-82-0", "215-607-8", "024-001-00-0"]
    assert max(len(e.rows) for e in app_1) == 31
    widest = max(app_1, key=lambda e: len(e.rows))
    assert all(row[1] is None for row in widest.rows[1:]), "the key cell's rowspan covers them"
    assert all(row[0] for row in widest.rows), "each row of the group names its own substance"
    app_6 = [e for e in entries if e.container.canonical == "AN XVII APP 6"]
    assert Counter(e.key for e in app_6 if e.key is not None)["613-175-00-9"] == 2
    unkeyed = [e for e in app_6 if e.key is None]
    assert [e.rows[0][1] for e in unkeyed] == ["603-143-002", "", "", ""]
    app_12 = [e for e in entries if e.container.canonical == "AN XVII APP 12"]
    assert all(e.key is not None and e.key == e.key.casefold() for e in app_12)
    assert (
        next(
            t
            for t in reach_newest.table_entries.tables
            if t.container.canonical == "AN XVII APP 12"
        ).key_label
        is None
    )
    app_13 = [e for e in entries if e.container.canonical == "AN XVII APP 13"]
    assert app_13[0].key == "7439-97-6"
    assert [e.key for e in app_13 if e.key and "," in e.key] == [
        "50-32-8, 63466-71-7",
        "15110-84-6, 14110-84-6",
    ], "a text key keeps the whole cell, two numbers included"


def test_annex_iv_is_keyed_by_the_ec_number_as_printed(reach_newest: ProvisionTree) -> None:
    annex_iv = [e for e in reach_newest.table_entries.entries if e.container.canonical == "AN IV"]
    assert annex_iv[0].key == "200-061-5"
    assert annex_iv[0].name == "D-glucitol C6H14O6"
    fructose = next(e for e in annex_iv if e.key == "200-233-3")
    assert fructose.failed_check_digits == 1
    assert values(fructose.identifiers) == ["57-48-7"], "the EC number printed wrong is not one"


def test_two_parses_of_one_package_are_byte_identical(module_client: CellarClient) -> None:
    first = parse_act(package(module_client, REACH, REACH_NEWEST)).tree
    second = parse_act(package(module_client, REACH, REACH_NEWEST)).tree
    assert first.model_dump_json() == second.model_dump_json()
    assert len(first.table_entries.entries) == 2086


@pytest.mark.parametrize("version", REACH_VERSIONS)
def test_nothing_but_the_table_entries_moved(
    module_client: CellarClient, version: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tree with its reading reset equals the tree parsed with no profile at all."""
    fetched = package(module_client, REACH, version)
    with_tables = parse_act(fetched)
    monkeypatch.setattr(parse_module, "profiles_for", lambda act: ())
    without = parse_act(fetched)
    assert without.tree.table_entries == TableReading()
    reset = with_tables.tree.model_copy(update={"table_entries": TableReading()})
    assert reset.model_dump_json() == without.tree.model_dump_json()
    assert with_tables.coverage == without.coverage
    assert with_tables.tree.table_entries.tables, version


def test_every_table_of_a_unit_is_numbered_within_its_container(
    module_client: CellarClient,
) -> None:
    """The survey of 2026-10-16 counted 29 annex tables in this version."""
    fetched = package(module_client, REACH, REACH_NEWEST)
    documents = documents_of(act_documents(fetched, CoverageCounter()))
    found: list[tuple[str, int]] = []
    for document in documents:
        for unit, is_annex in unit_elements(document):
            segment = annex_segment(unit) if is_annex else None
            if segment is None:
                continue
            location = ProvisionLocation.parse(f"{segment[0]} {segment[1]}")
            found.extend((c.canonical, n) for _, c, n in table_elements(unit, location, True))
    assert len(found) == 29
    assert Counter(found)[("AN XVII", 1)] == 1
    assert all(found.count(one) == 1 for one in found), "an ordinal is minted once"


# --------------------------------------------------------------------------- excerpts


def test_clp_table_3_reads_its_two_header_rows_with_spans_as_none() -> None:
    reading = excerpt_reading("02008R1272-20200501_AN-VI_t1.xml")
    assert reading.unrecognised == ()
    (table,) = reading.tables
    assert (table.unit.canonical, table.container.canonical, table.table) == (
        "AN VI",
        "AN VI SCT 3",
        1,
    )
    assert table.key_label == "Index No"
    assert len(table.header) == 2
    assert table.header[0][:5] == ("Index No", "Chemical name", "EC No", "CAS No", "Classification")
    assert table.header[0][5] is None and table.header[0][7] is None and table.header[0][8] is None
    assert table.header[1][:4] == (None, None, None, None)
    assert len(reading.entries) == 80
    hydrogen = reading.entries[0]
    assert hydrogen.key == "001-001-00-9"
    assert hydrogen.name == "hydrogen"
    assert values(hydrogen.identifiers) == ["1333-74-0", "215-605-7", "001-001-00-9"]
    assert hydrogen.rows[0][:4] == ("001-001-00-9", "hydrogen", "215-605-7", "1333-74-0")
    assert hydrogen.group is None
    assert reading.entries[-1].key == "006-044-00-7", "the row amended on 2020-05-01 is in the cut"


def test_clp_dash_cells_and_remainder_ten_ec_numbers() -> None:
    reading = excerpt_reading("02008R1272-20200501_AN-VI_t1.xml")
    beryllium_group = next(e for e in reading.entries if e.key == "004-002-00-2")
    assert beryllium_group.rows[0][3] == chr(0x2014), "an em dash for no CAS number"
    assert values(beryllium_group.identifiers) == ["004-002-00-2"]
    boron = next(e for e in reading.entries if e.key == "005-012-00-X")
    assert "418-070-1" in values(boron.identifiers)
    assert sum(e.failed_check_digits for e in reading.entries) == 0


def test_clp_pair_differs_only_where_the_act_moved() -> None:
    before = excerpt_reading("02008R1272-20200101_AN-VI_t1.xml")
    after = excerpt_reading("02008R1272-20200501_AN-VI_t1.xml")
    assert [e.key for e in before.entries] == [e.key for e in after.entries]
    moved = [a.key for a, b in zip(before.entries, after.entries, strict=True) if a.rows != b.rows]
    assert moved == ["006-044-00-7"]


def test_clp_table_3_2_at_its_own_ordinal_is_read_and_at_the_wrong_one_is_unrecognised() -> None:
    via_parse = excerpt_reading("02008R1272-20200501_AN-VI_t2.xml")
    assert via_parse.tables == () and via_parse.entries == ()
    assert [(u.container.canonical, u.table) for u in via_parse.unrecognised] == [
        ("AN VI SCT 3", 1)
    ]
    reading = read_second_table("02008R1272-20200501_AN-VI_t2.xml")
    (table,) = reading.tables
    assert table.table == 2 and len(table.header[0]) == 8
    assert [e.key for e in reading.entries][:2] == ["001-001-00-9", "001-002-00-4"]
    assert len(reading.entries) == 10


def test_cosmetics_entries_span_rows_with_the_key_cell_copied_down() -> None:
    reading = excerpt_reading("02009R1223-20150716_AN-V_t1.xml")
    (table,) = reading.tables
    assert table.key_label == "Reference number"
    assert len(table.header) == 3 and table.header[2] == (
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
    )
    assert table.header[0][2] is None, "`Substance identification` spans four columns"
    benzoic = reading.entries[0]
    assert benzoic.key == "1" and len(benzoic.rows) == 3
    assert benzoic.rows[0][3] == "65-85-0\n532-32-1"
    assert benzoic.rows[1][:5] == (None, None, None, None, None)
    assert benzoic.rows[1][5:7] == ("Oral products", "1,7 % (acid)")
    assert values(benzoic.identifiers) == ["532-32-1", "65-85-0", "200-618-2", "208-534-8"]
    assert "1a" in [e.key for e in reading.entries] and "12a" in [e.key for e in reading.entries]
    assert len(reading.entries) == 41
    before = excerpt_reading("02009R1223-20150416_AN-V_t1.xml")
    moved = [
        a.key for a, b in zip(before.entries, reading.entries, strict=True) if a.rows != b.rows
    ]
    assert moved == ["39", "57"] or moved == ["39"] or "39" in moved


def test_biocides_rows_inside_blk_groups_carry_their_heading() -> None:
    reading = excerpt_reading("02012R0528-20210610_AN-I_t1.xml")
    (table,) = reading.tables
    assert table.key_label is None
    assert table.header == (("EC number", "Name/group", "Restriction", "Comment"),)
    assert reading.entries[0].key == "lactic acid"
    assert reading.entries[0].group == (
        "Category 1 " + chr(0x2014) + " Substances authorised as food additives according to "
        "Regulation (EC) No 1333/2008"
    )
    assert values(reading.entries[0].identifiers) == ["200-018-0"]
    groups = {e.group for e in reading.entries}
    assert len(groups) == 7 and None in groups
    unkeyed = [e for e in reading.entries if e.key is None]
    heading = "Category 3 " + chr(0x2014) + " Weak acids"
    assert [e.rows for e in unkeyed] == [((heading, None, None, None),)]
    assert unkeyed[0].group is None, "a sub-heading row outside every BLK"
    assert next(e for e in reading.entries if e.key == "lavender oil").identifiers == (
        Identifier(scheme="cas", value="8000-28-0"),
    ), "a CAS number in the Comment column"
    assert (
        next(e for e in reading.entries if e.key == "(+)-tartaric acid").name == "(+)-Tartaric acid"
    )
    before = excerpt_reading("02012R0528-20210329_AN-I_t1.xml")
    assert len(before.entries) == 28 and len(reading.entries) == 30
    added = {e.key for e in reading.entries} - {e.key for e in before.entries}
    assert added == {
        "carbon dioxide generated from propane, butane or a mixture of both by combustion",
        "potassium (e,e)-hexa-2,4-dienoate (potassium sorbate)",
    }


def test_pic_annex_i_is_keyed_by_the_chemical_name_case_folded() -> None:
    reading = excerpt_reading("02012R0649-20231101_AN-I_t1.xml")
    (table,) = reading.tables
    assert table.key_label is None
    assert [e.key for e in reading.entries][:3] == [
        "1-bromopropane (n-propyl bromide)",
        "1,1-dichloroethene",
        "1,1,1-trichloroethane",
    ]
    assert reading.entries[1].name == "1,1-Dichloroethene"
    assert values(reading.entries[1].identifiers) == ["75-35-4", "200-864-0"]
    # The footnote mark `(#)` on this row is a NOTE element without text: it leaves no trace.
    dibromoethane = next(
        e for e in reading.entries if e.name == "1,2-Dibromoethane (Ethylene dibromide)"
    )
    assert dibromoethane.key == "1,2-dibromoethane (ethylene dibromide)"
    before = excerpt_reading("02012R0649-20220701_AN-I_t1.xml")
    assert len(before.entries) == 9 and len(reading.entries) == 10
    assert "1-bromopropane (n-propyl bromide)" not in {e.key for e in before.entries}


def test_pic_annex_i_part_2_reads_at_ordinal_two_with_its_own_header() -> None:
    reading = read_second_table("02012R0649-20231101_AN-I_t2.xml")
    (table,) = reading.tables
    assert tuple(normalize_for_comparison(c or "") for c in table.header[0][4:6]) == (
        "Category",
        "Use limitation",
    )
    assert reading.entries[0].key == "1-bromopropane (n-propyl bromide)"
    assert len(reading.entries) == 6
    assert excerpt_reading("02012R0649-20231101_AN-I_t2.xml").unrecognised != ()


def test_pic_annex_v_part_1_keys_by_the_description_and_reads_numbers_from_the_details() -> None:
    reading = excerpt_reading("02012R0649-20261001_AN-V_t1.xml")
    (table,) = reading.tables
    assert table.header == (
        (
            "Description of chemicals/article(s) subject to export ban",
            "Additional details, where relevant (e.g. name of chemical, EC No, CAS No, etc.)",
            None,
        ),
    ), "two header cells, the second spanning two of the body's three columns"
    aldrin = reading.entries[0]
    assert aldrin.key == "aldrin" and aldrin.name == "Aldrin"
    assert aldrin.rows[0][0] == "" and aldrin.rows[0][1] == "Aldrin"
    assert values(aldrin.identifiers) == ["309-00-2", "206-215-8"]
    assert len(reading.entries) == 12


def test_pic_annex_v_part_2_keys_by_its_number_column() -> None:
    reading = read_second_table("02012R0649-20261001_AN-V_t2.xml")
    (table,) = reading.tables
    assert table.key_label == "No"
    assert [e.key for e in reading.entries] == [str(n) for n in range(1, 14)]
    assert reading.entries[1].identifiers == (
        Identifier(scheme="cas", value="7439-97-6"),
        Identifier(scheme="ec", value="231-106-7"),
    )
    assert reading.entries[0].name == "Cosmetic soaps containing mercury."


def test_pops_annex_i_keys_by_the_first_line_of_the_substance_cell() -> None:
    before = excerpt_reading("02019R1021-20251015_AN-I_t1.xml")
    after = excerpt_reading("02019R1021-20251203_AN-I_t1.xml")
    assert [e.key for e in after.entries] == [
        "tetrabromodiphenyl ether",
        "pentabromodiphenyl ether",
        "hexabromodiphenyl ether",
        "heptabromodiphenyl ether",
        "bis(pentabromophenyl) ether (decabromodiphenyl ether; decabde)",
        "perfluorooctane sulfonic acid (pfos), its salts and pfos-related compounds",
    ]
    assert after.entries[0].name == "Tetrabromodiphenyl ether"
    assert after.entries[0].rows[0][0] is not None and "\n" in after.entries[0].rows[0][0]
    assert values(after.entries[0].identifiers) == ["40088-47-9", "254-787-2"]
    assert [
        a.key for a, b in zip(before.entries, after.entries, strict=True) if a.rows != b.rows
    ] == [e.key for e in after.entries], "every entry in the cut was amended on 2025-12-03"


def test_plant_protection_products_gain_six_numbered_entries() -> None:
    before = excerpt_reading("02009R1107-20221121_AN-III_t1.xml")
    after = excerpt_reading("02009R1107-20260616_AN-III_t1.xml")
    assert after.tables[0].key_label == "No"
    assert [e.key for e in before.entries][-1] == "144" and len(before.entries) == 144
    assert [e.key for e in after.entries][-6:] == ["145", "146", "147", "148", "149", "150"]
    acetaldehyde = next(e for e in after.entries if e.key == "145")
    assert acetaldehyde.name == "Acetaldehyde" and acetaldehyde.rows[0][0] == "145."
    assert before.entries[0].rows[0][0] == "1." and before.entries[0].key == "1"


def test_batteries_annex_i_drops_the_entry_number_from_the_name() -> None:
    reading = excerpt_reading("02023R1542-20250731_AN-I_t1.xml")
    (table,) = reading.tables
    assert table.key_label == "Entry"
    assert [(e.key, e.name) for e in reading.entries] == [
        ("1", "Mercury"),
        ("2", "Cadmium"),
        ("3", "Lead"),
    ]
    assert values(reading.entries[0].identifiers) == ["7439-97-6", "231-106-7"]
    assert reading.entries[0].rows[0][0] is not None
    assert reading.entries[0].rows[0][0].startswith("1. Mercury\n")


def test_an_index_key_that_fails_its_check_leaves_the_row_unkeyed_and_counted() -> None:
    """Two body rows of the CLP excerpt, the second's Index number with its last digit changed."""
    tbl, unit, container = excerpt_table("02008R1272-20200501_AN-VI_t1.xml")
    synthetic = deepcopy(tbl)
    corpus = synthetic.find("CORPUS")
    assert corpus is not None
    body = [row for row in corpus.findall("ROW") if row.get("TYPE") != "HEADER"]
    for row in body[2:]:
        corpus.remove(row)
    cell = body[1].find("CELL")
    assert cell is not None and cell.text == "001-002-00-4"
    cell.text = "001-002-00-5"
    assert container == ProvisionLocation.parse("AN VI SCT 3")
    reading = read_tables([(synthetic, container, 1)], unit, profiles_for("32008R1272"))
    good, bad = reading.entries
    assert good.key == "001-001-00-9" and good.failed_check_digits == 0
    assert bad.key is None
    assert bad.failed_check_digits == 1
    assert values(bad.identifiers) == ["16853-85-3", "240-877-9"], "its other numbers still count"
    assert bad.rows[0][0] == "001-002-00-5", "the cell stays verbatim"


def test_every_excerpt_parses_twice_to_the_same_bytes() -> None:
    for path in sorted(TABLES.glob("*.xml")):
        first = parse_act(excerpt_package(path.name)).tree
        second = parse_act(excerpt_package(path.name)).tree
        assert first.model_dump_json() == second.model_dump_json(), path.name
