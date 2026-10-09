"""Every command exists, and one missing its settings refuses to start with exit 2."""

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


@pytest.mark.usefixtures("no_service_environment")
def test_svc_serve_stops_without_its_settings() -> None:
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 2
    assert result.stderr == "emendrix-service: EMENDRIX_SERVICE_DATABASE_URL is not set\n"
