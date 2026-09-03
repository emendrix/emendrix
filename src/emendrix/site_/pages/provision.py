"""One provision, whole: every event that touched it, newest first, with what each one did.

The reader's fourth object, and the one the pipeline's own shape hides. An event page answers
"what did this consolidation change?", which is the question the loop is built around; a reader
arrives instead with "what has Annex XVII done over time?", and until this page existed the
site could only answer that by reading every event of the act and looking for one coordinate in
each. The history is `site_.history`'s inversion of the same committed changes; nothing on this
page is knowledge the event pages do not already hold.

**The newest step's verbatim text is here in full, and every older step links to the block that
holds its own.** That is the whole shape of the page and it is a weight decision, measured
rather than assumed: one committed change carries 4.1 million characters of before-and-after
text, and one coordinate is touched by as many as 47 events (counted 2026-09-03 over the 369
committed events). A page that repeated the evidence per step would multiply the largest page
on the site by its own history. A reader who arrived from a search for the provision wants the
current text, which is the newest step's, so that one is open; the rest are one link away, on
the event page that has always held them, at the anchor that page already publishes.

The step ids **are** those anchors. Nothing new is minted, so a link that worked on the event
page works here, a coordinate an event touched twice is two steps with two distinct ids, and
the pages can be read against each other without either side running its own counter.

The provision's own title is the newest step's `heading`, printed verbatim under the coordinate
where the consolidated text carries one that says more than the coordinate already does. A
heading can change with the text, and the earlier ones are visible in the diffs on the event
pages; showing one title here and saying which step it belongs to is the honest reading, where a
list of every title a provision has ever had would be a second history nobody asked for.
"""

from __future__ import annotations

from emendrix.output.markdown import applies_text
from emendrix.site_.amending import amenders, amending_links
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, unattributed
from emendrix.site_.chrome import page
from emendrix.site_.clocks import event_date
from emendrix.site_.dispute import dispute_note
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.history import ProvisionHistory, ProvisionStep
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.magnitude import magnitude_html
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.pages.prose import permalink, pill, prose
from emendrix.site_.pages.texts import RenderedText
from emendrix.site_.seo import provision_json_ld
from emendrix.site_.titles import SUFFIX
from emendrix.site_.urls import provision_href, up

__all__ = ["render_provision_page"]

_DEPTH = 3
"""`acts/<slug>/<provision>/index.html`: every internal link on this page climbs three levels.

A literal for the reason `pages/event.py` carries one: the page's own path needs an act and a
location to exist, and it is the same number as `depth_of(provision_href(slug, canonical))` for
any pair, which `test_urls.py` pins.
"""

_OLDER = "text before / after, on the event page →"
"""The older step's one link. It promises the block, not a page, because that is where it lands."""


def _header(act: ActSite, history: ProvisionHistory) -> list[Html]:
    """The coordinate, the act it belongs to, its title, and how much history there is.

    The H1 is the coordinate in its human form, `Annex XVII` rather than `AN XVII`, because
    that is what a reader types and what the act's own text calls it; the canonical string is
    in the address. The act is named on the facts line rather than in the heading, since the
    reader followed a link from that act and the page below is entirely about one of its parts.

    The provision's own title is printed only when it says something the H1 does not, the rule
    `pages/act.py` prints an act's official title under: the Formex title of an annex is often
    the words `ANNEX IX` and printing that under `Annex IX` reads as a rendering accident. The
    comparison folds case and whitespace and changes nothing: the title that is printed is the
    stored one, character for character.
    """
    events = len({step.entry.key for step in history.steps})
    facts = [
        escape(act.headline),
        Html(f"<code>{escape(act.act.key)}</code>"),
        Html('<a href="../">every event for this act</a>'),
    ]
    if act.eurlex_url:
        facts.append(Html(f'<a class="nowrap" href="{escape(act.eurlex_url)}">on EUR-Lex</a>'))
    lines = [
        Html(f"<h1>{escape(history.location.human)}</h1>"),
        Html(f'<p class="facts">{join(facts, " · ")}</p>'),
    ]
    heading = history.steps[0].change.heading
    if heading and heading.casefold().split() != history.location.human.casefold().split():
        lines.append(Html(f'<p class="official">{escape(heading)}</p>'))
    lines.append(
        Html(
            f'<p class="facts">{escape(count(len(history.steps), "change"))} recorded across '
            f"{escape(count(events, 'event'))}, newest first.</p>"
        )
    )
    return lines


