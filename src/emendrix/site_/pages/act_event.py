"""One amendment event, as a card: the facts, then one block per provision that moved.

The half of the act page that renders a single committed changelog entry. It sits beside
`act.py` rather than inside it because the page and the card are two jobs: the page decides what
an act's history looks like as a whole (header, index, order), the card decides how one event
states what it did and what evidence it has.

Four promises live here, each as a line of markup rather than a claim made elsewhere:

- **The facts are the diff's, not a model's.** The change type, the coordinate, the counts and
  both dates are read off the committed document. The sentences inside a change block are the
  only thing on the card a model wrote.
- **A sentence the gate quoted is marked as one**, in the changelog's own words, because a
  sentence a model composed and a sentence the gate lifted verbatim are different kinds of
  claim.
- **A disputed change is shown and says what disagreed.** Dropping it would make the card
  tidier and the counts wrong.
- **An event no amending act is named for says so**, once, above its changes: a label and a
  sentence about the corpus's records for the window, never a doubt about the text below.
- **Nothing here is cut.** A summary panel that merely points at the artifact can justify
  capping a sentence; this is where a reader arrives instead, so the sentences run in full and
  the before/after text sits one `<details>` away, uncut and verbatim.

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

from emendrix.core import ChangeType, Citation
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output import ChangelogEntry
from emendrix.output.markdown import (
    FALLBACK_PREFIX,
    applies_text,
    short_label,
)
from emendrix.site_.attribution import UNATTRIBUTED_LABEL, UNATTRIBUTED_NOTE, unattributed
from emendrix.site_.diffview import render_texts
from emendrix.site_.dispute import dispute_note
from emendrix.site_.markup import Html, count, escape, join

__all__ = ["pill", "render_event"]


def pill(change_type: ChangeType, *, disputed: bool = False) -> Html:
    """The change type as the diff reported it, marked when the signals disagree about it."""
    classes = "pill"
    if change_type is ChangeType.INSERTED:
        classes += " ins"
    if disputed:
        classes += " disp"
    return Html(f'<span class="{classes}">{escape(change_type.value)}</span>')


def _links(citations: tuple[Citation, ...], entry: ChangelogEntry) -> Html:
    """Citations as anchors. The URLs were rendered by the adapter; nothing here invents one."""
    return join(
        (
            Html(f'<a href="{escape(item.url)}">{escape(short_label(item.label, entry))}</a>')
            for item in citations
        ),
        " ",
    )


def _sentence(sentence: EmittedSentence, entry: ChangelogEntry) -> Html:
    """One shipped sentence, in full, with its citations and its provenance marker.

    Whitespace inside the sentence is folded, as the changelog folds it: this is prose, it is
    one line by construction, and the fold is a rendering of prose rather than of stored legal
    text. Nothing is dropped, so no cut has to be marked.
    """
    text = escape(" ".join(sentence.text.split()))
    prefix = (
        Html(f'<span class="quoted">{escape(FALLBACK_PREFIX)}</span> ')
        if sentence.fallback
        else Html("")
    )
    return Html(f"<p>{prefix}{text} {_links(sentence.citations, entry)}</p>")


def _prose(emitted: EmittedChange, entry: ChangelogEntry) -> list[Html]:
    """Whatever survived the gate, or the stated reason there is nothing.

    In a diff-only entry the explain stage never ran, so nothing is missing and there is no
    per-change reason to give: the event's own facts line says it once instead, exactly as the
    changelog renderer does.
    """
    lines = [_sentence(sentence, entry) for sentence in emitted.sentences]
    note = emitted.applicability_note
    if note is not None:
        lines.append(_sentence(note, entry))
    if not emitted.sentences and not entry.diff_only:
        reason = emitted.unexplained or "no explanation"
        lines.append(Html(f'<p class="none">No explanation shipped — {escape(reason)}.</p>'))
    return lines


def _change_block(emitted: EmittedChange, entry: ChangelogEntry, anchor: str) -> list[Html]:
    """One change: what it is, what is disputed about it, what was said, and the text itself."""
    change = emitted.change
    heading = Html(f" — {escape(change.heading)}") if change.heading else Html("")
    lines = [
        Html(f'<div class="chg" id="{escape(anchor)}">'),
        Html(
            f"<p>{pill(change.change_type, disputed=change.disputed)} "
            f"<strong>{escape(change.location.human)}</strong>{heading} "
            f'<span class="applies">· applies from {escape(applies_text(change.applies_from))}'
            "</span></p>"
        ),
    ]
    if change.disputed:
        note = dispute_note(change.signals)
        lines.append(
            Html(
                f'<p class="disputed"><strong>{escape(note.lead)}</strong> — '
                f"{escape(note.detail)}</p>"
            )
        )
    lines.extend(_prose(emitted, entry))
    lines.extend(
        (
            Html("<details><summary>text before / after</summary>"),
            render_texts(change, entry),
            Html("</details>"),
            Html("</div>"),
        )
    )
    return lines


def _facts(entry: ChangelogEntry) -> list[Html]:
    """The dates and the counts, all of them read off the document, none of them recomputed."""
    counts = entry.counts
    in_force = ", ".join(value.isoformat() for value in entry.in_force) or "not stated"
    gate = (
        "the explain stage did not run for this event, so it carries the structural facts only"
        if entry.diff_only
        else f"{count(counts.quoted, 'sentence')} quoted verbatim by the gate, "
        f"{count(counts.unexplained, 'change')} shipped without an explanation"
    )
    return [
        Html(
            f'<p class="facts">in force {escape(in_force)} · '
            f"detected {entry.detected_on.isoformat()}</p>"
        ),
        Html(
            f'<p class="facts">{escape(count(counts.touched, "provision"))} touched — '
            f"{counts.substantive} substantive, {counts.date_only} date-only, "
            f"<strong>{counts.disputed} disputed</strong> · {escape(gate)}</p>"
        ),
    ]


def render_event(entry: ChangelogEntry, anchors: tuple[str, ...]) -> list[Html]:
    """One event card. `anchors` is one fragment per change, in the entry's own order.

    The anchors are computed once for the whole page and handed down, so the provision index
    and the change blocks point at the same fragments by construction rather than by both
    sides running the same counter.
    """
    versions = (
        f"<code>{escape(str(entry.from_version))}</code> → "
        f"<code>{escape(str(entry.to_version))}</code>"
    )
    # The bare pill, no colour modifier: the label is a fact about the corpus's records, and
    # the palette spends colour on diffs, disputes and links only (`style.py`).
    unnamed = unattributed(entry)
    marker = f' <span class="pill">{escape(UNATTRIBUTED_LABEL)}</span>' if unnamed else ""
    lines = [
        Html(f'<article class="event" id="{escape(entry.key)}">'),
        Html(f"<h2>{versions}{marker}</h2>"),
        *_facts(entry),
    ]
    if unnamed:
        lines.append(Html(f'<p class="small muted">{escape(UNATTRIBUTED_NOTE)}</p>'))
    for emitted, anchor in zip(entry.changes, anchors, strict=True):
        lines.extend(_change_block(emitted, entry, anchor))
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
