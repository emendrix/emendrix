"""The twins index, one pair of acts' index, and the line an act page gives its pairs.

`twins/` lists every pair of acts whose provisions are compared, one line each. `twins/<pair>/`
lists every pair of units in the first act's document order with its score, linked to its page
or marked identical, or identical apart from numbering, then the units of either act with no
twin. Both say what "twin" means before anything else, because the word must never read as a
claim about the law: it means the two texts are textually similar by a stated measure, and
nothing more.

An identical pair is listed and has no page, because there is nothing to show but that the
texts are the same; so is a pair whose texts differ in numbering alone. A unit with no twin is
named with its closest match only when that match reached the floor and preferred another
unit; otherwise no unit of the other act reached it.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import ProvisionLocation
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import masthead, page_masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pages.twin import named, paired_on
from emendrix.site_.titles import SUFFIX
from emendrix.site_.trail import TWINS_ROSTER, Rung, twin_trail
from emendrix.site_.twin_inputs import pair_slug
from emendrix.site_.twin_model import TwinPairView
from emendrix.site_.twin_note import IDENTICAL, RENUMBERED, SIMILAR
from emendrix.site_.urls import depth_of, twin_api_href, twin_pair_href, twins_href, up
from emendrix.twins.model import Unpaired

__all__ = ["INDEX_LEAD", "render_twin_pair", "render_twins_index", "twin_doors"]

INDEX_LEAD: Final = (
    f"Pairs of watched acts whose provisions are compared word by word. A twin is a provision "
    f"of one act that is {SIMILAR} to one of the other, each the other's closest match; that "
    "says nothing about what either requires, or whether one should change because the other did."
)

_NONE: Final = "No pair of acts is compared in this build, so no provision has a twin here yet."


def _counts(view: TwinPairView) -> str:
    pairs = view.document.pairs
    identical = sum(pair.identical for pair in pairs)
    renumbered = sum(pair.numbering_only for pair in pairs)
    return (
        f"{count(len(pairs), 'pair')} of provisions, {identical} with {IDENTICAL}, "
        f"{renumbered} with {RENUMBERED}"
    )


def _sides(view: TwinPairView) -> str:
    first = view.pages[0] if view.pages else None
    if first is None:
        return ""
    return paired_on(first.a, first.b)


def render_twins_index(site: SiteInputs, views: tuple[TwinPairView, ...]) -> Html:
    """The page at `twins/`. Same inputs, same bytes, no clock, no network."""
    path = twins_href()
    root = up(depth_of(path))
    lines = [
        *page_masthead("index", "Textual twins", TWINS_ROSTER, path),
        Html(f'<p class="lede">{escape(INDEX_LEAD)}</p>'),
    ]
    if not views:
        lines.append(Html(f'<p class="none">{escape(_NONE)}</p>'))
    items = []
    for view in views:
        href = escape(root + view.path)
        words = f"{view.a.label} and {view.b.label}"
        items.append(
            Html(f'<li><a href="{href}">{escape(words)}</a>: {escape(_counts(view))}</li>')
        )
    if items:
        lines.append(Html(f"<ul>{join(items)}</ul>"))
    return page(
        title=f"Textual twins: provisions of two acts compared word by word{SUFFIX}",
        description=INDEX_LEAD,
        body=join(lines, "\n"),
        path=path,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )


def _unpaired(act: ActSite, other: ActSite, rows: tuple[Unpaired, ...]) -> list[Html]:
    if not rows:
        return []
    said = []
    for row in rows:
        unit = ProvisionLocation.parse(row.unit).human
        if row.best is not None and row.ratio is not None:
            best = ProvisionLocation.parse(row.best).human
            unit += f" (closest: {other.label} {best}, {row.ratio:.3f})"
        said.append(unit)
    lead = (
        f"{count(len(rows), 'provision')} of {act.label} with no twin in {other.label}. Where "
        f"one is named, its closest match reached the floor but is the twin of another."
    )
    return [
        Html(f'<h2 class="section">{escape(act.label)} provisions with no twin</h2>'),
        Html(f'<p class="small muted">{escape(lead)}</p>'),
        Html(f"<p>{escape(', '.join(said))}</p>"),
    ]


def render_twin_pair(site: SiteInputs, view: TwinPairView) -> Html:
    """The page at `twins/<pair>/`: every pair of units, then the units with none."""
    depth = depth_of(view.path)
    root = up(depth)
    document = view.document
    heading = f"{view.a.label} and {view.b.label}"
    rungs = twin_trail(Rung(name=heading, path=view.path))
    method = document.method
    lede = (
        f"Each line pairs a provision of {view.a.label} with one of {view.b.label} that are each "
        f"other's closest match by word ratio, at least {method.floor:.2f}, where 1 is identical "
        f"text: {SIMILAR}, and nothing more. The floor was read off the two acts' texts on "
        f"{method.verified_on}."
    )
    facts = [escape(_counts(view))]
    if sides := _sides(view):
        facts.append(escape(sides))
    api = escape(root + twin_api_href(view.slug))
    items = []
    for pair in document.pairs:
        shown = view.page_of(pair)
        if shown is None:
            words = (
                f"{view.a.label} {ProvisionLocation.parse(pair.a).human} and "
                f"{view.b.label} {ProvisionLocation.parse(pair.b).human}"
            )
            said = IDENTICAL if pair.identical else RENUMBERED
            items.append(Html(f"<li>{escape(words)} · {escape(said)}</li>"))
            continue
        href = escape(root + shown.path)
        words = f"{named(shown.a)} and {named(shown.b)}"
        withheld = " · differ too widely to excerpt" if pair.passages_withheld else ""
        items.append(
            Html(f'<li><a href="{href}">{escape(words)}</a> · {pair.ratio:.3f}{withheld}</li>')
        )
    lines = [
        *masthead("index", rungs, depth, escape("Textual twins"), escape(heading)),
        Html(f'<p class="facts">{join(facts, " · ")}</p>'),
        Html(f'<p class="lede">{escape(lede)}</p>'),
        Html(f'<p class="links"><a href="{api}">This pairing as JSON</a></p>'),
        Html('<h2 class="section">Pairs</h2>'),
        Html(f"<ul>{join(items)}</ul>"),
        *_unpaired(view.a, view.b, document.unpaired_a),
        *_unpaired(view.b, view.a, document.unpaired_b),
    ]
    description = (
        f"Every provision of {view.a.label} paired with a textually similar one of "
        f"{view.b.label}, with its score: {_counts(view)}."
    )
    return page(
        title=f"{heading}: textual twins, provision by provision{SUFFIX}",
        description=description,
        body=join(lines, "\n"),
        path=view.path,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
    )


def twin_doors(site: SiteInputs, act: ActSite, root: str) -> list[Html]:
    """One line on an act's page per pair it is in, linking the pair's index; none for none."""
    links = []
    for document in site.twins.maps:
        sides = {(document.a.corpus, document.a.key), (document.b.corpus, document.b.key)}
        if (act.act.corpus, act.act.key) not in sides:
            continue
        other = next(
            (
                one
                for one in site.acts
                if one.act != act.act and (one.act.corpus, one.act.key) in sides
            ),
            None,
        )
        if other is None:
            continue
        href = escape(root + twin_pair_href(pair_slug(document)))
        links.append(Html(f'<a href="{href}">Textual twins in {escape(other.label)}</a>'))
    return [Html(f'<p class="links">{join(links, " · ")}</p>')] if links else []
