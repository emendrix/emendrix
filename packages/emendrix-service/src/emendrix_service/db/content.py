"""The `content` schema's queries: what the loader writes, and what it compares against.

Every write takes rows the loader built from the record (`load/rows.py`) and stores them as
they are; nothing here computes a field. Lists are stored in the order the rows give them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Final

from sqlalchemy import (
    Table,
    Text,
    bindparam,
    delete,
    func,
    literal_column,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert

from emendrix_service.db.base import Base
from emendrix_service.db.engine import Tx
from emendrix_service.db.tables_content import Act, Change, Event, Load, Provision
from emendrix_service.load.models import (
    ActLoad,
    ChangeLoad,
    EventLoad,
    ProvisionLoad,
    StoredUnitChange,
)

__all__ = [
    "act_hashes",
    "delete_act_events",
    "delete_acts_missing",
    "delete_events",
    "dump_content",
    "event_hashes",
    "finish_load",
    "lock_content",
    "refresh_event_urls",
    "replace_event",
    "replace_provisions",
    "start_load",
    "truncate_content",
    "unit_changes",
    "upsert_acts",
]

LOCK: Final = 0x656D656E6C6F6164
"""The advisory lock one load holds for its transaction, so two loads never interleave."""

DUMPED: Final[tuple[Table, ...]] = tuple(
    Base.metadata.tables[f"content.{name}"] for name in ("acts", "events", "changes", "provisions")
)
"""Every table the record is projected into; `loads` is the loader's own history."""

ActKey = tuple[str, str]


async def lock_content(tx: Tx) -> None:
    """Wait for any other load to commit; held until this transaction ends."""
    await tx.execute(select(func.pg_advisory_xact_lock(LOCK)))


async def truncate_content(tx: Tx) -> None:
    """Empty every projected table; the history in `loads` is kept."""
    names = ", ".join(table.fullname for table in DUMPED)
    await tx.execute(text(f"TRUNCATE {names}"))


async def act_hashes(tx: Tx) -> dict[ActKey, str | None]:
    """Every stored act, with the act index hash its events were last fully loaded from."""
    rows = await tx.execute(select(Act.corpus, Act.act_key, Act.index_sha256))
    return {(corpus, key): sha for corpus, key, sha in rows}


async def event_hashes(tx: Tx, corpus: str, act_key: str) -> dict[str, str]:
    """Every stored event of one act, with the payload hash it was loaded from."""
    rows = await tx.execute(
        select(Event.event_key, Event.sha256).where(
            Event.corpus == corpus, Event.act_key == act_key
        )
    )
    return dict(rows.all())


async def upsert_acts(tx: Tx, acts: Iterable[ActLoad]) -> None:
    """Write each act, replacing every field of a stored one."""
    values = [
        {**act.model_dump(), "aliases": list(act.aliases), "waiting": list(act.waiting)}
        for act in acts
    ]
    if not values:
        return
    statement = insert(Act).values(values)
    keys = {"corpus", "act_key"}
    await tx.execute(
        statement.on_conflict_do_update(
            index_elements=sorted(keys),
            set_={
                name: statement.excluded[name] for name in ActLoad.model_fields if name not in keys
            },
        )
    )


def _event_values(event: EventLoad) -> dict[str, object]:
    return {**event.model_dump(), "in_force": list(event.in_force)}


def _change_values(change: ChangeLoad) -> dict[str, object]:
    values = change.model_dump()
    for name in ("dates_added", "dates_removed", "amending_acts", "changed_within", "sentences"):
        values[name] = list(values[name])
    return values


async def replace_event(tx: Tx, event: EventLoad, changes: Iterable[ChangeLoad]) -> None:
    """Write the event, replacing a stored one, and replace all of its changes."""
    statement = insert(Event).values(_event_values(event))
    await tx.execute(
        statement.on_conflict_do_update(
            index_elements=["event_key"],
            set_={
                name: statement.excluded[name]
                for name in EventLoad.model_fields
                if name != "event_key"
            },
        )
    )
    await tx.execute(delete(Change).where(Change.event_key == event.event_key))
    values = [_change_values(change) for change in changes]
    if values:
        await tx.execute(insert(Change).values(values))


