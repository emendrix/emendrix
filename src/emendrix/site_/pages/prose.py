"""What a change block carries wherever it appears: the pill, the permalink, the prose, the cites.

Split out of `act_event` on 2026-09-03, when naming the amending act pushed that module past
the size cap. The seam is real rather than arithmetic: everything here renders *one change*,
where what stays behind renders *one event*: its opening, its facts, its index and the block
each change sits in. An event page and a provision page both show a change, and both read this
module, which is what stops one change being stated two ways on the two pages that hold it.

Three promises live here:

- **The gate's.** A sentence a model composed and a sentence the gate lifted verbatim out of
  the legal text are different kinds of claim, so the second carries the changelog's own
  marker, imported rather than restated. Citation anchors are the adapter's URLs; nothing here
  invents one.
- **The citations are shown once per change, not once per sentence.** A change's sentences
  usually cite the same provision in both versions, and repeating that pair under every
  sentence put the same two links on the page four and six times over. One row of the distinct
  citations, in first-mention order, says everything the repetition said. This is a rendering
  decision and nothing below it moves: the JSON and the Markdown keep every citation on the
  sentence that carries it, which is the form the citation gate resolves and the eval harness
  counts, and a reader who wants that mapping has the committed entry.
- **A date the text names is stated as one.** The dates a change added and dropped are printed
  under the applies-from line, which is the one line on the block that says whether a date
  governs anything. Nothing here calls a date a deadline, an application date or an obligation:
  the parser read them off the source's own date markup and the site says exactly that.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import Change, ChangeType, Citation
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output import ChangelogEntry
from emendrix.output.markdown import FALLBACK_PREFIX, applies_text, short_label
from emendrix.site_.markup import Html, escape, join

__all__ = [
    "applies_line",
    "citation_links",
    "dates_line",
    "permalink",
    "pill",
    "prose",
    "sentence",
]

_PERMALINK_NAME = "Link to this change"
"""The permalink's accessible name. `§` is a symbol and never a name a screen reader can read."""

_CITED_LEAD = "Cited:"
"""What the row of links is, said in one word, so a row of coordinates is not read as prose."""

_APPLIES_LEAD = "applies from:"
"""Clock 2's label. The colon is load-bearing: see `applies_line`."""

_ADDED_LEAD = "dates added to the text"
_REMOVED_LEAD = "dates removed"
"""The two clauses of the dates line, added first, because the question is what the text says now.

The changelog states the same two tuples in one compact field, `*dates* -2020-05-26
+2021-05-26`, under the same word: a line of Markdown has one line to say it in, and a page has
room to say which tuple is which.
"""


def pill(change_type: ChangeType, *, disputed: bool = False) -> Html:
    """The change type as the diff reported it, marked when the signals disagree about it."""
    classes = "pill"
    if change_type is ChangeType.INSERTED:
        classes += " ins"
    if disputed:
        classes += " disp"
    return Html(f'<span class="{classes}">{escape(change_type.value)}</span>')


def permalink(anchor: str) -> Html:
    """One change's own address, at the end of the heading that names it.

    A page can carry hundreds of blocks and every one of them has been addressable since the
    anchors were minted, but until this link existed a reader could reach a single change only
    by knowing the fragment scheme. The name is spelled out for a screen reader because the
    visible mark is a symbol, and the anchor is the block's own id, so the link cannot point
    anywhere but at the block it sits in.
    """
    return Html(
        f'<a class="permalink" href="#{escape(anchor)}" '
        f'aria-label="{escape(_PERMALINK_NAME)}">§</a>'
    )


def citation_links(citations: tuple[Citation, ...], entry: ChangelogEntry) -> Html:
    """Citations as anchors, each label held on one line. The URLs are the adapter's.

    A label is a coordinate and a version, `Art. 17, v1`, and it reads as two facts if a line
    break lands between them, so each anchor carries the class the site uses for a name that
    may not be broken.
    """
    return join(
        (
            Html(
                f'<a class="nowrap" href="{escape(item.url)}">'
                f"{escape(short_label(item.label, entry))}</a>"
            )
            for item in citations
        ),
        " · ",
    )


