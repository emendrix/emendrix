"""The table-entry diff, on invented keys and cells first, then on the committed REACH packages.

The generic half runs on values with no law in them: keys like `k1`, cells like `one two`. It
is what proves `diff_entries` knows nothing about any act. The REACH half pins what the diff
reads over committed consecutive packages, measured on 2026-10-16 with the reader of that day.
**If one of those numbers moves, that is a finding to explain, not a test to update.** They
differ from the validation survey's figures in the two ways `tests/eu/test_formex_tables.py`
states: a key cell holding no well-formed Index number is unkeyed here, and identifiers come
from the profile's columns only.
"""

from __future__ import annotations

import pytest

from emendrix.core import (
    ActId,
    ChangeType,
    EntryChange,
    EntryDelta,
    EntryTable,
    ProvisionLocation,
    ProvisionNode,
    ProvisionTree,
    TableEntry,
    TableReading,
    TableRef,
    VersionId,
)
from emendrix.diff import compute_delta, diff_entries
from emendrix.diff.entries import plain, profiled_units
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.http import CellarHttp
from eu_pins import FIXTURE_DIR, OBSERVED_ON, REACH, package

UNIT = ProvisionLocation.parse("AN I")
OTHER_UNIT = ProvisionLocation.parse("AN II")
ACT = ActId(corpus="toy", key="tables")


# --------------------------------------------------------------------------- builders


def table(
    container: str = "AN I", ordinal: int = 1, key_label: str | None = "No", unit: str = "AN I"
) -> EntryTable:
    return EntryTable(
        unit=ProvisionLocation.parse(unit),
        container=ProvisionLocation.parse(container),
        table=ordinal,
        key_label=key_label,
        header=(("No", "Text"),),
    )


def entry(
    key: str | None,
    *rows: tuple[str | None, ...],
    container: str = "AN I",
    ordinal: int = 1,
    occurrence: int = 1,
    group: str | None = None,
    name: str | None = None,
    failed: int = 0,
    unit: str = "AN I",
) -> TableEntry:
    return TableEntry(
        unit=ProvisionLocation.parse(unit),
        container=ProvisionLocation.parse(container),
        table=ordinal,
        key=key,
        occurrence=occurrence,
        group=group,
        rows=rows or ((key, f"text of {key}"),),
        failed_check_digits=failed,
        name=name,
    )


def reading(
    *entries: TableEntry,
    tables: tuple[EntryTable, ...] = (table(),),
    unrecognised: tuple[TableRef, ...] = (),
) -> TableReading:
    return TableReading(tables=tables, entries=entries, unrecognised=unrecognised)


def kinds(delta: EntryDelta) -> list[tuple[str, str, int]]:
    return [(change.kind, change.key, change.occurrence) for change in delta.changes]


# --------------------------------------------------------------------------- the three kinds


def test_added_removed_and_amended_entries_are_told_apart() -> None:
    before = reading(entry("k1"), entry("k2", ("k2", "old words")), entry("k3"))
    after = reading(entry("k1"), entry("k2", ("k2", "new words")), entry("k4"))
    delta = diff_entries(before, after, UNIT)
    assert kinds(delta) == [("amended", "k2", 1), ("removed", "k3", 1), ("added", "k4", 1)]
    assert delta.unchanged == 1 and delta.whitespace_only == 0
    amended, removed, added = delta.changes
    assert amended.before is not None and amended.after is not None
    assert amended.before.rows == (("k2", "old words"),)
    assert amended.after.rows == (("k2", "new words"),)
    assert removed.after is None and removed.before is not None
    assert added.before is None and added.after is not None
    assert all(change.typography_only is False for change in delta.changes)


def test_an_entry_whose_block_heading_moved_is_amended() -> None:
    before = reading(entry("k1", group="Group A"))
    after = reading(entry("k1", group="Group B"))
    assert kinds(diff_entries(before, after, UNIT)) == [("amended", "k1", 1)]


