"""`emendrix-mcp`: read the settings from the environment and the command line, then serve.

This is the one module that reads the environment. Each setting has an `EMENDRIX_MCP_*`
variable and a flag of the same name, and the flag wins, so a container is configured through
its environment and a person at a shell can override one value without exporting anything. A
required setting that is missing stops the process with one line naming both, before anything
is read or bound.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Final, NoReturn

from pydantic import ValidationError

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.app import serve
from emendrix_mcp.settings import DEFAULT_BIND, DEFAULT_PORT, MCP_PATH, Settings

__all__ = ["VARIABLES", "main", "parser", "settings_from"]

VARIABLES: Final = {
    "changelogs": "EMENDRIX_MCP_CHANGELOGS",
    "catalogue": "EMENDRIX_MCP_CATALOGUE",
    "allowed_hosts": "EMENDRIX_MCP_ALLOWED_HOSTS",
    "bind": "EMENDRIX_MCP_BIND",
    "port": "EMENDRIX_MCP_PORT",
}
"""Each setting's environment variable. Its flag is the setting's name, dashed."""

_HELP: Final = {
    "changelogs": "required: the directory of a changelogs repository, read-only",
    "catalogue": "optional: a site build's api/v1/catalogue.json; without it every permalink "
    "is reported unavailable",
    "allowed_hosts": "required: comma-separated Host values to answer, such as "
    "'mcp.example.org,mcp:8000'; there is no default",
    "bind": f"optional: the address to listen on, default {DEFAULT_BIND}",
    "port": f"optional: the port to listen on, default {DEFAULT_PORT}",
}

_REQUIRED: Final = ("changelogs", "allowed_hosts")


def _flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def parser() -> argparse.ArgumentParser:
    """The command line. Every flag defaults to unset, so the variable behind it can apply."""
    described = argparse.ArgumentParser(
        prog="emendrix-mcp",
        description=f"A read-only MCP server over a published emendrix changelogs repository, "
        f"answering streamable HTTP at {MCP_PATH}. {DISCLAIMER}",
        epilog="Each flag can be set instead by the environment variable named beside it; "
        "the flag wins.",
    )
    for name, variable in VARIABLES.items():
        described.add_argument(_flag(name), dest=name, help=f"{_HELP[name]} [{variable}]")
    return described


def _stop(message: str) -> NoReturn:
    print(f"emendrix-mcp: {message}", file=sys.stderr)
    raise SystemExit(2)


def _hosts(value: str) -> tuple[str, ...]:
    return tuple(host.strip() for host in value.split(",") if host.strip())


def settings_from(argv: Sequence[str], environ: Mapping[str, str]) -> Settings:
    """The settings `argv` and `environ` give, or a stop naming what is missing or wrong."""
    flags = vars(parser().parse_args(list(argv)))
    chosen: dict[str, str] = {}
    for name, variable in VARIABLES.items():
        value = flags[name] if flags[name] is not None else environ.get(variable, "")
        if value.strip():
            chosen[name] = value.strip()
        elif name in _REQUIRED:
            _stop(f"{variable} is not set; set it or pass {_flag(name)}")
    values: dict[str, object] = dict(chosen)
    values["allowed_hosts"] = _hosts(chosen["allowed_hosts"])
    try:
        return Settings.model_validate(values)
    except ValidationError as error:
        problem = error.errors()[0]
        name = str(problem["loc"][0])
        _stop(f"{VARIABLES[name]} ({_flag(name)}) is not valid: {problem['msg']}")


def main(argv: Sequence[str] | None = None) -> None:
    """Configure from the process's environment and command line, then serve until stopped."""
    serve(settings_from(sys.argv[1:] if argv is None else argv, os.environ))
