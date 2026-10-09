"""`emendrix-service mail ...`: send what the outbox holds."""

from __future__ import annotations

import logging
from typing import Annotated, Final

import anyio
import typer

from emendrix_service.clock import Clock, SystemClock
from emendrix_service.db import COMMAND_POOL, Db
from emendrix_service.log import marker
from emendrix_service.mail.drain import DrainCounts
from emendrix_service.mail.drain import drain as drain_outbox
from emendrix_service.mail.transport import SmtpMailer, smtp_settings_complete
from emendrix_service.settings import ServiceSettings, load_settings, variable
from emendrix_service.stop import stop

__all__ = ["app", "drain", "drain_once"]

COMMAND: Final = "mail drain"

app = typer.Typer(no_args_is_help=True, help="Send queued email.")


async def drain_once(
    settings: ServiceSettings, db: Db, clock: Clock, *, limit: int = 200
) -> DrainCounts:
    """Drain the outbox once through the configured relay.

    Raises `ValueError` when a setting sending needs is missing: the caller checks
    `smtp_settings_complete` first, because otherwise every row would be refused and retried.
    """
    sender = settings.mail_from
    if sender is None or smtp_settings_complete(settings) is not None:
        raise ValueError("the SMTP settings are incomplete")
    return await drain_outbox(db, SmtpMailer(settings, clock), sender, clock, limit=limit)


async def _run(settings: ServiceSettings, limit: int) -> DrainCounts:
    db = Db.connect(settings, pool_size=COMMAND_POOL)
    try:
        return await drain_once(settings, db, SystemClock(), limit=limit)
    finally:
        await db.dispose()


@app.command("drain")
def drain(
    limit: Annotated[int, typer.Option(min=1, help="The most rows to send in this run.")] = 200,
) -> None:
    """Send queued outbox rows that are due, retrying transient refusals on schedule."""
    settings = load_settings()
    missing = smtp_settings_complete(settings)
    if missing is not None:
        stop(f"{variable(missing)} is not set")
    try:
        counts = anyio.run(_run, settings, limit)
    except Exception as error:
        # A database error's text can carry a row's parameters, an address among them.
        logging.getLogger(__name__).error("the drain did not complete: %s", type(error).__name__)
        marker(COMMAND, status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    marker(COMMAND, status="complete", **counts.model_dump())
