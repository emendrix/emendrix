"""What a page is and where it sits, said before anything else on it.

Every page below home opens with a masthead: the breadcrumb, a caption naming the kind of page,
and the page's own heading. A reader who lands cold on a deep page from a search result or a
feed has, until then, only the heading to go on, and a version page once carried its act's
heading word for word, so the two pages could not be told apart. The caption says the kind of
page in words, the masthead's class carries the same kind to the sheet, which gives each kind
of object its own band, and the heading names this page and no other.

The masthead is a `<header>` inside `<main>`. There it is the heading block of the page's
content, not the site's banner landmark, which is the `header.bar` outside `<main>`; a screen
reader announces one banner either way.

The breadcrumb is `trail`'s rungs, the ones `seo` publishes as JSON-LD, rendered as relative
links. The last rung is the page itself, plain text marked `aria-current="page"`. On a phone the
sheet shows the parent rung alone, as a way back, which needs no second list in the markup.
"""

from __future__ import annotations

from typing import Literal

from emendrix.site_.markup import Html, escape, join
from emendrix.site_.trail import Rung, page_trail
from emendrix.site_.urls import depth_of, up

__all__ = ["MastheadKind", "masthead", "page_masthead", "trail_html"]

MastheadKind = Literal["act", "version", "provision", "amending", "index", "prose"]
"""The six kinds of page. The first four are objects a reader follows between; the rosters are
`index`, and the pages about the site or across it are `prose`."""


def trail_html(rungs: tuple[Rung, ...], depth: int) -> Html:
    """The visible breadcrumb: every rung a link climbing from `depth`, the last one plain."""
    root = up(depth)
    items = [
        Html(f'<li><a href="{escape(root + rung.path or "./")}">{escape(rung.name)}</a></li>')
        for rung in rungs[:-1]
    ]
    if rungs:
        items.append(Html(f'<li aria-current="page">{escape(rungs[-1].name)}</li>'))
    return Html(f'<nav class="trail" aria-label="Breadcrumb"><ol>{join(items, "")}</ol></nav>')


def masthead(
    kind: MastheadKind,
    rungs: tuple[Rung, ...],
    depth: int,
    caption: Html,
    heading: Html,
) -> list[Html]:
    """The page's opening: trail, caption and heading, in one sectioning header.

    A page with no place in the tree, the not-found page, passes no rungs and prints no trail.
    What the page says next, its facts and its links, the caller writes after the header.
    """
    trail = [trail_html(rungs, depth)] if rungs else []
    return [
        Html(f'<header class="masthead masthead--{kind}">'),
        *trail,
        Html(f'<p class="caption">{caption}</p>'),
        Html(f"<h1>{heading}</h1>"),
        Html("</header>"),
    ]


def page_masthead(kind: MastheadKind, caption: str, name: str, path: str) -> list[Html]:
    """The masthead of a page one rung below home: a roster or a page about the site.

    Its heading is its name and its trail is home and itself, so the three are passed once
    here rather than spelled at each of six call sites, where a heading and its rung could
    come apart.
    """
    return masthead(kind, page_trail(name, path), depth_of(path), escape(caption), escape(name))
