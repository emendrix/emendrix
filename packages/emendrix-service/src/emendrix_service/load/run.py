"""One load: the record as it stands on disk now, projected into `content` in one transaction.

The repository is rewritten underneath a running load every hour, so the hashes decide what is
read, never the order files were written in. An act's index is read only when the root index
states a hash for it other than the one stored; a payload only when its act index states a hash
other than the one stored for its event. A payload whose bytes differ from that hash is
mid-write: it is skipped and counted, its event keeps the old hash, and its act keeps the old
index hash, so the next load reads both again. The same holds for an act index that does not
describe the event set the root index counts for it.

`root_sha256` in `loads` is the sha256 of the root index as parsed and re-serialised by the
record's reader: the reader returns no bytes, and this digest moves whenever any act's index
hash does.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from emendrix_record.models import ActIndex, ActRow, Catalogue, CatalogueAct, EventRow, RootIndex
from emendrix_record.reads import Unavailable
from emendrix_record.record import Record
from emendrix_service.clock import Clock
from emendrix_service.db import Db, Tx
from emendrix_service.db import content as store
from emendrix_service.load.models import ActLoad, EventLoad
from emendrix_service.load.rows import (
    act_load,
    change_loads,
    event_load,
    filed_rows,
    provision_loads,
)

__all__ = ["LoadCounts", "load"]


class LoadCounts(BaseModel):
    """How one load ended, and what it did."""

    model_config = ConfigDict(frozen=True)

    status: Literal["complete", "failed"] = Field(description="Whether the load committed.")
    reason: str | None = Field(default=None, description="Why a failed load wrote nothing.")
    upserted: int = Field(default=0, ge=0, description="Events written or rewritten.")
    removed: int = Field(default=0, ge=0, description="Events the record has stopped listing.")
    skipped: int = Field(default=0, ge=0, description="Events whose payload was mid-write.")
    unsettled: int = Field(
        default=0,
        ge=0,
        description="Acts whose index hash was not stored: an event was skipped, or the act "
        "index could not be read or did not match the root index.",
    )


class _Tally(BaseModel):
    """What one act's load did; summed into `LoadCounts`."""

    model_config = ConfigDict(frozen=True)

    upserted: int = 0
    removed: int = 0
    skipped: int = 0
    settled: bool = True


def _root_digest(root: RootIndex) -> str:
    return hashlib.sha256(root.model_dump_json().encode("utf-8")).hexdigest()


def _matches_root(row: ActRow, index: ActIndex) -> bool:
    """Whether the act index read describes the events the root index counts for the act."""
    return (
        len(index.events) == row.events
        and sum(len(rows) for rows in index.provisions.values()) == row.changes
        and (not index.events or index.events[0].to_version == row.newest_version)
        and max((event.updated_on for event in index.events), default=row.updated_on)
        == row.updated_on
    )


def _settled(record: Record, row: ActRow, index: ActIndex) -> bool:
    """Whether the act index read may be vouched for by the hash the load started from.

    The reader returns no act index bytes to hash, so this asks what it can: that the root
    index still names that hash after the read, and that the index read describes the events
    the root counts. An index rewritten under the read fails the first.
    """
    again = record.act_row(f"{row.corpus}/{row.key}")
    if isinstance(again, Unavailable) or again.index_sha256 != row.index_sha256:
        return False
    return _matches_root(row, index)


async def _load_event(
    tx: Tx, record: Record, index: ActIndex, event: EventRow, loaded: EventLoad
) -> bool:
    """Replace one event from its payload; false when the payload is not the one indexed."""
    read = record.payload(event.path, event.sha256)
    if isinstance(read, Unavailable) or not read.matches_index:
        return False
    rows = filed_rows(index, event, read.payload)
    changes = change_loads(loaded.event_key, loaded.entry_key, read.payload, rows)
    await store.replace_event(tx, loaded, changes)
    return True


async def _load_events(tx: Tx, record: Record, listing: CatalogueAct, row: ActRow | None) -> _Tally:
    """Bring one act's stored events and provisions to its act index, or to none."""
    corpus, key = listing.corpus, listing.key
    index: ActIndex | None = None
    if row is not None:
        read = record.act(f"{corpus}/{key}")
        if isinstance(read, Unavailable):
            return _Tally(settled=False)
        index = read
    stored = await store.event_hashes(tx, corpus, key)
    upserted = skipped = 0
    listed: set[str] = set()
    for event in () if index is None else index.events:
        loaded = event_load(corpus, key, event, listing)
        listed.add(loaded.event_key)
        if stored.get(loaded.event_key) == event.sha256:
            continue
        if index is not None and await _load_event(tx, record, index, event, loaded):
            upserted += 1
        else:
            skipped += 1
    removed = await store.delete_events(tx, set(stored) - listed)
    provisions = provision_loads(corpus, key, await store.unit_changes(tx, corpus, key))
    await store.replace_provisions(tx, corpus, key, provisions)
    settled = skipped == 0 and (row is None or index is None or _settled(record, row, index))
    return _Tally(upserted=upserted, removed=removed, skipped=skipped, settled=settled)


async def _load_all(
    tx: Tx, record: Record, catalogue: Catalogue, rows: dict[tuple[str, str], ActRow]
) -> LoadCounts:
    hashes = await store.act_hashes(tx)
    upserted = removed = skipped = unsettled = 0
    acts: list[ActLoad] = []
    for listing in catalogue.acts:
        act = (listing.corpus, listing.key)
        row = rows.get(act)
        target = None if row is None else row.index_sha256
        index_sha256 = hashes.get(act)
        if act not in hashes or index_sha256 != target:
            tally = await _load_events(tx, record, listing, row)
            upserted += tally.upserted
            removed += tally.removed
            skipped += tally.skipped
            if tally.settled:
                index_sha256 = target
            else:
                unsettled += 1
        await store.refresh_event_urls(tx, listing.corpus, listing.key, listing.events)
        acts.append(act_load(listing, row, catalogue.checked_through, index_sha256=index_sha256))
    await store.upsert_acts(tx, acts)
    removed += await store.delete_acts_missing(tx, [(act.corpus, act.act_key) for act in acts])
    return LoadCounts(
        status="complete",
        upserted=upserted,
        removed=removed,
        skipped=skipped,
        unsettled=unsettled,
    )


async def load(db: Db, record: Record, *, clock: Clock, rebuild: bool = False) -> LoadCounts:
    """Project the record into `content`; `rebuild` empties it first and loads everything.

    An unreadable root index or catalogue ends the load with nothing written. An act the root
    index lists and the catalogue does not is not loaded, because the catalogue is where an act's
    names and pages come from; a later catalogue that lists it loads it.
    """
    root = record.root()
    if isinstance(root, Unavailable):
        return LoadCounts(status="failed", reason=root.reason)
    catalogue = record.catalogue()
    if isinstance(catalogue, Unavailable):
        return LoadCounts(status="failed", reason=catalogue.reason)
    async with db.transaction() as tx:
        load_id = await store.start_load(tx, _root_digest(root), clock.now())
    async with db.transaction() as tx:
        await store.lock_content(tx)
        if rebuild:
            await store.truncate_content(tx)
        rows = {(row.corpus, row.key): row for row in root.acts}
        counts = await _load_all(tx, record, catalogue, rows)
        await store.finish_load(
            tx,
            load_id,
            upserted=counts.upserted,
            removed=counts.removed,
            skipped=counts.skipped,
            now=clock.now(),
        )
    return counts
