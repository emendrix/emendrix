"""The line that stays on screen while a long version page scrolls: which act, which version.

A version with dozens of changes is tens of thousands of pixels tall, and once its masthead has
scrolled away nothing on screen says which act or which version the block in view belongs to,
nor how to get back to the list of changes. This line says both. The sheet pins it to the top of
the viewport, so it is one slim row and never a second header.

It is a `<div>` holding a `<p>`, not a `<nav>`: the page already names four landmarks (the site
navigation, the breadcrumb, the pager and the index of changes), and a fifth carrying the same
links again would be noise to a screen reader's landmark list. It sits after the version's
masthead in the markup, so a keyboard reader meets it once, after the page has introduced itself.

It exists exactly where the index does, and keys off the index's own threshold rather than one
of its own, so the page can never carry a way back to an index it does not have.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.clocks import version_heading
from emendrix.site_.inputs import ActSite
from emendrix.site_.markup import Html, escape
from emendrix.site_.pages.event_index import INDEX_ABOVE, INDEX_ID
from emendrix.site_.urls import act_href, up

__all__ = ["context_bar"]


def context_bar(act: ActSite, entry: ChangelogEntry, depth: int) -> list[Html]:
    """The act (a link to its page), the version's name, and a link to the index of changes.

    Empty below `INDEX_ABOVE`, where the page has no index: a short page's masthead is still on
    screen when its last change ends, so there is nothing for the line to remind anyone of.
    """
    if len(entry.changes) < INDEX_ABOVE:
        return []
    act_page = escape(up(depth) + act_href(act.slug))
    return [
        Html(
            f'<div class="context"><p><a href="{act_page}">{escape(act.label)}</a> · '
            f'{version_heading(entry)} · <a href="#{INDEX_ID}">Index</a></p></div>'
        )
    ]
