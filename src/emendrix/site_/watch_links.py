"""Where a "Watch this" link sends a reader: the account service's landing, with the item named.

The service answers `account/watch` under the site's own root and reads the item from the query:
`act` is the act's key within its corpus and `loc`, when the item is one provision, its canonical
location. The act is named by its key and never by its page slug, because the key is what the
published record and the catalogue are keyed by, and the slug is only this site's file name.
Both values are percent-encoded whole, so a location's spaces and an act key's punctuation reach
the service as written; the caller escapes the result for the attribute it writes it into.
"""

from __future__ import annotations

from urllib.parse import quote

from emendrix.site_.act_site import ActSite

__all__ = ["watch_href"]


def watch_href(root: str, act: ActSite, canonical: str | None) -> str:
    """The landing's address for the whole act, or for one of its provisions when one is named."""
    href = f"{root}account/watch?act={quote(act.act.key, safe='')}"
    if canonical is not None:
        href += f"&loc={quote(canonical, safe='')}"
    return href
