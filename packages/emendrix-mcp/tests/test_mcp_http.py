"""The server over HTTP, driven in process through its ASGI app: no socket and no network.

Hosts are `example.org` names throughout, so nothing here can depend on the hosted instance's
address. Each request is a plain JSON-RPC POST with no `initialize` before it and no session
header, which is what stateless means to a client.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from starlette.testclient import TestClient

from emendrix_mcp import DISCLAIMER
from emendrix_mcp.app import create_app
from emendrix_mcp.record import Record
from emendrix_mcp.server import TOOLS
from emendrix_mcp.tools_text import get_change

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HOST = "mcp.example.org"
ACCEPT = {"accept": "application/json, text/event-stream"}


def _record() -> Record:
    return Record(FIXTURES / "changelogs", FIXTURES / "catalogue.json")


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    app = create_app(_record(), allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}") as served:
        yield served


def _call(
    client: TestClient, method: str, params: dict[str, Any] | None = None, **headers: str
) -> httpx2.Response:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body, headers={**ACCEPT, **headers})


def test_tools_list_is_one_json_response_naming_the_seven_tools(client: TestClient) -> None:
    response = _call(client, "tools/list")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "mcp-session-id" not in response.headers
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert sorted(names) == sorted(TOOLS) and len(names) == 7


def test_get_change_over_http_returns_the_stored_change(client: TestClient) -> None:
    arguments = {"act": "house-rules", "version": "v3", "location": "AR 9"}
    response = _call(client, "tools/call", {"name": "get_change", "arguments": arguments})
    assert response.status_code == 200
    result = response.json()["result"]
    assert not result.get("isError")
    stored = get_change(_record(), "house-rules", "v3", "AR 9")
    assert result["structuredContent"] == json.loads(stored.model_dump_json())
    assert result["structuredContent"]["disclaimer"] == DISCLAIMER


def test_two_requests_share_no_state(client: TestClient) -> None:
    first = _call(client, "tools/list")
    second = _call(client, "tools/call", {"name": "list_acts", "arguments": {}})
    assert first.status_code == second.status_code == 200
    assert "error" not in first.json() and "error" not in second.json()
    assert "mcp-session-id" not in first.headers and "mcp-session-id" not in second.headers


def test_a_host_not_configured_is_refused(client: TestClient) -> None:
    assert _call(client, "tools/list", host="evil.example").status_code == 421


@pytest.mark.parametrize("origin", ["http://localhost:1234", "null", "https://", "file://x"])
def test_an_origin_that_is_not_https_is_refused(client: TestClient, origin: str) -> None:
    assert _call(client, "tools/list", origin=origin).status_code == 403


@pytest.mark.parametrize("origin", [None, "https://claude.ai", "https://app.example.org:8443"])
def test_no_origin_or_an_https_one_is_answered(client: TestClient, origin: str | None) -> None:
    headers = {} if origin is None else {"origin": origin}
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**ACCEPT, **headers},
    )
    assert response.status_code == 200


def test_only_post_is_answered_and_no_stream_is_opened(client: TestClient) -> None:
    response = client.get("/mcp", headers=ACCEPT)
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"


def test_an_oversized_body_is_refused(client: TestClient) -> None:
    response = client.post(
        "/mcp", content=b" " * (65 * 1024), headers={**ACCEPT, "content-type": "application/json"}
    )
    assert response.status_code == 413


def test_the_probe_answers_ok_whatever_the_host(client: TestClient) -> None:
    response = client.get("/healthz", headers={"host": "10.0.0.7:8000"})
    assert response.status_code == 200
    assert response.text == "ok"


def test_the_probe_fails_when_the_record_cannot_be_read(tmp_path: Path) -> None:
    app = create_app(Record(tmp_path, None), allowed_hosts=(HOST,))
    with TestClient(app, base_url=f"http://{HOST}") as served:
        response = served.get("/healthz")
    assert response.status_code == 503
    assert "index.json" in response.text
