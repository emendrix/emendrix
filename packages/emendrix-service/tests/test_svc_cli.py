"""Every command exists; one not built in this version says so and exits 2."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from emendrix_service import DISCLAIMER
from emendrix_service.cli import app

runner = CliRunner()

COMMANDS = ("serve", "migrate", "load", "notify", "digest", "tick", "retention", "status")


def test_svc_help_lists_every_command_and_the_disclaimer() -> None:
    result = runner.invoke(app, ["--help"], terminal_width=200)
    assert result.exit_code == 0
    for command in (*COMMANDS, "mail", "backup"):
        assert command in result.output
    assert " ".join(DISCLAIMER.split()) in " ".join(result.output.split())


@pytest.mark.parametrize(
    ("argv", "name"),
    [
        (["load", "--rebuild"], "load"),
        (["notify"], "notify"),
        (["digest", "--now", "2026-10-12T05:00:00+00:00"], "digest"),
        (["tick"], "tick"),
        (["mail", "drain", "--limit", "5"], "mail drain"),
        (["retention"], "retention"),
        (["status", "--email"], "status"),
        (["backup", "ship", "dump.pgc"], "backup ship"),
    ],
)
def test_svc_a_stub_says_it_is_not_built(argv: list[str], name: str) -> None:
    result = runner.invoke(app, argv)
    assert result.exit_code == 2
    assert result.stderr == f"emendrix-service: {name} is not built in this version\n"


@pytest.mark.usefixtures("no_service_environment")
def test_svc_serve_stops_without_its_settings() -> None:
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_DATABASE_URL is not set\n"
