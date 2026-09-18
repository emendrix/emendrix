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
- **A change where the sources differ is shown, says what differed and says which shape the
  difference has**, in its tag, in the lead of its note and in the weight of both. Dropping it
  would make the card tidier and the counts wrong; grading it changes what the page says about
  a difference and never whether one is recorded.
- **A change with no text to show is one line, and every one is still on the page.** They
  gather at the foot of the changes under a heading saying how many and what they are, each
  still a block with its own anchor, permalink and disagreement note, and each opens where it
  stands when a permalink names it. Nothing leaves the page or the counts for it.
- **Nothing here is cut.** A summary panel that merely points at the artifact can justify
  capping a sentence; this is where a reader arrives instead, so the sentences run in full and
  the before/after text sits one `<details>` away, uncut and verbatim, open on a version short
  enough that it has no index.
- **Every provision is a heading**, and a long page opens with a list of them built from the
  same anchors the blocks carry, so the list cannot point where no block is.
- **Every change says how much of the provision moved**, in characters, measured on the very
  comparison the block below it renders. It is a size and never a judgement: the words for that
  are in `site_/magnitude.py`, which prints the count and the sentence saying what it is not.
- **Every coordinate leads to its own history.** The heading's coordinate is a link to the
  provision's page, which is the same act's directory one level up from this event's, so a
  reader who arrived asking what this event did can ask what has ever been done to Annex XVII.
- **Every change block is addressable from itself**, by the permalink at the end of its
  heading. On a page long enough to open with an index, every block closes with the way back
  to that index and the page closes with the way back to the top.
- **The index is beside the changes where there is room for it.** A page listing its
  provisions puts the list in a column at the same width the act page's index becomes one, so
  a reader forty blocks down can still see the map; below that width it stays the wrapping row
  it has always been, which costs a few lines rather than a screen.

What a change block carries wherever it appears, the permalink, the note where sources differ,
the sentences, the row of their citations and the facts line, lives in `pages/prose.py`, and
the index a long page opens with lives in `pages/event_index.py`. Each is a statement this
module places rather than composes. What is left is one version's changes: the block each
sits in, and the order all of them come in.

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
from emendrix.site_.diffview import summary_words
from emendrix.site_.dispute import QUIET_NOTE, SHAPE_CLASS, dispute_shape, named_by, quiet_heading
from emendrix.site_.magnitude import magnitude_html
from emendrix.site_.markup import Html, escape
from emendrix.site_.pages.event_index import INDEX_ABOVE, INDEX_ID, touched
from emendrix.site_.pages.prose import (
    applies_line,
    dates_line,
    differ_note,
    permalink,
    prose,
    title_span,
)
from emendrix.site_.pages.texts import RenderedText
from emendrix.site_.sources import repo_file
from emendrix.site_.tags import SPOKEN_COMMA, kind_tag
from emendrix.site_.urls import location_slug, up

__all__ = ["render_event"]

_DEPTH = 3
"""`acts/<slug>/<key>/index.html`, the version page every block here is printed on."""

_WHAT_CHANGED = "What changed"
"""The heading the changes open under, between the version's masthead and its first block, so the
page reads as a version, then what changed, then each change."""

_BACK_TO_TOP = "Back to top ↑"
"""The foot of a page that opened with an index, aimed at the id the skip link already targets.

Only on such a page: below the index threshold the top of the page is still on the screen when
the last block ends, and a link back to what a reader can see is furniture rather than help.
"""

_TO_INDEX = f'<p class="to-index"><a href="#{INDEX_ID}">↑ Index</a></p>'
"""The close of every change on a page with an index: the way back to the list of changes.

Kept to one element and one class because a long act can print thousands of blocks. In a
gathered row with no text it is hidden with the rest of the row and shows when the row opens.
"""


def _change_block(
    emitted: EmittedChange,
    entry: ChangelogEntry,
    anchor: str,
    text: RenderedText,
    *,
    open_: bool,
    indexed: bool,
) -> list[Html]:
    """One change: what it is, where its sources differ, what was said, and the text itself.

    The block opens with a heading because the provision is the unit a reader and a crawler
    both look for: a passage is ranked, and a screen reader jumps, under `Art. 6` and its
    title. The heading leads with what a reader scans for, the coordinate, then the title, then
    the kind of change as a tag, so its name reads `Art. 1 Subject matter, Modified`. The `id`
    stays on the wrapping `div`, which is what the anchors were minted for and what
    `.chg:target` highlights.

    The coordinate is a link to that provision's own page, a sibling of this event's page under
    the act, so `../` climbs to the act's directory and the slug names the provision. The
    permalink closes the heading and points at this block's own `id`, so a reader can hand one
    change to somebody without knowing the anchor scheme.

    Under the heading, one line of facts: how much of the provision moved, measured on the
    comparison `text` carries, and the applies line. A punctuation fix and a rewritten
    paragraph are both modified, and the count is what tells them apart without opening
    either; it is a size and not part of the provision's name, which is why it left the
    heading. A change with no text on either side has nothing to measure and prints no count.
    The dates line follows where a date moved.

    Where the sources differ the block carries the shape as a class and says it twice, as the
    shape's tag with its definition link and as the lead and detail of the note. A change with
    no text names its naming source in the heading: that heading is the whole of such a row
    until a permalink opens it.

    `text` is the evidence, rendered once for the whole entry by `pages.texts` and handed in:
    the provision page shows the same block, and a diff computed twice is the one cost the
    split of these pages could have introduced. `open_` opens it where the version is short
    enough that every change's text belongs on the first read, and `indexed` closes the block
    with the way back to the index where the page has one; both are decided once by the caller.
    """
    change = emitted.change
    title = title_span(change)
    graded = f" {SHAPE_CLASS[dispute_shape(change.signals)]}" if change.disputed else ""
    named = (
        Html(f' <span class="by">named by {escape(named_by(change.signals))}</span>')
        if change.textless
        else Html("")
    )
    lines = [
        Html(f'<div class="chg{graded}" id="{escape(anchor)}">'),
        Html(
            f'<h3><a class="loc" href="../{escape(location_slug(change.location.canonical))}/">'
            f"{escape(change.location.human)}</a>{title}{SPOKEN_COMMA} "
            f"{kind_tag(change.change_type)}{named}{permalink(anchor)}</h3>"
        ),
        applies_line(change, up(_DEPTH), None if change.textless else magnitude_html(text)),
    ]
    dates = dates_line(change)
    if dates is not None:
        lines.append(dates)
    if change.disputed:
        lines.extend(differ_note(change.signals, up(_DEPTH)))
    lines.extend(prose(emitted, entry))
    lines.extend(
        (
            Html(
                f"<details{' open' if open_ else ''}>"
                f"<summary>{escape(summary_words(change))}</summary>"
            ),
            text.html,
            Html("</details>"),
        )
    )
    if indexed:
        lines.append(Html(_TO_INDEX))
    lines.append(Html("</div>"))
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
    long = len(entry.changes) >= INDEX_ABOVE
    for emitted, anchor, text in zip(entry.changes, anchors, texts, strict=True):
        block = _change_block(emitted, entry, anchor, text, open_=not long, indexed=long)
        if emitted.change.textless:
            quiet += 1
            hushed.extend(block)
        else:
            shown.extend(block)
    blocks = shown + (_quiet(hushed, quiet) if quiet else [])
    if long:
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
