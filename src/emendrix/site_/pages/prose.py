"""What a change block says in words: the type pill, the shipped sentences, their citations.

Split out of `act_event` on 2026-09-03, when naming the amending act pushed that module past
the size cap. The seam is real rather than arithmetic: everything here renders *one change's
prose*, where what stays behind renders *one event*: its opening, its facts, its index and the
block each change sits in. The four functions moved unchanged, and `act_event` imports them.

The one promise that lives here is the gate's: a sentence a model composed and a sentence the
gate lifted verbatim out of the legal text are different kinds of claim, so the second carries
the changelog's own marker, imported rather than restated. Citation anchors are the adapter's
URLs; nothing here invents one.
"""

from __future__ import annotations

from emendrix.core import ChangeType, Citation
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output import ChangelogEntry
from emendrix.output.markdown import FALLBACK_PREFIX, short_label
from emendrix.site_.markup import Html, escape, join

__all__ = ["citation_links", "pill", "prose", "sentence"]


def pill(change_type: ChangeType, *, disputed: bool = False) -> Html:
    """The change type as the diff reported it, marked when the signals disagree about it."""
    classes = "pill"
    if change_type is ChangeType.INSERTED:
        classes += " ins"
    if disputed:
        classes += " disp"
    return Html(f'<span class="{classes}">{escape(change_type.value)}</span>')


def citation_links(citations: tuple[Citation, ...], entry: ChangelogEntry) -> Html:
    """Citations as anchors. The URLs were rendered by the adapter; nothing here invents one."""
    return join(
        (
            Html(f'<a href="{escape(item.url)}">{escape(short_label(item.label, entry))}</a>')
            for item in citations
        ),
        " ",
    )


def sentence(emitted: EmittedSentence, entry: ChangelogEntry) -> Html:
    """One shipped sentence, in full, with its citations and its provenance marker.

    Whitespace inside the sentence is folded, as the changelog folds it: this is prose, it is
    one line by construction, and the fold is a rendering of prose rather than of stored legal
    text. Nothing is dropped, so no cut has to be marked.
    """
    text = escape(" ".join(emitted.text.split()))
    prefix = (
        Html(f'<span class="quoted">{escape(FALLBACK_PREFIX)}</span> ')
        if emitted.fallback
        else Html("")
    )
    return Html(f"<p>{prefix}{text} {citation_links(emitted.citations, entry)}</p>")


def prose(emitted: EmittedChange, entry: ChangelogEntry) -> list[Html]:
    """Whatever survived the gate, or the stated reason there is nothing.

    In a diff-only entry the explain stage never ran, so nothing is missing and there is no
    per-change reason to give: the event's own facts line says it once instead, exactly as the
    changelog renderer does.
    """
    lines = [sentence(shipped, entry) for shipped in emitted.sentences]
    note = emitted.applicability_note
    if note is not None:
        lines.append(sentence(note, entry))
    if not emitted.sentences and not entry.diff_only:
        reason = emitted.unexplained or "no explanation"
        lines.append(Html(f'<p class="none">No explanation shipped — {escape(reason)}.</p>'))
    return lines
