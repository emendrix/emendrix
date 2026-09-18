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

from datetime import date

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct, made_by
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, UNATTRIBUTED_NOTE, unattributed
from emendrix.site_.clocks import event_date, human_date, version_heading
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
    coded: date | None = None,
) -> list[Html]:
    """One version, as a card headed `<h{level}>`, linking the version's page at `href`.

    `root` climbs from the listing page to the site root. `omit` is the key of an amending act
    the card must not name, because the page the card is printed on is that act's own; any
    other act the version folded in is still named. `extra` is what one page has to add about
    this version that is true only there, closed inside the same article. `coded` is the date
    the composition root resolved for the version's code, which the card sets beside the
    in-force date where the two differ.

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
    lines.extend(_coded(entry, coded))
    if untouched(entry):
        lines.append(Html(f'<p class="note">{escape(untouched_note(entry))}</p>'))
    elif all_textless(entry):
        lines.append(Html(f'<p class="note">{escape(textless_note(entry))}</p>'))
    lines.extend((*extra, Html("</article>")))
    return lines


def _coded(entry: ChangelogEntry, coded: date | None) -> list[Html]:
    """Why the version's code carries a date it is not in force from, where it does.

    Printed only where an in-force date is recorded and differs from the coded one: a reader
    comparing `20180101` in the identifier with `31 December 2015` in the heading is owed the
    reason, and a reader whose two dates agree is owed nothing. The coded date is printed as
    the code writes it, never read back out of the code here.
    """
    if coded is None or not entry.in_force:
        return []
    in_force = event_date(entry).on
    if in_force == coded:
        return []
    return [
        Html(
            f'<p class="note">Coded {coded.strftime("%Y%m%d")}, the date EUR-Lex gives this '
            f"consolidated text; in force from {escape(human_date(in_force))}.</p>"
        )
    ]
