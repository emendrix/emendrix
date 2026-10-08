"""The settings a server runs with: each from its variable, each overridden by its flag.

`settings_from` is handed the environment as a mapping, so nothing here reads or changes the
test process's own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from emendrix_mcp.cli import VARIABLES, parser, settings_from
from emendrix_mcp.settings import DEFAULT_BIND, DEFAULT_PORT

BASE = {
    "EMENDRIX_MCP_CHANGELOGS": "/srv/changelogs",
    "EMENDRIX_MCP_ALLOWED_HOSTS": "mcp.example.org",
}


def test_each_setting_is_read_from_its_variable() -> None:
    environ = {
        **BASE,
        "EMENDRIX_MCP_CATALOGUE": "/srv/site/api/v1/catalogue.json",
        "EMENDRIX_MCP_BIND": "127.0.0.1",
        "EMENDRIX_MCP_PORT": "9000",
    }
    settings = settings_from([], environ)
    assert settings.changelogs == Path("/srv/changelogs")
    assert settings.catalogue == Path("/srv/site/api/v1/catalogue.json")
    assert settings.allowed_hosts == ("mcp.example.org",)
    assert (settings.bind, settings.port) == ("127.0.0.1", 9000)


def test_the_optional_settings_have_their_defaults() -> None:
    settings = settings_from([], BASE)
    assert settings.catalogue is None
    assert (settings.bind, settings.port) == (DEFAULT_BIND, DEFAULT_PORT)


@pytest.mark.parametrize(
    ("flag", "value", "field", "expected"),
    [
        ("--changelogs", "/elsewhere", "changelogs", Path("/elsewhere")),
        ("--catalogue", "/c.json", "catalogue", Path("/c.json")),
        ("--allowed-hosts", "a.example.org", "allowed_hosts", ("a.example.org",)),
        ("--bind", "::", "bind", "::"),
        ("--port", "8123", "port", 8123),
    ],
)
def test_a_flag_overrides_its_variable(flag: str, value: str, field: str, expected: object) -> None:
    environ = {
        **BASE,
        "EMENDRIX_MCP_CATALOGUE": "/srv/catalogue.json",
        "EMENDRIX_MCP_BIND": "127.0.0.1",
        "EMENDRIX_MCP_PORT": "9000",
    }
    assert getattr(settings_from([flag, value], environ), field) == expected


@pytest.mark.parametrize(
    ("variable", "flag"),
    [
        ("EMENDRIX_MCP_CHANGELOGS", "--changelogs"),
        ("EMENDRIX_MCP_ALLOWED_HOSTS", "--allowed-hosts"),
    ],
)
def test_a_missing_required_setting_stops_naming_it(
    variable: str, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    environ = {name: value for name, value in BASE.items() if name != variable}
    with pytest.raises(SystemExit) as stopped:
        settings_from([], environ)
    assert stopped.value.code != 0
    message = capsys.readouterr().err
    assert message.count("\n") == 1
    assert variable in message and flag in message


def test_the_allowed_hosts_split_on_commas_and_are_trimmed() -> None:
    environ = {**BASE, "EMENDRIX_MCP_ALLOWED_HOSTS": " mcp.example.org , mcp:8000,, "}
    assert settings_from([], environ).allowed_hosts == ("mcp.example.org", "mcp:8000")


def test_a_list_of_no_hosts_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        settings_from([], {**BASE, "EMENDRIX_MCP_ALLOWED_HOSTS": " , "})
    assert "EMENDRIX_MCP_ALLOWED_HOSTS" in capsys.readouterr().err


def test_a_port_that_is_not_one_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        settings_from([], {**BASE, "EMENDRIX_MCP_PORT": "eighty"})
    assert "EMENDRIX_MCP_PORT" in capsys.readouterr().err


def test_the_help_lists_every_variable() -> None:
    text = parser().format_help()
    for variable in VARIABLES.values():
        assert variable in text
