"""What a reader gets when the address does not match anything the site publishes.

`404.html` at the site root, which is the file a static host serves for an unmatched path. It
is a real page rather than the host's generic one: it carries the shell, so it has the header
bar, the search box, the disclaimer and three links back into the site. A reader who mistyped
an act's identifier is one search away from the page they wanted, and search is the useful
thing here because the address they guessed is the one piece of information the page has.

It is the one page that asks not to be indexed. A search result reading "page not found" tells
a reader nothing about this site, and the page holds no content of its own to be found by.

The page names no specific act and reads no artifact. Only the shell's own footer varies with
the build, so nothing on it can go stale with respect to the corpus.

Its links are relative to the site root like every other page's, which is right when the file
is fetched as `/404.html` and is the reason the tree also works from `file://` and from a
subpath. A host that serves this file's contents under the address the reader actually typed
leaves the browser at that address, and a relative link then resolves against it: the deeper
the mistyped path, the further the links point from where they mean. The head carries the
absolute form, as this page's canonical address. The links in the body stay relative on purpose,
because a build given no site URL has no base to write them against and relative is the only
form that works at all in that mode; absolute links would trade a page that is wrong from a
deep address for a page that is broken everywhere.
"""

from __future__ import annotations

from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, join
from emendrix.site_.urls import depth_of, up

__all__ = ["render_not_found"]

_PATH = "404.html"
_DEPTH = depth_of(_PATH)
"""The file sits at the site root, so nothing on it climbs a directory first."""


def render_not_found(site: SiteInputs) -> Html:
    """The not-found page. Deterministic: same inputs, same bytes, no clock, no network."""
    root = up(_DEPTH)
    lines = [
        Html("<h1>Page not found</h1>"),
        Html(
            '<p class="lede muted">This address does not match anything the site publishes. '
            "An act's own page carries its whole watched history, every amendment event on it "
            "in one place, so that is usually the page worth reaching for.</p>"
        ),
        Html("<ul>"),
        Html(f'<li><a href="{root}acts/">All watched acts</a>, the full roster</li>'),
        Html(f'<li><a href="{root}methodology/">Methodology</a>, what the numbers mean</li>'),
        Html(f'<li><a href="{root}feeds/">Feeds</a>, one per act and one for everything</li>'),
        Html("</ul>"),
    ]
    return page(
        title="Page not found — emendrix",
        description=(
            "This address does not match anything emendrix publishes; the watched acts, the "
            "methodology and the feeds are all one link away."
        ),
        body=join(lines, "\n"),
        path=_PATH,
        generated_on=site.generated_on,
        repo_url=site.repo_url,
        noindex=True,
        site_url=site.site_url,
        feeds=((feed_path(None), feed_title(None)),),
    )
