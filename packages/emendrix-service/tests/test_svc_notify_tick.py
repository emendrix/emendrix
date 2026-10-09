"""`tick` chains load, notify, digest and drain, ends with one marker, and survives a failed
step."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix_service.cli import app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.db.enums import Cadence
from emendrix_service.log import MARKER_LOGGER, JsonFormatter
from emendrix_service.mail.port import RecordingMailer
from emendrix_service.notify.cli import TickCounts, tick_once
from emendrix_service.notify.run import notify
from tests.conftest import NOW, SECRET_KEY, SITE_URL
from tests.test_svc_load_run import copy_record
from tests.test_svc_notify_run import add_watchlist, go_live, notify_settings

runner = CliRunner()


def markers(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    formatter = JsonFormatter()
    return [
        json.loads(formatter.format(record))
        for record in caplog.records
        if record.name == MARKER_LOGGER
    ]


@pytest.mark.anyio
async def test_svc_notify_tick_sends_a_new_event_to_its_instant_watcher(
    db: Db, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "instant@example.org", cadence=Cadence.INSTANT)
    await add_watchlist(db, "weekly@example.org")
    await go_live(db, record)
    mailer = RecordingMailer()
    caplog.set_level(logging.INFO, logger=MARKER_LOGGER)
    settings = notify_settings(record)
    counts = await tick_once(settings, db, FixedClock(NOW), mailer, pace=0)
    assert counts == TickCounts(announced=1, eligible=1, matches=10, deliveries=1, sent=1)
    assert [mail.to for mail in mailer.sent] == ["instant@example.org"]
    assert dict(mailer.sent[0].headers)["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert markers(caplog) == [
        {
            "emendrix_service": "tick",
            "status": "complete",
            "loaded": 0,
            "announced": 1,
            "eligible": 1,
            "matches": 10,
            "deliveries": 1,
            "sent": 1,
        }
    ]
    again = await tick_once(settings, db, FixedClock(NOW + timedelta(minutes=5)), mailer, pace=0)
    assert again == TickCounts()
    assert len(mailer.sent) == 1


@pytest.mark.anyio
async def test_svc_notify_a_failed_load_still_lets_digests_and_mail_go(
    db: Db, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    record = copy_record(tmp_path)
    await add_watchlist(db, "weekly@example.org")
    await go_live(db, record)
    await notify(db, notify_settings(record), NOW - timedelta(days=1))
    broken = notify_settings(record, changelogs=tmp_path / "missing")
    mailer = RecordingMailer()
    caplog.set_level(logging.INFO, logger=MARKER_LOGGER)
    counts = await tick_once(broken, db, FixedClock(NOW), mailer, pace=0)
    assert counts == TickCounts(failed=True, deliveries=1, sent=1)
    assert [mail.to for mail in mailer.sent] == ["weekly@example.org"]
    assert [line["status"] for line in markers(caplog)] == ["failed"]


def environment(database_url: str, tmp_path: Path, **extra: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": database_url,
        "SITE_URL": SITE_URL,
        "ALLOWED_HOSTS": "example.org",
        "SECRET_KEY": SECRET_KEY,
        "CHANGELOGS": str(tmp_path / "missing"),
        "CATALOGUE": str(tmp_path / "catalogue.json"),
        "LIVE_SINCE": "2026-10-01",
        "SMTP_HOST": "relay.example.org",
        "MAIL_FROM": "Emendrix alerts <alerts@example.org>",
        **extra,
    }
    return {f"EMENDRIX_SERVICE_{name}": value for name, value in values.items() if value}


@pytest.mark.usefixtures("no_service_environment")
def test_svc_notify_cli_tick_exits_1_when_a_step_failed(
    worker_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = runner.invoke(app, ["tick"], env=environment(worker_url, tmp_path))
    assert result.exit_code == 1
    lines = [line for line in (result.stdout + capsys.readouterr().out).splitlines() if line]
    marker = json.loads(lines[-1])
    assert (marker["emendrix_service"], marker["status"]) == ("tick", "failed")


@pytest.mark.usefixtures("no_service_environment")
@pytest.mark.parametrize(
    ("argv", "unset", "variable"),
    [
        (["tick"], "CHANGELOGS", "EMENDRIX_SERVICE_CHANGELOGS"),
        (["tick"], "LIVE_SINCE", "EMENDRIX_SERVICE_LIVE_SINCE"),
        (["tick"], "SMTP_HOST", "EMENDRIX_SERVICE_SMTP_HOST"),
        (["notify"], "LIVE_SINCE", "EMENDRIX_SERVICE_LIVE_SINCE"),
    ],
)
def test_svc_notify_cli_stops_without_what_it_needs(
    worker_url: str, tmp_path: Path, argv: list[str], unset: str, variable: str
) -> None:
    env = environment(worker_url, tmp_path, **{unset: ""})
    result = runner.invoke(app, argv, env=env)
    assert result.exit_code == 2
    assert result.stderr == f"emendrix-service: {variable} is not set\n"


@pytest.mark.usefixtures("no_service_environment")
def test_svc_notify_cli_digest_takes_an_instant_with_an_offset(
    worker_url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = environment(worker_url, tmp_path)
    refused = runner.invoke(app, ["digest", "--now", "2026-10-12T07:00:00"], env=env)
    assert refused.exit_code == 2
    result = runner.invoke(app, ["digest", "--now", "2026-10-12T07:00:00+02:00"], env=env)
    assert result.exit_code == 0, result.output
    lines = [line for line in (result.stdout + capsys.readouterr().out).splitlines() if line]
    assert json.loads(lines[-1]) == {
        "emendrix_service": "digest",
        "status": "complete",
        "daily": 0,
        "weekly": 0,
        "heartbeat": 0,
        "failed": 0,
    }
