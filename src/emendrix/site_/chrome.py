"""The shell every page shares. Pages differ in body; honesty lines do not.

`path` is where the page lives, relative to the site root and with no leading slash, exactly
as the builder's file table names it. The prefix that climbs back to the root is derived from
it by `depth_of`, and every internal href and asset link carries that prefix, so the tree works
from `file://`, a subpath, or a domain root without a base tag. A page is handed its path
rather than its depth because the two are one fact, and because a page that knows its path can
also state its own absolute address once it is given a base to state it against. The disclaimer
is part of the shell because a page without it must be unrepresentable, not merely unlikely.

The header's `#search` element is an empty div: the search control is built by the script,
so a reader without JavaScript sees no dead input box, and the recent-act links and the acts
index remain the whole navigation. `generated_on` is a parameter, never a clock read.
"""

from __future__ import annotations

from datetime import date

from emendrix import DISCLAIMER
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.seo import head_metadata
from emendrix.site_.urls import depth_of, up

__all__ = ["nav_links", "page"]


def nav_links(depth: int) -> Html:
    """The header bar: wordmark, the three fixed destinations, and the search mount point."""
    root = up(depth)
    return Html(
        f'<header class="bar"><a class="wordmark" href="{root or "./"}">emendrix</a>'
        f'<nav><a href="{root}acts/">All acts</a> '
        f'<a href="{root}methodology/">Methodology</a> '
        f'<a href="{root}feeds/">Feeds</a></nav>'
        f'<div id="search" data-root="{root}"></div></header>'
    )


def _footer(generated_on: date, repo_url: str) -> Html:
    """The disclaimer, the build date and what the site does on the reader's machine.

    An unset repository URL renders as plain words rather than a dead link: a link that goes
    nowhere is worse than a sentence naming the repository.
    """
    source = (
        Html(f'<a href="{escape(repo_url)}">the emendrix repository</a>')
        if repo_url
        else Html("the emendrix repository")
    )
    return join(
        (
            Html("<footer>"),
            Html(
                f'<p class="disclaimer"><strong>Not legal advice.</strong> {escape(DISCLAIMER)} '
                'Read the official consolidated text on <a href="https://eur-lex.europa.eu/">'
                "EUR-Lex</a>.</p>"
            ),
            Html(
                f"<p>Generated on {generated_on.isoformat()} from artifacts committed in "
                f"{source}. One small script for search; no cookies, no analytics, no "
                f"third-party requests.</p>"
            ),
            Html("</footer>"),
        ),
        "\n",
    )


def page(
    *,
    title: str,
    description: str,
    body: Html,
    path: str,
    generated_on: date,
    repo_url: str,
    noindex: bool = False,
    site_url: str = "",
    feeds: tuple[tuple[str, str], ...] = (),
    structured: Html | None = None,
) -> Html:
    """One complete document: head, header bar, the caller's body, footer. Newline-terminated.

    `path` is the page's own site-root-relative path, the key the builder writes it under.

    `noindex` asks a search engine to keep the page out of its results. It defaults to off
    because a page that exists to be read should be findable; the one page that sets it is the
    not-found page, which says only that an address is wrong and would be noise in a result
    list. The icon link is relative like every other asset link, so it needs no base address
    and is written on every page unconditionally.

    `site_url`, `feeds` and `structured` are what the page declares about itself: its one
    absolute address and the link preview built from it, the Atom feeds it advertises as
    `(path, title)` pairs, and its JSON-LD block. All three default to nothing, and
    `seo.head_metadata` contributes no line at all without a base address, so a build given no
    site URL writes a head with nothing in it from here rather than one carrying a blank line.

    That is ten keyword arguments, which is the edge of what a signature should carry. An
    eleventh is the signal to gather them into one frozen model, not to add one more.
    """
    depth = depth_of(path)
    root = up(depth)
    robots = (Html('<meta name="robots" content="noindex">'),) if noindex else ()
    return join(
        (
            Html("<!DOCTYPE html>"),
            Html('<html lang="en">'),
            Html("<head>"),
            Html('<meta charset="utf-8">'),
            Html('<meta name="viewport" content="width=device-width, initial-scale=1">'),
            Html(f"<title>{escape(title)}</title>"),
            Html(f'<meta name="description" content="{escape(description)}">'),
            *robots,
            *head_metadata(
                title=title,
                description=description,
                path=path,
                site_url=site_url,
                root=root,
                feeds=feeds,
                structured=structured,
            ),
            Html(f'<link rel="icon" href="{root}icon.svg" type="image/svg+xml">'),
            Html(f'<link rel="stylesheet" href="{root}style.css">'),
            Html(f'<script defer src="{root}search.js"></script>'),
            Html("</head>"),
            Html("<body>"),
            nav_links(depth),
            Html("<main>"),
            body,
            Html("</main>"),
            _footer(generated_on, repo_url),
            Html("</body>"),
            Html("</html>"),
            Html(""),
        ),
        "\n",
    )
