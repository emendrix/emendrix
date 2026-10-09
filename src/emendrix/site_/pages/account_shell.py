"""The account shell: the site's own chrome, with markers where an account service writes.

`account-shell.html` at the site root, written only by a build that links an account service
and has a site URL. It is not a page for readers. The service reads it once, splits it on the
four markers below and renders each of its pages into the pieces, so its pages carry this
site's header, stylesheet, search and disclaimer without importing a line of this package, and
a restyled site restyles them on the service's next start.

The markers are HTML comments, so the file is a well-formed page as written:

- `TITLE_MARKER` is the whole text of `<title>`;
- the description is left empty, for the service to fill or leave;
- `ACCOUNT_MARKER` stands where every static page ends its header with the account link, after
  the search mount, so the service can name the reader there, or leave it empty;
- `CONTENT_MARKER` is the whole body of `<main id="content">`;
- `FOOTER_NOTE_MARKER` stands in the footer where every static page says it sets no cookies.
  An account page keeps a reader signed in with one, so the static sentence would be false
  there, and the service writes its own.

Every root-bound reference starts from the site URL's path, as on the not-found page and for
the same reason: the service serves these bytes under its own addresses, `/account/...`, where
a relative stylesheet link would resolve against the wrong directory. The head carries no
canonical address and no link preview, because the only address it could name is this file's,
which is never the address of a page rendered into it. It asks not to be indexed, and the
sitemap leaves it out as it leaves out the not-found page.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.chrome import account_link, page
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, escape
from emendrix.site_.pages.not_found import not_found_root

__all__ = [
    "ACCOUNT_MARKER",
    "CONTENT_MARKER",
    "FOOTER_NOTE_MARKER",
    "SHELL",
    "TITLE_MARKER",
    "render_account_shell",
]

SHELL: Final = "account-shell.html"
"""Where the build writes the shell, at the site root."""

TITLE_MARKER: Final = "<!--emendrix:title-->"
ACCOUNT_MARKER: Final = "<!--emendrix:account-->"
CONTENT_MARKER: Final = "<!--emendrix:content-->"
FOOTER_NOTE_MARKER: Final = "<!--emendrix:footer-note-->"
"""The exact strings an account service splits the shell on. Each appears once in the file."""


def render_account_shell(site: SiteInputs) -> Html | None:
    """The shell, or None for a build that links no account service or has no site URL.

    `page` escapes a title, as it must for every real one, so the title marker goes in as
    text and the escaped form is swapped back for the raw comment afterwards. The chrome is
    handed with no site URL, which is what leaves the canonical address and the preview out of
    the head; the root still comes from the real one. The account link is swapped for its
    marker by the very string the header wrote, so the swap finds exactly one.
    """
    if not (site.accounts and site.site_url):
        return None
    root = not_found_root(site.site_url)
    rendered = page(
        title=TITLE_MARKER,
        description="",
        body=Html(CONTENT_MARKER),
        path=SHELL,
        chrome=site.chrome.model_copy(update={"site_url": ""}),
        noindex=True,
        root=root,
        footer_note=Html(FOOTER_NOTE_MARKER),
    )
    return Html(
        rendered.replace(escape(TITLE_MARKER), TITLE_MARKER).replace(
            account_link(root), ACCOUNT_MARKER
        )
    )
