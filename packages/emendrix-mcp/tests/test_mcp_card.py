"""The server card, built in process from a `Host`: its shape, its name and its stable bytes.

The required fields and patterns below were read from the server-card extension's `schema.json`
(github.com/modelcontextprotocol/experimental-ext-server-card, branch `main`) on 2026-10-19.
The schema is not fetched here: CI never touches the network.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from emendrix_mcp import __version__
from emendrix_mcp.card import build_card, registry_name
from emendrix_mcp.settings import MCP_PATH

HOST = "mcp.example.org"
REQUIRED = ("$schema", "description", "name", "version")
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
SCHEMA_PATTERN = re.compile(
    r"^https://static\.modelcontextprotocol\.io/schemas/v1/server-card\.schema\.json$"
)


def _card(host: str = HOST) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(build_card(host).body)
    return loaded


def test_the_card_carries_every_required_field() -> None:
    card = _card()
    assert all(field in card for field in REQUIRED)
    assert 1 <= len(card["description"]) <= 100
    assert NAME_PATTERN.match(card["name"])
    assert 3 <= len(card["name"]) <= 200
    assert SCHEMA_PATTERN.match(card["$schema"])


def test_the_remote_is_the_streamable_http_endpoint() -> None:
    remote = _card()["remotes"][0]
    assert remote["type"] == "streamable-http"
    assert remote["url"].endswith(MCP_PATH)
    assert remote["supportedProtocolVersions"]


def test_the_card_lists_nothing_that_varies_at_run_time() -> None:
    assert not {"tools", "resources", "prompts", "capabilities"} & set(_card())


@pytest.mark.parametrize(
    ("host", "name"),
    [
        ("emendrix.eu", "eu.emendrix/emendrix"),
        ("mcp.example.org:8443", "org.example.mcp/emendrix"),
        ("localhost:8080", "localhost/emendrix"),
        ("127.0.0.1:8000", "127.0.0.1/emendrix"),
    ],
)
def test_the_name_is_the_host_reversed_without_its_port(host: str, name: str) -> None:
    assert registry_name(host) == name
    assert NAME_PATTERN.match(name)


@pytest.mark.parametrize(
    ("host", "url"),
    [
        (HOST, "https://mcp.example.org/mcp"),
        ("mcp.example.org:8443", "https://mcp.example.org:8443/mcp"),
        ("localhost:8080", "http://localhost:8080/mcp"),
        ("127.0.0.1:8000", "http://127.0.0.1:8000/mcp"),
    ],
)
def test_only_a_loopback_host_is_given_plain_http(host: str, url: str) -> None:
    card = _card(host)
    assert card["remotes"][0]["url"] == url
    assert card["websiteUrl"] == url.removesuffix("mcp")


def test_the_bytes_and_the_etag_are_stable_and_follow_the_host() -> None:
    first, second = build_card(HOST), build_card(HOST)
    assert first == second
    assert first.body.endswith(b"\n") and first.body.isascii()
    assert re.fullmatch(r'"[0-9a-f]{32}"', first.etag)
    assert build_card("other.example.org").etag != first.etag


def test_the_version_is_the_server_version() -> None:
    assert _card()["version"] == __version__
