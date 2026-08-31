"""The two files written for crawlers rather than for readers.

`robots.txt` states the crawl policy and points at the sitemap; `sitemap.xml` lists every page
the site publishes, with the date each one's content last moved. Neither is a page: no shell, no
navigation, no disclaimer.

Both are assembled as strings rather than through an XML library, for the reason the feeds give:
two builds of one repository state have to produce identical bytes, and a serialiser free to
reorder attributes or pick its own quoting is diff noise in a published artifact. Every value
interpolated into the sitemap goes through `markup.escape`, which is HTML escaping and is also
valid XML escaping for a text node. `robots.txt` has no escape syntax at all; its one
interpolated value is the site URL, which reaches this package only after the command line has
refused anything that does not begin `https://`.

A `<loc>` is absolute by definition, so `sitemap_xml` refuses without a site URL rather than
inventing a base, exactly as `render_feed` does. `robots.txt` is written either way and loses
only its `Sitemap:` line, because a crawl policy is about paths. Every `<loc>` is built with
`seo.canonical_url`, the same function that writes the page's canonical, so a sitemap entry and
a canonical cannot name two addresses for one page.

Pages only: the four fixed ones and one per act. Feeds are advertised by `rel="alternate"` in
every head and a sitemap indexes pages rather than subscriptions; the stylesheet, the script,
the search index, the icon and the card are assets. `404.html` is absent by construction,
because a sitemap entry for a page marked `noindex` is a contradiction handed to a crawler.

`<lastmod>` comes from the corpus, never from `generated_on`: an act page is dated by that act's
newest event, the home page, the roster and the feeds page by the newest event on the site, and
the methodology page by the date of the report its figures were read out of. `generated_on`
would restamp every URL on every rebuild and tell a crawler the whole site changed when nothing
did, which is what `feeds.py` refuses for an entry's `<updated>` for the identical reason. An
act nothing has happened to yet has no content date, so its `<lastmod>` element is omitted
rather than guessed. No `<changefreq>` and no `<priority>`, because Google ignores both.

The sitemap namespace is spelled `http://`, and that is not a mistake. A namespace name is an
identifier, compared as a string and never fetched; `https://` there produces a document in a
different namespace that no sitemap parser recognises as a sitemap. It must not be "hardened".
"""

from __future__ import annotations

from datetime import date

from emendrix.site_.inputs import SiteInputs, event_dated
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.seo import canonical_url
from emendrix.site_.urls import act_href

__all__ = ["ROBOTS", "SITEMAP", "robots_txt", "sitemap_xml"]

ROBOTS = "robots.txt"
SITEMAP = "sitemap.xml"
"""Where the builder writes each file. Both sit at the site root, which is where crawlers look."""

_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
"""The sitemap namespace name. `http://`, and see the module docstring for why it stays."""

_UNCONFIGURED = (
    "a sitemap's locations are absolute, so writing one needs a site URL; "
    "check `site.site_url` before asking for a sitemap"
)


def robots_txt(site: SiteInputs) -> str:
    """The crawl policy, newline-terminated. Four lines with a base address, two without.

    `Allow: /` is written explicitly even though an empty `Disallow:` and a file with no
    directive at all mean the same thing to every crawler: a policy that states what it permits
    reads as a decision, one that states nothing reads as an oversight, and the decision belongs
    in the clone rather than in a dashboard. Stating no AI-crawler directives is that same
    decision made the same way, because the site is published to be found. No comment header
    either: a host may append a managed comment block of its own, and two stacked blocks
    explaining different things is noise in a file whose whole audience is machines.
    """
    lines = ["User-agent: *", "Allow: /"]
    if site.site_url:
        lines.extend(("", f"Sitemap: {canonical_url(site.site_url, SITEMAP)}"))
    return "\n".join(lines) + "\n"


def _entries(site: SiteInputs) -> tuple[tuple[str, date | None], ...]:
    """Every page a crawler should know about, with the date its content last moved.

    The four fixed paths are literals, the same site-root-relative paths the page modules are
    rendered under and the builder writes them to. Nothing derives one from the other, so
    `test_discovery.py` compares the sitemap against the built tree in both directions: a path
    that stops matching a file, and a page that gains no entry, both fail there rather than
    reaching a crawler.

    `max` needs its default: a checkout with a watchlist and an empty changelog repository is a
    real state, and every date here is then `None` except the methodology page's.
    """
    newest = max((event_dated(entry) for _, entry in site.recent), default=None)
    fixed: list[tuple[str, date | None]] = [
        ("", newest),
        ("acts/", newest),
        ("methodology/", site.run.run_date),
        ("feeds/", newest),
    ]
    fixed.extend(
        (act_href(act.slug), None if act.dated is None else act.dated.on) for act in site.acts
    )
    return tuple(fixed)


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


def sitemap_xml(site: SiteInputs) -> str:
    """The sitemap, newline-terminated. Deterministic: no clock, no network, no set iteration.

    `site.acts` arrives already sorted by label then key, so the entry order is the roster's own
    and two builds of one `SiteInputs` produce identical bytes.
    """
    if not site.site_url:
        raise ValueError(_UNCONFIGURED)
    lines = [
        Html('<?xml version="1.0" encoding="utf-8"?>'),
        Html(f'<urlset xmlns="{_NAMESPACE}">'),
        *(_url(site.site_url, path, dated) for path, dated in _entries(site)),
        Html("</urlset>"),
        Html(""),
    ]
    return join(lines, "\n")
