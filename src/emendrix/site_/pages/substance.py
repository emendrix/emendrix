"""One CAS or EC number's page: every entry that prints it now, and every change to those entries.

The order is the reader's: which number this is and what else its rows print; the standing note
saying what the page can and cannot tell; where it appears now, one block per entry of the
newest version each act's register holds, with the row as printed under its table's header and
the last recorded change to it; the lookup; the history, newest first, each change with its rows
before and after and a link to the change block on its version page; then the sources.

Every sentence is about where a number appears. Nothing here says what an entry means for the
substance, and absence has one wording, because an entry naming a group prints no number and a
page that said a number was absent from the law would be wrong for every such group. The rows
are the act's own words, verbatim; the page's prose around them is held to that rule by
`tests/site_/test_substance_page.py`.
"""

from __future__ import annotations

from emendrix.core import EntryTable
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_date, time_html
from emendrix.site_.entry_grid import printed
from emendrix.site_.entry_table import change_table
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.outbound import external
from emendrix.site_.pages.substances_index import lookup
from emendrix.site_.seo import substance_json_ld
from emendrix.site_.substance_inputs import Holding, Moved, Substance, SubstanceLinks
from emendrix.site_.substance_words import (
    changed_by,
    entry_words,
    first_version,
    page_name,
    scheme_word,
    standing_note,
    substance_description,
    substance_title,
)
from emendrix.site_.trail import substance_trail
from emendrix.site_.urls import (
    act_href,
    depth_of,
    event_href,
    provision_href,
    substance_href,
    up,
)

__all__ = ["render_substance"]


def _identifiers(substance: Substance, links: SubstanceLinks) -> Html:
    """`CAS 121-43-7 · EC 204-468-9 · Index No 005-005-00-1`, every other page linked."""
    parts: list[Html] = []
    for one in substance.identifiers:
        words = escape(f"{scheme_word(one.scheme)} {one.value}")
        href = links.href(one.scheme, one.value)
        own = (one.scheme, one.value) == (substance.scheme, substance.value)
        parts.append(Html(f'<a href="{escape(href)}">{words}</a>') if href and not own else words)
    return Html(f'<p class="facts">{join(parts, " · ")}</p>')


def _same_entry(holding: Holding, moved: Moved) -> bool:
    entry, change = holding.entry, moved.change
    return (
        moved.act.act == holding.act.act
        and change.after is not None
        and (change.container, change.table, change.key, change.occurrence)
        == (entry.container, entry.table, entry.key, entry.occurrence)
    )


def _last(site: SiteInputs, substance: Substance, holding: Holding, root: str) -> Html:
    """The last recorded change to this entry, linked to its block, or why there is none."""
    if holding.entry.key is None:
        return escape("This row carries no key, so no change to it is compared.")
    moved = next((m for m in substance.history if _same_entry(holding, m)), None)
    if moved is None:
        first = first_version(holding.act)
        since = f" since the first version the record holds, {first}" if first else " recorded"
        return escape(f"No change to this entry{since}.")
    href = f"{root}{event_href(moved.act.slug, moved.event.key)}#{moved.anchor}"
    by = changed_by(site, moved)
    dated = moved.dated
    return Html(
        f'<a href="{escape(href)}">Last changed in the version {dated.clock} '
        f"{time_html(dated.on)}</a>{escape(', ' + by if by else '')}"
    )


def _now(site: SiteInputs, substance: Substance, root: str, links: SubstanceLinks) -> list[Html]:
    lines = [Html('<h2 class="section">Where it appears now</h2>')]
    if not substance.holdings:
        lines.append(
            Html(
                '<p class="none">No entry in the newest versions the record holds prints this '
                "number; the history below lists every recorded change that did.</p>"
            )
        )
    touched = site.substances.touched
    for holding in substance.holdings:
        act, unit = holding.act, holding.entry.unit
        facts = [_last(site, substance, holding, root)]
        if unit.canonical in touched.get(act.slug, frozenset()):
            href = escape(root + provision_href(act.slug, unit.canonical))
            facts.append(Html(f'<a href="{href}">{escape(unit.human)} on this site</a>'))
        if holding.entry.group:
            facts.append(escape(f"In: {holding.entry.group}"))
        lines += [
            Html('<section class="holding">'),
            Html(f"<h3>{escape(entry_words(holding))}</h3>"),
            Html(f'<p class="facts">{join(facts, " · ")}</p>'),
            printed(holding.entry, holding.table),
            Html("</section>"),
        ]
    return lines


Drawn = dict[tuple[str, str, int, int], Html]
"""Change tables already drawn, by act, event, change and entry change: a change printing both a
CAS and an EC number is drawn once for the two pages, which link from the same depth."""


