"""One version as an item in a list: the act's timeline and an amending act's page.

A card is a point on a rail, headed by the version's human name as its one link, so a version
has one name and one destination wherever it is listed. Under the name: the amending act that
made it, with its official title uncut, then the tally and the identifiers, small. The version's
own page opens with a masthead instead (`pages/version_masthead.py`), because a page's subject
and an item in a list are two jobs; the two share the helpers that read the document's facts and
never their markup.

The card keeps `id="{entry.key}"`: every feed entry's `<id>` was minted from the act page's copy
of it, and an address published once never stops resolving.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct, made_by
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, UNATTRIBUTED_NOTE, unattributed
from emendrix.site_.clocks import version_heading
from emendrix.site_.markup import Html, escape
from emendrix.site_.tags import tag, tally
from emendrix.site_.untouched import all_textless, textless_note, untouched, untouched_note

__all__ = ["version_card"]


def version_card(
    entry: ChangelogEntry,
    href: str,
    acts: tuple[AmendingAct, ...],
    *,
    level: int,
    root: str,
    extra: tuple[Html, ...] = (),
    omit: str = "",
) -> list[Html]:
    """One version, as a card headed `<h{level}>`, linking the version's page at `href`.

    `root` climbs from the listing page to the site root. `omit` is the key of an amending act
    the card must not name, because the page the card is printed on is that act's own; any
    other act the version folded in is still named. `extra` is what one page has to add about
    this version that is true only there, closed inside the same article.

    The glossary link is not on the card: a list of cards prints it once, above them.
    """
    named = tuple(act for act in acts if act.key != omit)
    lines = [
        Html(f'<article class="event" id="{escape(entry.key)}">'),
        Html(f'<h{level}><a href="{escape(href)}">{version_heading(entry)}</a></h{level}>'),
    ]
    if named:
        lines.extend(made_by(named, root, verb="Made by"))
        title = named[0].title
        if title:
            lines.append(Html(f'<p class="subject">{escape(title)}</p>'))
    elif not acts and unattributed(entry):
        stated = "" if entry.in_force else " In force date not stated."
        lines.extend(
            (
                Html(f'<p class="amending">{tag("unattributed", UNATTRIBUTED_LABEL)}{stated}</p>'),
                Html(f'<p class="note">{escape(UNATTRIBUTED_NOTE)}</p>'),
            )
        )
    lines.extend(tally(entry, shapes=False))
    lines.append(
        Html(
            f'<p class="ident"><code class="id">{escape(str(entry.from_version))}</code> → '
            f'<code class="id">{escape(str(entry.to_version))}</code></p>'
        )
    )
    if untouched(entry):
        lines.append(Html(f'<p class="note">{escape(untouched_note(entry))}</p>'))
    elif all_textless(entry):
        lines.append(Html(f'<p class="note">{escape(textless_note(entry))}</p>'))
    lines.extend((*extra, Html("</article>")))
    return lines
