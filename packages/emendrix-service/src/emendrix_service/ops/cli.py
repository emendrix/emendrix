"""`emendrix-service status` and `backup ship`: what an operator runs and reads."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Final

import anyio
import typer

from emendrix_service.clock import SystemClock
from emendrix_service.db import COMMAND_POOL, Db
from emendrix_service.db import ops as store
from emendrix_service.db.enums import OutboxPurpose
from emendrix_service.db.outbox import enqueue
from emendrix_service.log import marker
from emendrix_service.ops.ship import ShipCounts, parse_target
from emendrix_service.ops.ship import ship as ship_dump
from emendrix_service.ops.status import DAY, WEEK, StatusReport, operator_mail, render
from emendrix_service.settings import ServiceSettings, load_settings, require, variable
from emendrix_service.stop import stop

__all__ = ["backup_app", "report", "ship", "status"]

_log = logging.getLogger(__name__)

STATUS: Final = "status"
BACKUP: Final = "backup"

backup_app = typer.Typer(no_args_is_help=True, help="Ship database backups off the host.")


async def report(db: Db, now: datetime, *, email_to: str | None = None) -> str:
    """Read every count at `now` and render the block; queue it to `email_to` when given.

    The counts and the queued email share one transaction, so the email says what was read.
    """
    async with db.transaction() as tx:
        text = render(
            StatusReport(
                at=now,
                load=await store.last_load(tx),
                announcements=await store.announcements_since(tx, now - DAY),
                deliveries=await store.deliveries_since(tx, now - DAY),
                outbox=await store.outbox_health(tx, now - DAY),
                mail=await store.mail_health_since(tx, now - WEEK),
                population=await store.population(tx),
                acts=await store.items_per_act(tx),
            )
        )
        if email_to is not None:
            await enqueue(
                tx,
                purpose=OutboxPurpose.OPERATOR,
                to=email_to,
                mail=operator_mail(text, to=email_to, at=now),
                user_id=None,
                now=now,
            )
    return text


async def _status(settings: ServiceSettings, email_to: str | None) -> str:
    db = Db.connect(settings, pool_size=COMMAND_POOL)
    try:
        return await report(db, SystemClock().now(), email_to=email_to)
    finally:
        await db.dispose()


def status(
    email: Annotated[
        bool, typer.Option("--email", help="Also send the block to the operator address.")
    ] = False,
) -> None:
    """Print one status block: the last load, notify and drain, the queue and the bounces."""
    settings = load_settings()
    if email:
        require(settings, "operator_email")
    try:
        text = anyio.run(_status, settings, settings.operator_email if email else None)
    except Exception as error:
        # A database error's text can carry a row's parameters, an address among them.
        _log.error("status did not complete: %s", type(error).__name__)
        marker(STATUS, status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    typer.echo(text, nl=False)
    marker(STATUS, status="complete", emailed=int(email))


def _file(settings: ServiceSettings, name: str) -> Path:
    path = getattr(settings, name)
    if not isinstance(path, Path) or not path.is_file():
        stop(f"{variable(name)} names no readable file")
    return path


@backup_app.command("ship")
def ship(
    dump: Annotated[Path, typer.Argument(help="The database dump to encrypt and upload.")],
) -> None:
    """Encrypt a dump to the age recipient, upload it over SFTP and prune old copies."""
    settings = load_settings()
    require(
        settings, "backup_target", "backup_ssh_key", "backup_known_hosts", "backup_age_recipient"
    )
    try:
        target = parse_target(settings.backup_target or "")
    except ValueError as error:
        stop(f"{variable('backup_target')} is not valid: {error}")
    key_path = _file(settings, "backup_ssh_key")
    known_hosts = _file(settings, "backup_known_hosts")
    if not dump.is_file():
        stop(f"{dump} is not a file")
    today = SystemClock().now().date()

    async def run() -> ShipCounts:
        return await ship_dump(
            dump,
            target=target,
            key_path=key_path,
            known_hosts_path=known_hosts,
            recipient=settings.backup_age_recipient or "",
            today=today,
        )

    try:
        counts = anyio.run(run)
    except Exception as error:
        _log.error("the backup did not ship: %s: %s", type(error).__name__, error)
        marker(BACKUP, status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    marker(BACKUP, status="complete", **counts.model_dump())