def _history(
    site: SiteInputs, substance: Substance, root: str, links: SubstanceLinks, drawn: Drawn
) -> list[Html]:
    lines = [Html('<h2 class="section">Its history</h2>')]
    if not substance.history:
        first = first_version(substance.holdings[0].act) if substance.holdings else None
        since = f" since the first version the record holds, {first}" if first else " recorded"
        lines.append(Html(f'<p class="none">{escape(f"No change to this entry{since}.")}</p>'))
    for moved in substance.history:
        dated = moved.dated
        href = f"{root}{event_href(moved.act.slug, moved.event.key)}#{moved.anchor}"
        by = changed_by(site, moved)
        only = (
            " Only spacing, dash forms or accents differ." if moved.change.typography_only else ""
        )
        tables = (moved.table,) if moved.table is not None else ()
        lines += [
            Html('<section class="moved">'),
            Html(
                f"<h3>{time_html(dated.on)} · {escape(moved.change.kind)} · "
                f"{escape(entry_words(moved))}</h3>"
            ),
            Html(
                f'<p class="facts">Recorded in the version {escape(dated.clock)} '
                f"{time_html(dated.on)}{escape(', ' + by if by else '')}.{escape(only)} "
                f'<a href="{escape(href)}">The change on its version page</a></p>'
            ),
            _drawn(moved, tables, links, drawn),
            Html("</section>"),
        ]
    return lines


def _sources(site: SiteInputs, substance: Substance, root: str) -> list[Html]:
    """Each act's page, and the consolidated version its register was read from."""
    versions: dict[str, tuple[ActSite, str | None]] = {}
    for holding in substance.holdings:
        versions.setdefault(holding.act.slug, (holding.act, holding.version))
    for moved in substance.history:
        versions.setdefault(moved.act.slug, (moved.act, None))
    items: list[Html] = []
    for act, version in versions.values():
        href = escape(root + act_href(act.slug))
        parts = [Html(f'<a href="{href}">{escape(act.label)}</a>: every version the record holds')]
        if version is not None and version in act.eurlex_url:
            found = next((e for e in act.entries if str(e.to_version) == version), None)
            dated = f", {event_date(found).human}" if found is not None else ""
            parts.append(external(act.eurlex_url, f"EUR-Lex consolidated version {version}{dated}"))
        items.append(Html(f"<li>{join(parts, '; rows read from ')}</li>"))
    lines = [Html('<h2 class="section">Sources</h2>'), Html(f"<ul>{join(items)}</ul>")]
    if site.accounts:
        href = escape(f"{root}account/watch?substance={substance.slug}")
        lines.append(Html(f'<p class="links"><a href="{href}">Watch this substance</a></p>'))
    return lines


def _drawn(
    moved: Moved, tables: tuple[EntryTable, ...], links: SubstanceLinks, drawn: Drawn
) -> Html:
    key = (moved.act.slug, moved.event.key, moved.index, moved.position)
    if key not in drawn:
        drawn[key] = change_table(moved.change, tables, links)
    return drawn[key]


def render_substance(site: SiteInputs, substance: Substance, drawn: Drawn | None = None) -> Html:
    """One identifier's page. Deterministic: same inputs, same bytes, no clock, no network.

    `drawn` is a table of change tables shared across the pages of one build; every substance
    page sits at one depth, so a table drawn for one is the same bytes on the next."""
    path = substance_href(substance.scheme, substance.value)
    depth = depth_of(path)
    root = up(depth)
    links = site.substances.links(root)
    number = f"{scheme_word(substance.scheme)} {substance.value}"
    name = page_name(substance)
    heading = escape(number)
    if name:
        heading = Html(f'{heading} <span class="sub">{escape(name)}</span>')
    caption = escape(f"{scheme_word(substance.scheme)} number")
    rungs = substance_trail(number, path)
    body = join(
        (
            *masthead("prose", rungs, depth, caption, heading),
            _identifiers(substance, links),
            Html(f'<p class="lede">{escape(standing_note(substance))}</p>'),
            *_now(site, substance, root, links),
            *lookup(root),
            *_history(site, substance, root, links, {} if drawn is None else drawn),
            *_sources(site, substance, root),
        ),
        "\n",
    )
    title = substance_title(substance)
    description = substance_description(site, substance)
    parts: dict[str, tuple[ActSite, list[str]]] = {}
    sides = [(h.act, h.entry.unit.human) for h in substance.holdings] or [
        (m.act, m.side.unit.human) for m in substance.history
    ]
    for act, unit in sides:
        units = parts.setdefault(act.slug, (act, []))[1]
        if unit not in units:
            units.append(unit)
    target = substance.canonical
    return page(
        title=title,
        description=description,
        body=body,
        path=path,
        chrome=site.chrome,
        canonical=None if target is None else substance_href(target.scheme, target.value),
        substances=True,
        feeds=((feed_path(None), feed_title(None)),),
        structured=(
            substance_json_ld(
                site,
                rungs,
                tuple((act, tuple(units)) for act, units in parts.values()),
                title=title,
                description=description,
            )
            if site.site_url
            else None
        ),
    )