def test_whitespace_only_differences_are_counted_and_are_not_changes() -> None:
    before = reading(entry("k1", ("k1", "one two\n  three")), entry("k2", ("k2", "x", None)))
    after = reading(entry("k1", ("k1", "one  two three ")), entry("k2", ("k2", "x", None)))
    delta = diff_entries(before, after, UNIT)
    assert delta.changes == ()
    assert (delta.unchanged, delta.whitespace_only) == (1, 1)


def test_a_span_covered_cell_is_not_the_same_as_an_empty_one() -> None:
    """`None` compares as `None`: a cell the row lacks is not a cell holding nothing."""
    before = reading(entry("k1", ("k1", None)))
    after = reading(entry("k1", ("k1", "")))
    assert kinds(diff_entries(before, after, UNIT)) == [("amended", "k1", 1)]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("2,4-D", "2,4" + chr(0x2013) + "D"),
        ("ethyl ene", "ethylene"),
        (chr(0x00C0) + " propos", "A propos"),
        ("a " + chr(0x2212) + " b", "a-b"),
    ],
)
def test_spacing_dash_forms_and_accents_label_an_amendment_as_typography_only(
    old: str, new: str
) -> None:
    delta = diff_entries(reading(entry("k1", ("k1", old))), reading(entry("k1", ("k1", new))), UNIT)
    assert kinds(delta) == [("amended", "k1", 1)]
    assert delta.changes[0].typography_only is True
    assert delta.typography_only == 1


def test_a_word_level_difference_is_not_typography() -> None:
    delta = diff_entries(
        reading(entry("k1", ("k1", "two words"))), reading(entry("k1", ("k1", "three words"))), UNIT
    )
    assert delta.changes[0].typography_only is False
    assert delta.typography_only == 0


def test_the_fold_is_the_measured_one() -> None:
    dashes = " ".join(chr(code) for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212))
    assert plain(chr(0x00C0) + " propos " + dashes + " x") == "Apropos------x"
    assert plain("  a\tb" + chr(0x00A0) + "c  ") == "abc"


# --------------------------------------------------------------------------- repeated keys


def test_a_key_printed_equally_often_on_both_sides_pairs_by_occurrence() -> None:
    before = reading(entry("k1", ("k1", "first")), entry("k1", ("k1", "second"), occurrence=2))
    after = reading(entry("k1", ("k1", "first")), entry("k1", ("k1", "changed"), occurrence=2))
    delta = diff_entries(before, after, UNIT)
    assert kinds(delta) == [("amended", "k1", 2)]
    assert delta.unchanged == 1 and delta.unpaired == ()
    for gaps in (delta.gaps_before, delta.gaps_after):
        assert [(ref.container.canonical, ref.table, ref.key) for ref in gaps.repeated_keys] == [
            ("AN I", 1, "k1")
        ]


def test_a_key_printed_a_different_number_of_times_is_unpaired_and_not_diffed() -> None:
    before = reading(entry("k1", ("k1", "first")), entry("k2"))
    after = reading(
        entry("k1", ("k1", "first")), entry("k1", ("k1", "again"), occurrence=2), entry("k2")
    )
    delta = diff_entries(before, after, UNIT)
    assert delta.changes == ()
    assert [(ref.container.canonical, ref.table, ref.key) for ref in delta.unpaired] == [
        ("AN I", 1, "k1")
    ]
    assert delta.unchanged == 1, "the other key is still compared"
    assert delta.gaps_before.repeated_keys == ()
    assert [ref.key for ref in delta.gaps_after.repeated_keys] == ["k1"]


def test_several_unpaired_keys_are_listed_in_natural_order_whatever_the_input_order() -> None:
    before = reading(entry("k10"), entry("k9"), entry("k2"))
    after = reading(
        entry("k2"),
        entry("k2", occurrence=2),
        entry("k9"),
        entry("k9", occurrence=2),
        entry("k10"),
        entry("k10", occurrence=2),
    )
    delta = diff_entries(before, after, UNIT)
    assert [ref.key for ref in delta.unpaired] == ["k2", "k9", "k10"]
    assert [ref.key for ref in delta.gaps_after.repeated_keys] == ["k2", "k9", "k10"]


