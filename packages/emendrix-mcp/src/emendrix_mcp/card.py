"""The server card: what this server is and where to connect, answered before a client connects.

The card is built per request from the validated `Host`, `__version__` and `MCP_PATH`, so it
cannot drift from the code that answers the endpoint. It names no tool, resource, prompt or
capability, because those vary at run time and are listed over the protocol itself, and it
carries no `repository`, because that would be an address written into a module.

The shape follows `schema.json` and `docs/discovery.md` of the server-card extension, verified
2026-10-19 against github.com/modelcontextprotocol/experimental-ext-server-card (branch `main`):
required `$schema`, `description` (1 to 100 characters), `name`
(`^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$`) and `version`; each remote requires `type` and `url`;
served as `application/mcp-server-card+json` with `Access-Control-Allow-Origin: *`, an `ETag`
honoured by `If-None-Match`, and `Cache-Control: public, max-age=3600`.

The card's `name` is the reverse-DNS namespace the MCP Registry publishes under. Verified
2026-10-19 against `docs/modelcontextprotocol-io/authentication.mdx` of
github.com/modelcontextprotocol/registry, the registry proves control of that namespace either
by a DNS TXT record on the domain's apex, `v=MCPv1; k=ed25519; p=<base64 public key>`, or by
the same line served at `/.well-known/mcp-registry-auth` on the domain; it does not check that
the remote URL is on the domain. The protocol versions are the SDK's own, read from it.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from collections.abc import Mapping
from typing import Final
from urllib.parse import urlsplit, urlunsplit

from mcp.types.version import HANDSHAKE_PROTOCOL_VERSIONS, MODERN_PROTOCOL_VERSIONS
from pydantic import BaseModel, ConfigDict
from starlette.responses import Response

from emendrix_mcp import __version__
from emendrix_mcp.server import NAME
from emendrix_mcp.settings import MCP_PATH

__all__ = [
    "CARD_PATH",
    "DESCRIPTION",
    "MEDIA_TYPE",
    "Card",
    "build_card",
    "card_response",
    "endpoint",
    "registry_name",
]

CARD_PATH: Final = f"{MCP_PATH}/server-card"
MEDIA_TYPE: Final = "application/mcp-server-card+json"
DESCRIPTION: Final = "Verified changes to watched EU acts, read-only, with each fact's source."
SCHEMA_PATH: Final = "/schemas/v1/server-card.schema.json"
SCHEMA_HOST: Final = "static.modelcontextprotocol.io"

_CORS: Final = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET",
    "Access-Control-Allow-Headers": "Content-Type, If-None-Match",
    "Access-Control-Expose-Headers": "ETag",
}


class Card(BaseModel):
    """The card's bytes as served, and the strong validator that names them."""

    model_config = ConfigDict(frozen=True)

    body: bytes
    etag: str


def _hostname(host: str) -> str:
    return urlsplit(f"//{host}").hostname or host


def _is_domain(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return "." in hostname
    return False


def _scheme(hostname: str) -> str:
    """`http` for a developer's own machine only: the public scheme is invisible behind the
    TLS-terminating proxy, and `X-Forwarded-Proto` is the client's to set."""
    if hostname == "localhost":
        return "http"
    try:
        return "http" if ipaddress.ip_address(hostname).is_loopback else "https"
    except ValueError:
        return "https"


def registry_name(host: str) -> str:
    """The host's labels reversed, port dropped, then `/emendrix`; an IP or bare name as is."""
    hostname = _hostname(host.lower())
    namespace = ".".join(reversed(hostname.split("."))) if _is_domain(hostname) else hostname
    return f"{namespace.replace(':', '-')}/{NAME}"


def endpoint(host: str) -> str:
    """The streamable-HTTP URL a client connects to when it reached this server as `host`."""
    host = host.lower()
    return urlunsplit((_scheme(_hostname(host)), host, MCP_PATH, "", ""))


def build_card(host: str) -> Card:
    """The card for a request that named `host`, as canonical JSON bytes."""
    host = host.lower()
    scheme = _scheme(_hostname(host))
    card = {
        "$schema": urlunsplit(("https", SCHEMA_HOST, SCHEMA_PATH, "", "")),
        "name": registry_name(host),
        "title": NAME,
        "description": DESCRIPTION,
        "version": __version__,
        "websiteUrl": urlunsplit((scheme, host, "/", "", "")),
        "remotes": [
            {
                "type": "streamable-http",
                "url": endpoint(host),
                "supportedProtocolVersions": [
                    *HANDSHAKE_PROTOCOL_VERSIONS,
                    *MODERN_PROTOCOL_VERSIONS,
                ],
            }
        ],
    }
    text = json.dumps(card, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    body = text.encode("utf-8")
    return Card(body=body, etag=f'"{hashlib.sha256(body).hexdigest()[:32]}"')


def card_response(method: str, headers: Mapping[str, str]) -> Response:
    """The answer to any method on the card path from a request whose `Host` is accepted."""
    if method == "OPTIONS":
        return Response(status_code=204, headers={**_CORS, "Allow": "GET, HEAD, OPTIONS"})
    if method not in ("GET", "HEAD"):
        return Response(
            "The server card answers GET, HEAD and OPTIONS only.",
            status_code=405,
            media_type="text/plain",
            headers={"Allow": "GET, HEAD, OPTIONS"},
        )
    card = build_card(headers.get("host", ""))
    validators = {
        **_CORS,
        "ETag": card.etag,
        "Cache-Control": "public, max-age=3600",
        "Vary": "Host",
        "X-Content-Type-Options": "nosniff",
    }
    tags = {tag.strip().removeprefix("W/") for tag in headers.get("if-none-match", "").split(",")}
    if card.etag in tags or "*" in tags:
        return Response(status_code=304, headers=validators)
    return Response(card.body, media_type=MEDIA_TYPE, headers=validators)
