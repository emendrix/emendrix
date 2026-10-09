"""`emendrix-service notify`, `digest` and `tick`: announce new events and plan deliveries.

`tick` is the one job a scheduler runs every few minutes: load, notify, digest and drain, in
that order. Each step catches its own failure, logs it and lets the next one run, so a load that
cannot read the record still lets due digests and queued mail go out; the run then exits 1. It
ends with one `tick` marker carrying every step's count.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Final

import anyio
import typer
from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.clock import Clock, FixedClock, SystemClock
from emendrix_service.db import COMMAND_POOL, Db
from emendrix_service.load.cli import load_once
from emendrix_service.log import marker
from emendrix_service.mail.drain import PACE
from emendrix_service.mail.drain import drain as drain_outbox
from emendrix_service.mail.port import Mailer
from emendrix_service.mail.transport import SmtpMailer, smtp_settings_complete
from emendrix_service.notify.digest_run import DigestCounts
from emendrix_service.notify.digest_run import digest as run_digest
from emendrix_service.notify.run import NotifyCounts
from emendrix_service.notify.run import notify as run_notify
from emendrix_service.settings import ServiceSettings, load_settings, require, variable
from emendrix_service.stop import stop

__all__ = ["TickCounts", "digest", "notify", "tick", "tick_once"]

_log = logging.getLogger(__name__)

TICK: Final = "tick"


class TickCounts(BaseModel):
    """What one `tick` did, step by step, and whether every step completed."""

    model_config = ConfigDict(frozen=True)

    failed: bool = Field(default=False, description="Whether any step failed.")
    loaded: int = Field(default=0, description="Events the load wrote.")
    announced: int = Field(default=0, description="Events judged.")
    eligible: int = Field(default=0, description="Events matched against watchlists.")
    matches: int = Field(default=0, description="Matches written.")
    deliveries: int = Field(default=0, description="Emails queued, instant and periodic.")
    sent: int = Field(default=0, description="Emails the relay accepted.")


def _failed(step: str, error: BaseException) -> None:
    # A database error's text can carry a row's parameters, an address among them.
    _log.error("the %s step did not complete: %s", step, type(error).__name__)


async def tick_once(
    settings: ServiceSettings, db: Db, clock: Clock, mailer: Mailer, *, pace: float = PACE
) -> TickCounts:
    """One tick over `db`, sending through `mailer`; writes the `tick` marker."""
    failed = False
    loaded = 0
    notified = NotifyCounts()
    planned = DigestCounts()
    sent = 0
    try:
        load = await load_once(settings, db, clock)
        loaded = load.upserted
        if load.status == "failed":
            _log.error("the load step did not complete: %s", load.reason)
            failed = True
    except Exception as error:
        _failed("load", error)
        failed = True
    try:
        notified = await run_notify(db, settings, clock.now())
    except Exception as error:
        _failed("notify", error)
        failed = True
    try:
        planned = await run_digest(db, settings, clock.now())
    except Exception as error:
        _failed("digest", error)
        failed = True
    try:
        if settings.mail_from is None:
            raise ValueError("the sender is not set")
        sent = (await drain_outbox(db, mailer, settings.mail_from, clock, pace=pace)).sent
    except Exception as error:
        _failed("drain", error)
        failed = True
    counts = TickCounts(
        failed=failed or bool(notified.failed or planned.failed),
        loaded=loaded,
        announced=notified.announced,
        eligible=notified.eligible,
        matches=notified.matches,
        deliveries=notified.deliveries + planned.deliveries,
        sent=sent,
    )
    marker(
        TICK,
        status="failed" if failed else "complete",
        **counts.model_dump(exclude={"failed"}),
    )
    return counts


def _command(name: str, run: Callable[[], Awaitable[NotifyCounts | DigestCounts]]) -> None:
    """Run a command body and write its marker; a crash or a failed unit exits 1."""
    try:
        counts = anyio.run(run)
    except Exception as error:
        _failed(name, error)
        marker(name, status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    marker(name, status="failed" if counts.failed else "complete", **counts.model_dump())
    if counts.failed:
        raise typer.Exit(1)


def notify() -> None:
    """Announce new events once each, and write their matches and instant deliveries."""
    settings = load_settings()
    require(settings, "live_since")

    async def run() -> NotifyCounts:
        db = Db.connect(settings, pool_size=COMMAND_POOL)
        try:
            return await run_notify(db, settings, SystemClock().now())
        finally:
            await db.dispose()

    _command("notify", run)


def _instant(text: str) -> datetime:
    try:
        at = datetime.fromisoformat(text)
    except ValueError:
        stop(f"--now is not an ISO 8601 instant: {text!r}")
    if at.tzinfo is None or at.utcoffset() is None:
        stop("--now needs an offset, such as 2026-10-12T07:00:00+02:00")
    return at


def digest(
    now: Annotated[
        str | None,
        typer.Option(
            "--now",
            help="Plan as if it were this ISO 8601 instant, with an offset; default the clock.",
        ),
    ] = None,
) -> None:
    """Plan the daily, weekly and heartbeat deliveries that are due."""
    clock: Clock = SystemClock() if now is None else FixedClock(_instant(now))
    settings = load_settings()

    async def run() -> DigestCounts:
        db = Db.connect(settings, pool_size=COMMAND_POOL)
        try:
            return await run_digest(db, settings, clock.now())
        finally:
            await db.dispose()

    _command("digest", run)


def tick() -> None:
    """Load, notify, digest and drain, each step logged, in one run."""
    settings = load_settings()
    require(settings, "changelogs", "catalogue", "live_since")
    missing = smtp_settings_complete(settings)
    if missing is not None:
        stop(f"{variable(missing)} is not set")
    clock = SystemClock()

    async def run() -> TickCounts:
        db = Db.connect(settings, pool_size=COMMAND_POOL)
        try:
            return await tick_once(settings, db, clock, SmtpMailer(settings, clock))
        finally:
            await db.dispose()

    try:
        counts = anyio.run(run)
    except Exception as error:
        _failed(TICK, error)
        marker(TICK, status="failed", error=type(error).__name__)
        raise typer.Exit(1) from error
    if counts.failed:
        raise typer.Exit(1)