# --------------------------------------------------------------------------- gaps and scope


def test_unkeyed_rows_are_never_paired_and_are_counted_on_each_side() -> None:
    before = reading(entry(None, ("", "a")), entry("k1"))
    after = reading(entry(None, ("", "a")), entry(None, ("", "b"), failed=2), entry("k1"))
    delta = diff_entries(before, after, UNIT)
    assert delta.changes == () and delta.unchanged == 1
    assert (delta.gaps_before.unkeyed_rows, delta.gaps_after.unkeyed_rows) == (1, 2)
    assert (delta.gaps_before.failed_check_digits, delta.gaps_after.failed_check_digits) == (0, 2)


def test_unrecognised_tables_are_counted_for_the_unit_alone() -> None:
    mine = TableRef(unit=UNIT, container=UNIT, table=2)
    other = TableRef(unit=OTHER_UNIT, container=OTHER_UNIT, table=1)
    before = reading(entry("k1"), unrecognised=(mine, other))
    after = reading(entry("k1"), unrecognised=(other,))
    delta = diff_entries(before, after, UNIT)
    assert (delta.gaps_before.unrecognised_tables, delta.gaps_after.unrecognised_tables) == (1, 0)
    assert profiled_units(before) == {"AN I", "AN II"}


def test_entries_of_another_unit_are_not_compared() -> None:
    before = reading(entry("k1"), entry("k9", unit="AN II", container="AN II"))
    after = reading(entry("k1", ("k1", "moved")))
    delta = diff_entries(before, after, UNIT)
    assert kinds(delta) == [("amended", "k1", 1)]
    assert delta.gaps_before.unkeyed_rows == 0


def test_a_renumbered_unit_is_read_at_its_old_location_on_the_older_side() -> None:
    before = reading(
        entry("k1", unit="AN II", container="AN II"),
        tables=(table(container="AN II", unit="AN II"),),
    )
    after = reading(entry("k1", ("k1", "moved")))
    delta = diff_entries(before, after, UNIT, unit_before=OTHER_UNIT)
    assert kinds(delta) == [("amended", "k1", 1)]


# --------------------------------------------------------------------------- order and tables


def test_changes_sort_by_table_position_then_natural_key_then_occurrence() -> None:
    second = table(container="AN I SCT 2", ordinal=1)
    after = reading(
        entry("10"),
        entry("9"),
        entry("46a"),
        entry("5"),
        entry("5", occurrence=2),
        entry("2", container="AN I SCT 2"),
        tables=(table(), second),
    )
    before = reading(entry("5"), entry("5", occurrence=2), tables=(table(), second))
    before = before.model_copy(update={"entries": ()})
    delta = diff_entries(before, after, UNIT)
    assert kinds(delta) == [
        ("added", "5", 1),
        ("added", "5", 2),
        ("added", "9", 1),
        ("added", "10", 1),
        ("added", "46a", 1),
        ("added", "2", 1),
    ]


def test_tables_are_the_newer_sides_where_both_have_one_and_the_older_ones_after() -> None:
    old_only = table(container="AN I SCT 9", ordinal=1)
    new_head = table().model_copy(update={"header": (("No", "Text", "More"),)})
    before = reading(entry("k1", container="AN I SCT 9"), tables=(table(), old_only))
    after = reading(entry("k1"), tables=(new_head,))
    delta = diff_entries(before, after, UNIT)
    assert delta.tables == (new_head, old_only)
    assert kinds(delta) == [("added", "k1", 1), ("removed", "k1", 1)]
    assert [change.container.canonical for change in delta.changes] == ["AN I", "AN I SCT 9"]


def test_two_runs_over_the_same_readings_are_byte_identical() -> None:
    before = reading(entry("k1"), entry("k2", ("k2", "old")))
    after = reading(entry("k2", ("k2", "new")), entry("k3"))
    first = diff_entries(before, after, UNIT).model_dump_json()
    second = diff_entries(before, after, UNIT).model_dump_json()
    assert first == second


