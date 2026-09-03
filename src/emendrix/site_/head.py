"""What one page's head declares about itself: its address, its preview, its feeds.

Everything assembled here needs an absolute base. A canonical address, an `og:url` and an
`og:image` are absolute by definition, so the whole block is written only when the build was
given a site URL, and without one it is absent in its entirety rather than in part: a page
carrying `og:title` with no `og:url` renders a preview that is wrong, which is worse than a page
with no preview. That is the rule `render_feed` keeps, extended rather than reinvented. The feed
`rel="alternate"` links join it for a second reason of their own: they are relative and would
survive without a base, but no `.xml` file is written without a site URL, so a build without one
would advertise feeds the tree does not hold. The favicon link is the one head element that needs
no base at all, which is why `chrome.page` writes it unconditionally and this module does not
know about it.

Split from `seo.py` on 2026-09-03, when a provision page's structured data pushed that module
past the size cap. The seam is the one `seo.py`'s own docstring already drew: what a head states
in meta tags, which is this module, against what a page publishes as machine-readable data,
which stays there because `tests/test_architecture.py` pins that module as the only one allowed
to mint a JSON-LD element. The two names both surfaces need, the site's own and its one absolute
join, live here because a head is written for every page and structured data is not.

**No `twitter:title`, `twitter:description` or `keywords`**: X falls back to the Open Graph
values, so a second prefix would be one sentence in two places and one of them would get edited
alone, and keywords have been ignored by every major engine since 2009. **No `og:type: article`
on an act page** either, because an article wants an author and a published time and these pages
render a corpus whose explanations are partly model-written.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.markup import Html, escape

__all__ = ["SITE_NAME", "canonical_url", "head_metadata"]

SITE_NAME: Final = "emendrix"
"""What the site calls itself, in Open Graph and in every JSON-LD payload alike."""

_CARD: Final = "og.png"
_CARD_WIDTH: Final = 1200
_CARD_HEIGHT: Final = 630
_CARD_ALT: Final = "emendrix: provision-level changelogs for EU legislation"
"""The link-preview card as `build.py` writes it, at the site root and at that size.

Its address is built with `canonical_url` like a page's, because a scraper resolves neither a
relative `og:image` nor a page-relative one, and because the card is written on every build
whether or not anything yet points at it.
"""


def canonical_url(site_url: str, path: str) -> str:
    """The page's one absolute address.

    `site_url` reaches this package with its trailing slash already stripped, and every page
    path is site-root-relative with no leading slash, so exactly one separator joins them and
    no caller strips anything a second time. The home page's path is `""`, which gives
    `https://host/` with the trailing slash, the form a static host serves and redirects to.
    """
    return f"{site_url}/{path}"


def head_metadata(
    *,
    title: str,
    description: str,
    path: str,
    site_url: str,
    root: str,
    feeds: tuple[tuple[str, str], ...] = (),
    structured: Html | None = None,
) -> tuple[Html, ...]:
    """Everything one head declares about the page, or nothing at all without a base address.

    Returned as separate fragments rather than as one joined block, so that a build with no
    site URL contributes no line at all to the head. An empty string joined into the head would
    show up as a blank line on every page, which is a formatting change nobody asked for.

    `feeds` arrives as `(site-root-relative path, title)` pairs and is prefixed with `root`
    here, so a feed link resolves from a page at any depth. The pairs are passed in rather than
    looked up because `feeds.py` imports `chrome.page`, and a lookup from here would close that
    cycle.

    `og:url` is the canonical address, computed once and used twice: the one way those two can
    disagree is by being built separately.
    """
    if not site_url:
        return ()
    canonical = escape(canonical_url(site_url, path))
    alternates = tuple(
        Html(
            f'<link rel="alternate" type="application/atom+xml" '
            f'title="{escape(name)}" href="{escape(root + where)}">'
        )
        for where, name in feeds
    )
    block = (
        Html(f'<link rel="canonical" href="{canonical}">'),
        *alternates,
        Html('<meta property="og:type" content="website">'),
        Html(f'<meta property="og:site_name" content="{escape(SITE_NAME)}">'),
        Html(f'<meta property="og:title" content="{escape(title)}">'),
        Html(f'<meta property="og:description" content="{escape(description)}">'),
        Html(f'<meta property="og:url" content="{canonical}">'),
        Html(f'<meta property="og:image" content="{escape(canonical_url(site_url, _CARD))}">'),
        Html(f'<meta property="og:image:width" content="{_CARD_WIDTH}">'),
        Html(f'<meta property="og:image:height" content="{_CARD_HEIGHT}">'),
        Html(f'<meta property="og:image:alt" content="{escape(_CARD_ALT)}">'),
        Html('<meta name="twitter:card" content="summary_large_image">'),
    )
    return block if structured is None else (*block, structured)
