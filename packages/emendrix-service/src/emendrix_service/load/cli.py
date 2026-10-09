"""`emendrix-service load`: read the published record into the `content` schema."""

from __future__ import annotations

import logging
from typing import Annotated

import anyio
import typer

from emendrix_record.record import Record
from emendrix_service.clock import Clock, SystemClock
from emendrix_service.db import COMMAND_POOL, Db
from emendrix_service.load.run import LoadCounts
from emendrix_service.load.run import load as run_load
from emendrix_service.log import marker
from emendrix_service.settings import ServiceSettings, load_settings, require

__all__ = ["load", "load_once", "record_of"]


def record_of(settings: ServiceSettings) -> Record:
    """The record the settings name; stops with exit code 2 when either input is unset."""
    require(settings, "changelogs", "catalogue")
    assert settings.changelogs is not None and settings.catalogue is not None
    return Record(settings.changelogs, settings.catalogue)


async def load_once(
    settings: ServiceSettings, db: Db, clock: Clock, *, rebuild: bool = False
) -> LoadCounts:
    """One load of the record the settings name into `db`."""
    return await run_load(db, record_of(settings), clock=clock, rebuild=rebuild)


def load(
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="Empty the content schema and load it afresh.")
    ] = False,
) -> None:
    """Upsert every published event into the content schema."""
    settings = load_settings()
    record_of(settings)

    async def run() -> LoadCounts:
        db = Db.connect(settings, pool_size=COMMAND_POOL)
        try:
            return await load_once(settings, db, SystemClock(), rebuild=rebuild)
        finally:
            await db.dispose()

    try:
        counts = anyio.run(run)
    except Exception as error:
        logging.getLogger(__name__).exception("the load did not complete")
        marker("load", status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    reason = {} if counts.reason is None else {"reason": counts.reason}
    marker(
        "load",
        status=counts.status,
        upserted=counts.upserted,
        removed=counts.removed,
        skipped=counts.skipped,
        unsettled=counts.unsettled,
        **reason,
    )
    if counts.status == "failed":
        raise typer.Exit(1)
