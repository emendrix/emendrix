"""Cross-site request forgery: a signed token in every form, checked on every account POST.

The token is an HMAC (`signing`, purpose `csrf`) over what binds the form to this browser: the
hash of the session cookie when there is one, else a random pre-sign-in id kept in its own
cookie. Nothing is stored server-side. A form rendered for a visitor with neither cookie mints
the pre-sign-in id, and `CookieWriter` sets its cookie on the way out, so the first page with a
form is also the one that makes its own post verifiable.

Paths under `/u/` are not checked: they carry their own signed token in the path and are posted
by mail clients (one-click unsubscribe), which hold no cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Final

from fastapi import HTTPException, Request
from markupsafe import Markup, escape
from starlette.datastructures import FormData

from emendrix_service.signing import sign, verify

__all__ = [
    "CSRF_FIELD",
    "PRE_COOKIE",
    "PROTECTED_PREFIX",
    "SESSION_COOKIE",
    "csrf_field",
    "csrf_protect",
    "csrf_token",
    "verify_csrf",
]

SESSION_COOKIE: Final = "__Host-emendrix"
PRE_COOKIE: Final = "__Host-emendrix-pre"
CSRF_FIELD: Final = "csrf"
PROTECTED_PREFIX: Final = "/account/"

NEW_PRE: Final = "emendrix_new_pre"
"""The request-state key holding a pre-sign-in id minted during this request."""

_PRE_SHAPE: Final = re.compile(r"[A-Za-z0-9_-]{22}")
"""`secrets.token_urlsafe(16)`: 128 bits, 22 characters."""


def session_hash(token: str) -> bytes:
    """The sha256 a session is stored under."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def _binding(request: Request) -> str | None:
    session = request.cookies.get(SESSION_COOKIE)
    if session:
        return f"s:{session_hash(session).hex()}"
    pre = request.cookies.get(PRE_COOKIE) or getattr(request.state, NEW_PRE, None)
    if pre and _PRE_SHAPE.fullmatch(pre):
        return f"p:{pre}"
    return None


def csrf_token(request: Request) -> str:
    """The token a form on this page carries; mints a pre-sign-in id when the visitor has none."""
    binding = _binding(request)
    if binding is None:
        pre = secrets.token_urlsafe(16)
        setattr(request.state, NEW_PRE, pre)
        binding = f"p:{pre}"
    return sign("csrf", binding, secret=request.app.state.settings.secret_key)


def csrf_field(request: Request) -> Markup:
    """The hidden input every account form carries."""
    token = escape(csrf_token(request))
    return Markup(f'<input type="hidden" name="{CSRF_FIELD}" value="{token}">')


def verify_csrf(request: Request, form: FormData) -> None:
    """Raise 403 unless `form` carries the token this browser's cookies bind to."""
    sent = form.get(CSRF_FIELD)
    expected = _binding(request)
    if not isinstance(sent, str) or expected is None:
        raise HTTPException(status_code=403)
    payload = verify("csrf", sent, secret=request.app.state.settings.secret_key)
    if payload is None or not hmac.compare_digest(payload.encode(), expected.encode()):
        raise HTTPException(status_code=403)


async def csrf_protect(request: Request) -> None:
    """The dependency on every account router: checks each POST under `/account/`."""
    if request.method == "POST" and request.url.path.startswith(PROTECTED_PREFIX):
        verify_csrf(request, await request.form())
