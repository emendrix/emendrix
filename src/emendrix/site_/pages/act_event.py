"""One version's changes, on the version's own page: the evidence the act page points at.

`render_event` is the body of a version's page below its masthead: one block per provision that
moved, the index over them on a long page, and where the committed entry lives. The version's
subject, its facts and its tally are `pages/version_masthead.py`, and the card a list prints is
`pages/version_card.py`; this module decides how a version states what it changed and what
evidence it has.

The promises live here, each as a line of markup rather than a claim made elsewhere:

- **The facts are the diff's, not a model's.** The change type, the coordinate, the counts and
  both dates are read off the committed document. The sentences inside a change block are the
  only thing on the card a model wrote.
- **A sentence the gate quoted is marked as one**, in the changelog's own words, because a
  sentence a model composed and a sentence the gate lifted verbatim are different kinds of
  claim.
- **A disputed change is shown, says what disagreed and says which shape the disagreement
  has**, in the lead of its note and in the weight of its badge. Dropping it would make the
  card tidier and the counts wrong; grading it changes what the page says about a disagreement
  and never whether one is recorded.
- **A change with no text to show is one line, and every one is still on the page.** They
  gather at the foot of the changes under a heading saying how many and what they are, each
  still a block with its own anchor, permalink and disagreement note, and each opens where it
  stands when a permalink names it. Nothing leaves the page or the counts for it.
- **Nothing here is cut.** A summary panel that merely points at the artifact can justify
  capping a sentence; this is where a reader arrives instead, so the sentences run in full and
  the before/after text sits one `<details>` away, uncut and verbatim.
- **Every provision is a heading**, and a long page opens with a list of them built from the
  same anchors the blocks carry, so the list cannot point where no block is.
- **Every change says how much of the provision moved**, in characters, measured on the very
  comparison the block below it renders. It is a size and never a judgement: the words for that
  are in `site_/magnitude.py`, which prints the count and the sentence saying what it is not.
- **Every coordinate leads to its own history.** The heading's coordinate is a link to the
  provision's page, which is the same act's directory one level up from this event's, so a
  reader who arrived asking what this event did can ask what has ever been done to Annex XVII.
- **Every change block is addressable from itself**, by the permalink at the end of its
  heading, and a page long enough to open with an index closes with the way back to the top.
- **The index is beside the changes where there is room for it.** A page listing its
  provisions puts the list in a column at the same width the act page's index becomes one, so
  a reader forty blocks down can still see the map; below that width it stays the wrapping row
  it has always been, which costs a few lines rather than a screen.

What a change block carries wherever it appears, the pill, the permalink, the sentences, the row
of their citations and the dates its text moved, lives in `pages/prose.py`, and the index a long
page opens with lives in `pages/event_index.py`. Each is a statement this module places rather
than composes. What is left is one version's changes: the block each sits in, and the order all
of them come in.

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
from emendrix.site_.dispute import (
    QUIET_NOTE,
    SHAPE_CLASS,
    dispute_note,
    dispute_shape,
    named_by,
    quiet_heading,
)
from emendrix.site_.magnitude import magnitude_html
from emendrix.site_.markup import Html, escape
from emendrix.site_.pages.event_index import INDEX_ABOVE, touched
from emendrix.site_.pages.prose import applies_line, dates_line, permalink, pill, prose
from emendrix.site_.pages.texts import RenderedText
from emendrix.site_.sources import repo_file
from emendrix.site_.urls import location_slug

__all__ = ["render_event"]

_WHAT_CHANGED = "What changed"
"""The heading the changes open under, between the version's masthead and its first block, so the
page reads as a version, then what changed, then each change."""

_BACK_TO_TOP = "Back to top ↑"
"""The foot of a page that opened with an index, aimed at the id the skip link already targets.

