"""The table-entry vocabulary: frozen, defaulted, and ordered the way a reader counts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emendrix.core import (
    ActId,
    EntryGaps,
    EntryTable,
    Identifier,
    KeyRef,
    ProvisionLocation,
    ProvisionTree,
    TableEntry,
    TableReading,
    TableRef,
    VersionId,
    entry_order,
)

UNIT = ProvisionLocation.parse("AN VI")
CONTAINER = ProvisionLocation.parse("AN VI SCT 3")


def entry(key: str | None, **overrides: object) -> TableEntry:
    fields: dict[str, object] = {
        "unit": UNIT,
        "container": CONTAINER,
        "table": 1,
        "key": key,
        "rows": (("a", None, "c"),),
    }
    fields.update(overrides)
    return TableEntry.model_validate(fields)


def test_every_model_is_frozen() -> None:
    models = (
        Identifier(scheme="s", value="v"),
        TableRef(unit=UNIT, container=CONTAINER, table=1),
        EntryTable(unit=UNIT, container=CONTAINER, table=1, key_label=None),
        entry("k"),
        TableReading(),
        KeyRef(container=CONTAINER, table=1, key="k"),
        EntryGaps(),
    )
    for model in models:
        first = next(iter(type(model).model_fields))
        with pytest.raises(ValidationError):
            setattr(model, first, getattr(model, first))


def test_defaults_describe_a_row_nothing_was_read_about() -> None:
    one = entry(None)
    assert one.occurrence == 1
    assert one.group is None
    assert one.identifiers == ()
    assert one.failed_check_digits == 0
    assert one.name is None
    assert one.rows == (("a", None, "c"),)
    assert TableReading() == TableReading(tables=(), entries=(), unrecognised=())
    assert EntryGaps() == EntryGaps(
        unrecognised_tables=0, unkeyed_rows=0, failed_check_digits=0, repeated_keys=()
    )
    assert EntryTable(unit=UNIT, container=CONTAINER, table=1, key_label="Entry").header == ()


def test_ordinals_and_counts_cannot_go_below_their_floor() -> None:
    with pytest.raises(ValidationError):
        TableRef(unit=UNIT, container=CONTAINER, table=0)
    with pytest.raises(ValidationError):
        entry("k", occurrence=0)
    with pytest.raises(ValidationError):
        entry("k", failed_check_digits=-1)


def test_the_tree_carries_an_empty_reading_by_default() -> None:
    tree = ProvisionTree(act=ActId(corpus="toy", key="house"), version=VersionId("v1"))
    assert tree.table_entries == TableReading()
    again = ProvisionTree.model_validate_json(tree.model_dump_json())
    assert again == tree


def test_entry_order_reads_digit_runs_as_numbers() -> None:
    """`5` before `46a` before `68`, and the second `68` after the first."""
    assert entry_order("5") < entry_order("46a") < entry_order("68") < entry_order("68", 2)
    keys = ["68", "46a", "5", "1731", "x", "46", "4"]
    assert sorted(keys, key=entry_order) == ["4", "5", "46", "46a", "68", "1731", "x"]


def test_entry_order_keeps_distinct_spellings_apart() -> None:
    assert entry_order("05") != entry_order("5")
    assert entry_order("603-148-00-X") < entry_order("603-149-00-5")
    assert sorted(["aldicarb", "Aldicarb"], key=entry_order) == ["Aldicarb", "aldicarb"]
