"""One amendment event, wherever it appears: the facts, and on its own page the evidence.

The module that renders a single committed changelog entry, on the two surfaces the site gives
one: `render_event_summary` is the card on the act page's timeline, the facts and a link to the
evidence; `render_event` is the body of the event's own page, the same facts and then one block
per provision that moved. Both open through one shared header, so the two surfaces cannot state
one event differently, and the card keeps minting `id="{entry.key}"` on the act page because
that fragment was published in every feed entry before the event had a page of its own. It sits
beside `act.py` rather than inside it because the page and the card are two jobs: the page
decides what an act's history looks like as a whole (header, index, order), this module decides
how one event states what it did and what evidence it has.

The promises live here, each as a line of markup rather than a claim made elsewhere:

- **The facts are the diff's, not a model's.** The change type, the coordinate, the counts and
  both dates are read off the committed document. The sentences inside a change block are the
  only thing on the card a model wrote.
- **A sentence the gate quoted is marked as one**, in the changelog's own words, because a
  sentence a model composed and a sentence the gate lifted verbatim are different kinds of
  claim.
- **A disputed change is shown and says what disagreed.** Dropping it would make the card
  tidier and the counts wrong.
- **An event names the instrument that made it**, where a document names one: the number, the
  declared short name, the identifier, and on the event's own page the recorded official title.
- **An event no amending act is named for says so**, once, above its changes: a label and a
  sentence about the corpus's records for the window, never a doubt about the text below.
- **An event that touched nothing states the finding in words**: a sentence in place of the
  count line, and a note saying how much was compared, because a row of zeros reads like a
  counter that failed rather than a comparison that ran.
- **Nothing here is cut.** A summary panel that merely points at the artifact can justify
  capping a sentence; this is where a reader arrives instead, so the sentences run in full and
  the before/after text sits one `<details>` away, uncut and verbatim.
- **Every provision is a heading**, and a long page opens with a list of them built from the
  same anchors the blocks carry, so the list cannot point where no block is.
- **Every coordinate leads to its own history.** The heading's coordinate is a link to the
  provision's page, which is the same act's directory one level up from this event's, so a
  reader who arrived asking what this event did can ask what has ever been done to Annex XVII.

What a change block says in words, the pill and the shipped sentences with their citations,
moved to `pages/prose.py` on 2026-09-03 when naming the amending act pushed this module past
the size cap: one change's prose is a different job from one event's shape, and this module
imports the four functions it still calls.

Wording is imported rather than restated wherever the changelog says the same thing
(`output.markdown`): two renderings of one fact that describe it differently are how a caveat
gets softened in one of them. The disagreement marker is the one deliberate exception, written
by `site_.dispute` in a first-time reader's words. Both it and the changelog's marker are read
off the same signal verdicts, so they can differ in how plainly they speak and not in what they
claim. A changelog file is appended to and its committed entries keep their bytes, so a reworded
marker would leave one file speaking two ways forever; the site is rebuilt whole from those same
entries every time, so it can say it one way.
"""

from __future__ import annotations

from emendrix.graph.report import EmittedChange
from emendrix.output import ChangelogEntry
from emendrix.output.markdown import applies_text
from emendrix.site_.amending import AmendingAct, amending_lines
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, UNATTRIBUTED_NOTE, unattributed
from emendrix.site_.clocks import event_date
from emendrix.site_.dispute import dispute_note
from emendrix.site_.markup import Html, count, escape
from emendrix.site_.pages.prose import pill, prose
from emendrix.site_.pages.texts import RenderedText
from emendrix.site_.untouched import UNTOUCHED_SENTENCE, untouched, untouched_note
from emendrix.site_.urls import location_slug

__all__ = ["INDEX_ABOVE", "render_event", "render_event_summary"]

_THREE_SOURCES = (
    "Emendrix checks every change against three independent sources. Where they disagree it "
    "says so rather than picking a winner."
)
"""Said once above an event's first disagreement, and only on a page that has one.

It lives here rather than on the act page because the disagreement notes it primes render
here: since the evidence moved to the event's own page, a reader meets the sentence where the
first "Sources disagree" marker actually is, and a page whose changes all agree does not get
it, since an explanation of something not present reads as a warning about it.
"""

_SUMMARY_LINK = "Every change in this event, with the text before and after →"
"""The card's one link. The words promise exactly what the event page holds and no more."""

INDEX_ABOVE = 6
"""How many changes an event needs before its page opens with a list of them.

Below six the headings are on one screen and a list of them is a second copy of what the
reader can already see; the MDR postponement in the golden has nine, the AI Act's Digital
Omnibus event 45. Zero is under the line too, so an untouched event never opens with an
empty list.
"""


