"""The server over HTTP: MCP at `/mcp`, stateless, one JSON response per request, and a probe.

This is the one module that imports the ASGI server and listens. Every request is answered on
its own, with no session and no stream held open, so any replica can answer any request and a
proxy in front needs no affinity.

The endpoint is keyless and read-only over public data, so a cross-origin page has nothing to
act on; the Host and Origin check exists to refuse DNS-rebinding shapes. A request must name one
of the configured hosts, and may carry no `Origin` or an `https` one: a plain `http` origin and
the opaque `null` are refused. The SDK's own check matches origins only exactly or by port
wildcard and cannot say "any `https` origin", so it is switched off and this one sits in front.
`GET /healthz` is left outside it, because a probe reaches the pod by its own address.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from urllib.parse import urlsplit

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from emendrix_mcp.server import build_server
from emendrix_mcp.settings import MCP_PATH, Settings
from emendrix_record.reads import Unavailable
from emendrix_record.record import Record

__all__ = ["HEALTH_PATH", "MAX_BODY", "create_app", "health", "refusal", "serve"]

HEALTH_PATH: Final = "/healthz"

MAX_BODY: Final = 64 * 1024
"""Bytes a request body may hold. A tool call names an act, a version and a location."""


def _secure(origin: str) -> bool:
    try:
        parts = urlsplit(origin)
        return parts.scheme == "https" and bool(parts.hostname)
    except ValueError:
        return False


def refusal(
    headers: Mapping[str, str], method: str, allowed_hosts: frozenset[str]
) -> Response | None:
    """Why a request to the endpoint is refused, or None when it may be answered."""
    if headers.get("host", "").lower() not in allowed_hosts:
        return PlainTextResponse("This server does not answer for that Host.", status_code=421)
    origin = headers.get("origin")
    if origin is not None and not _secure(origin):
        return PlainTextResponse("Only an https Origin, or none, is accepted.", status_code=403)
    if method != "POST":
        return PlainTextResponse(
            "The endpoint answers POST only; it holds no stream open.",
            status_code=405,
            headers={"Allow": "POST"},
        )
    return None


def health(record: Record) -> Response:
    """`ok` when the root index can be read now, else why not, so a probe sees a broken mount."""
    root = record.root()
    if isinstance(root, Unavailable):
        return PlainTextResponse(root.reason, status_code=503)
    return PlainTextResponse("ok")


class _Front:
    """The probe, then the Host, Origin and method check, then the SDK's app."""

    def __init__(self, app: ASGIApp, record: Record, allowed_hosts: frozenset[str]) -> None:
        self._app = app
        self._record = record
        self._allowed_hosts = allowed_hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            answer: Response | None
            if scope["path"] == HEALTH_PATH and scope["method"] in ("GET", "HEAD"):
                answer = health(self._record)
            else:
                answer = refusal(Headers(scope=scope), scope["method"], self._allowed_hosts)
            if answer is not None:
                await answer(scope, receive, send)
                return
        await self._app(scope, receive, send)


def create_app(record: Record, *, allowed_hosts: tuple[str, ...]) -> ASGIApp:
    """The ASGI app serving `record` at `/mcp` to requests naming one of `allowed_hosts`."""
    inner = build_server(record).streamable_http_app(
        streamable_http_path=MCP_PATH,
        json_response=True,
        stateless_http=True,
        max_request_body_size=MAX_BODY,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return _Front(inner, record, frozenset(host.lower() for host in allowed_hosts))


def serve(settings: Settings) -> None:
    """Listen on the configured address until the process is stopped."""
    record = Record(settings.changelogs, settings.catalogue)
    app = create_app(record, allowed_hosts=settings.allowed_hosts)
    uvicorn.run(app, host=settings.bind, port=settings.port, server_header=False)
