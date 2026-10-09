"""Which client a request came from, for rate limits only.

The configured header is trusted as written because only the proxy in front of the service can
reach it, and the proxy sets the header itself. It must be a header the proxy overwrites with
one value (the edge's client address), never one it appends to such as `X-Forwarded-For`, whose
first value the client chooses. Without the setting the peer address is used, which behind a
proxy is the proxy's own.
"""

from __future__ import annotations

from typing import Final

from fastapi import Request

from emendrix_service.settings import ServiceSettings

__all__ = ["UNKNOWN_CLIENT", "client_ip"]

UNKNOWN_CLIENT: Final = "unknown"
"""The key a request with no peer and no header is counted under."""


def client_ip(request: Request, settings: ServiceSettings) -> str:
    """The client's address: the header's first value when the header is configured and sent."""
    if settings.client_ip_header:
        stated = request.headers.get(settings.client_ip_header, "").split(",")[0].strip()
        if stated:
            return stated
    return request.client.host if request.client else UNKNOWN_CLIENT
