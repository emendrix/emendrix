"""One amending instrument, whole: every watched act it moved and what it did to each.

The reader's third object, after the act and the event. Somebody who has read that Regulation
(EU) 2026/1744 amended the AI Act wants to know what else it amended, and until this page
existed the site could only answer that by being read act by act. Nothing here is new
knowledge: every act, every event and every coordinate on the page is on an event page too,
gathered under the instrument instead of under the act.

This is the one page whose job is to *be* the instrument, so it prints the instrument's names
in full: the short name as the heading, the official number under it where the heading is a
declared label, and the recorded official title verbatim and uncut, which is the same reason
`pages/act.py` prints an act's own title in full on the act's own page and cuts it in a list.

Each watched act gets a section headed by its name, linking its page, and inside it the
card of every version this amending act made there, newest first, one heading level below the
act's. Under each card sit the coordinates that version's changes attribute to **this** amending
act, and only those: one consolidation can fold several, and listing a version's whole change
set under each of them would credit every one with all of the work. The card is the shared one
the act page uses, so a version cannot be stated one way here and another way there, except
that it does not say "Made by" the act whose page this is. It still names any other amending
act the same version folded in.
"""

from __future__ import annotations

from emendrix.output import ChangelogEntry
from emendrix.site_.amending import AmendingAct, amenders
from emendrix.site_.chrome import page
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.identity import masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.instruments import Amended
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.outbound import external
from emendrix.site_.pages.version_card import version_card
from emendrix.site_.seo import amendment_json_ld
from emendrix.site_.tags import LIST_HELP_WORDS, tags_help
from emendrix.site_.titles import SUFFIX
from emendrix.site_.trail import amending_trail
from emendrix.site_.urls import act_href, amendment_href, entry_anchors, event_href, up

__all__ = ["render_amendment_page"]

_DEPTH = 2
"""`amendments/<slug>/index.html`: every internal link on this page climbs two directories.

A literal for the reason `pages/act.py` carries one: the page's own path needs a key to exist,
and it is the same number as `depth_of(amendment_href(key))` for any key, which
`test_urls.py` pins.
"""

_ATTRIBUTED = "Changes this amending act made:"
"""What the coordinate list under a card is, said before it rather than left to be inferred."""


def _grouped(amended: Amended) -> list[tuple[ActSite, list[ChangelogEntry]]]:
    """The `(act, event)` pairs as one entry list per act, both orders left exactly as given."""
    order: list[ActSite] = []
    events: dict[str, list[ChangelogEntry]] = {}
    for act, entry in amended:
        if act.act.key not in events:
            order.append(act)
            events[act.act.key] = []
        events[act.act.key].append(entry)
    return [(act, events[act.act.key]) for act in order]


def _header(instrument: AmendingAct, acts: int, events: int) -> list[Html]:
    """The instrument's names, its identifier, what it did, and where the official text is."""
    lines = masthead(
        "amending",
        amending_trail(instrument),
        _DEPTH,
        Html("Amending act"),
        escape(instrument.short),
    )
    if instrument.number and instrument.number != instrument.short:
        lines.append(Html(f'<p class="official">{escape(instrument.number)}</p>'))
    if instrument.title:
        lines.append(Html(f'<p class="official">{escape(instrument.title)}</p>'))
    facts = [
        Html(f"<code>{escape(instrument.key)}</code>"),
        escape(f"Changed {count(acts, 'watched act')} in {count(events, 'version')}"),
    ]
    lines.append(Html(f'<p class="facts">{join(facts, " · ")}</p>'))
    if instrument.eurlex_url:
        lines.append(Html(f'<p class="links">{external(instrument.eurlex_url, "on EUR-Lex")}</p>'))
    lines.append(tags_help(up(_DEPTH), LIST_HELP_WORDS))
    return lines


def _provisions(instrument: AmendingAct, act: ActSite, entry: ChangelogEntry) -> tuple[Html, ...]:
    """The coordinates of this event that name this instrument, each linked to its own block.

    The anchors come from `entry_anchors` over the whole entry, in the entry's own order, so a
    coordinate the event touched twice keeps the suffix its block carries; the filter then
    drops the positions that name another instrument. Counting only the filtered changes would
    mint the second occurrence's anchor for the first one.
    """
    anchors = entry_anchors(
        entry.key, [emitted.change.location.canonical for emitted in entry.changes]
    )
    href = up(_DEPTH) + event_href(act.slug, entry.key)
    links = [
        Html(
            f'<a href="{escape(href)}#{escape(anchor)}">{escape(emitted.change.location.human)}</a>'
        )
        for emitted, anchor in zip(entry.changes, anchors, strict=True)
        if any(named.key == instrument.key for named in emitted.change.amending_acts)
    ]
    if not links:
        return ()
    return (Html(f'<p class="small">{escape(_ATTRIBUTED)} {join(links, ", ")}</p>'),)


def render_amendment_page(site: SiteInputs, instrument: AmendingAct, amended: Amended) -> Html:
    """One instrument's complete page. Deterministic: same inputs, same bytes, no clock."""
    grouped = _grouped(amended)
    acts = tuple(act for act, _ in grouped)
    lines = _header(instrument, len(acts), len(amended))
    for act, entries in grouped:
        lines.extend(
            (
                Html('<section class="amended">'),
                Html(
                    f'<h2><a href="{escape(up(_DEPTH) + act_href(act.slug))}">'
                    f"{escape(act.headline)}</a></h2>"
                ),
                Html('<div class="timeline">'),
            )
        )
        for entry in entries:
            lines.extend(
                version_card(
                    entry,
                    up(_DEPTH) + event_href(act.slug, entry.key),
                    amenders(site.amending, entry),
                    level=3,
                    root=up(_DEPTH),
                    coded=site.version_dates.get((entry.act, entry.to_version)),
                    extra=_provisions(instrument, act, entry),
                    omit=instrument.key,
                )
            )
        lines.extend((Html("</div>"), Html("</section>")))
    named = instrument.short
    numbered = f" ({instrument.number})" if instrument.number and instrument.number != named else ""
    title = f"{named}{numbered}: every watched act it amended{SUFFIX}"
    description = (
        f"{named}{', ' + instrument.number if numbered else ''} amended "
        f"{count(len(acts), 'watched act')} in {count(len(amended), 'version')}. Each version "
        f"lists every changed provision with its text before and after."
    )
    return page(
        title=title,
        description=description,
        body=join(lines, "\n"),
        path=amendment_href(instrument.key),
        chrome=site.chrome,
        section="amendments/",
        # The site-wide feed alone, whatever the instrument moved: one feed per amended act
        # would advertise sixteen of them on the page of an instrument that touched sixteen,
        # and a reader who wants one act's feed is one click from the act's own page.
        feeds=((feed_path(None), feed_title(None)),),
        structured=(
            amendment_json_ld(site, instrument, acts, title=title, description=description)
            if site.site_url
            else None
        ),
    )
