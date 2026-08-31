"""What one page declares about itself: its address, its preview, its feeds, its JSON-LD.

Everything assembled here needs an absolute base. A canonical address, an `og:url` and an
`og:image` are absolute by definition, and a JSON-LD `@id` that does not resolve identifies
nothing. So the whole block is written only when the build was given a site URL, and without
one it is absent in its entirety rather than in part: a page carrying `og:title` with no
`og:url` renders a preview that is wrong, which is worse than a page with no preview. That is
the rule `render_feed` keeps, extended rather than reinvented. The feed `rel="alternate"` links
join it for a second reason of their own: they are relative and would survive without a base,
but no `.xml` file is written without a site URL, so a build without one would advertise feeds
the tree does not hold. The favicon link is the one head element that needs no base at all,
which is why `chrome.page` writes it unconditionally and this module does not know about it.

**`markup.escape` is wrong inside `<script type="application/ld+json">` and must not be used
there.** A browser decodes no HTML entities inside that element, so an escaped `&amp;` reaches a
consumer as those five characters and corrupts the JSON, while a literal `</script>` in any
value ends the element early, which is the injection escaping exists to stop. `_ld_block` is the
one correct path and the only place in the package that mints such an element: it rewrites `<`,
`>` and `&` as JSON string escapes, which keeps the document valid JSON and cannot break out of
the element. `indent=2` rather than compact separators, because the published tree is diffed in
git and reviewed as a golden; Python dicts are insertion-ordered, so the bytes are deterministic
without sorting keys.

Three things are deliberately not declared. **No `SearchAction` on the `WebSite`**, because the
search runs in the reader's browser over a prebuilt index and there is no `?q=` route to hand
anyone; a search endpoint that does not exist would be a false claim in a machine-readable
field. **No `og:type: article` on an act page**, because an article wants an author and a
published time and these pages render a corpus whose explanations are partly model-written.
**No `twitter:title`, `twitter:description` or `keywords`**: X falls back to the Open Graph
values, so a second prefix would be one sentence in two places and one of them would get edited
alone, and keywords have been ignored by every major engine since 2009.
"""

from __future__ import annotations

import json
from typing import Final

from emendrix.output import ChangelogEntry
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape
from emendrix.site_.urls import act_href, event_href

__all__ = ["act_json_ld", "canonical_url", "event_json_ld", "head_metadata", "website_json_ld"]

_NAME: Final = "emendrix"
"""What the site calls itself, in Open Graph and in every JSON-LD payload alike."""

_SCHEMA: Final = "https://schema.org"
"""The `https` spelling, never `http`: the site publishes no `http://` string anywhere."""

_CARD: Final = "og.png"
_CARD_WIDTH: Final = 1200
_CARD_HEIGHT: Final = 630
_CARD_ALT: Final = "emendrix: provision-level changelogs for EU legislation"
"""The link-preview card as `build.py` writes it, at the site root and at that size.

Its address is built with `canonical_url` like a page's, because a scraper resolves neither a
relative `og:image` nor a page-relative one, and because the card is written on every build
whether or not anything yet points at it.
"""