def _step(site: SiteInputs, step: ProvisionStep, text: RenderedText | None) -> list[Html]:
    """One event's change to this provision: when, by what, what it says, and the evidence.

    The heading is the date with its clock and the change type, the two facts that place a step
    in a history; the instrument follows, linked to its own page, because the reader scanning a
    provision's history is asking which instrument did each thing. An event that names none says
    so with the label the rest of the site uses for that class, in place of the instrument
    line, rather than with the sentence behind it: on a page of many steps that sentence would
    be repeated per step, and it is one link away on each event's own page.

    `text` is the evidence for the newest step and `None` for every other one. The newest opens
    its `<details>`, because a reader arriving from a search for this provision wants the
    current text visible; an older step links the block on the event page that holds its own.

    The heading carries how much moved only where the evidence is on this page, for the same
    reason: the count is measured on a rendered comparison, and an older step's comparison is
    rendered on the event page, which is where that step's count is printed.

    The heading closes with the same permalink a change block carries on its event page, and
    on the same anchor, so one change can be handed to somebody from either view of it.
    """
    entry = step.entry
    change = step.change
    magnitude = magnitude_html(text) if text is not None else Html("")
    lines = [
        Html(f'<article class="chg step" id="{escape(step.anchor)}">'),
        Html(
            f"<h2>{escape(event_date(entry).words)} "
            f"{pill(change.change_type, disputed=change.disputed)}"
            f"{magnitude}{permalink(step.anchor)}</h2>"
        ),
    ]
    acts = amenders(site.amending, entry)
    lines.extend(amending_links(acts, up(_DEPTH)))
    if not acts and unattributed(entry):
        lines.append(Html(f'<p class="amending">{escape(UNATTRIBUTED_LABEL)}</p>'))
    lines.append(
        Html(f'<p class="applies">applies from {escape(applies_text(change.applies_from))}</p>')
    )
    if change.disputed:
        note = dispute_note(change.signals)
        lines.append(
            Html(
                f'<p class="disputed"><strong>{escape(note.lead)}</strong> — '
                f"{escape(note.detail)}</p>"
            )
        )
    lines.extend(prose(entry.changes[step.index], entry))
    if text is None:
        lines.append(
            Html(
                f'<p class="small"><a href="../{escape(entry.key)}/#{escape(step.anchor)}">'
                f"{escape(_OLDER)}</a></p>"
            )
        )
    else:
        lines.extend(
            (
                Html("<details open><summary>text before / after</summary>"),
                text.html,
                Html("</details>"),
            )
        )
    lines.append(Html("</article>"))
    return lines


def render_provision_page(
    site: SiteInputs, act: ActSite, history: ProvisionHistory, texts: tuple[RenderedText, ...]
) -> Html:
    """One provision's complete page. Deterministic: same inputs, same bytes, no clock.

    `texts` is the evidence blocks of the newest step's own entry, the tuple the builder
    computed for that event's page, and the newest step's position in it says which one to
    show. No other step's block is rendered here, which is what keeps this page's weight a
    function of one change rather than of the whole history.
    """
    newest = history.steps[0]
    steps: list[Html] = []
    for position, step in enumerate(history.steps):
        steps.extend(_step(site, step, texts[newest.index] if position == 0 else None))
    body = join((*_header(act, history), *steps), "\n")
    named = history.location.human
    events = len({step.entry.key for step in history.steps})
    title = f"{act.label} {named}: every consolidated version and what changed{SUFFIX}"
    description = (
        f"{named} of {act.headline}: {count(len(history.steps), 'change')} across "
        f"{count(events, 'event')}, newest first, with the verbatim text of the newest change "
        "and a link to every earlier one."
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=provision_href(act.slug, history.location.canonical),
        chrome=site.chrome,
        # The act's own feed leads, for the reason the act page gives: a reader subscribing
        # from one of its provisions is asking for this act. There is no feed of one
        # provision, and nothing here pretends there is.
        feeds=((feed_path(act), feed_title(act)), (feed_path(None), feed_title(None))),
        structured=(
            provision_json_ld(site, act, history.location, title=title, description=description)
            if site.site_url
            else None
        ),
    )