def sentence(emitted: EmittedSentence) -> Html:
    """One shipped sentence, in full, with its provenance marker.

    Whitespace inside the sentence is folded, as the changelog folds it: this is prose, it is
    one line by construction, and the fold is a rendering of prose rather than of stored legal
    text. Nothing is dropped, so no cut has to be marked. The citations this sentence carries
    are rendered by `prose` for the whole change instead of here, and the stored entry keeps
    them where they are.
    """
    text = escape(" ".join(emitted.text.split()))
    prefix = (
        Html(f'<span class="quoted">{escape(FALLBACK_PREFIX)}</span> ')
        if emitted.fallback
        else Html("")
    )
    return Html(f"<p>{prefix}{text}</p>")


def _cited(emitted: EmittedChange, entry: ChangelogEntry) -> tuple[Citation, ...]:
    """Every citation the change's prose carries, first mention first, each pair once.

    Deduplicated by the rendered pair of address and label rather than by address alone: the
    gate can resolve two coordinates to one anchor, `Art. 5` and `Art. 5(1)` both landing on
    `#art_5`, and which coordinate a sentence named is information the URL has lost. Two
    sentences citing the identical pair are the case this exists for, and they are the common
    one.
    """
    shipped = list(emitted.sentences)
    if emitted.applicability_note is not None:
        shipped.append(emitted.applicability_note)
    seen: set[tuple[str, str]] = set()
    distinct: list[Citation] = []
    for one in shipped:
        for item in one.citations:
            key = (item.url, short_label(item.label, entry))
            if key not in seen:
                seen.add(key)
                distinct.append(item)
    return tuple(distinct)


def prose(emitted: EmittedChange, entry: ChangelogEntry) -> list[Html]:
    """Whatever survived the gate, or the stated reason there is nothing, and then the cites.

    In a diff-only entry the explain stage never ran, so nothing is missing and there is no
    per-change reason to give: the event's own facts line says it once instead, exactly as the
    changelog renderer does.

    The citation row closes the change and is absent when nothing was cited, which is every
    change of a diff-only entry and every change the gate left unexplained. It is one row for
    the block rather than one per sentence; the module docstring says what that does and does
    not change.
    """
    lines = [sentence(shipped) for shipped in emitted.sentences]
    note = emitted.applicability_note
    if note is not None:
        lines.append(sentence(note))
    if not emitted.sentences and not entry.diff_only:
        reason = emitted.unexplained or "no explanation"
        lines.append(Html(f'<p class="none">No explanation shipped — {escape(reason)}.</p>'))
    cited = _cited(emitted, entry)
    if cited:
        lines.append(
            Html(f'<p class="cites">{escape(_CITED_LEAD)} {citation_links(cited, entry)}</p>')
        )
    return lines


def applies_line(change: Change) -> Html:
    """`applies from: 2021-05-26`, and the two stated non-answers in the same shape.

    The application clock's answer, on every change block without exception. A block with no
    line here would leave the question to the reader, and the reader's own fill-in is the
    inference this project refuses to make: an application date is published only where it is
    deterministically readable, and `ApplicabilityUnknown` is a value that reaches the output,
    never a silence.

    The label carries a colon because two of the three values are not dates: without it
    `applies from` reads as a sentence that `unchanged` and `unknown` cannot finish. With it
    the line is a label and a value, which is the form the committed Markdown and the CLI
    already print.

    Only a real date is wrapped, so the stylesheet can lift it out of the muted colour the two
    non-answers keep. The words are `output.markdown`'s own, so one change says one thing on
    the site and in the changelog.
    """
    value = applies_text(change.applies_from)
    shown = (
        Html(f'<span class="date">{escape(value)}</span>')
        if isinstance(change.applies_from, date)
        else escape(value)
    )
    return Html(f'<p class="applies">{_APPLIES_LEAD} {shown}</p>')


def dates_line(change: Change) -> Html | None:
    """`dates added to the text: 2027-12-02, 2028-08-02 · dates removed: 2026-08-02`.

    The machine-readable dates that moved, as the parser read them off the source's own date
    markup. Whether any of them is the date the provision applies from is the applies line's
    question, answered above this one and never here.

    `None` where neither tuple holds anything, which is most changes: a paragraph saying that
    no date moved would be a line on every block to carry a fact about nine hundred of them.

    The dates are printed in the order the change carries them, which the diff sorted, and in
    the ISO form every date on the site is printed in.
    """
    clauses = [
        f"{label}: {', '.join(value.isoformat() for value in dates)}"
        for label, dates in (
            (_ADDED_LEAD, change.dates_added),
            (_REMOVED_LEAD, change.dates_removed),
        )
        if dates
    ]
    if not clauses:
        return None
    return Html(f'<p class="dates">{escape(" · ".join(clauses))}</p>')
