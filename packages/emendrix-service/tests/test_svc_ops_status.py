"""The status block: every count labelled, the disclaimer at its end, and no address in it."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from typer.testing import CliRunner

from emendrix_service import DISCLAIMER
from emendrix_service.cli import app
from emendrix_service.db import Db
from emendrix_service.db.enums import (
    Cadence,
    DeliveryKind,
    ItemKind,
    MailEventKind,
    OutboxPurpose,
    OutboxStatus,
    SuppressionReason,
    UserStatus,
)
from emendrix_service.db.suppressions import email_sha256
from emendrix_service.db.tables import (
    Announced,
    Delivery,
    Load,
    MailEvent,
    Outbox,
    Suppression,
    User,
    WatchItem,
    Watchlist,
)
from emendrix_service.ops.cli import report
from tests.conftest import NOW, SECRET_KEY, SITE_URL, TRUNCATE, execute

ALICE = "alice.reader@example.org"
BOB = "bob.reader@example.org"
OPERATOR = "operator@example.org"


def user(email: str, status: UserStatus = UserStatus.ACTIVE) -> User:
    return User(
        email=email,
        status=status,
        created_at=NOW,
        verified_at=NOW,
        last_signin_at=NOW,
        last_seen_at=NOW,
    )


def watchlist(owner: User, cadence: Cadence, *, paused: bool = False) -> Watchlist:
    return Watchlist(
        user_id=owner.id,
        name=f"{cadence} list",
        cadence=cadence,
        date_alerts=True,
        paused=paused,
        created_at=NOW,
    )


def item(owner: Watchlist, act_key: str, location: str | None = None) -> WatchItem:
    return WatchItem(
        watchlist_id=owner.id,
        kind=ItemKind.ACT if location is None else ItemKind.PROVISION,
        corpus="eu",
        act_key=act_key,
        location=location,
        created_at=NOW,
    )


def outbox(to: str, status: OutboxStatus, *, age: timedelta, user_id: UUID | None) -> Outbox:
    return Outbox(
        user_id=user_id,
        purpose=OutboxPurpose.WEEKLY,
        to_email=to,
        subject="a digest",
        text_body="body",
        html_body="<p>body</p>",
        headers=[],
        status=status,
        attempts=0,
        next_attempt_at=NOW - age,
        created_at=NOW - age,
    )


async def seed(db: Db) -> None:
    alice, bob = user(ALICE), user(BOB, UserStatus.SUSPENDED)
    async with db.transaction() as tx:
        tx.add_all([alice, bob])
        await tx.flush()
        weekly, instant = watchlist(alice, Cadence.WEEKLY), watchlist(alice, Cadence.INSTANT)
        quiet = watchlist(bob, Cadence.DAILY, paused=True)
        tx.add_all([weekly, instant, quiet])
        await tx.flush()
        tx.add_all(
            [
                item(weekly, "32017R0745"),
                item(weekly, "32017R0745", "AR 6"),
                item(quiet, "32017R0745", "AR 7"),
                item(instant, "32024R1689", "AR 5"),
            ]
        )
        tx.add(
            Load(
                root_sha256="ab" * 32,
                started_at=NOW - timedelta(minutes=5),
                finished_at=NOW - timedelta(minutes=4),
                events_upserted=3,
                events_removed=1,
                events_skipped=120,
            )
        )
        tx.add_all(
            [
                Announced(event_key="eu/a@1", first_seen_at=NOW, eligible=True, reason="ok"),
                Announced(event_key="eu/a@2", first_seen_at=NOW, eligible=False, reason="old"),
                Announced(
                    event_key="eu/a@0",
                    first_seen_at=NOW - timedelta(days=3),
                    eligible=True,
                    reason="ok",
                ),
            ]
        )
        tx.add_all(
            [
                Delivery(
                    watchlist_id=instant.id,
                    kind=DeliveryKind.INSTANT,
                    period_key="eu/a@1",
                    created_at=NOW,
                ),
                Delivery(
                    watchlist_id=weekly.id,
                    kind=DeliveryKind.WEEKLY,
                    period_key="2026-W41",
                    created_at=NOW - timedelta(days=2),
                ),
            ]
        )
        tx.add_all(
            [
                outbox(ALICE, OutboxStatus.QUEUED, age=timedelta(minutes=30), user_id=alice.id),
                outbox(ALICE, OutboxStatus.QUEUED, age=timedelta(minutes=2), user_id=alice.id),
                outbox(BOB, OutboxStatus.FAILED, age=timedelta(hours=2), user_id=bob.id),
                outbox(BOB, OutboxStatus.FAILED, age=timedelta(days=3), user_id=bob.id),
                outbox(ALICE, OutboxStatus.SENT, age=timedelta(hours=1), user_id=alice.id),
            ]
        )
        tx.add_all(
            [
                MailEvent(email_sha256=email_sha256(BOB), kind=MailEventKind.HARD_BOUNCE, at=NOW),
                MailEvent(email_sha256=email_sha256(ALICE), kind=MailEventKind.DELIVERED, at=NOW),
                MailEvent(
                    email_sha256=email_sha256(ALICE),
                    kind=MailEventKind.SOFT_BOUNCE,
                    at=NOW - timedelta(days=9),
                ),
                Suppression(
                    email_sha256=email_sha256(BOB),
                    reason=SuppressionReason.HARD_BOUNCE,
                    created_at=NOW,
                ),
            ]
        )


@pytest.mark.anyio
async def test_svc_ops_status_counts_everything_and_names_no_one(db: Db) -> None:
    await seed(db)
    text = await report(db, NOW)
    expected = [
        "Emendrix account service status at 2026-10-12 05:00 UTC",
        "Last load: started 2026-10-12 04:55 UTC, finished 2026-10-12 04:56 UTC",
        "  root index digest abababababababab",
        "  events upserted 3, removed 1, skipped 120",
        "Announcements, last 24 h: eligible 1, not eligible 1",
        "Deliveries, last 24 h: instant 1, daily 0, weekly 0, heartbeat 0",
        "Outbox: queued 2 (oldest waiting 30 min); failed: 1 written in the last 24 h, "
        "2 held in all",
        "Mail events, last 7 days: hard bounces 1, soft bounces 0, complaints 0, delivered 1",
        "Suppressed addresses: 1 (hard bounce 1, complaint 0, soft bounces 0)",
        "Accounts: 2 (active 1, suspended 1)",
        "Watchlists: 3 by cadence (instant 1, daily 1, weekly 1, none 0), paused 1",
        "Watch items per act:",
        "  eu/32017R0745: 3 (act 1, provision 2)",
        "  eu/32024R1689: 1 (act 0, provision 1)",
    ]
    lines = text.splitlines()
    for line in expected:
        assert line in lines, line
    assert text.rstrip().endswith(DISCLAIMER)
    for address in (ALICE, BOB, "alice", "bob", "@"):
        assert address not in text


@pytest.mark.anyio
async def test_svc_ops_status_of_an_empty_database_says_so(db: Db) -> None:
    text = await report(db, NOW)
    assert "Last load: none recorded" in text
    assert "Outbox: queued 0 (none waiting)" in text
    assert "Watch items per act: none" in text


@pytest.mark.anyio
async def test_svc_ops_status_email_queues_one_operator_row(db: Db) -> None:
    await seed(db)
    text = await report(db, NOW, email_to=OPERATOR)
    async with db.transaction() as tx:
        rows = list(
            await tx.scalars(select(Outbox).where(Outbox.purpose == OutboxPurpose.OPERATOR))
        )
    assert len(rows) == 1
    row = rows[0]
    assert (row.to_email, row.user_id, row.status) == (OPERATOR, None, OutboxStatus.QUEUED)
    assert row.next_attempt_at == NOW
    assert row.text_body == text
    assert row.subject == "[Emendrix] Status at 2026-10-12 05:00 UTC"
    assert "Accounts: 2" in row.html_body


# --- the command ----------------------------------------------------------------------------

runner = CliRunner()


def environment(database_url: str, **extra: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": database_url,
        "SITE_URL": SITE_URL,
        "ALLOWED_HOSTS": "example.org",
        "SECRET_KEY": SECRET_KEY,
        **extra,
    }
    return {f"EMENDRIX_SERVICE_{name}": value for name, value in values.items()}


@pytest.mark.usefixtures("no_service_environment")
def test_svc_ops_status_email_needs_the_operator_address(worker_url: str) -> None:
    result = runner.invoke(app, ["status", "--email"], env=environment(worker_url))
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_OPERATOR_EMAIL is not set\n"


@pytest.mark.usefixtures("no_service_environment")
def test_svc_ops_status_command_prints_the_block_and_its_marker(
    worker_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    env = environment(worker_url, OPERATOR_EMAIL=OPERATOR)
    try:
        result = runner.invoke(app, ["status", "--email"], env=env)
        purposes = queued_purposes(worker_url)
    finally:
        execute(worker_url, TRUNCATE)
    assert result.exit_code == 0, result.output
    output = result.stdout + capsys.readouterr().out
    assert "Emendrix account service status at " in output
    assert OPERATOR not in output
    lines = [line for line in output.splitlines() if line]
    assert json.loads(lines[-1]) == {
        "emendrix_service": "status",
        "status": "complete",
        "emailed": 1,
    }
    assert purposes == ["operator"]


def queued_purposes(url: str) -> list[str]:
    plain = make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(plain) as connection:
        rows = connection.execute("SELECT purpose::text FROM app.outbox").fetchall()
    return [str(row[0]) for row in rows]