async def delete_events(tx: Tx, keys: Iterable[str]) -> int:
    """Delete the named events and, by cascade, their changes; the number deleted."""
    wanted = sorted(set(keys))
    if not wanted:
        return 0
    result = await tx.execute(
        delete(Event).where(Event.event_key.in_(wanted)).returning(Event.event_key)
    )
    return len(result.all())


async def delete_act_events(tx: Tx, corpus: str, act_key: str) -> int:
    """Delete every event of one act, and its provisions; the number of events deleted."""
    await tx.execute(
        delete(Provision).where(Provision.corpus == corpus, Provision.act_key == act_key)
    )
    result = await tx.execute(
        delete(Event)
        .where(Event.corpus == corpus, Event.act_key == act_key)
        .returning(Event.event_key)
    )
    return len(result.all())


async def refresh_event_urls(tx: Tx, corpus: str, act_key: str, urls: Mapping[str, str]) -> None:
    """Set each stored event's page to the catalogue's for its entry key, or null if none."""
    pages = bindparam("pages", value=dict(urls), type_=JSONB)
    url = pages.op("->>", return_type=Text)(Event.entry_key)
    await tx.execute(
        update(Event)
        .where(
            Event.corpus == corpus,
            Event.act_key == act_key,
            Event.url.is_distinct_from(url),
        )
        .values(url=url)
    )


async def unit_changes(tx: Tx, corpus: str, act_key: str) -> tuple[StoredUnitChange, ...]:
    """Every stored change of one act, with its event's version, for its provision rows."""
    rows = await tx.execute(
        select(Change.unit, Event.to_version, Change.location, Change.occurrence, Change.heading)
        .join(Event, Event.event_key == Change.event_key)
        .where(Event.corpus == corpus, Event.act_key == act_key)
    )
    return tuple(
        StoredUnitChange(
            unit=unit,
            to_version=to_version,
            location=location,
            occurrence=occurrence,
            heading=heading,
        )
        for unit, to_version, location, occurrence, heading in rows
    )


async def replace_provisions(
    tx: Tx, corpus: str, act_key: str, rows: Iterable[ProvisionLoad]
) -> None:
    """Replace every provision row of one act with `rows`."""
    await tx.execute(
        delete(Provision).where(Provision.corpus == corpus, Provision.act_key == act_key)
    )
    values = [row.model_dump() for row in rows]
    if values:
        await tx.execute(insert(Provision).values(values))


async def delete_acts_missing(tx: Tx, keep: Iterable[ActKey]) -> int:
    """Delete every act not in `keep`, with its events, changes and provisions.

    Events and provisions are matched by their own act columns, so rows of an act that has no
    `acts` row go too. Returns the number of events deleted.
    """
    kept = sorted(set(keep))
    removed = 0
    for name in ("events", "provisions", "acts"):
        table = Base.metadata.tables[f"content.{name}"]
        columns = tuple_(table.c.corpus, table.c.act_key)
        condition = columns.not_in(kept) if kept else literal_column("true")
        result = await tx.execute(delete(table).where(condition).returning(table.c.corpus))
        if name == "events":
            removed = len(result.all())
    return removed


async def start_load(tx: Tx, root_sha256: str, now: datetime) -> int:
    """Record that a load started over the root index of `root_sha256`; the load's id."""
    load = Load(root_sha256=root_sha256, started_at=now)
    tx.add(load)
    await tx.flush()
    return load.id


async def finish_load(
    tx: Tx, load_id: int, *, upserted: int, removed: int, skipped: int, now: datetime
) -> None:
    """Record how a load ended."""
    await tx.execute(
        update(Load)
        .where(Load.id == load_id)
        .values(
            finished_at=now,
            events_upserted=upserted,
            events_removed=removed,
            events_skipped=skipped,
        )
    )


async def dump_content(tx: Tx) -> dict[str, list[tuple[object, ...]]]:
    """Every projected row, table by table, each table ordered by its primary key."""
    dumped: dict[str, list[tuple[object, ...]]] = {}
    for table in DUMPED:
        rows = await tx.execute(select(table).order_by(*table.primary_key.columns))
        dumped[table.name] = [tuple(row) for row in rows]
    return dumped
