"""One twin pair's page: where the texts of two textually similar provisions differ.

The order is the reader's: which two provisions these are and how similar, one sentence saying
what that means and does not; the differing passages side by side, or the sentence saying they
differ too widely to excerpt; the aligned sub-provisions with their scores; the changes the
record holds to either unit since the texts were paired; and where to read both whole.

**No provision's full text is on this page.** The passages are the committed map's, each a
differing span with a few words of context, capped in length and number when the map was
written, and a pair whose passages would show too large a share of either text carries none.
Everything else is names, scores and links: the acts' own publications serve the text.
"""

from __future__ import annotations

from typing import Final

from emendrix.core import ProvisionLocation
from emendrix.site_.chrome import page
from emendrix.site_.clocks import human_date, version_heading
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import masthead
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.outbound import external
from emendrix.site_.seo import substance_json_ld
from emendrix.site_.tags import kind_tag
from emendrix.site_.titles import SUFFIX
from emendrix.site_.trail import Rung, twin_trail
from emendrix.site_.twin_model import TwinPageView, TwinPairView, TwinSideView
from emendrix.site_.twin_note import SIMILAR
from emendrix.site_.urls import depth_of, event_href, provision_href, up
from emendrix.twins.passages import CONTEXT_WORDS, CUT, PASSAGE_CHARS

__all__ = ["WITHHELD", "named", "paired_on", "render_twin_page"]

WITHHELD: Final = "These two provisions differ too widely to excerpt here; read both on EUR-Lex."

_STANDING: Final = (
    "That says nothing about what either provision requires, or whether one should change "
    "because the other did."
)

_EXCERPTS: Final = (
    f"Each passage is a differing span with up to {CONTEXT_WORDS} unchanged words either side, "
    f"from the text as compared, spacing collapsed, and cut at {PASSAGE_CHARS} characters where "
    f"it ends {CUT}. It is an excerpt for reading where the two differ, not the verbatim text."
)


def named(side: TwinSideView) -> str:
    """`Medical Devices Regulation Art. 10`: the act's label and the unit in its human form."""
    return f"{side.act.label} {ProvisionLocation.parse(side.unit).human}"


def paired_on(a: TwinSideView, b: TwinSideView) -> str:
    """`paired on both acts' texts of 10 January 2025`, or the two dates when they differ."""

    def said(side: TwinSideView) -> str:
        return side.version if side.paired_on is None else human_date(side.paired_on)

    if said(a) == said(b):
        return f"paired on both acts' texts of {said(a)}"
    return f"paired on the {a.act.label} text of {said(a)} and the {b.act.label} text of {said(b)}"


def _side_words(text: str) -> Html:
    """One side of a passage, its cut marker set apart as the site's interruption."""
    if not text:
        return Html('<span class="elided">no words</span>')
    if text.endswith(CUT):
        return Html(f'{escape(text[: -len(CUT)])}<span class="elided">{escape(CUT)}</span>')
    return escape(text)


def _passages(view: TwinPageView) -> list[Html]:
    lines = [Html('<h2 class="section" id="differences">Where the texts differ</h2>')]
    pair = view.pair
    if pair.passages_withheld:
        return [*lines, Html(f'<p class="none">{escape(WITHHELD)}</p>')]
    left, right = named(view.a), named(view.b)
    head = "".join(
        f'<th role="columnheader">{escape(words)}</th>' for words in ("Passage", left, right)
    )
    lines += [
        Html(f'<p class="small muted">{escape(_EXCERPTS)}</p>'),
        Html('<div class="scroll"><table role="table">'),
        Html(f'<thead role="rowgroup"><tr role="row">{head}</tr></thead>'),
        Html('<tbody role="rowgroup">'),
    ]
    for number, passage in enumerate(pair.passages, start=1):
        cells = [
            f'<td role="cell">{number}</td>',
            f'<td role="cell" data-label="{escape(left)}"><p class="diff">'
            f"{_side_words(passage.a)}</p></td>",
            f'<td role="cell" data-label="{escape(right)}"><p class="diff">'
            f"{_side_words(passage.b)}</p></td>",
        ]
        lines.append(Html(f'<tr role="row">{"".join(cells)}</tr>'))
    lines += [Html("</tbody>"), Html("</table></div>")]
    if pair.passages_omitted:
        more = count(pair.passages_omitted, "more passage")
        lines.append(Html(f'<p class="small">{escape(more)} not shown; read both on EUR-Lex.</p>'))
    return lines


