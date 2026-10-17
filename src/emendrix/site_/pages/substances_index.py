"""The substances index, each act's list of numbers, and the lookup every substance page carries.

`substances/` says what the pages under it are, counts them per act and links each act's list;
`substances/acts/<slug>/` lists every CAS and EC number an entry of that act prints, now or in a
recorded change, sorted, split into numbered continuation pages of at most `PER_PAGE`, so no
list grows past a few hundred kilobytes however large the act's tables are. A build with no
register at all still writes the index, saying so, because a door on every page leads here.

The lookup is the site's search box, which reads a number typed with or without its hyphens;
the paragraph says so, and the lists are the way in for a reader without the script.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import masthead, page_masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.substance_inputs import Substance
from emendrix.site_.substance_words import page_name, scheme_word
from emendrix.site_.titles import SUFFIX
from emendrix.site_.trail import SUBSTANCES_ROSTER, substance_trail
from emendrix.site_.urls import depth_of, substance_href, substance_list_href, substances_href, up

__all__ = [
    "INDEX_LEAD",
    "PER_PAGE",
    "act_lists",
    "lookup",
    "render_substance_list",
    "render_substances_index",
]

PER_PAGE: Final = 2000
"""Numbers on one list page. Past it the list continues on `.../2/`, `.../3/` and so on."""

INDEX_LEAD: Final = (
    "Every CAS and EC number an entry in the record prints, by act. A number missing here is "
    "printed by no entry in the acts this record holds, which says nothing about the law."
)

_NONE: Final = (
    "No act in this build has a register of table entries, so no CAS or EC number has a page "
    "here yet."
)


def lookup(root: str) -> list[Html]:
    """How to look a number up: the search box, and the lists for a reader without the script."""
    return [
        Html('<h2 class="section" id="lookup">Look up a number</h2>'),
        Html(
            "<p>Type a CAS or EC number, with or without its hyphens, or an Index No into the "
            "search box at the top of the page: it reads <code>50000</code> as CAS "
            "<code>50-00-0</code>. Every number is also listed by act on "
            f'<a href="{root}{substances_href()}">the substances page</a>.</p>'
        ),
    ]


def act_lists(site: SiteInputs) -> tuple[tuple[ActSite, tuple[Substance, ...]], ...]:
    """Each shown act with at least one number, in roster order, with every paged number an
    entry of it prints now or in a recorded change, sorted. One pass over the numbers."""
    found: dict[tuple[str, str], list[Substance]] = {}
    for substance in site.substances.substances:
        acts = {(h.act.act.corpus, h.act.act.key) for h in substance.holdings}
        acts |= {(m.act.act.corpus, m.act.act.key) for m in substance.history}
        for key in acts:
            found.setdefault(key, []).append(substance)
    return tuple(
        (act, tuple(found[(act.act.corpus, act.act.key)]))
        for act in site.acts
        if (act.act.corpus, act.act.key) in found
    )


def render_substances_index(site: SiteInputs) -> Html:
    """The page at `substances/`. Same inputs, same bytes, no clock, no network."""
    path = substances_href()
    root = up(depth_of(path))
    lines = [
        *page_masthead("index", "Substances", SUBSTANCES_ROSTER, path),
        Html(f'<p class="lede">{escape(INDEX_LEAD)}</p>'),
    ]
    lists = act_lists(site)
    if not lists:
        lines.append(Html(f'<p class="none">{escape(_NONE)}</p>'))
    else:
        items = []
        for act, numbers in lists:
            cas = sum(1 for one in numbers if one.scheme == "cas")
            ec = len(numbers) - cas
            href = escape(root + substance_list_href(act.slug))
            words = f"{count(cas, 'CAS number')} and {count(ec, 'EC number')}"
            items.append(
                Html(f'<li><a href="{href}">{escape(act.label)}</a>: {escape(words)}</li>')
            )
        lines += [Html('<h2 class="section">By act</h2>'), Html(f"<ul>{join(items)}</ul>")]
    lines += lookup(root)
    return page(
        title=f"Substances: every CAS and EC number an entry prints{SUFFIX}",
        description=INDEX_LEAD,
        body=join(lines, "\n"),
        path=path,
        chrome=site.chrome,
        substances=True,
        feeds=((feed_path(None), feed_title(None)),),
    )


def _pager(act: ActSite, number: int, pages: int, root: str) -> list[Html]:
    links: list[Html] = []
    if number > 1:
        href = escape(root + substance_list_href(act.slug, number - 1))
        links.append(Html(f'<a href="{href}" rel="prev">Previous page</a>'))
    if number < pages:
        href = escape(root + substance_list_href(act.slug, number + 1))
        links.append(Html(f'<a href="{href}" rel="next">Next page</a>'))
    return [Html(f'<p class="links">{join(links, " · ")}</p>')] if links else []


def render_substance_list(
    site: SiteInputs, act: ActSite, numbers: tuple[Substance, ...], number: int
) -> Html:
    """Page `number` of one act's list of numbers, `PER_PAGE` at most."""
    pages = max(1, -(-len(numbers) // PER_PAGE))
    path = substance_list_href(act.slug, number)
    depth = depth_of(path)
    root = up(depth)
    shown = numbers[(number - 1) * PER_PAGE : number * PER_PAGE]
    items = []
    for substance in shown:
        href = escape(root + substance_href(substance.scheme, substance.value))
        words = escape(f"{scheme_word(substance.scheme)} {substance.value}")
        name = page_name(substance)
        named = f' <span class="sub">{escape(name)}</span>' if name else ""
        items.append(Html(f'<li><a href="{href}">{words}</a>{named}</li>'))
    heading = f"CAS and EC numbers in {act.label}"
    if pages > 1:
        heading += f", page {number} of {pages}"
    first = (number - 1) * PER_PAGE + 1
    summary = (
        f"{count(len(numbers), 'number')} an entry of {act.label} prints in the newest version "
        "the record holds or in a recorded change"
        + (f"; numbers {first} to {first + len(shown) - 1} here." if pages > 1 else ".")
    )
    lines = [
        *masthead(
            "index", substance_trail(heading, path), depth, escape("Substances"), escape(heading)
        ),
        Html(f'<p class="lede">{escape(summary)}</p>'),
        Html(f'<ul class="roster">{join(items, chr(10))}</ul>'),
        *_pager(act, number, pages, root),
    ]
    return page(
        title=f"{heading}{SUFFIX}",
        description=summary,
        body=join(lines, "\n"),
        path=path,
        chrome=site.chrome,
        substances=True,
        feeds=((feed_path(None), feed_title(None)),),
    )
