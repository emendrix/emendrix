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

The stylesheet and the script are linked under the names `fingerprint` computes from their own
bytes, the same names `build.py` writes them to, so a cached asset can never be a page's stale
one. The icon is linked by its fixed name for the reason that module gives.

`PageChrome`, what the shell is handed, is defined here beside the shell that reads it. A build
fills one from `SiteInputs`, so this module needs nothing from `inputs` and the two can be read
in either order.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix import DISCLAIMER
from emendrix.site_.fingerprint import SCRIPT, STYLESHEET
from emendrix.site_.head import head_metadata
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.urls import depth_of, up

__all__ = ["PageChrome", "disclaimer_html", "nav_links", "page", "repository_links"]


class PageChrome(BaseModel):
    """The site-wide facts every page's shell renders, whatever the page is about.

    Gathered into one frozen model because `page` below had reached ten keyword arguments,
    and its own docstring named an eleventh as the signal to gather rather than grow. It lives
    beside the shell it describes, and `inputs` builds one from what a build was given; the
    dependency runs that one way, so neither module needs the other to be read first.

    `operator`, `operator_url` and `contact` are deployment facts like `site_url`: they arrive
    on the command line and nothing about them is committed, so a build that names nobody is
    the normal state and every page that reads them says nothing rather than something blank.
    """

    model_config = ConfigDict(frozen=True)

    generated_on: date = Field(description="Passed in at the CLI boundary; never clock-read.")
    repo_url: str = Field(default="", description="Public home of the source, or ''.")
    changelogs_url: str = Field(default="", description="Public home of the changelog data, or ''.")
    site_url: str = Field(default="", description="Absolute base for feeds, or '' for none.")
    operator: str = Field(default="", description="Who runs this instance, or '' for nobody named.")
    operator_url: str = Field(default="", description="Public page of the operator, or ''.")
    contact: str = Field(default="", description="Address readers may write to, or ''.")


def nav_links(depth: int) -> Html:
    """The header bar: a skip link, the wordmark, the six destinations and the search mount.

    The order is the decision. The first two are the site's two rosters, of acts and of the
    instruments that amended them; the third is the only one of the three facing forward, so it
    sits with them and not among the pages that are about the site rather than about the corpus.
    Everything after it describes the tool.

    The skip link comes first in the source because that is the only thing that makes it
    useful: it is the first stop of a keyboard tab and is off-screen until it takes focus.
    An event page carries hundreds of focusable provision links, and without it every one of
    them sits between the top of the page and the first word a reader came for. The `<nav>`
    is named, because a page whose provision index is also a `<nav>` would otherwise announce
    two landmarks of the same name and leave a screen reader to guess which is which.
    """
    root = up(depth)
    return Html(
        f'<a class="skip" href="#content">Skip to content</a>'
        f'<header class="bar"><a class="wordmark" href="{root or "./"}">emendrix</a>'
        f'<nav aria-label="Site"><a href="{root}acts/">All acts</a> '
        f'<a href="{root}amendments/">Amendments</a> '
        f'<a href="{root}dates/">Dates ahead</a> '
        f'<a href="{root}methodology/">Methodology</a> '
        f'<a href="{root}about/">About</a> '
        f'<a href="{root}feeds/">Feeds</a></nav>'
        f'<div id="search" data-root="{root}"></div></header>'
    )


def repository_links(chrome: PageChrome) -> tuple[Html, Html]:
    """The source and the changelog data, each a link when configured and words when not.

    An unset repository URL renders as plain words rather than a dead link: a link that goes
    nowhere is worse than a sentence naming the repository. Both halves are minted here rather
    than at each call site, so the footer and the about page cannot name the two repositories
    in two different shapes.
    """
    source = (
        Html(f'<a href="{escape(chrome.repo_url)}">the emendrix repository</a>')
        if chrome.repo_url
        else Html("the emendrix repository")
    )
    changelogs = (
        Html(f'<a href="{escape(chrome.changelogs_url)}">the changelog repository</a>')
        if chrome.changelogs_url
        else Html("the changelog repository")
    )
    return source, changelogs


def disclaimer_html() -> Html:
    """The disclaimer paragraph, its lead emphasised and its words untouched.

    `DISCLAIMER` is one sentence whose first clause is the part a reader scans for, so the
    paragraph splits it at its own colon and bolds the lead rather than prefixing a second
    heading of the same words. The constant itself never moves: the feed, the CLI and the
    changelog print it whole, and the split is a rendering decision belonging to the page.
    """
    lead, rest = DISCLAIMER.split(": ", 1)
    return Html(
        f'<p class="disclaimer"><strong>{escape(lead)}:</strong> {escape(rest)} '
        'Read the official consolidated text on <a href="https://eur-lex.europa.eu/">'
        "EUR-Lex</a>.</p>"
    )


def _footer(chrome: PageChrome, root: str) -> Html:
    """The disclaimer, the build date and what the site does on the reader's machine.

    `root` is the page's own climb back to the site root, passed in rather than read off the
    chrome model: which directory a page sits in is a fact about the page, and the footer's
    one internal link has to resolve from wherever the file was written.
    """
    source, changelogs = repository_links(chrome)
    return join(
        (
            Html("<footer>"),
            disclaimer_html(),
            Html(
                f"<p>Generated on {chrome.generated_on.isoformat()} from artifacts committed in "
                f"{source}; the changelog data it renders is public in {changelogs}. One small "
                f"script for search; no cookies, no analytics, no third-party requests. "
                f'<a href="{root}about/">About this site</a>.</p>'
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
    chrome: PageChrome,
    noindex: bool = False,
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

    `feeds` and `structured` are what the page declares about itself: the Atom feeds it
    advertises as `(path, title)` pairs, and its JSON-LD block. Both default to nothing.

    Everything site-wide, the build date, the public repository URLs and the site's one
    absolute address, arrives gathered in `chrome`: the signature once carried each as its own
    keyword argument, reached ten, and was folded into the frozen model rather than grow an
    eleventh. `head.head_metadata` contributes no line at all without a base address, so a
    build given no site URL writes a head with nothing in it from here rather than one
    carrying a blank line.
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
                site_url=chrome.site_url,
                root=root,
                feeds=feeds,
                structured=structured,
            ),
            Html(f'<link rel="icon" href="{root}icon.svg" type="image/svg+xml">'),
            Html(f'<link rel="stylesheet" href="{root}{STYLESHEET}">'),
            Html(f'<script defer src="{root}{SCRIPT}"></script>'),
            Html("</head>"),
            Html("<body>"),
            nav_links(depth),
            Html('<main id="content">'),
            body,
            Html("</main>"),
            _footer(chrome, root),
            Html("</body>"),
            Html("</html>"),
            Html(""),
        ),
        "\n",
    )
