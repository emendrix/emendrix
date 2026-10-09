"""Loading the record step by step and loading it afresh write the same rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from emendrix_service.db import Db
from emendrix_service.db.content import dump_content
from emendrix_service.load.run import LoadCounts
from tests.test_svc_load_run import copy_record, edit_payload, retitle, run

pytestmark = pytest.mark.anyio


async def dump(db: Db) -> dict[str, list[tuple[object, ...]]]:
    async with db.transaction() as tx:
        return await dump_content(tx)


async def test_svc_load_incremental_and_rebuilt_loads_are_row_for_row_equal(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    edit_payload(record.changelogs, "garden-rules", "v2", retitle("Bins and compost"))
    assert await run(db, record) == LoadCounts(status="complete", upserted=1)
    incremental = await dump(db)
    assert await run(db, record, rebuild=True) == LoadCounts(status="complete", upserted=3)
    assert await dump(db) == incremental
    assert sum(len(rows) for rows in incremental.values()) == 2 + 3 + 14 + 10


async def test_svc_load_a_catalogue_that_moves_alone_is_followed_without_a_rebuild(
    db: Db, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    await run(db, record)
    moved = record.catalogue_path.read_text("utf-8").replace("/acts/", "/law/")
    record.catalogue_path.write_text(moved, "utf-8")
    assert await run(db, record) == LoadCounts(status="complete")
    incremental = await dump(db)
    await run(db, record, rebuild=True)
    assert await dump(db) == incremental
    assert "https://example.org/law/house-rules/v3/" in {row[-1] for row in incremental["events"]}
