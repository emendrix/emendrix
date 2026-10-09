"""What the header's account slot holds: the reader's identity, or the plain `Account` link.

Pure: the caller says who reads, and nothing here looks at a request or a session. The link is
root-relative, because the service answers on the site's own host.
"""

from __future__ import annotations

from typing import Final

from markupsafe import Markup

__all__ = ["SIGNED_OUT", "account_slot"]

SIGNED_OUT: Final = Markup('<a class="account" href="/account/">Account</a>')


def account_slot(email: str | None, *, current: bool = False) -> Markup:
    """The header link for `email`, signed out when None; `current` marks the Account tab."""
    if not email:
        return SIGNED_OUT
    current_attr = Markup(' aria-current="page"') if current else Markup("")
    return Markup(
        '<a class="account account--in" href="/account/"{current}'
        ' aria-label="Your account, signed in as {email}">'
        '<span class="account-initial" aria-hidden="true">{initial}</span>'
        '<span class="account-email">{email}</span></a>'
    ).format(current=current_attr, email=email, initial=email[:1].upper())
