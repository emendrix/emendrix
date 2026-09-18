"""What a version is, said on its own page between its heading and its first change.

A version page used to open with the same card the act's timeline prints, under its parent's
title, so a reader who landed on it could not tell the page from an item in a list. This module
is the page's subject instead: who made the version, its official title as a readable lede,
where it sits in the act's sequence, its dates in words that define themselves, the tally, the
identifiers once, and the way to the versions either side. The card a list prints is
`pages/version_card.py`; the two share the helpers that read the document's facts and never
their markup.

The facts are the document's. Every count is read off `entry.counts`, the dates off the two
clocks, the position off the act's own newest-first list, and nothing is recomputed. The heading
above names one clock and one date, so the dates line never repeats that clause: it states the
clock the heading did not name, every in-force date where the corpus records several, and that
an in-force date is not stated where none is.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct, made_by, official_titles
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, UNATTRIBUTED_NOTE, unattributed
from emendrix.site_.clocks import event_date, time_html
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.instruments import amended_by
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.tags import tag, tally
from emendrix.site_.untouched import all_textless, textless_note, untouched, untouched_note
from emendrix.site_.urls import act_href, amendment_href, up

__all__ = ["pager", "status_sentence", "version_masthead"]

_DEPTH = 3
"""`acts/<slug>/<key>/index.html`, the version page this masthead is printed on."""

_PAGER = "Versions of this act"
"""The pager's landmark name. The copy at the top adds `(top)`, so the two landmarks a screen
reader lists are told apart by name."""


def status_sentence(act: ActSite, entry: ChangelogEntry) -> str:
    """`Version 5 of 5 recorded for FIC Regulation, the newest.`, or `''` off the act's list.

    Counted from the act's own history, which runs newest first, so the oldest recorded version
    is number one. The words say "recorded" because the history holds what emendrix recorded,
    which need not be every version the corpus ever published.
    """
    keys = [other.key for other in act.entries]
    if entry.key not in keys:
        return ""
    total = len(keys)
    number = total - keys.index(entry.key)
    if total == 1:
        where = ", the only one."
    elif number == total:
        where = ", the newest."
    elif number == 1:
        where = ", the oldest recorded."
    else:
        where = "."
    return f"Version {number} of {total} recorded for {act.label}{where}"


def _dates(entry: ChangelogEntry) -> Html | None:
    """The clocks the heading did not name, in sentences that say what each date is."""
    sentences: list[str] = []
    if not entry.in_force:
        sentences.append("In force date not stated.")
    elif len(entry.in_force) > 1:
        sentences.append(f"In force {', '.join(time_html(on) for on in entry.in_force)}.")
    if event_date(entry).in_force:
        sentences.append(
            f"First seen by emendrix on {time_html(entry.detected_on)}, when it first read this "
            "version; that is not a legal date."
        )
    return Html(f'<p class="dates">{" ".join(sentences)}</p>') if sentences else None


def _instruments(site: SiteInputs, act: ActSite, acts: tuple[AmendingAct, ...]) -> list[Html]:
    """Each amending act's own page, and the other watched acts it also changed.

    One line per amending act: "also changed" is a different set for each of them, and the act
    this page belongs to is never in it, being the page the reader is already on.
    """
    found = amended_by(site)
    lines: list[Html] = []
    for instrument in acts:
        parts = [
            Html(
                f'<a href="{escape(up(_DEPTH) + amendment_href(instrument.key))}">'
                f"Everything {escape(instrument.short)} changed</a>"
            )
        ]
        others = {
            other.act.key: other
            for other, _ in found.get(instrument.key, ())
            if other.act != act.act
        }
        if others:
            named = [
                Html(
                    f'<a href="{escape(up(_DEPTH) + act_href(other.slug))}">'
                    f"{escape(other.label)}</a>"
                )
                for other in others.values()
            ]
            parts.append(Html(f"also changed {join(named, ', ')}"))
        lines.append(Html(f'<p class="instruments">{join(parts, " · ")}</p>'))
    return lines


def pager(act: ActSite, entry: ChangelogEntry, *, top: bool) -> list[Html]:
    """The versions either side of this one, each named by its direction and dated under it.

    The act's history runs newest first, so the previous version is the older one and carries
    `rel="prev"`, and the next is the newer. The words say the direction and the date under
    each says where it lands. It is printed twice, quietly under the masthead and again at the
    foot, and each copy is a landmark with its own name.
    """
    keys = [other.key for other in act.entries]
    if entry.key not in keys:
        return []
    at = keys.index(entry.key)
    older = act.entries[at + 1] if at + 1 < len(act.entries) else None
    newer = act.entries[at - 1] if at > 0 else None
    links: list[Html] = []
    for rel, other, words in (
        ("prev", older, "← Previous version"),
        ("next", newer, "Next version →"),
    ):
        if other is None:
            continue
        dated = event_date(other)
        links.append(
            Html(
                f'<a rel="{rel}" href="../{escape(other.key)}/"><span>{escape(words)}</span> '
                f'<span class="small">{dated.clock} {time_html(dated.on)}</span></a>'
            )
        )
    if not links:
        return []
    label = f"{_PAGER} (top)" if top else _PAGER
    kind = "pager" if top else "pager pager--foot"
    return [Html(f'<nav class="{kind}" aria-label="{escape(label)}">'), *links, Html("</nav>")]


def version_masthead(
    site: SiteInputs, act: ActSite, entry: ChangelogEntry, acts: tuple[AmendingAct, ...]
) -> list[Html]:
    """Everything between the version's heading and its first change, as one block.

    It carries the version's key as its `id`, the fragment the version page has always answered
    to. The facts sit in two groups: what the version is and did on the left, and how to check
    it and what else its amending acts did on the right, which the sheet sets side by side on a
    wide screen and one under the other on a phone.
    """
    lines = [Html(f'<div class="version-masthead" id="{escape(entry.key)}">')]
    if acts:
        lines.extend((*made_by(acts, up(_DEPTH), verb="Made by"), *official_titles(acts)))
    elif unattributed(entry):
        lines.extend(
            (
                Html(f'<p class="amending">{tag("unattributed", UNATTRIBUTED_LABEL)}</p>'),
                Html(f'<p class="small muted">{escape(UNATTRIBUTED_NOTE)}</p>'),
            )
        )
    lines.extend((Html('<div class="summary">'), Html("<div>")))
    status = status_sentence(act, entry)
    if status:
        lines.append(Html(f'<p class="status">{escape(status)}</p>'))
    dates = _dates(entry)
    if dates is not None:
        lines.append(dates)
    lines.extend(tally(entry, shapes=True, root=up(_DEPTH)))
    if untouched(entry):
        lines.append(Html(f'<p class="small muted">{escape(untouched_note(entry))}</p>'))
    elif all_textless(entry):
        lines.append(Html(f'<p class="small muted">{escape(textless_note(entry))}</p>'))
    lines.extend(
        (
            Html("</div>"),
            Html("<div>"),
            Html(
                f'<p class="ident">Consolidated versions <code class="id">'
                f'{escape(str(entry.from_version))}</code> → <code class="id">'
                f"{escape(str(entry.to_version))}</code>. v1 is the previous version, v2 this "
                "one.</p>"
            ),
            *_instruments(site, act, acts),
            Html("</div>"),
            Html("</div>"),
            *pager(act, entry, top=True),
            Html("</div>"),
        )
    )
    return lines