_ACTS_INDEX: Final = "acts/"
"""The roster's own path, which is also the directory `act_href` puts every act page under.

Named here for the breadcrumb's middle rung; `test_seo.py` pins it to a file the build wrote,
so the two cannot drift apart silently.
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
        Html(f'<meta property="og:site_name" content="{escape(_NAME)}">'),
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


def _ld_block(payload: object) -> Html:
    """A JSON-LD element. `markup.escape` is wrong here, and this is the whole reason why.

    Inside `<script type="application/ld+json">` the browser decodes no HTML entities, so an
    escaped `&amp;` corrupts the JSON, while a literal `</script>` in any value ends the element
    early. Escaping those three characters as JSON string escapes instead keeps the document
    valid JSON and cannot break out of the element, which is what justifies the `Html` mint.
    """
    body = (
        json.dumps(payload, ensure_ascii=False, indent=2)
        .replace("<", "\\u003C")
        .replace(">", "\\u003E")
        .replace("&", "\\u0026")
    )
    return Html(f'<script type="application/ld+json">\n{body}\n</script>')


def website_json_ld(site: SiteInputs, *, description: str) -> Html:
    """The home page's `WebSite`, and the one place the publisher is named.

    The publisher is an `Organization` called `emendrix` whose address is the site's own. No
    person is named, because nothing in the build knows one and a machine-readable field is
    the last place to guess. `description` is the page's own description meta, passed in so the
    two say the same thing rather than being written twice.
    """
    home = canonical_url(site.site_url, "")
    payload: dict[str, object] = {
        "@context": _SCHEMA,
        "@type": "WebSite",
        "name": _NAME,
        "url": home,
        "description": description,
        "publisher": {"@type": "Organization", "name": _NAME, "url": home},
    }
    return _ld_block(payload)


def _breadcrumb(rungs: tuple[tuple[str, str], ...]) -> dict[str, object]:
    """One `BreadcrumbList` from `(name, absolute url)` pairs in trail order.

    Shared by every page whose breadcrumb is the URL trail itself, so a rung's position and
    its address are computed in one place however many rungs the URL actually has, and no
    page can invent a rung its address does not carry.
    """
    return {
        "@context": _SCHEMA,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": name, "item": item}
            for position, (name, item) in enumerate(rungs, start=1)
        ],
    }


def _legislation(act: ActSite) -> dict[str, str]:
    """The `about` object every page describing this act shares.

    A `Legislation`, schema.org's ELI-derived type, and ELI is the vocabulary EU legislation
    is actually published under, so it is the honest label even though no engine renders
    anything from it. `sameAs` points at the official document and is omitted rather than
    emitted empty for an act with no resolved address; that is the same omission the act page
    already makes visibly. The act's own key is a corpus identifier and belongs here: it is
    core vocabulary rather than the vocabulary of any one corpus, and it is what identifies
    the act everywhere else.
    """
    about: dict[str, str] = {
        "@type": "Legislation",
        "name": act.label,
        "identifier": act.act.key,
    }
    if act.eurlex_url:
        about["sameAs"] = act.eurlex_url
    return about


def _webpage(
    here: str, *, title: str, description: str, about: dict[str, str]
) -> dict[str, object]:
    """The `WebPage` object every described page carries, its `@id` its canonical address."""
    return {
        "@context": _SCHEMA,
        "@type": "WebPage",
        "@id": here,
        "name": title,
        "description": description,
        "about": about,
    }


def act_json_ld(site: SiteInputs, act: ActSite, *, title: str, description: str) -> Html:
    """One act page's breadcrumb trail and the page itself, as one element holding two things.

    The breadcrumb is derived entirely from the URL structure, which is the one shape here that
    earns a real search result: the trail a reader sees under the link. It is three rungs deep
    because that is how deep the site is here, and no rung is invented.
    """
    home = canonical_url(site.site_url, "")
    roster = canonical_url(site.site_url, _ACTS_INDEX)
    here = canonical_url(site.site_url, act_href(act.slug))
    payload: list[dict[str, object]] = [
        _breadcrumb(((_NAME, home), ("All watched acts", roster), (act.label, here))),
        _webpage(here, title=title, description=description, about=_legislation(act)),
    ]
    return _ld_block(payload)


def event_json_ld(
    site: SiteInputs, act: ActSite, entry: ChangelogEntry, *, title: str, description: str
) -> Html:
    """One event page's breadcrumb trail and the page itself. Four rungs, because the site is
    four deep here: home, the roster, the act, this event, the same no-invented-rung rule
    `act_json_ld` holds at three.

    `about` is the same `Legislation` the act page names, because this page still describes
    that act; which transition it describes is stated by the fourth rung and by
    `title`/`description`, and schema.org has no honest type for one amendment event, so no
    machine-readable field pretends to one.
    """
    home = canonical_url(site.site_url, "")
    roster = canonical_url(site.site_url, _ACTS_INDEX)
    act_page = canonical_url(site.site_url, act_href(act.slug))
    here = canonical_url(site.site_url, event_href(act.slug, entry.key))
    event = f"{entry.from_version} → {entry.to_version}"
    payload: list[dict[str, object]] = [
        _breadcrumb(
            ((_NAME, home), ("All watched acts", roster), (act.label, act_page), (event, here))
        ),
        _webpage(here, title=title, description=description, about=_legislation(act)),
    ]
    return _ld_block(payload)
