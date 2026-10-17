"""The header bar every page opens with: the skip link, the wordmark, the destinations, search.

Split out of `chrome` on 2026-10-17, when the shell had to learn which pages ask the script for
the substance index and that module stood at the size cap. The seam is the bar itself: this
module renders the one `<header class="bar">` and the account link that closes it, and knows
nothing of heads, footers or the disclaimer, which stay in the shell. `chrome` re-exports both
names, so a caller may import them from either module.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.markup import Html
from emendrix.site_.urls import up

__all__ = ["account_link", "nav_links"]

_SECTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("acts/", "All acts"),
    ("amendments/", "Amending acts"),
    ("dates/", "Dates ahead"),
    ("methodology/", "Methodology"),
    ("about/", "About"),
    ("feeds/", "Feeds"),
    ("api/", "API"),
)
"""The header bar's destinations as `(path, name)`, in the order the bar prints them."""


def nav_links(
    depth: int,
    section: str = "",
    root: str | None = None,
    *,
    accounts: bool = False,
    substances: bool = False,
) -> Html:
    """The header bar: a skip link, the wordmark, the seven destinations and the search mount.

    The order is the decision. The first two are the site's two rosters, of acts and of the
    amending acts that changed them; the third is the only one of the three facing forward, so
    it sits with them and not among the pages that are about the site rather than about the
    corpus. Everything after it describes the tool. `API` closes the bar beside `Feeds`
    because the two are the ways to take the record away from the site.

    `section` is the path of the destination the page belongs to, and that link alone carries
    `aria-current="page"`: an act, a version and a provision all sit under `acts/`, an amending
    act under `amendments/`. The sheet marks it by weight and an underline, never by colour
    alone. Home and the not-found page belong to no section and pass nothing.

    The skip link comes first in the source because that is the only thing that makes it
    useful: it is the first stop of a keyboard tab and is off-screen until it takes focus.
    An event page carries hundreds of focusable provision links, and without it every one of
    them sits between the top of the page and the first word a reader came for. The `<nav>`
    is named, because a page whose provision index is also a `<nav>` would otherwise announce
    two landmarks of the same name and leave a screen reader to guess which is which.

    `root` overrides the climb `depth` implies, for the pages `page` documents.

    With `accounts`, `account_link` closes the bar, after the search mount and outside `<nav>`.
    The word is `Account` because it is true whether the reader is signed in or not, and the
    address shows a signed-out reader the sign-in page. It sits after search, in a slot of its
    own, so an account service can put the reader's identity there without touching the site's
    navigation.

    With `substances`, the search mount carries `data-substances`, which tells the script to
    fetch the substance index on the first keystroke rather than only for a query that opens
    with a digit: on a page about table entries, a name typed into the box is as likely to be a
    substance's as an act's. Every other page carries no attribute and its bar is unchanged.
    """
    root = up(depth) if root is None else root
    current = ' aria-current="page"'
    links = " ".join(
        f'<a href="{root}{path}"{current if path == section else ""}>{name}</a>'
        for path, name in _SECTIONS
    )
    account = account_link(root) if accounts else ""
    flag = " data-substances" if substances else ""
    return Html(
        f'<a class="skip" href="#content">Skip to content</a>'
        f'<header class="bar"><a class="wordmark" href="{root or "./"}">emendrix</a>'
        f'<nav aria-label="Site">{links}</nav>'
        f'<div id="search" data-root="{root}"{flag}></div>{account}</header>'
    )


def account_link(root: str) -> str:
    """The header's link to the account service's root, under the page's own climb `root`.

    One string for the static pages and for the account shell, which swaps exactly this for its
    marker, so the two cannot drift apart and the swap cannot miss.
    """
    return f'<a class="account" href="{root}account/">Account</a>'