def test_an_entry_change_refuses_sides_that_contradict_its_kind() -> None:
    with pytest.raises(ValueError, match="added"):
        EntryChange(kind="added", container=UNIT, table=1, key="k1", before=entry("k1"))
    with pytest.raises(ValueError, match="removed"):
        EntryChange(kind="removed", container=UNIT, table=1, key="k1", after=entry("k1"))
    with pytest.raises(ValueError, match="both sides"):
        EntryChange(kind="amended", container=UNIT, table=1, key="k1", after=entry("k1"))
    with pytest.raises(ValueError, match="typography"):
        EntryChange(
            kind="added", container=UNIT, table=1, key="k1", after=entry("k1"), typography_only=True
        )


# --------------------------------------------------------------------------- in the delta


def tree(version: str, texts: dict[str, str], table_entries: TableReading) -> ProvisionTree:
    return ProvisionTree(
        act=ACT,
        version=VersionId(version),
        roots=tuple(
            ProvisionNode.from_plain_text(location, text) for location, text in texts.items()
        ),
        table_entries=table_entries,
    )


def test_the_delta_carries_an_entry_diff_only_for_units_with_a_profiled_table() -> None:
    before = tree(
        "v1",
        {"AR 1": "one", "AN I": "table one", "AN II": "gone"},
        reading(
            entry("k1"),
            entry("k2", unit="AN II", container="AN II"),
            tables=(table(), table(container="AN II", unit="AN II")),
        ),
    )
    after = tree(
        "v2",
        {"AR 1": "one changed", "AN I": "table two", "AN III": "new"},
        reading(
            entry("k1", ("k1", "changed")),
            entry("k3", unit="AN III", container="AN III"),
            tables=(table(), table(container="AN III", unit="AN III")),
        ),
    )
    delta = compute_delta(before, after)
    by_unit = {change.unit.canonical: change for change in delta.changes}
    assert by_unit["AR 1"].table_entries is None
    modified = by_unit["AN I"].table_entries
    assert modified is not None and kinds(modified) == [("amended", "k1", 1)]
    deleted = by_unit["AN II"]
    assert deleted.change_type is ChangeType.DELETED and deleted.table_entries is not None
    assert kinds(deleted.table_entries) == [("removed", "k2", 1)]
    inserted = by_unit["AN III"]
    assert inserted.change_type is ChangeType.INSERTED and inserted.table_entries is not None
    assert kinds(inserted.table_entries) == [("added", "k3", 1)]


def test_a_unit_whose_only_profiled_table_was_not_recognised_reads_as_a_gap() -> None:
    ref = TableRef(unit=UNIT, container=UNIT, table=1)
    before = tree("v1", {"AN I": "x"}, reading(tables=(), unrecognised=(ref,)))
    after = tree("v2", {"AN I": "y"}, reading(tables=(), unrecognised=(ref,)))
    (change,) = compute_delta(before, after).changes
    assert change.table_entries is not None
    assert change.table_entries.changes == ()
    assert change.table_entries.gaps_after.unrecognised_tables == 1


def test_a_tree_with_no_table_entries_yields_none_everywhere() -> None:
    before = tree("v1", {"AR 1": "a"}, TableReading())
    after = tree("v2", {"AR 1": "b"}, TableReading())
    assert [change.table_entries for change in compute_delta(before, after).changes] == [None]


# --------------------------------------------------------------------------- REACH


@pytest.fixture(scope="module")
def module_client() -> CellarClient:
    return CellarClient(
        CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR)), observed_on=OBSERVED_ON
    )


def reach_delta(client: CellarClient, before: str, after: str) -> dict[str, EntryDelta | None]:
    delta = compute_delta(
        parse_act(package(client, REACH, f"02006R1907-{before}")).tree,
        parse_act(package(client, REACH, f"02006R1907-{after}")).tree,
    )
    return {change.unit.canonical: change.table_entries for change in delta.changes}


Counts = tuple[int, int, int, int, int]
"""`(added, removed, amended, whitespace_only, unchanged)` of one unit's delta."""


