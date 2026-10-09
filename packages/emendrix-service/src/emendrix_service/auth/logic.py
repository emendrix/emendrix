"""The rules of signing in, as pure functions: tokens, lifetimes, addresses, intents, consent.

Nothing here reads a clock, the database or the environment. A token is random and only its
sha256 is ever stored, so a leaked table cannot sign anyone in. An address is checked for shape
only: no DNS lookup, because whether mail reaches it is what the emailed link itself proves.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

from emendrix_service.db.enums import TokenPurpose

__all__ = [
    "ADDRESS_LINKS_PER_HOUR",
    "LINK_LIFE",
    "SESSION_LIFE",
    "Silent",
    "WatchIntent",
    "consent_version",
    "decide_link",
    "hash_token",
    "link_expiry",
    "local_path",
    "may_sign_up",
    "new_token",
    "normalise_email",
    "session_expiry",
]

LINK_LIFE: Final = timedelta(minutes=30)
SESSION_LIFE: Final = timedelta(days=30)
ADDRESS_LINKS_PER_HOUR: Final = 3

TOKEN_BYTES: Final = 32
"""256 bits: nobody guesses a live link or session in its lifetime."""

LOCAL_LIMIT: Final = 64
ADDRESS_LIMIT: Final = 254
"""The longest local part and address SMTP carries (RFC 5321, 4.5.3.1)."""

_REFUSED: Final = frozenset('<>,;:"()[]\\')
"""Characters that are legal only inside a quoted local part, which no form here accepts, and
that would change the meaning of a `To` header."""


def hash_token(token: str) -> bytes:
    """The sha256 under which `token` is stored and looked up."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def new_token() -> tuple[str, bytes]:
    """A fresh URL-safe token and its sha256."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def link_expiry(now: datetime) -> datetime:
    """When a login link sent at `now` stops working."""
    return now + LINK_LIFE


def session_expiry(now: datetime) -> datetime:
    """When a session used at `now` ends unless it is used again."""
    return now + SESSION_LIFE


def normalise_email(text: str) -> str | None:
    """`text` as one address with its domain lower-cased, or None when it is not one.

    The local part keeps its case: only the domain is case-insensitive by rule, and the stored
    column compares case-insensitively anyway.
    """
    address = text.strip()
    if address.count("@") != 1 or any(char.isspace() for char in address):
        return None
    if any(char in _REFUSED or ord(char) < 32 for char in address):
        return None
    local, domain = address.split("@")
    if not local or not domain or len(local) > LOCAL_LIMIT or len(address) > ADDRESS_LIMIT:
        return None
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return None
    return f"{local}@{domain.lower()}"


class WatchIntent(BaseModel):
    """A watch item a sign-up link carries until the address is confirmed.

    Stored as the link's `intent` JSON. Confirming a sign-up turns it into the first watchlist's
    one item; confirming a sign-in sends the reader to the watch landing for it instead.
    """

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(min_length=1, description="The corpus the act belongs to, e.g. `eu`.")
    act_key: str = Field(min_length=1, description="The act's key, e.g. `32017R0745`.")
    location: str | None = Field(
        default=None, description="A canonical location within the act; None is the whole act."
    )

    def landing(self) -> str:
        """The watch landing for this item, as a local path."""
        query = {"act": self.act_key, **({"loc": self.location} if self.location else {})}
        return f"/account/watch?{urlencode(query)}"


def consent_version(notice: bytes) -> str:
    """The version of the privacy notice a consent records: its first 12 sha256 hex digits."""
    return hashlib.sha256(notice).hexdigest()[:12]


def local_path(value: str | None) -> str | None:
    """`value` when it is a path of the account pages this service serves, else None.

    Anything else (another host, a scheme-relative `//host`, a backslash some browsers read as
    a slash) is refused, so a `next` parameter can never send a reader off the site.
    """
    if not value or not value.startswith("/account/"):
        return None
    if "\\" in value or "//" in value or any(ord(char) < 33 for char in value):
        return None
    return value


class Silent(StrEnum):
    """Why a link request sends nothing. The reader sees the same page in every case."""

    IP_LIMITED = "ip_limited"
    ADDRESS_LIMITED = "address_limited"
    UNKNOWN_ADDRESS = "unknown_address"
    SUSPENDED = "suspended"
    SIGNUP_CLOSED = "signup_closed"
    NO_NOTICE = "no_privacy_notice"


def decide_link(
    *,
    asked: TokenPurpose,
    known: bool,
    active: bool,
    may_sign_up: bool,
    has_notice: bool,
    recent: int,
) -> TokenPurpose | Silent:
    """What a link request for one address sends: a link for a purpose, or nothing and why.

    A known address always gets a sign-in link, whatever was asked, so a sign-up form cannot be
    used to learn that an address has an account. An unknown address asking to sign in gets
    nothing, on the same page.
    """
    if known:
        purpose = TokenPurpose.SIGNIN
        if not active:
            return Silent.SUSPENDED
    elif asked is TokenPurpose.SIGNIN:
        return Silent.UNKNOWN_ADDRESS
    elif not may_sign_up:
        return Silent.SIGNUP_CLOSED
    elif not has_notice:
        return Silent.NO_NOTICE
    else:
        purpose = TokenPurpose.SIGNUP
    if recent >= ADDRESS_LINKS_PER_HOUR:
        return Silent.ADDRESS_LIMITED
    return purpose


def may_sign_up(email: str, *, signup_open: bool, allowlist: tuple[str, ...]) -> bool:
    """Whether a new account may be made for `email` under the sign-up settings."""
    if signup_open:
        return True
    admitted = {(normalise_email(entry) or entry).lower() for entry in allowlist}
    return email.lower() in admitted
