"""The table profiles: each matches the header the act prints, and fails closed otherwise.

The name-key figures in `profiles.py`'s docstring were read on 2026-10-16 over the CELLAR disk
cache, which tests never read. To read them again, from the repository root, with the cache
the validation script enumerates::

    uv run python - <<'EOF'
    import importlib.util, sys
    from collections import Counter
    spec = importlib.util.spec_from_file_location("st", "scripts/validation/substance_tables.py")
    st = importlib.util.module_from_spec(spec); sys.modules["st"] = st; spec.loader.exec_module(st)
    from emendrix.eu.cache import default_cache_dir
    from emendrix.eu.formex import parse_act
    from emendrix.eu.substances import profiles_for
    root = default_cache_dir() / "cellar"; cache = st.OfflineDiskCache(root)
    for act in ("32012R0649", "32019R1021", "32012R0528", "32006R1907"):
        named = {(p.container, p.table) for p in profiles_for(act) if p.key_form == "name"}
        totals, previous, versions = Counter(), None, 0
        for item in st.cached_packages(root)[act]:
            tree = parse_act(st.load(cache, item)).tree
            if not tree.roots:
                continue
            versions += 1
            keys = {}
            for e in tree.table_entries.entries:
                if (e.container.canonical, e.table) in named and e.key is not None:
                    keys.setdefault((e.container.canonical, e.table), Counter())[e.key] += 1
            totals["repeated"] += sum(1 for c in keys.values() for n in c.values() if n > 1)
            if previous is not None:
                for ident in set(previous) | set(keys):
                    before, after = set(previous.get(ident, ())), set(keys.get(ident, ()))
                    totals["added"] += len(after - before); totals["removed"] += len(before - after)
            previous = keys
        print(act, versions, dict(totals))
    EOF
"""

from __future__ import annotations

from datetime import date

from test_formex_tables import TABLES, excerpt_reading, excerpt_table, read_second_table

from emendrix.core import ProvisionLocation
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.formex.tables import read_tables
from emendrix.eu.substances import PROFILES, TableProfile, header_matches, profiles_for
from eu_pins import REACH, package

PROFILED_ACTS = {
    "32006R1907",
    "32008R1272",
    "32009R1223",
    "32012R0528",
    "32012R0649",
    "32019R1021",
    "32009R1107",
    "32023R1542",
}


def test_eight_acts_are_profiled_and_every_profile_is_dated() -> None:
    assert set(PROFILES) == PROFILED_ACTS
    assert sum(len(profiles) for profiles in PROFILES.values()) == 28
    for act, profiles in PROFILES.items():
        for profile in profiles:
            assert profile.act == act
            assert profile.verified_on == date(2026, 10, 16)
            assert profile.container.startswith(profile.unit)
            assert profile.header, "a profile without a header requirement would never fail closed"
            assert (profile.key_label is None) == (profile.key_form == "name")
    assert profiles_for("32024R1689") == ()
    assert profiles_for("32006R1907") == PROFILES["32006R1907"]


def test_positions_are_unique_within_an_act() -> None:
    for profiles in PROFILES.values():
        positions = [(p.unit, p.container, p.table) for p in profiles]
        assert len(positions) == len(set(positions))


def test_every_excerpt_matches_its_profile_header() -> None:
    """A `_t1` excerpt is read through the parser; a `_t2` one at ordinal 2 through the reader."""
    for path in sorted(TABLES.glob("*.xml")):
        if path.name.endswith("_t2.xml"):
            reading = read_second_table(path.name)
        else:
            reading = excerpt_reading(path.name)
        assert len(reading.tables) == 1, path.name
        assert reading.unrecognised == (), path.name
        assert reading.entries, path.name


def test_reach_2007_prints_einecs_in_capitals_and_the_2009_header_without_column_1(
    client: CellarClient,
) -> None:
    tree = parse_act(package(client, REACH, "02006R1907-20071123")).tree
    reading = tree.table_entries
    assert reading.unrecognised == ()
    assert [(t.container.canonical, t.table) for t in reading.tables] == [
        ("AN IV", 1),
        ("AN XVII", 1),
        ("AN XVII APP 1", 1),
        ("AN XVII APP 2", 1),
        ("AN XVII APP 4", 1),
        ("AN XVII APP 5", 1),
        ("AN XVII APP 6", 1),
        ("AN XVII APP 8", 1),
    ], "Annex XIV, Appendix 12 and Appendix 13 did not exist yet"
    annex_iv, annex_xvii = reading.tables[:2]
    assert annex_iv.header[0][0] == "EINECS No"
    designation = annex_xvii.header[0][0]
    assert designation is not None and "Column 1" not in designation
    assert designation.startswith("Designation")


def test_a_header_with_one_required_word_changed_fails_closed() -> None:
    tbl, unit, _ = excerpt_table("02012R0649-20231101_AN-I_t1.xml")
    (genuine,) = (p for p in profiles_for("32012R0649") if p.container == "AN I" and p.table == 1)
    assert read_tables([(tbl, unit, 1)], unit, (genuine,)).unrecognised == ()
    changed = genuine.model_copy(
        update={"header": ((1, "Chemical"), (2, "CAS No"), (5, "Category"))}
    )
    reading = read_tables([(tbl, unit, 1)], unit, (changed,))
    assert reading.tables == () and reading.entries == ()
    assert [(u.container.canonical, u.table) for u in reading.unrecognised] == [("AN I", 1)]
    plural = genuine.model_copy(update={"header": ((1, "Chemicals"),)})
    assert read_tables([(tbl, unit, 1)], unit, (plural,)).unrecognised != ()


def test_a_table_at_an_unprofiled_position_is_ignored_whatever_its_header_says() -> None:
    """POPs Annex I Part B prints Part A's header at ordinal 2 and is not an entry table."""
    tbl, unit, _ = excerpt_table("02019R1021-20251203_AN-I_t1.xml")
    reading = read_tables([(tbl, unit, 2)], unit, profiles_for("32019R1021"))
    assert reading.tables == () and reading.entries == () and reading.unrecognised == ()
    assert read_tables([(tbl, unit, 1)], unit, profiles_for("32019R1021")).entries


def test_header_words_match_whole_and_case_insensitively() -> None:
    profile = TableProfile(
        act="x",
        unit="AN I",
        container="AN I",
        table=1,
        header=((1, "Chemical"), (5, "Category")),
        key_form="name",
        key_col=1,
        key_label=None,
        name_col=1,
        verified_on=date(2026, 10, 16),
    )
    assert header_matches(profile, [("chemical", None, None, None, "CATEGORY")])
    assert header_matches(profile, [("Chemical name", "x", "x", "x", "Category (1)")])
    assert not header_matches(profile, [("Chemical", None, None, None, "Subcategory")])
    assert not header_matches(profile, [("Chemicals", None, None, None, "Category")])
    assert not header_matches(profile, [("Chemical", None, None, None, None)])
    assert not header_matches(profile, [("Chemical",)]), "a short header row has no column 5"
    two_rows = [(None, None, None, None, "Category"), ("Chemical", None, None, None, None)]
    assert header_matches(profile, two_rows), "any header row may carry a requirement"


def test_the_unit_location_of_an_excerpt_is_the_profiled_one() -> None:
    _, unit, container = excerpt_table("02008R1272-20200501_AN-VI_t1.xml")
    assert unit == ProvisionLocation.parse("AN VI")
    assert container == ProvisionLocation.parse("AN VI SCT 3")
