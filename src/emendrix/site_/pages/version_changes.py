"""The line a short version's masthead opens with, naming each change it made.

A version with six or more changes opens with the in-page index; one with fewer had no map at
its top at all, and on a phone its changes began below the first screen, under the amending
act's full official title. This line is the map such a page lacked: each change's coordinate,
linked to the block below, and its subject where the provision has one.

It reads the one threshold `event_index.INDEX_ABOVE` so the two maps never both print and a
page with changes never prints neither. It links on the anchors the page already computed and
names each change the way the index does, coordinate first and then title, so the two read
alike. Here the coordinate alone is the link, so a screen reader's list of links stays short
and every link names a place.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.pages.event_index import INDEX_ABOVE
from emendrix.site_.pages.prose import title_span

__all__ = ["changes_line"]


def changes_line(entry: ChangelogEntry, anchors: tuple[str, ...]) -> list[Html]:
    """`Changes: Annex II · …`, one link per change, where the page has no index.

    Items keep the entry's own order, the order the blocks below carry them, and a repeated
    coordinate is listed once per block on that block's own anchor. A change with no title
    prints its coordinate alone.
    """
    if not 0 < len(entry.changes) < INDEX_ABOVE:
        return []
    items = [
        Html(
            f'<a href="#{escape(anchor)}">{escape(emitted.change.location.human)}</a>'
            f"{title_span(emitted.change)}"
        )
        for emitted, anchor in zip(entry.changes, anchors, strict=True)
    ]
    return [
        Html('<nav class="changes-line" aria-label="Changes in this version">'),
        Html(f'<p><span class="lead">Changes:</span> {join(items, " · ")}</p>'),
        Html("</nav>"),
    ]