def _change_block(
    emitted: EmittedChange, entry: ChangelogEntry, anchor: str, text: RenderedText
) -> list[Html]:
    """One change: what it is, what is disputed about it, what was said, and the text itself.

    The block opens with a heading because the provision is the unit a reader and a crawler
    both look for: a passage is ranked, and a screen reader jumps, under `Art. 6` and its
    title. The heading holds the pill, the coordinate and the title, each its own element so
    the stylesheet sets the spacing; the applies line is a fact about the change rather than
    part of its name, so it is a paragraph of its own. The `id` stays on the wrapping `div`,
    which is what the anchors were minted for and what `.chg:target` highlights.

    The coordinate is a link to that provision's own page, a sibling of this event's page under
    the act, so `../` climbs to the act's directory and the slug names the provision. It keeps
    the weight it had as a span, because the coordinate is still the heading of the block and
    not an invitation to leave it.

    `text` is the evidence, rendered once for the whole entry by `pages.texts` and handed in:
    the provision page shows the same block, and a diff computed twice is the one cost the
    split of these pages could have introduced.
    """
    change = emitted.change
    title = (
        Html(f' <span class="ttl">{escape(change.heading)}</span>') if change.heading else Html("")
    )
    lines = [
        Html(f'<div class="chg" id="{escape(anchor)}">'),
        Html(
            f"<h3>{pill(change.change_type, disputed=change.disputed)} "
            f'<a class="loc" href="../{escape(location_slug(change.location.canonical))}/">'
            f"{escape(change.location.human)}</a>{title}</h3>"
        ),
        Html(f'<p class="applies">applies from {escape(applies_text(change.applies_from))}</p>'),
    ]
    if change.disputed:
        note = dispute_note(change.signals)
        lines.append(
            Html(
                f'<p class="disputed"><strong>{escape(note.lead)}</strong> — '
                f"{escape(note.detail)}</p>"
            )
        )
    lines.extend(prose(emitted, entry))
    lines.extend(
        (
            Html("<details><summary>text before / after</summary>"),
            text.html,
            Html("</details>"),
            Html("</div>"),
        )
    )
    return lines


def _facts(entry: ChangelogEntry) -> list[Html]:
    """The dates and the counts, all of them read off the document, none of them recomputed.

    An event that touched nothing states the finding as a sentence instead of the count line:
    "0 provisions touched" with three more zeros and a gate clause reads like a counter that
    failed, where the sentence says what the comparison found.

    The dates line carries what the heading above it did not. The heading names one clock and
    one date, so repeating that clause here would print the same fact twice on one screen and
    invite a reader to look for the difference between them. Nothing is dropped: an event with
    no in-force date says so, an event carrying several lists them all, and the clock the
    heading did not name is always here.
    """
    counts = entry.counts
    headed = event_date(entry)
    rest = []
    if not entry.in_force:
        rest.append("in force not stated")
    elif len(entry.in_force) > 1:
        rest.append("in force " + ", ".join(value.isoformat() for value in entry.in_force))
    if headed.in_force:
        rest.append(f"detected {entry.detected_on.isoformat()}")
    dates = Html(f'<p class="facts">{escape(" · ".join(rest))}</p>')
    if untouched(entry):
        return [dates, Html(f'<p class="facts">{escape(UNTOUCHED_SENTENCE)}</p>')]
    gate = (
        "the explain stage did not run for this event, so it carries the structural facts only"
        if entry.diff_only
        else f"{count(counts.quoted, 'sentence')} quoted verbatim by the gate, "
        f"{count(counts.unexplained, 'change')} shipped without an explanation"
    )
    return [
        dates,
        Html(
            f'<p class="facts">{escape(count(counts.touched, "provision"))} touched — '
            f"{counts.substantive} substantive, {counts.date_only} date-only, "
            f"<strong>{counts.disputed} disputed</strong> · {escape(gate)}</p>"
        ),
    ]


