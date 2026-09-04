"""Every date one act's amended text names, gathered under its timeline as a list of facts.

An act page answers what changed and when it was recorded. This section answers a third thing
the committed data already holds and no page printed: which dates the text itself names, and
which amendment put each one there or took it away. The MDR's postponement moved 2020-05-26 to
2021-05-26 in six provisions at once, and until this list existed a reader could see that only
by opening six change blocks.

It sits beside `act_event.py` for the reason that module sits beside `act.py`: the act page
decides what an act's history looks like as a whole, and each of these renders one statement
the page places. Keeping it here also keeps `act.py` under the size cap, which is the second
reason and not the first.

**Every word of the lede is load-bearing.** A list of dates under a heading is read as a
schedule unless the page says otherwise, and this project may not publish a schedule: a date in
a provision's text is a date the parser read off the source's own date markup, and what it
governs is prose nothing here parses. So the lede says what the list is, says what it is not,
and points at the one line on the site that answers the other question, the applies-from line
on each change. No word here calls a date a deadline, an obligation or an application date.

The rows are links and nothing else: the coordinate leads to that provision's whole history and
the dated words lead to the change block that moved the date, so every row can be checked
against the verbatim text in two clicks. Nothing is summarised, counted into a claim, or
grouped into a period.
"""

from __future__ import annotations

from typing import Final

from emendrix.site_.clocks import event_date
from emendrix.site_.history import DateMention
from emendrix.site_.inputs import ActSite
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.urls import event_href, provision_href

__all__ = ["ANCHOR", "FOLD_ABOVE", "LEDE", "LINK", "dates_section"]

ANCHOR: Final = "dates-named"
"""The section's id, and the fragment the act page's index links it by."""

HEADING: Final = "Dates the amended text names"
LINK: Final = "Dates named"
"""The heading, and the shorter form the index uses for the same section."""

LEDE: Final = (
    "Every date an amendment added to or removed from a provision's text, as the parser read "
    "it, with the provision and the event. This is a list of dates the text contains. Whether "
    'a provision applies from one of them is stated for each change under "applies from", and '
    "nowhere else."
)
"""What the list is and what it is not, above the list rather than under it.

Two sentences of it are the disclaimer: the site publishes the dates a machine read out of the
text, and reading a date as the day an obligation starts is the inference `CLAUDE.md`
§"Two clocks" forbids. A reader who wants that answer is pointed at the one line that gives it.
"""

FOLD_ABOVE: Final = 12
"""How many rows the list shows open before the whole of it goes behind a `<details>`.

About one screen, which is the same measure `pages/event_index.py` sets its own threshold by.
An act amended once carries a handful of dates and a list of them costs a reader nothing; an
act whose annexes have been renumbered for a decade carries scores, and a section that pushed
the timeline off the page would be a list nobody asked for standing in front of the one they
did. One number, with the count in the summary so the fold says how much it holds.
"""

_MOVED: Final = {True: "added to", False: "removed from"}
"""Which direction the date moved, in the two words `DateMention.added` distinguishes."""


def dates_section(act: ActSite, mentions: tuple[DateMention, ...], root: str) -> list[Html]:
    """The act's whole list of dates its text names, or nothing at all when none moved.

    `root` is the climb from this page to the site root, `up(_DEPTH)` on the act page, handed in
    rather than computed here: the page owns its own depth and a second construction of it is
    how one of them drifts from the other. The two links per row are then built the same way
    every other link on that page is.
    """
    if not mentions:
        return []
    rows = [
        Html(
            f'<li><span class="on">{escape(one.on.isoformat())}</span> '
            f"{escape(_MOVED[one.added])} "
            f'<a href="{escape(root + provision_href(act.slug, one.location.canonical))}">'
            f"{escape(one.location.human)}</a> · "
            f'<a href="{escape(root + event_href(act.slug, one.entry.key))}'
            f'#{escape(one.anchor)}">{escape(event_date(one.entry).words)}</a></li>'
        )
        for one in mentions
    ]
    folded = len(rows) > FOLD_ABOVE
    lines = [
        Html(f'<section class="dates-named" id="{ANCHOR}">'),
        Html(f"<h2>{escape(HEADING)}</h2>"),
        Html(f'<p class="small muted">{escape(LEDE)}</p>'),
    ]
    if folded:
        lines.append(Html(f"<details><summary>{escape(count(len(rows), 'date'))}</summary>"))
    lines.extend((Html("<ul>"), *rows, Html("</ul>")))
    if folded:
        lines.append(Html("</details>"))
    lines.append(Html("</section>"))
    return lines
