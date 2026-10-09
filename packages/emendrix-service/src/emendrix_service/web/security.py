"""The middleware every response passes through: headers, hosts, cookies and the request log.

The service sends its own content security policy. Account pages run no script and post forms
only to themselves, so the policy names no script source and allows `form-action 'self'`; the
proxy in front must send no second policy on these paths, since browsers enforce both and the
static site's forbids every form.

Each is a plain ASGI middleware, so it sees every response, the error pages and the host check's
refusal included, and never buffers a body.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Final

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from emendrix_service.web.csrf import NEW_PRE, PRE_COOKIE
from emendrix_service.web.session import REFRESH, set_session_cookie

__all__ = [
    "CONTENT_SECURITY_POLICY",
    "SECURITY_HEADERS",
    "CookieWriter",
    "HostCheck",
    "RequestLog",
    "SecurityHeaders",
    "loggable_path",
]

CONTENT_SECURITY_POLICY: Final = (
    "default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

SECURITY_HEADERS: Final = (
    ("content-security-policy", CONTENT_SECURITY_POLICY),
    ("strict-transport-security", "max-age=31536000; includeSubDomains"),
    ("x-content-type-options", "nosniff"),
    # A link token in a path must never travel to another host in a Referer.
    ("referrer-policy", "same-origin"),
    ("cache-control", "private, no-store"),
    ("permissions-policy", "camera=(), microphone=(), geolocation=(), interest-cohort=()"),
)

_TOKEN_PATHS: Final = re.compile(r"^(/account/confirm|/u/[^/]+)/.*$")
"""Paths whose remainder is a token, which no log line may carry."""

request_logger = logging.getLogger("emendrix_service.web")


def loggable_path(path: str) -> str:
    """`path` with any token in it replaced, fit for a log line."""
    return _TOKEN_PATHS.sub(r"\1/-", path)


class SecurityHeaders:
    """Sets the service's security headers on every response, replacing any of the same name."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._names = {name.encode() for name, _ in SECURITY_HEADERS}
        self._headers = [(name.encode(), value.encode()) for name, value in SECURITY_HEADERS]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                kept = [(k, v) for k, v in message.get("headers", ()) if k not in self._names]
                message["headers"] = [*kept, *self._headers]
            await send(message)

        await self.app(scope, receive, with_headers)


class HostCheck:
    """Answers 400 to a `Host` outside the allowed list, except on the two probe paths.

    The probes reach the pod by its own address, which is no public host name.
    """

    def __init__(self, app: ASGIApp, *, allowed_hosts: Iterable[str], exempt: Iterable[str]):
        self.app = app
        self.exempt = frozenset(exempt)
        self.checked = TrustedHostMiddleware(
            app, allowed_hosts=list(allowed_hosts), www_redirect=False
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in self.exempt:
            await self.app(scope, receive, send)
        else:
            await self.checked(scope, receive, send)


class CookieWriter:
    """Sets the cookies a request decided on while it ran: a minted pre-sign-in id, or a
    session whose expiry slid. Responses built anywhere (a page, a redirect, an error) get them."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state: dict[str, object] = scope.setdefault("state", {})

        async def with_cookies(message: Message) -> None:
            if message["type"] == "http.response.start":
                carrier = Response()
                pre = state.get(NEW_PRE)
                if isinstance(pre, str):
                    carrier.set_cookie(
                        PRE_COOKIE, pre, path="/", secure=True, httponly=True, samesite="lax"
                    )
                refresh = state.get(REFRESH)
                if isinstance(refresh, str):
                    set_session_cookie(carrier, refresh)
                cookies = [(k, v) for k, v in carrier.raw_headers if k == b"set-cookie"]
                message["headers"] = [*message.get("headers", ()), *cookies]
            await send(message)

        await self.app(scope, receive, with_cookies)


class RequestLog:
    """One line per request: method, path with tokens removed, status. No query, no body.

    The `quiet` paths (the probes, asked every few seconds) are not logged.
    """

    def __init__(self, app: ASGIApp, *, quiet: Iterable[str] = ()) -> None:
        self.app = app
        self.quiet = frozenset(quiet)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.quiet:
            await self.app(scope, receive, send)
            return
        status = [0]

        async def noting(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[0] = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, noting)
        finally:
            request_logger.info(
                "%s %s %d", scope["method"], loggable_path(scope["path"]), status[0]
            )
