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
from emendrix_mcp.server import TOOLS
from emendrix_mcp.tools_text import get_change
from emendrix_record.record import Record

FIXTURES = Path(__file__).resolve().parents[2] / "emendrix-record" / "tests" / "fixtures"
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


def test_tools_list_is_one_json_response_naming_the_eight_tools(client: TestClient) -> None:
    response = _call(client, "tools/list")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "mcp-session-id" not in response.headers
    names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert sorted(names) == sorted(TOOLS) and len(names) == 8


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
    assert "/mcp/server-card" in response.text and "/llms.txt" in response.text
    assert response.text.isascii()


CORS = {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET",
    "access-control-allow-headers": "Content-Type, If-None-Match",
    "access-control-expose-headers": "ETag",
}


def test_the_server_card_is_served_with_its_validators(client: TestClient) -> None:
    response = client.get("/mcp/server-card")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/mcp-server-card+json"
    assert {key: response.headers[key] for key in CORS} == CORS
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["vary"] == "Host"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["etag"]
    card = response.json()
    assert card["remotes"][0]["url"] == f"https://{HOST}/mcp"


def test_a_matching_etag_gets_304_with_no_body(client: TestClient) -> None:
    etag = client.get("/mcp/server-card").headers["etag"]
    response = client.get("/mcp/server-card", headers={"if-none-match": etag})
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == etag
    stale = client.get("/mcp/server-card", headers={"if-none-match": '"0"'})
    assert stale.status_code == 200


def test_head_on_the_card_answers_like_get(client: TestClient) -> None:
    response = client.head("/mcp/server-card")
    assert response.status_code == 200
    assert response.headers["etag"] == client.get("/mcp/server-card").headers["etag"]


def test_the_card_preflight_is_answered(client: TestClient) -> None:
    response = client.options("/mcp/server-card", headers={"origin": "https://app.example.org"})
    assert response.status_code == 204
    assert {key: response.headers[key] for key in CORS} == CORS


def test_the_card_answers_read_methods_only(client: TestClient) -> None:
    response = client.post("/mcp/server-card", json={})
    assert response.status_code == 405
    assert response.headers["allow"] == "GET, HEAD, OPTIONS"


def test_the_card_keeps_the_host_check(client: TestClient) -> None:
    assert client.get("/mcp/server-card", headers={"host": "evil.example"}).status_code == 421


def test_a_plain_http_origin_blocks_the_endpoint_but_not_the_card(client: TestClient) -> None:
    origin = "http://evil.example"
    assert client.get("/mcp/server-card", headers={"origin": origin}).status_code == 200
    assert _call(client, "tools/list", origin=origin).status_code == 403


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
