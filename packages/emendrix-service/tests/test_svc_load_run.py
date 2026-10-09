"""A load makes `content` the record as it stands on disk, reading only what moved.

Each test loads a copy of the record fixture, so a test may rewrite a payload, an act index or
the catalogue the way the poller does: payload bytes first, then the act index naming their
hash, then the root index naming the act index's.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import select

from emendrix_record.models import ActIndex
from emendrix_record.reads import PayloadRead, Unavailable
from emendrix_record.record import INDEX_FILE, Record
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.content import dump_content
from emendrix_service.db.tables import Act, Change, Event, Load
from emendrix_service.load.run import LoadCounts, load
from tests.conftest import NOW

pytestmark = pytest.mark.anyio

FIXTURE = Path(__file__).resolve().parents[2] / "emendrix-record" / "tests" / "fixtures"

Json = dict[str, object]


class CountingRecord(Record):
    """The record, counting the act indexes and payloads a load asks for."""

    def __init__(self, changelogs: Path, catalogue: Path) -> None:
        super().__init__(changelogs, catalogue)
        self.changelogs = changelogs
        self.catalogue_path = catalogue
        self.acts = 0
        self.payloads = 0

    def act(self, act: str) -> ActIndex | Unavailable:
        self.acts += 1
        return super().act(act)

    def payload(self, path: str, sha256: str) -> PayloadRead | Unavailable:
        self.payloads += 1
        return super().payload(path, sha256)


def copy_record(tmp_path: Path) -> CountingRecord:
    """A writable copy of the record fixture, read through a counting reader."""
    shutil.copytree(FIXTURE, tmp_path / "record")
    root = tmp_path / "record"
    return CountingRecord(root / "changelogs", root / "catalogue.json")


def read_json(path: Path) -> Json:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def write_json(path: Path, value: object) -> str:
    """Write `value` and return the hex sha256 of the bytes written."""
    raw = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def edit_act_index(changelogs: Path, act: str, edit: Callable[[Json], None]) -> None:
    """Rewrite one act index, then name its new hash and counts in the root index."""
    path = changelogs / "toy" / act / INDEX_FILE
    index = read_json(path)
    edit(index)
    sha = write_json(path, index)
    root = read_json(changelogs / INDEX_FILE)
    acts = root["acts"]
    assert isinstance(acts, list)
    for row in acts:
        if row["key"] == act:
            events = index["events"]
            provisions = index["provisions"]
            assert isinstance(events, list) and isinstance(provisions, dict)
            row.update(
                index_sha256=sha,
                events=len(events),
                changes=sum(len(rows) for rows in provisions.values()),
            )
    write_json(changelogs / INDEX_FILE, root)


def edit_payload(changelogs: Path, act: str, version: str, edit: Callable[[Json], None]) -> bytes:
    """Rewrite one payload as a repair does; the bytes it held before."""
    path = changelogs / "toy" / act / "changes" / f"{version}.json"
    before = path.read_bytes()
    payload = read_json(path)
    edit(payload)
    sha = write_json(path, payload)

    def name_hash(index: Json) -> None:
        events = index["events"]
        assert isinstance(events, list)
        for event in events:
            if event["to_version"] == version:
                event["sha256"] = sha

    edit_act_index(changelogs, act, name_hash)
    return before


def retitle(heading: str) -> Callable[[Json], None]:
    def edit(payload: Json) -> None:
        changes = payload["changes"]
        assert isinstance(changes, list)
        changes[0]["change"]["heading"] = heading

    return edit


async def run(db: Db, record: Record, *, rebuild: bool = False) -> LoadCounts:
    return await load(db, record, clock=FixedClock(NOW), rebuild=rebuild)


async def table_sizes(db: Db) -> dict[str, int]:
    async with db.transaction() as tx:
        dumped = await dump_content(tx)
    return {name: len(rows) for name, rows in dumped.items()}


async def test_svc_load_first_load_writes_every_act_event_and_change(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    counts = await run(db, record)
    assert counts == LoadCounts(status="complete", upserted=3)
    assert await table_sizes(db) == {"acts": 2, "events": 3, "changes": 14, "provisions": 10}
    async with db.transaction() as tx:
        events = (await tx.execute(select(Event.event_key, Event.url))).all()
        acts = (await tx.execute(select(Act.act_key, Act.title, Act.index_sha256))).all()
        load_row = (await tx.execute(select(Load))).scalar_one()
        stored_acts = {key: (title, sha) for key, title, sha in acts}
    assert sorted(events) == [
        ("toy/garden-rules@v2", "https://example.org/acts/garden-rules/v2/"),
        ("toy/house-rules@v2", "https://example.org/acts/house-rules/v2/"),
        ("toy/house-rules@v3", "https://example.org/acts/house-rules/v3/"),
    ]
    root = record.root()
    assert not isinstance(root, Unavailable)
    assert stored_acts == {row.key: (row.title, row.index_sha256) for row in root.acts}
    assert (load_row.started_at, load_row.finished_at, load_row.events_upserted) == (NOW, NOW, 3)


async def test_svc_load_a_quiet_catalogue_act_is_stored_with_its_label(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    catalogue = read_json(record.catalogue_path)
    acts = catalogue["acts"]
    assert isinstance(acts, list)
    quiet = {**acts[0], "key": "quiet-rules", "label": "Quiet Rules", "events": {}, "waiting": []}
    write_json(record.catalogue_path, {**catalogue, "acts": [*acts, quiet]})
    assert (await run(db, record)).upserted == 3
    async with db.transaction() as tx:
        row = await tx.get_one(Act, ("toy", "quiet-rules"))
        assert (row.title, row.index_sha256, row.waiting) == ("Quiet Rules", None, [])
    again = await run(db, record)
    assert (again.upserted, record.acts) == (0, 2)


async def test_svc_load_nothing_moved_reads_no_act_index_and_no_payload(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    first = await table_sizes(db)
    record.acts = record.payloads = 0
    assert await run(db, record) == LoadCounts(status="complete")
    assert (record.acts, record.payloads) == (0, 0)
    assert await table_sizes(db) == first


async def test_svc_load_a_rewritten_payload_moves_exactly_its_event(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    edit_payload(record.changelogs, "house-rules", "v3", retitle("Bins and recycling"))
    record.acts = record.payloads = 0
    assert await run(db, record) == LoadCounts(status="complete", upserted=1)
    assert (record.acts, record.payloads) == (1, 1)
    async with db.transaction() as tx:
        headings = await tx.execute(
            select(Change.event_key, Change.heading).where(Change.location == "AR 2")
        )
        assert sorted(headings.all()) == [
            ("toy/garden-rules@v2", "Bins"),
            ("toy/house-rules@v2", "Bins"),
            ("toy/house-rules@v3", "Bins and recycling"),
        ]


async def test_svc_load_an_event_the_index_drops_is_deleted_with_its_changes(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await run(db, record)

    def drop_v2(index: Json) -> None:
        events = index["events"]
        provisions = index["provisions"]
        assert isinstance(events, list) and isinstance(provisions, dict)
        index["events"] = [event for event in events if event["to_version"] != "v2"]
        for unit, rows in provisions.items():
            provisions[unit] = [row for row in rows if row["version"] != "v2"]

    edit_act_index(record.changelogs, "house-rules", drop_v2)
    assert await run(db, record) == LoadCounts(status="complete", removed=1)
    async with db.transaction() as tx:
        gone = await tx.execute(select(Change).where(Change.event_key == "toy/house-rules@v2"))
        assert gone.first() is None
        act = await tx.get_one(Act, ("toy", "house-rules"))
        root = record.root()
        assert not isinstance(root, Unavailable)
        assert act.index_sha256 == root.acts[1].index_sha256
    assert await table_sizes(db) == {"acts": 2, "events": 2, "changes": 10, "provisions": 10}


async def test_svc_load_a_payload_mid_write_is_skipped_then_loaded(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    changelogs = record.changelogs
    path = changelogs / "toy" / "house-rules" / "changes" / "v3.json"
    old = edit_payload(changelogs, "house-rules", "v3", retitle("Bins and recycling"))
    new = path.read_bytes()
    path.write_bytes(old)
    assert await run(db, record) == LoadCounts(status="complete", skipped=1, unsettled=1)
    async with db.transaction() as tx:
        event = await tx.get_one(Event, "toy/house-rules@v3")
        act = await tx.get_one(Act, ("toy", "house-rules"))
        load_row = (await tx.execute(select(Load).order_by(Load.id.desc()))).scalars().first()
        assert event.sha256 == hashlib.sha256(old).hexdigest()
        assert act.index_sha256 != (root_sha(record, "house-rules"))
        assert load_row is not None and load_row.events_skipped == 1
    path.write_bytes(new)
    assert await run(db, record) == LoadCounts(status="complete", upserted=1)
    async with db.transaction() as tx:
        event = await tx.get_one(Event, "toy/house-rules@v3")
        act = await tx.get_one(Act, ("toy", "house-rules"))
        assert event.sha256 == hashlib.sha256(new).hexdigest()
        assert act.index_sha256 == root_sha(record, "house-rules")


def root_sha(record: Record, act: str) -> str:
    root = record.root()
    assert not isinstance(root, Unavailable)
    return next(row.index_sha256 for row in root.acts if row.key == act)


async def test_svc_load_the_catalogue_states_waiting_and_checked_through(
    db: Db, tmp_path: Path
) -> None:
    await run(db, copy_record(tmp_path))
    async with db.transaction() as tx:
        rows = (await tx.execute(select(Act).order_by(Act.act_key))).scalars().all()
        stored = [(row.act_key, row.checked_through, row.waiting) for row in rows]
    assert [(key, str(through)) for key, through, _ in stored] == [
        ("garden-rules", "2026-08-12"),
        ("house-rules", "2026-08-12"),
    ]
    assert [waiting for _, _, waiting in stored] == [
        [{"version": None, "state": "english_unavailable", "first_seen": "2026-08-10"}],
        [{"version": "v4", "state": "consolidation_pending", "first_seen": "2026-08-11"}],
    ]


async def test_svc_load_an_act_the_catalogue_drops_is_deleted(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    catalogue = read_json(record.catalogue_path)
    acts = catalogue["acts"]
    assert isinstance(acts, list)
    write_json(record.catalogue_path, {**catalogue, "acts": acts[1:]})
    assert await run(db, record) == LoadCounts(status="complete", removed=1)
    assert await table_sizes(db) == {"acts": 1, "events": 2, "changes": 9, "provisions": 5}


async def test_svc_load_an_unreadable_root_writes_nothing(db: Db, tmp_path: Path) -> None:
    record = copy_record(tmp_path)
    (record.changelogs / INDEX_FILE).write_text("{", encoding="utf-8")
    counts = await run(db, record)
    assert counts.status == "failed"
    assert counts.reason == "index.json is not a change index this server can read"
    async with db.transaction() as tx:
        assert (await tx.execute(select(Load))).first() is None
    assert await table_sizes(db) == {"acts": 0, "events": 0, "changes": 0, "provisions": 0}


async def test_svc_load_an_act_index_rewritten_under_the_read_is_read_again(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    edit_payload(record.changelogs, "house-rules", "v3", retitle("Bins and recycling"))
    moved = root_sha(record, "house-rules")
    original_act = CountingRecord.act

    def act_then_rewrite(self: CountingRecord, act: str) -> ActIndex | Unavailable:
        read = original_act(self, act)
        edit_act_index(self.changelogs, "house-rules", lambda index: index.update(title="Rules"))
        return read

    record.act = act_then_rewrite.__get__(record)  # type: ignore[method-assign]
    assert await run(db, record) == LoadCounts(status="complete", upserted=1, unsettled=1)
    async with db.transaction() as tx:
        act = await tx.get_one(Act, ("toy", "house-rules"))
        assert act.index_sha256 not in (moved, root_sha(record, "house-rules"))
