"""The two files written for crawlers rather than for readers.

`robots.txt` states the crawl policy and points at `sitemap_index.xml`, which names
`sitemap.xml`, which lists every page the site publishes with the date each one's content last
moved. None of the three is a page: no shell, no navigation, no disclaimer.

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
`head.canonical_url`, the same function that writes the page's canonical, so a sitemap entry and
a canonical cannot name two addresses for one page.

Pages only: the seven fixed ones, one per act, one per amendment event, one per provision any
event touched and one per amending instrument a committed event names. An event page's
`<lastmod>` is that event's own `event_dated`, the same clock its feed entry's `<updated>`
reads, so the two records of one fact cannot disagree. Feeds are advertised by `rel="alternate"` in
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

from collections.abc import Iterable
from datetime import date

from emendrix.site_.clocks import event_dated
from emendrix.site_.head import canonical_url
from emendrix.site_.history import histories
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.instruments import amended_by
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.urls import (
    act_href,
    amendment_href,
    amendments_href,
    dates_href,
    event_href,
    provision_href,
)

__all__ = [
    "ROBOTS",
    "SITEMAP",
    "SITEMAP_INDEX",
    "robots_txt",
    "sitemap_index_xml",
    "sitemap_xml",
]

ROBOTS = "robots.txt"
SITEMAP = "sitemap.xml"
SITEMAP_INDEX = "sitemap_index.xml"
"""Where the builder writes each file. All three sit at the site root, which is where a crawler
looks, and `robots.txt` names the index rather than the sitemap: one address a search engine
holds, behind which the sitemap may be split or renamed without that address ever moving."""

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
        lines.extend(("", f"Sitemap: {canonical_url(site.site_url, SITEMAP_INDEX)}"))
    return "\n".join(lines) + "\n"


def _moved(dates: Iterable[date | None], built: date) -> date | None:
    """The newest of these dates the build can stand behind, or `None` when there is none.

    `<lastmod>` says when a page's content last moved, and content cannot move after the build
    that wrote it. `event_dated` reads clock 1, the day an amendment takes effect, which a
    consolidation is routinely notified before, so the newest date a page has is not always one
    this build can claim. Such a date is left out rather than clamped to the build date, which
    is the value this module refuses to stamp a URL with: a crawler handed a `<lastmod>` in the
    future either discards it or stops trusting the field across the whole sitemap, and an
    omission is what an act with no events already gets.

    The default is what a page whose every date is ahead of the build falls back to, and what
    a checkout with a watchlist and an empty changelog repository produces for all of them.
    """
    return max((value for value in dates if value is not None and value <= built), default=None)


def _entries(site: SiteInputs) -> tuple[tuple[str, date | None], ...]:
    """Every page a crawler should know about, with the date its content last moved.

    The seven fixed paths are literals, the same site-root-relative paths the page modules are
    rendered under and the builder writes them to. Nothing derives one from the other, so
    `test_discovery.py` compares the sitemap against the built tree in both directions: a path
    that stops matching a file, and a page that gains no entry, both fail there rather than
    reaching a crawler.

    The about page carries no date at all: its content moves with the build rather than with
    the corpus, and `generated_on` is exactly the value this module refuses to stamp a URL
    with. That is the same rule an act nothing has happened to yet is under, and the same
    answer the dates page gets: it splits its list at the build date, so its content moves
    with the build too, and dating it by the newest event would say it last changed when the
    corpus did, which is false.

    Every date goes through `_moved`, which is where the rule that a page cannot have moved
    after the build that wrote it lives, and which supplies the `None` a page with no date it
    can stand behind gets.

    An act's date is its newest entry's, whatever that entry is: `<lastmod>` answers when the
    page's content last moved, and an event no amending act is named for moved it like any
    other. `ActSite.dated` answers the different question of when the act was last amended,
    skips exactly those events, and must not be read here: a crawler told the page was stale
    would be told a lie the human-facing date rule exists to prevent, not to cause.
    """
    built = site.generated_on
    newest = _moved((event_dated(entry) for _, entry in site.recent), built)
    fixed: list[tuple[str, date | None]] = [
        ("", newest),
        ("acts/", newest),
        ("methodology/", _moved((site.run.run_date,), built)),
        ("about/", None),
        ("feeds/", newest),
        (amendments_href(), newest),
        (dates_href(), None),
    ]
    fixed.extend(
        (act_href(act.slug), _moved((event_dated(entry) for entry in act.entries), built))
        for act in site.acts
    )
    fixed.extend(
        (event_href(act.slug, entry.key), _moved((event_dated(entry),), built))
        for act in site.acts
        for entry in act.entries
    )
    # A provision's page is dated by the newest event that touched it: the page is a rendering
    # of those events and moves exactly when one of them does.
    fixed.extend(
        (
            provision_href(act.slug, history.location.canonical),
            _moved((event_dated(step.entry) for step in history.steps), built),
        )
        for act in site.acts
        for history in histories(act)
    )
    # An instrument's page is dated by the newest event attributed to it, for the same reason.
    fixed.extend(
        (amendment_href(key), _moved((event_dated(entry) for _, entry in amended), built))
        for key, amended in amended_by(site).items()
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


def sitemap_index_xml(site: SiteInputs) -> str:
    """The index, newline-terminated: one entry, naming the sitemap written beside it.

    An index is what a search engine is given to remember, and the file behind it can grow,
    split or be renamed without the submitted address moving. One entry today is not a
    degenerate index: it is the indirection itself that is the point, and a second sitemap
    joins it here rather than anywhere a crawler has to be told about.

    `<lastmod>` is the newest date the sitemap it names publishes, which is when that file's
    contents last moved under the same rule every entry in it is dated by. A sitemap with no
    dated entry at all carries none, for the reason `_moved` gives.
    """
    if not site.site_url:
        raise ValueError(_UNCONFIGURED)
    lines = [
        Html('<?xml version="1.0" encoding="utf-8"?>'),
        Html(f'<sitemapindex xmlns="{_NAMESPACE}">'),
        Html("<sitemap>"),
        Html(f"<loc>{escape(canonical_url(site.site_url, SITEMAP))}</loc>"),
    ]
    newest = _moved((dated for _, dated in _entries(site)), site.generated_on)
    if newest is not None:
        lines.append(Html(f"<lastmod>{escape(newest.isoformat())}</lastmod>"))
    lines.extend((Html("</sitemap>"), Html("</sitemapindex>"), Html("")))
    return join(lines, "\n")