def counts(delta: EntryDelta | None) -> Counts:
    assert delta is not None
    return (
        delta.count("added"),
        delta.count("removed"),
        delta.count("amended"),
        delta.whitespace_only,
        delta.unchanged,
    )


@pytest.mark.parametrize(
    ("before", "after", "unit", "expected", "keys"),
    [
        ("20160203", "20160308", "AN XVII", (0, 0, 1, 0, 1698), [("amended", "23")]),
        (
            "20170302",
            "20170704",
            "AN XIV",
            (12, 0, 0, 23, 8),
            [("added", str(n)) for n in range(32, 44)],
        ),
        ("20170302", "20170704", "AN XVII", (1, 0, 0, 581, 1124), [("added", "68")]),
        ("20210101", "20210215", "AN XIV", (0, 0, 1, 0, 53), [("amended", "42")]),
        (
            "20220301",
            "20220501",
            "AN XIV",
            (5, 0, 0, 0, 54),
            [("added", str(n)) for n in range(55, 60)],
        ),
        ("20251023", "20260511", "AN XVII", (1, 0, 0, 0, 1979), [("added", "83")]),
    ],
)
def test_the_committed_reach_pairs_read_these_entry_diffs(
    module_client: CellarClient,
    before: str,
    after: str,
    unit: str,
    expected: Counts,
    keys: list[tuple[str, str]],
) -> None:
    """Measured 2026-10-16. The 2017 pair is the re-typesetting: 604 rows moved in whitespace
    alone across the two annexes and not one of them is a change."""
    delta = reach_delta(module_client, before, after)[unit]
    assert counts(delta) == expected
    assert delta is not None
    assert [(change.kind, change.key) for change in delta.changes] == keys
    assert delta.typography_only == 0 and delta.unpaired == ()


def test_appendix_13_arrives_as_a_new_table_with_ninety_entries(
    module_client: CellarClient,
) -> None:
    """2021-01-01 to 2021-02-15: Annex XVII gains Appendix 13 whole, beside four other moves."""
    delta = reach_delta(module_client, "20210101", "20210215")["AN XVII"]
    assert counts(delta) == (91, 0, 3, 0, 1788)
    assert delta is not None
    per_table: dict[str, list[str]] = {}
    for change in delta.changes:
        per_table.setdefault(change.container.canonical, []).append(change.kind)
    assert per_table["AN XVII"] == ["amended", "amended", "amended", "added"]
    assert per_table["AN XVII APP 13"] == ["added"] * 90
    assert [c.key for c in delta.changes if c.container.canonical == "AN XVII"] == [
        "3",
        "28",
        "63",
        "75",
    ]
    assert len(delta.tables) == 9
    assert [ref.key for ref in delta.gaps_after.repeated_keys] == ["613-175-00-9"]


def test_the_eval_corpus_reach_pair_reads_its_annex_xvii_rows(module_client: CellarClient) -> None:
    """2008-10-12 to 2009-01-20 is in the eval corpus; its 40 changes include Annex XVII, whose
    main table has 31 amended rows and Appendix 2 five, with four whitespace-only rows apart."""
    deltas = reach_delta(module_client, "20081012", "20090120")
    assert len(deltas) == 40
    assert sum(1 for delta in deltas.values() if delta is not None) == 1
    assert counts(deltas["AN XVII"]) == (0, 0, 36, 4, 1254)


def test_the_first_reach_consolidation_removes_most_of_annex_iv(
    module_client: CellarClient,
) -> None:
    """2007-11-23 to 2008-10-12: Annex IV, keyed by its EC number as printed, loses 35 entries,
    gains 7 and amends 7; one value on the newer side fails its check digit and is counted."""
    deltas = reach_delta(module_client, "20071123", "20081012")
    assert set(deltas) == {"AN IV", "AN V"}
    assert deltas["AN V"] is None
    annex_iv = deltas["AN IV"]
    assert counts(annex_iv) == (7, 35, 7, 0, 26)
    assert annex_iv is not None
    assert (annex_iv.gaps_before.failed_check_digits, annex_iv.gaps_after.failed_check_digits) == (
        0,
        1,
    )