def _event_header(
    entry: ChangelogEntry, acts: tuple[AmendingAct, ...], *, full: bool
) -> list[Html]:
    """The article's opening, shared by the card and the event page: id, date, versions, facts.

    The `id` is the fragment every feed entry's `<id>` was minted from, so both surfaces must
    keep answering to it forever. The heading is the date, because a reader arriving at a
    timeline is asking when; it names its clock through the one helper every dated line on the
    site reads, so a detection date can never be set as an in-force date. The version pair is
    what the event *is* and sits directly below in the mono face, an identifier to check against
    EUR-Lex rather than a name to scan a list by. Then the instrument that made it, where one is
    named, because that is what a reader knows the event by; `full` is the event's own page
    rather than the card, and is what lets the official titles through. The facts line carries
    both clocks, so the record of when this happened is whole whichever the heading named.
    """
    versions = f"<code>{escape(str(entry.from_version))} → {escape(str(entry.to_version))}</code>"
    # The bare pill, no colour modifier: the label is a fact about the corpus's records, and
    # the palette spends colour on diffs, disputes and links only (`style/tokens.py`).
    unnamed = unattributed(entry)
    marker = f' <span class="pill">{escape(UNATTRIBUTED_LABEL)}</span>' if unnamed else ""
    lines = [
        Html(f'<article class="event" id="{escape(entry.key)}">'),
        Html(f"<h2>{escape(event_date(entry).words)}{marker}</h2>"),
        Html(f'<p class="ident">{versions}</p>'),
        *amending_lines(acts, full=full),
        *_facts(entry),
    ]
    if unnamed:
        lines.append(Html(f'<p class="small muted">{escape(UNATTRIBUTED_NOTE)}</p>'))
    if untouched(entry):
        lines.append(Html(f'<p class="small muted">{escape(untouched_note(entry))}</p>'))
    return lines


def render_event_summary(
    entry: ChangelogEntry,
    href: str,
    acts: tuple[AmendingAct, ...] = (),
    extra: tuple[Html, ...] = (),
) -> list[Html]:
    """One event as a timeline card: the facts, and where the evidence is.

    `href` is the event's own page, already climbed to the site root and back down by the
    caller, the convention every cross-page link on the site follows. No verbatim text and no
    per-change block reaches the card: the act page stays a timeline a phone can hold, and the
    evidence sits one link away instead of one fold away.

    `extra` is what a page has to add about this event that is true only on that page, closed
    inside the same article so it is read as part of the event rather than after it. The
    amending instrument's page is the one caller: on it, an event of a consolidation that
    folded several instruments carries only the coordinates that name the instrument the page
    is about, which is a fact about the pairing and not about the event.
    """
    return [
        *_event_header(entry, acts, full=False),
        Html(f'<p><a href="{escape(href)}">{escape(_SUMMARY_LINK)}</a></p>'),
        *extra,
        Html("</article>"),
    ]


def _touched(entry: ChangelogEntry, anchors: tuple[str, ...]) -> list[Html]:
    """The in-page index: one link per change block, in the order the page carries them.

    A table of contents for the page below rather than a sorted list of coordinates, so a
    coordinate touched twice in one event appears twice, once per block, and each link lands
    on its own anchor. The pill is the same call the heading makes, so the two can never
    disagree about a change's kind.
    """
    lines = [Html('<nav class="touched" aria-label="Provisions in this event">'), Html("<ol>")]
    for emitted, anchor in zip(entry.changes, anchors, strict=True):
        change = emitted.change
        lines.append(
            Html(
                f'<li><a href="#{escape(anchor)}">{escape(change.location.human)}</a> '
                f"{pill(change.change_type, disputed=change.disputed)}</li>"
            )
        )
    lines.extend((Html("</ol>"), Html("</nav>")))
    return lines


def render_event(
    entry: ChangelogEntry,
    anchors: tuple[str, ...],
    texts: tuple[RenderedText, ...],
    acts: tuple[AmendingAct, ...] = (),
) -> list[Html]:
    """One event's full body. `anchors` is one fragment per change, in the entry's own order.

    The anchors are computed once for the whole page and handed down, so the index over the
    changes and the blocks themselves point at the same fragments by construction rather than by
    both sides running the same counter; `acts`, the instruments the entry names, and `texts`,
    the evidence blocks, arrive resolved for the same reason. `texts` is positional too, one
    block per change, and is built once per entry however many pages show one of its changes.
    """
    lines = _event_header(entry, acts, full=True)
    if any(emitted.change.disputed for emitted in entry.changes):
        lines.append(Html(f'<p class="small muted">{escape(_THREE_SOURCES)}</p>'))
    if len(entry.changes) >= INDEX_ABOVE:
        lines.extend(_touched(entry, anchors))
    for emitted, anchor, text in zip(entry.changes, anchors, texts, strict=True):
        lines.extend(_change_block(emitted, entry, anchor, text))
    lines.extend(
        (
            Html(
                f'<p class="small muted">The full entry, with the citation mapping '
                f"<code>v1</code> = <code>{escape(str(entry.from_version))}</code>, "
                f"<code>v2</code> = <code>{escape(str(entry.to_version))}</code>, is committed "
                f"at <code>{escape(entry.act_dir)}/CHANGELOG.md</code>.</p>"
            ),
            Html("</article>"),
        )
    )
    return lines
