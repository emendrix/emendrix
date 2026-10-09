"""Purpose-bound tokens: a payload and an HMAC over it, under a key derived for one purpose.

A token is `base64url(payload) + "." + base64url(mac)`, unpadded. The key for a purpose is
`HMAC-SHA256(secret_key, purpose)`, so a token minted for one purpose (`"csrf"`) never verifies
for another (`"unsub"`), even over the same payload. Nothing is stored: a token is valid as long
as the secret key is, and rotating the key invalidates every token at once.

The payload is signed, not encrypted: it is readable by whoever holds the token, so it carries
an identifier and never an address.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from typing import Final

from pydantic import SecretBytes

__all__ = ["sign", "verify"]

_SEPARATOR: Final = "."


def _key(purpose: str, secret: SecretBytes) -> bytes:
    if not purpose:
        raise ValueError("a token needs a purpose")
    return hmac.digest(secret.get_secret_value(), purpose.encode("utf-8"), hashlib.sha256)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(text: str) -> bytes | None:
    """The bytes `text` encodes, or None unless `text` is exactly how `_encode` writes them."""
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError):
        return None
    return raw if _encode(raw) == text else None


def sign(purpose: str, payload: str, *, secret: SecretBytes) -> str:
    """A token carrying `payload`, valid only for `purpose` under `secret`."""
    body = payload.encode("utf-8")
    mac = hmac.digest(_key(purpose, secret), body, hashlib.sha256)
    return f"{_encode(body)}{_SEPARATOR}{_encode(mac)}"


def verify(purpose: str, token: str, *, secret: SecretBytes) -> str | None:
    """The payload `token` carries if it was signed for `purpose` under `secret`, else None."""
    encoded_body, separator, encoded_mac = token.partition(_SEPARATOR)
    if not separator:
        return None
    body, mac = _decode(encoded_body), _decode(encoded_mac)
    if body is None or mac is None:
        return None
    expected = hmac.digest(_key(purpose, secret), body, hashlib.sha256)
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return None
