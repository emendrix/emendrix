"""`mail drain` refuses without its settings and ends a run with one marker line."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from emendrix_service.cli import app
from emendrix_service.clock import FixedClock
from emendrix_service.db import Db
from emendrix_service.mail.cli import drain_once
from tests.conftest import SECRET_KEY, SITE_URL, service_settings

runner = CliRunner()

pytestmark = pytest.mark.usefixtures("no_service_environment")


def environment(database_url: str, **extra: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": database_url,
        "SITE_URL": SITE_URL,
        "ALLOWED_HOSTS": "example.org",
        "SECRET_KEY": SECRET_KEY,
        **extra,
    }
    return {f"EMENDRIX_SERVICE_{name}": value for name, value in values.items()}


def test_svc_mail_cli_drain_stops_without_a_relay(worker_url: str) -> None:
    result = runner.invoke(app, ["mail", "drain"], env=environment(worker_url))
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_SMTP_HOST is not set\n"
    result = runner.invoke(
        app, ["mail", "drain"], env=environment(worker_url, SMTP_HOST="relay.example.org")
    )
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_MAIL_FROM is not set\n"


def test_svc_mail_cli_drain_of_an_empty_outbox_ends_with_its_marker(
    worker_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    env = environment(
        worker_url, SMTP_HOST="relay.example.org", MAIL_FROM="Alerts <alerts@example.org>"
    )
    result = runner.invoke(app, ["mail", "drain", "--limit", "5"], env=env)
    assert result.exit_code == 0, result.output
    lines = [line for line in (result.stdout + capsys.readouterr().out).splitlines() if line]
    assert json.loads(lines[-1]) == {
        "emendrix_service": "mail drain",
        "status": "complete",
        "sent": 0,
        "retried": 0,
        "failed": 0,
        "suppressed": 0,
    }


@pytest.mark.anyio
async def test_svc_mail_cli_drain_once_needs_the_relay(
    db: Db, clock: FixedClock, worker_url: str
) -> None:
    with pytest.raises(ValueError, match="SMTP settings"):
        await drain_once(service_settings(worker_url), db, clock)
