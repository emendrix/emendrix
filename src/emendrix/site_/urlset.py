"""The `<urlset>` every sitemap is written as, one `<url>` block per page.

Assembled as strings for the reason `discovery` gives, every value through `markup.escape`, and
every `<loc>` through `head.canonical_url`, the function that writes a page's canonical. Which
pages a sitemap lists and which dates it may publish is `discovery`'s to decide; this module
only writes what it is handed, in the order it is handed.

The namespace is spelled `http://`, and that is not a mistake: a namespace name is an identifier,
compared as a string and never fetched, and must not be "hardened".
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Final

from emendrix.site_.head import canonical_url
from emendrix.site_.markup import Html, escape, join

__all__ = ["NAMESPACE", "urlset"]

NAMESPACE: Final = "http://www.sitemaps.org/schemas/sitemap/0.9"
"""The sitemap namespace name, shared by a `<urlset>` and the `<sitemapindex>` naming it."""


def _url(site_url: str, path: str, dated: date | None) -> Html:
    """One `<url>` block. No date means no `<lastmod>` element, never an empty one."""
    lines = [
        Html("<url>"),
        Html(f"<loc>{escape(canonical_url(site_url, path))}</loc>"),
    ]
    if dated is not None:
        lines.append(Html(f"<lastmod>{escape(dated.isoformat())}</lastmod>"))
    lines.append(Html("</url>"))
    return join(lines, "\n")


def urlset(site_url: str, entries: Iterable[tuple[str, date | None]]) -> str:
    """A whole sitemap, newline-terminated: the declaration, then one block per entry."""
    lines = [
        Html('<?xml version="1.0" encoding="utf-8"?>'),
        Html(f'<urlset xmlns="{NAMESPACE}">'),
        *(_url(site_url, path, dated) for path, dated in entries),
        Html("</urlset>"),
        Html(""),
    ]
    return join(lines, "\n")
