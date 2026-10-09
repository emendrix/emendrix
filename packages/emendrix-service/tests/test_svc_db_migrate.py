"""`emendrix-service migrate` brings an empty database to the newest migration."""

from __future__ import annotations

import json
from collections.abc import Iterator

import anyio
import pytest
from typer.testing import CliRunner

from emendrix_service.cli import app
from emendrix_service.db import Db
from emendrix_service.db.migrate import current_matches_head
from emendrix_service.settings import variable
from tests.conftest import SECRET_KEY, SITE_URL, database_url, drop, execute, service_settings

runner = CliRunner()


@pytest.fixture
def empty_url(pg_url: str, worker_id: str) -> Iterator[str]:
    name = f"svc_{worker_id}_empty"
    execute(pg_url, f"DROP DATABASE IF EXISTS {name} WITH (FORCE)", f"CREATE DATABASE {name}")
    yield database_url(pg_url, name)
    drop(pg_url, name)


async def at_head(url: str) -> bool:
    db = Db.connect(service_settings(url))
    try:
        return await current_matches_head(db)
    finally:
        await db.dispose()


@pytest.mark.usefixtures("no_service_environment")
def test_svc_migrate_upgrades_an_empty_database(
    empty_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in (
        ("database_url", empty_url),
        ("site_url", SITE_URL),
        ("allowed_hosts", "example.org"),
        ("secret_key", SECRET_KEY),
    ):
        monkeypatch.setenv(variable(name), value)
    assert not anyio.run(at_head, empty_url)
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output
    last = json.loads(result.stdout.strip().splitlines()[-1])
    assert last == {"emendrix_service": "migrate", "status": "complete", "head": "0001"}
    assert anyio.run(at_head, empty_url)
    again = runner.invoke(app, ["migrate"])
    assert again.exit_code == 0, again.output


@pytest.mark.usefixtures("no_service_environment")
def test_svc_migrate_stops_without_its_settings() -> None:
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_DATABASE_URL is not set\n"
