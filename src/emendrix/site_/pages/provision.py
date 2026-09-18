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

The provision's own title is the newest step's `heading`, printed verbatim beside the
coordinate in the page's heading where the consolidated text carries one that says more than
the coordinate already does. A heading can change with the text, and the earlier ones are
visible in the diffs on the event pages; showing one title here and saying which step it belongs
to is the honest reading, where a list of every title a provision has ever had would be a second
history nobody asked for.
"""

from __future__ import annotations

from emendrix.site_.amending import amenders, made_by
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, unattributed
from emendrix.site_.chrome import page
from emendrix.site_.clocks import version_heading
from emendrix.site_.diffview import summary_words
from emendrix.site_.dispute import SHAPE_CLASS, dispute_shape
from emendrix.site_.feeds import feed_path, feed_title
from emendrix.site_.history import ProvisionHistory, ProvisionStep
from emendrix.site_.identity import masthead
from emendrix.site_.inputs import ActSite, SiteInputs
from emendrix.site_.magnitude import magnitude_html
from emendrix.site_.markup import Html, count, escape, join
from emendrix.site_.outbound import external
from emendrix.site_.pages.prose import applies_line, dates_line, differ_note, permalink, prose
from emendrix.site_.pages.texts import RenderedText
from emendrix.site_.seo import provision_json_ld
from emendrix.site_.tags import SPOKEN_COMMA, kind_tag
from emendrix.site_.titles import SUFFIX
from emendrix.site_.trail import provision_trail
from emendrix.site_.urls import provision_href, up

__all__ = ["render_provision_page"]

_DEPTH = 3
"""`acts/<slug>/<provision>/index.html`: every internal link on this page climbs three levels.

A literal for the reason `pages/event.py` carries one: the page's own path needs an act and a
location to exist, and it is the same number as `depth_of(provision_href(slug, canonical))` for
any pair, which `test_urls.py` pins.
"""

_OLDER = "Text from EUR-Lex, on this version's page →"
"""The older step's one link. It promises the block, not a page, because that is where it lands."""


def _header(act: ActSite, history: ProvisionHistory) -> list[Html]:
    """The coordinate and its subject, the act it belongs to, and how much history there is.

    The H1 is the coordinate in its human form, `Annex XVII` rather than `AN XVII`, because
    that is what a reader types and what the act's own text calls it; the canonical string is
    in the address. The caption names the page a provision history and links the act, since
    the page below is entirely about one of that act's parts.

    The provision's own title joins the H1, `Annex II · Substances or products causing
    allergies or intolerances`, only when it says something the coordinate does not, the rule
    `pages/act.py` prints an act's official title under: the Formex title of an annex is often
    the words `ANNEX IX`, and `Annex IX · ANNEX IX` reads as a rendering accident. The
    comparison folds case and whitespace and changes nothing: the title that is printed is the
    stored one, character for character.
    """
    events = len({step.entry.key for step in history.steps})
    facts = [
        escape(act.headline),
        Html(f"<code>{escape(act.act.key)}</code>"),
        Html('<a href="../">every version of this act</a>'),
    ]
    if act.eurlex_url:
        facts.append(external(act.eurlex_url, "on EUR-Lex"))
    named = history.location.human
    heading = history.steps[0].change.heading
    subject = (
        f"{named} · {heading}"
        if heading and heading.casefold().split() != named.casefold().split()
        else named
    )
    caption = Html(f'Provision history · <a href="../">{escape(act.label)}</a>')
    trail = provision_trail(act, history.location)
    return [
        *masthead("provision", trail, _DEPTH, caption, escape(subject)),
        Html(f'<p class="facts">{join(facts, " · ")}</p>'),
        Html(
            f'<p class="facts">{escape(count(len(history.steps), "change"))} recorded across '
            f"{escape(count(events, 'version'))}, newest first.</p>"
        ),
    ]


def _step(site: SiteInputs, step: ProvisionStep, text: RenderedText | None) -> list[Html]:
    """One event's change to this provision: when, by what, what it says, and the evidence.

    The heading is the version, named by its date and clock and linked to its own page, then
    the change type as a tag; the instrument follows, linked to its own page, because the reader
    scanning a provision's history is asking which instrument did each thing. An event that
    names none says so with the label the rest of the site uses for that class, in place of the
    instrument line, rather than with the sentence behind it: on a page of many steps that
    sentence would be repeated per step, and it is one link away on each event's own page.

    `text` is the evidence for the newest step and `None` for every other one. The newest opens
    its `<details>`, because a reader arriving from a search for this provision wants the
    current text visible; an older step links the block on the event page that holds its own.

    The heading carries how much moved only where the evidence is on this page, for the same
    reason: the count is measured on a rendered comparison, and an older step's comparison is
    rendered on the event page, which is where that step's count is printed.

    Where the sources differ, the step carries the shape as a class and states it with the same
    tag and note a version page gives the same change, so the two pages grade it alike. The
    dates line sits under the applies line, in the order and for the reason a change block on
    the event page carries the two.

    The heading closes with the same permalink a change block carries on its event page, and
    on the same anchor, so one change can be handed to somebody from either view of it.
    """
    entry = step.entry
    change = step.change
    magnitude = Html(f" {magnitude_html(text)}") if text is not None else Html("")
    graded = f" {SHAPE_CLASS[dispute_shape(change.signals)]}" if change.disputed else ""
    lines = [
        Html(f'<article class="chg step{graded}" id="{escape(step.anchor)}">'),
        Html(
            f'<h2><a href="../{escape(entry.key)}/">{version_heading(entry)}</a>{SPOKEN_COMMA} '
            f"{kind_tag(change.change_type)}{magnitude}{permalink(step.anchor)}</h2>"
        ),
    ]
    acts = amenders(site.amending, entry)
    lines.extend(made_by(acts, up(_DEPTH), verb="Amended by"))
    if not acts and unattributed(entry):
        lines.append(Html(f'<p class="amending">{escape(UNATTRIBUTED_LABEL)}</p>'))
    lines.append(applies_line(change, up(_DEPTH)))
    dates = dates_line(change)
    if dates is not None:
        lines.append(dates)
    if change.disputed:
        lines.extend(differ_note(change.signals, up(_DEPTH)))
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
                Html(f"<details open><summary>{escape(summary_words(change))}</summary>"),
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
        f"{count(events, 'version')}, newest first, with the verbatim text of the newest change "
        "and a link to every earlier one."
    )
    return page(
        title=title,
        description=description,
        body=body,
        path=provision_href(act.slug, history.location.canonical),
        chrome=site.chrome,
        section="acts/",
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