Only on such a page: below the index threshold the top of the page is still on the screen when
the last block ends, and a link back to what a reader can see is furniture rather than help.
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
    not an invitation to leave it. The permalink closes the heading and points at this block's
    own `id`, so a reader can hand one change to somebody without knowing the anchor scheme.

    The dates line follows the applies line where a date moved, and is absent where none did.
    The order is the argument: the applies line answers whether one of them governs the
    provision, and the dates below it are the ones the text stopped and started naming.

    The block carries the shape of its disagreement as a class, which is what grades its badge
    in the sheet, and a change with no text names its naming source in the heading: that
    heading is the whole of such a row until a permalink opens it.

    `text` is the evidence, rendered once for the whole entry by `pages.texts` and handed in:
    the provision page shows the same block, and a diff computed twice is the one cost the
    split of these pages could have introduced. It carries the size of the difference it shows,
    which the heading prints beside the pill: a punctuation fix and a rewritten paragraph are
    both `MODIFIED`, and the count is what tells them apart without opening either.
    """
    change = emitted.change
    title = (
        Html(f' <span class="ttl">{escape(change.heading)}</span>') if change.heading else Html("")
    )
    graded = f" {SHAPE_CLASS[dispute_shape(change.signals)]}" if change.disputed else ""
    named = (
        Html(f' <span class="by">named by {escape(named_by(change.signals))}</span>')
        if change.textless
        else Html("")
    )
    lines = [
        Html(f'<div class="chg{graded}" id="{escape(anchor)}">'),
        Html(
            f"<h3>{pill(change.change_type, disputed=change.disputed)} "
            f"{magnitude_html(text)} "
            f'<a class="loc" href="../{escape(location_slug(change.location.canonical))}/">'
            f"{escape(change.location.human)}</a>{title}{named}{permalink(anchor)}</h3>"
        ),
        applies_line(change),
    ]
    dates = dates_line(change)
    if dates is not None:
        lines.append(dates)
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


def _quiet(rows: list[Html], number: int) -> list[Html]:
    """The changes with no text to show, gathered under a heading that says what they are.

    They are the same blocks as any other change, in the same order and with the same anchors;
    the section adds the heading, the sentence saying how a row opens, and the class the sheet
    collapses each row to its own heading under. `number` counts the rows, which is also the
    count of provisions the heading states: the corroborator appends one such change per
    top-level unit and never for a unit the comparison already covered.
    """
    return [
        Html('<section class="quiet">'),
        Html(f"<h3>{escape(quiet_heading(number))}</h3>"),
        Html(f'<p class="small muted">{escape(QUIET_NOTE)}</p>'),
        *rows,
        Html("</section>"),
    ]


def render_event(
    entry: ChangelogEntry,
    anchors: tuple[str, ...],
    texts: tuple[RenderedText, ...],
    changelogs_url: str = "",
) -> list[Html]:
    """One event's full body. `anchors` is one fragment per change, in the entry's own order.

    The anchors are computed once for the whole page and handed down, so the index over the
    changes and the blocks themselves point at the same fragments by construction rather than by
    both sides running the same counter; `texts`, the evidence blocks, arrive resolved for the
    same reason. `texts` is positional too, one
    block per change, and is built once per entry however many pages show one of its changes.

    The changes with no text to show are moved to the foot of the list, which is the one place
    this page reorders anything. Anchors, permalinks and the index above them are untouched by
    the move: a link into one still lands on it and still opens it.

    `changelogs_url` is the changelog repository's public home, or `""` where a deployment
    publishes none, and it decides only whether the closing sentence's path is a link. Where
    that repository lives on the operator's machine is never printed either way; the path it
    does print is the stable one inside the repository.
    """
    lines = [Html(f'<h2 class="section">{escape(_WHAT_CHANGED)}</h2>')] if entry.changes else []
    shown: list[Html] = []
    hushed: list[Html] = []
    quiet = 0
    for emitted, anchor, text in zip(entry.changes, anchors, texts, strict=True):
        block = _change_block(emitted, entry, anchor, text)
        if emitted.change.textless:
            quiet += 1
            hushed.extend(block)
        else:
            shown.extend(block)
    blocks = shown + (_quiet(hushed, quiet) if quiet else [])
    if len(entry.changes) >= INDEX_ABOVE:
        lines.append(Html('<div class="layout event-layout">'))
        lines.extend(touched(entry, anchors, texts))
        lines.append(Html('<section class="changes">'))
        lines.extend(blocks)
        lines.append(
            Html(f'<p class="small backtop"><a href="#content">{escape(_BACK_TO_TOP)}</a></p>')
        )
        lines.extend((Html("</section>"), Html("</div>")))
    else:
        lines.extend(blocks)
    committed = repo_file(f"{entry.act_dir}/CHANGELOG.md", changelogs_url)
    lines.append(Html(f'<p class="small muted">The full entry is committed at {committed}.</p>'))
    return lines
