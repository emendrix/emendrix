"""Each change's moved table rows are stored as hits, one per CAS or EC number and side.

The committed record fixture predates table entries, and it is held byte for byte to what the
pipeline's writers produce, so these tests give one copy of it a table-entry diff the way a
repair would: the payload rewritten, then the act index and the root index naming its hash. The
numbers are well-formed and check-digit valid; the rows around them are a toy's.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from emendrix_record.payload import Payload
from emendrix_service.db import Db
from emendrix_service.db.tables import TableHit
from emendrix_service.load.models import TableHitLoad
from emendrix_service.load.rows import table_hit_loads
from tests.test_svc_load_rows import loads_of
from tests.test_svc_load_run import CountingRecord, Json, copy_record, edit_payload, run

pytestmark = pytest.mark.anyio

TABLED = ("house-rules", "v3")
"""The event given a table-entry diff: the one the notifier tests publish after going live."""

UNIT = "AN I"
"""The change of that event the diff rides on."""

DUST = "Dust of the shelves; including the shelf above the radiator and behind it"


def entry(table: int, key: str, *numbers: tuple[str, str], name: str | None = None) -> Json:
    """One table row group carrying `numbers`, as a payload stores it."""
    return {
        "unit": UNIT,
        "container": UNIT,
        "table": table,
        "key": key,
        "occurrence": 1,
        "group": None,
        "rows": [[key, name, *(value for _, value in numbers)]],
        "identifiers": [{"scheme": scheme, "value": value} for scheme, value in numbers],
        "failed_check_digits": 0,
        "name": name,
    }


def moved(kind: str, table: int, key: str, before: Json | None, after: Json | None) -> Json:
    return {
        "kind": kind,
        "container": UNIT,
        "table": table,
        "key": key,
        "occurrence": 1,
        "typography_only": False,
        "before": before,
        "after": after,
    }


def table_entries() -> Json:
    """Three moved rows: a labelled key amended, a name key added, a typography-only amendment."""
    ethanol = entry(1, "9", ("cas", "64-17-5"))
    typography = {**moved("amended", 1, "9", ethanol, ethanol), "typography_only": True}
    return {
        "tables": [
            {"unit": UNIT, "container": UNIT, "table": 1, "key_label": "Entry", "header": []},
            {"unit": UNIT, "container": UNIT, "table": 2, "key_label": None, "header": []},
        ],
        "changes": [
            moved(
                "amended",
                1,
                "7",
                entry(1, "7", ("cas", "50-00-0"), ("index", "605-001-00-5")),
                entry(1, "7", ("cas", "50-00-0"), ("ec", "200-001-8")),
            ),
            typography,
            moved(
                "added",
                2,
                "dust of the shelves",
                None,
                entry(2, "dust of the shelves", ("cas", "7732-18-5"), name=DUST),
            ),
        ],
        "unchanged": 4,
        "whitespace_only": 0,
        "unpaired": [],
        "gaps_before": {},
        "gaps_after": {},
    }


def give_table_entries(payload: Json) -> None:
    changes = payload["changes"]
    assert isinstance(changes, list)
    for change in changes:
        if change["change"]["provision"]["location"] == UNIT:
            change["change"]["table_entries"] = table_entries()


def tabled_record(tmp_path: Path) -> CountingRecord:
    """A copy of the record fixture whose `house-rules` v3 carries `table_entries()`."""
    record = copy_record(tmp_path)
    edit_payload(record.changelogs, *TABLED, give_table_entries)
    return record


EXPECTED = {
    ("1", "7", "before", "cas:50-00-0", "amended", False, "Entry", None),
    ("1", "7", "after", "cas:50-00-0", "amended", False, "Entry", None),
    ("1", "7", "after", "ec:200-001-8", "amended", False, "Entry", None),
    ("1", "9", "before", "cas:64-17-5", "amended", True, "Entry", None),
    ("1", "9", "after", "cas:64-17-5", "amended", True, "Entry", None),
    ("2", "dust of the shelves", "after", "cas:7732-18-5", "added", False, None, DUST),
}
"""Every CAS and EC number on each side of each moved row; the Index No is never loaded."""


def shown(hit: TableHitLoad | TableHit) -> tuple[object, ...]:
    """A hit as `EXPECTED` writes it."""
    return (
        str(hit.table_ordinal),
        hit.row_key,
        hit.side,
        hit.identifier,
        hit.kind,
        hit.typography_only,
        hit.key_label,
        hit.name,
    )


def test_svc_load_table_hits_are_every_watched_number_on_either_side() -> None:
    payload, changes = loads_of(*TABLED)
    edited = payload.model_dump(mode="json")
    give_table_entries(edited)
    hits = table_hit_loads(Payload.model_validate(edited), changes)
    assert {shown(h) for h in hits} == EXPECTED
    assert {(h.event_key, h.location, h.occurrence, h.unit) for h in hits} == {
        ("toy/house-rules@v3", UNIT, 1, UNIT)
    }
    assert table_hit_loads(payload, changes) == ()


def test_svc_load_table_hits_need_one_change_row_per_payload_change() -> None:
    payload, changes = loads_of(*TABLED)
    with pytest.raises(ValueError, match="one change row"):
        table_hit_loads(payload, changes[1:])


async def stored_hits(db: Db) -> set[tuple[object, ...]]:
    async with db.transaction() as tx:
        rows = (await tx.scalars(select(TableHit))).all()
    return {shown(r) for r in rows}


async def test_svc_load_stores_the_hits_and_a_repair_replaces_them(db: Db, tmp_path: Path) -> None:
    record = tabled_record(tmp_path)
    await run(db, record)
    assert await stored_hits(db) == EXPECTED

    def drop_entries(payload: Json) -> None:
        changes = payload["changes"]
        assert isinstance(changes, list)
        for change in changes:
            change["change"]["table_entries"] = None

    edit_payload(record.changelogs, *TABLED, drop_entries)
    await run(db, record)
    assert await stored_hits(db) == set()
