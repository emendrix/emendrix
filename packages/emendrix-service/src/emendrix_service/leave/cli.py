"""`emendrix-service retention`: apply the retention table."""

from __future__ import annotations

import logging

import anyio
import typer

from emendrix_service.clock import SystemClock
from emendrix_service.db import COMMAND_POOL, Db
from emendrix_service.leave.retention import RetentionCounts, retain
from emendrix_service.log import marker
from emendrix_service.settings import load_settings

__all__ = ["retention"]

_log = logging.getLogger(__name__)

RETENTION = "retention"


def retention() -> None:
    """Delete or blank every row past its retention period, and warn or delete unused accounts."""
    settings = load_settings()
    now = SystemClock().now()

    async def run() -> RetentionCounts:
        db = Db.connect(settings, pool_size=COMMAND_POOL)
        try:
            return await retain(db, settings, now)
        finally:
            await db.dispose()

    try:
        counts = anyio.run(run)
    except Exception as error:
        _log.error("retention did not complete: %s", type(error).__name__)
        marker(RETENTION, status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    marker(RETENTION, status="failed" if counts.failed else "complete", **counts.model_dump())
    if counts.failed:
        raise typer.Exit(1)
