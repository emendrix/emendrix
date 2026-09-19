"""The methodology page's first section: the corpus this site renders, counted.

Split off `methodology.py` on 2026-09-18, when the page gained its glossary and had no room left
under the size cap. The seam is what the corpus holds against what was measured and how: every
figure here is rolled up at build time from the committed entries this build renders, where the
rest of the page reports a dated evaluation of a pinned, labelled set. The table both sections
print, `measure_table`, lives here too, so the two tables cannot be marked up two ways.
"""

from __future__ import annotations

from collections.abc import Iterable

from emendrix.site_.entries import corpus_rows, counted
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, escape, inline

__all__ = ["corpus_section", "measure_table"]

_COLUMNS = ("Result", "n", "What it means — and what it does not")
_CLASSES = ("", ' class="result"', "", ' class="meaning"')


def measure_table(first: str, rows: Iterable[tuple[Html, Html, Html, Html]]) -> list[Html]:
    """A table of measures, each row a measure, its result, its `n` and what it means.

    Every cell carries its column's header as `data-label`, which the sheet prints above the
    cell when a phone stacks each row into a block. The explicit roles are redundant on a wide
    screen and are what keep the table a table for a screen reader once the sheet sets its
    parts to `display: block`, which drops their table semantics in WebKit.
    """
    headers = (first, *_COLUMNS)
    head = "".join(f'<th role="columnheader">{escape(words)}</th>' for words in headers)
    lines = [
        Html('<div class="scroll">'),
        Html('<table role="table">'),
        Html(f'<thead role="rowgroup"><tr role="row">{head}</tr></thead>'),
        Html('<tbody role="rowgroup">'),
    ]
    for row in rows:
        cells = "".join(
            f'<td{css} role="cell" data-label="{escape(words)}">{cell}</td>'
            for css, words, cell in zip(_CLASSES, headers, row, strict=True)
        )
        lines.append(Html(f'<tr role="row">{cells}</tr>'))
    lines.extend((Html("</tbody>"), Html("</table>"), Html("</div>")))
    return lines


def corpus_section(site: SiteInputs) -> list[Html]:
    """What the reader is browsing, counted, above the table that scores a labelled subset.

    Above it rather than below because these rates describe the corpus on screen and those
    below it do not: a reader who met the pinned figures first would carry them onto every
    page they opened next. Every figure is rolled up at build time from the committed entries
    this build renders, and each arrives with its own caveat attached, by the same rule the
    measured table lives under: the result and its meaning are fields of one frozen row, so
    the table cannot print half of a measure.
    """
    counts = site.corpus
    lines = [Html('<h2 id="corpus">The corpus on this site, counted</h2>')]
    if counts.changes == 0:
        lines.append(
            Html(
                '<p class="small muted">This build was given no committed changelog entries, so '
                "there is nothing here to count.</p>"
            )
        )
        return lines
    lines.append(
        Html(
            f'<p class="small muted">Counted over the '
            f"{escape(counted(counts.events, 'version'))} and "
            f"{escape(counted(counts.changes, 'change'))} this site renders, and over "
            f"nothing else. The measured table below scores emendrix against a small labelled "
            f"set of transitions instead: a different question over a different denominator, "
            f"so a figure there is not a better reading of one here, and neither is adjusted "
            f"for the other.</p>"
        )
    )
    lines.extend(
        measure_table(
            "Over the published corpus",
            (
                (inline(row.measure), escape(row.result), escape(row.n), inline(row.meaning))
                for row in corpus_rows(counts)
            ),
        )
    )
    return lines