def _children(view: TwinPageView) -> list[Html]:
    if not view.pair.children:
        return []
    items = [
        Html(
            f"<li>{escape(ProvisionLocation.parse(child.a).human)} and "
            f"{escape(ProvisionLocation.parse(child.b).human)} · {child.ratio:.3f}</li>"
        )
        for child in view.pair.children
    ]
    return [
        Html('<h2 class="section">Aligned sub-provisions</h2>'),
        Html(
            f'<p class="small muted">{escape(view.a.act.label)} first, then '
            f"{escape(view.b.act.label)}, each with its word ratio.</p>"
        ),
        Html(f"<ul>{join(items)}</ul>"),
    ]


def _changes(view: TwinPageView, root: str) -> list[Html]:
    lines = [Html('<h2 class="section">Changes since the texts were paired</h2>')]
    if not view.changes:
        words = (
            "The record holds no change to either provision after the versions they were paired on."
        )
        return [*lines, Html(f'<p class="none">{escape(words)}</p>')]
    items = []
    for change in view.changes:
        step = change.step
        href = escape(f"{root}{event_href(change.act.slug, step.entry.key)}#{step.anchor}")
        unit = ProvisionLocation.parse(step.change.location.canonical).human
        items.append(
            Html(
                f"<li>{escape(change.act.label)} {escape(unit)} · "
                f'<a href="{href}">{version_heading(step.entry)}</a> · '
                f"{kind_tag(step.change.change_type)}</li>"
            )
        )
    return [*lines, Html(f"<ul>{join(items)}</ul>")]


def _sources(view: TwinPageView, root: str) -> Html:
    links: list[Html] = []
    for side in (view.a, view.b):
        if side.url:
            links.append(external(side.url, f"{named(side)} on EUR-Lex"))
    for side in (view.a, view.b):
        if side.page:
            href = escape(root + provision_href(side.act.slug, side.unit))
            links.append(Html(f'<a href="{href}">{escape(named(side))}: its history</a>'))
    return Html(f'<p class="links">{join(links, " · ")}</p>') if links else Html("")


def render_twin_page(site: SiteInputs, pair: TwinPairView, view: TwinPageView) -> Html:
    """One twin pair's page. Deterministic: same inputs, same bytes, no clock, no network."""
    depth = depth_of(view.path)
    root = up(depth)
    left, right = named(view.a), named(view.b)
    both = f"{left} and {right}"
    ratio = f"{view.pair.ratio:.3f}"
    rungs = twin_trail(
        Rung(name=f"{pair.a.label} and {pair.b.label}", path=pair.path),
        Rung(name=both, path=view.path),
    )
    heading = Html(f'{escape(both)} <span class="sub">where the texts differ</span>')
    headings = "the same" if view.pair.headings_equal else "different"
    facts = [
        escape(f"{SIMILAR} ({ratio})"),
        escape(paired_on(view.a, view.b)),
        escape(f"headings {headings}"),
    ]
    lede = (
        f"{both} are {SIMILAR}: their words match at a ratio of {ratio}, where 1 is identical "
        f"text. {_STANDING}"
    )
    body = join(
        (
            *masthead("provision", rungs, depth, escape("Textual twins"), heading),
            Html(f'<p class="facts">{join(facts, " · ")}</p>'),
            Html(f'<p class="lede">{escape(lede)}</p>'),
            _sources(view, root),
            *_passages(view),
            *_children(view),
            *_changes(view, root),
        ),
        "\n",
    )
    title = f"{both}: where the texts differ{SUFFIX}"
    passages = view.pair.passages
    if view.pair.passages_withheld:
        shown = "they differ too widely to excerpt, and both are linked on EUR-Lex"
    elif view.pair.passages_omitted:
        total = len(passages) + view.pair.passages_omitted
        shown = f"{len(passages)} of the {total} passages where they differ, side by side"
    else:
        shown = f"{count(len(passages), 'passage')} where they differ, side by side"
    description = f"{both} are {SIMILAR} ({ratio}). Here: {shown}."
    units = tuple(
        (side.act, (ProvisionLocation.parse(side.unit).human,)) for side in (view.a, view.b)
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=view.path,
        chrome=site.chrome,
        feeds=((feed_path(None), feed_title(None)),),
        structured=(
            substance_json_ld(site, rungs, units, title=title, description=description)
            if site.site_url
            else None
        ),
    )
