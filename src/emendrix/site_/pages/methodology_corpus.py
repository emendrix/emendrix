"""The methodology page's first section: the corpus this site renders, counted.

Split off `methodology.py` on 2026-09-18, when the page gained its glossary and had no room left
under the size cap. The seam is what the corpus holds against what was measured and how: every
figure here is rolled up at build time from the committed entries this build renders, where the
rest of the page reports a dated evaluation of a pinned, labelled set.
"""

from __future__ import annotations

from emendrix.site_.entries import corpus_rows, counted
from emendrix.site_.inputs import SiteInputs
from emendrix.site_.markup import Html, escape, inline

__all__ = ["corpus_section"]


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
    lines.extend(
        (
            Html(
                f'<p class="small muted">Counted over the '
                f"{escape(counted(counts.events, 'version'))} and "
                f"{escape(counted(counts.changes, 'change'))} this site renders, and over "
                f"nothing else. The measured table below scores emendrix against a small labelled "
                f"set of transitions instead: a different question over a different denominator, "
                f"so a figure there is not a better reading of one here, and neither is adjusted "
                f"for the other.</p>"
            ),
            Html('<div class="scroll">'),
            Html("<table>"),
            Html(
                "<thead><tr><th>Over the published corpus</th><th>Result</th><th>n</th>"
                "<th>What it means — and what it does not</th></tr></thead>"
            ),
            Html("<tbody>"),
        )
    )
    lines.extend(
        Html(
            f"<tr><td>{inline(row.measure)}</td>"
            f'<td class="result">{escape(row.result)}</td>'
            f"<td>{escape(row.n)}</td>"
            f'<td class="meaning">{inline(row.meaning)}</td></tr>'
        )
        for row in corpus_rows(counts)
    )
    lines.extend((Html("</tbody>"), Html("</table>"), Html("</div>")))
    return lines
