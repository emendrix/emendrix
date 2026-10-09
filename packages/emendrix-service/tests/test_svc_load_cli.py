"""`emendrix-service load` refuses to start without its inputs and ends with one marker line."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emendrix_service.cli import app
from emendrix_service.settings import variable
from tests.conftest import SECRET_KEY, SITE_URL, TRUNCATE, execute
from tests.test_svc_load_run import copy_record

runner = CliRunner()


@pytest.fixture
def environment(
    no_service_environment: None, worker_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[pytest.MonkeyPatch]:
    """The variables every command needs, over this worker's database, emptied afterwards."""
    for name, value in (
        ("database_url", worker_url),
        ("site_url", SITE_URL),
        ("allowed_hosts", "example.org"),
        ("secret_key", SECRET_KEY),
    ):
        monkeypatch.setenv(variable(name), value)
    yield monkeypatch
    execute(worker_url, TRUNCATE)


def last_line(output: str) -> object:
    return json.loads(output.strip().splitlines()[-1])


def test_svc_load_stops_without_the_changelogs(environment: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["load"])
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_CHANGELOGS is not set\n"


def test_svc_load_runs_and_ends_with_its_marker(
    environment: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    environment.setenv(variable("changelogs"), str(record.changelogs))
    environment.setenv(variable("catalogue"), str(record.catalogue_path))
    result = runner.invoke(app, ["load"])
    assert result.exit_code == 0, result.output
    assert last_line(result.stdout) == {
        "emendrix_service": "load",
        "status": "complete",
        "upserted": 3,
        "removed": 0,
        "skipped": 0,
        "unsettled": 0,
    }
    again = runner.invoke(app, ["load", "--rebuild"])
    assert again.exit_code == 0, again.output
    assert last_line(again.stdout) == {
        "emendrix_service": "load",
        "status": "complete",
        "upserted": 3,
        "removed": 0,
        "skipped": 0,
        "unsettled": 0,
    }


def test_svc_load_fails_with_its_reason_when_the_catalogue_is_unreadable(
    environment: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    record = copy_record(tmp_path)
    environment.setenv(variable("changelogs"), str(record.changelogs))
    environment.setenv(variable("catalogue"), str(tmp_path / "missing.json"))
    result = runner.invoke(app, ["load"])
    assert result.exit_code == 1
    assert last_line(result.stdout) == {
        "emendrix_service": "load",
        "status": "failed",
        "upserted": 0,
        "removed": 0,
        "skipped": 0,
        "unsettled": 0,
        "reason": "permalink unavailable: the site catalogue this server was given could not "
        "be read",
    }
