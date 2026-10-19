"""The MCP Registry descriptor and the server card state one fact: who the server is and where.

`server.json` is read by the registry's publisher, not by the server, so the hosted instance's
address may live in it. The card is computed from the request's `Host`; built for the hosted
host, it must name the same server, version and endpoint as the descriptor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emendrix_mcp import __version__
from emendrix_mcp.card import build_card, registry_name

DESCRIPTOR = Path(__file__).resolve().parents[1] / "server.json"
HOSTED = "emendrix.eu"


def _descriptor() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(DESCRIPTOR.read_text(encoding="utf-8"))
    return loaded


def test_the_descriptor_names_the_version_the_server_reports() -> None:
    assert _descriptor()["version"] == __version__


def test_the_descriptor_and_the_hosted_card_are_one_server() -> None:
    descriptor = _descriptor()
    card = json.loads(build_card(HOSTED).body)
    assert descriptor["name"] == registry_name(HOSTED) == card["name"]
    assert descriptor["remotes"][0]["url"] == card["remotes"][0]["url"]
    assert descriptor["remotes"][0]["type"] == card["remotes"][0]["type"]
    assert descriptor["description"] == card["description"]
    assert descriptor["title"] == card["title"]
    assert descriptor["websiteUrl"] == card["websiteUrl"]
