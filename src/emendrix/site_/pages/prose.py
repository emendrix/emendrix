"""What a change block carries wherever it appears: the permalink, the prose, the cites, the meta.

Split out of `act_event` on 2026-09-03, when naming the amending act pushed that module past
the size cap. The seam is real rather than arithmetic: everything here renders *one change*,
where what stays behind renders *one event*: its opening, its facts, its index and the block
each change sits in. An event page and a provision page both show a change, and both read this
module, which is what stops one change being stated two ways on the two pages that hold it.

Four promises live here:

- **Two registers.** The explanation is a model's words and the text below it is EUR-Lex's, so
  the sentences sit under a label saying who wrote them and what checked them, and the text is
  in its own face under a summary naming its source. A reader can tell who is speaking before
  reading a word of either.
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
from typing import Final

from emendrix.core import Change, Citation, SignalSet
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output import ChangelogEntry
from emendrix.output.markdown import FALLBACK_PREFIX, applies_text, short_label
from emendrix.site_.dispute import dispute_note
from emendrix.site_.markup import Html, escape, join
from emendrix.site_.outbound import external
from emendrix.site_.tags import differ_tag

__all__ = [
    "applies_line",
    "citation_links",
    "dates_line",
    "differ_note",
    "permalink",
    "prose",
    "sentence",
    "title_span",
]

_PERMALINK_NAME = "Link to this change"
"""The permalink's accessible name. `§` is a symbol and never a name a screen reader can read."""

_CITED_LEAD = "Cited:"
"""What the row of links is, said in one word, so a row of coordinates is not read as prose."""

_APPLIES_LEAD = "Applies from:"
"""Clock 2's label. The colon is load-bearing: see `applies_line`."""

_UNCHANGED = "no date changed"
_UNREADABLE = "not readable"
"""The site's words for the two non-answers `output.markdown.applies_text` states as `unchanged`
and `unknown`. See `applies_line` for why the site says them differently."""

REGISTER = "Explanation, written by a model and checked against the cited text"
"""The label over a change's sentences: who wrote them, and what the gate checked them against."""

_NO_TEXT_REASONS: Final = frozenset(
    {
        "the structural diff did not see this change, so it carries no text; another signal "
        "named the unit and the disagreement ships marked disputed",
        "the structural diff did not see this change, so it carries no text; another signal "
        "named the unit and the disagreement ships as `disputed`",
    }
)
_NO_TEXT_WORDS: Final = (
    "the text comparison did not see this change, so it carries no text; another source named "
    "the provision, and it is listed where sources differ"
)
"""The one stored reason the site words for itself, as it words `disputed` everywhere else.

The explain stage records it against every change no text-carrying source saw, in the two
spellings committed documents hold, and both name the stored word. The fact is unchanged: the
comparison did not see the change, another source named it, and it ships as a difference
between the sources. Every other stored reason is printed as it was written.
"""

_CITES_KEY = "v1 is the previous version, v2 this one."
"""What the version half of a citation label means, printed under the row that uses it."""

_ADDED_LEAD = "dates added to the text"
_REMOVED_LEAD = "dates removed"
"""The two clauses of the dates line, added first, because the question is what the text says now.

The changelog states the same two tuples in one compact field, `*dates* -2020-05-26
+2021-05-26`, under the same word: a line of Markdown has one line to say it in, and a page has
room to say which tuple is which.
"""


def title_span(change: Change) -> Html:
    """The provision's title after its coordinate, only where it says more than the coordinate.

    The rule the provision page's heading applies: a Formex annex is often titled `ANNEX II`,
    and `Annex II ANNEX II` reads as a rendering accident. The comparison folds case and
    whitespace; what is printed is the stored title, character for character.
    """
    heading = change.heading
    named = change.location.human
    if not heading or heading.casefold().split() == named.casefold().split():
        return Html("")
    return Html(f' <span class="ttl">{escape(heading)}</span>')


def differ_note(signals: SignalSet, root: str) -> list[Html]:
    """Where a change's sources differ: the shape's tag and its definition, then the sentence.

    The same two lines on a version page and on a provision step, so one change is graded
    alike wherever it is shown. The lead is the part a reader scans for and is set apart; the
    detail names the sources.
    """
    note = dispute_note(signals)
    return [
        Html(f"<p>{differ_tag(signals, root)}</p>"),
        Html(f'<p class="differ"><strong>{escape(note.lead)}</strong> — {escape(note.detail)}</p>'),
    ]


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
    break lands between them; an outbound link is never broken, and every citation leaves the
    site for EUR-Lex, so each is marked as the one kind of link that does.
    """
    return join((external(item.url, short_label(item.label, entry)) for item in citations), " · ")


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

    The sentences open under the register label, and only where there are sentences: a change
    with none keeps its stated reason, which is the site speaking and not the model.

    The citation row closes the change and is absent when nothing was cited, which is every
    change of a diff-only entry and every change the gate left unexplained. It is one row for
    the block rather than one per sentence; the module docstring says what that does and does
    not change. Where a label in it names `v1` or `v2`, the line under it says what those are,
    so the meaning sits beside the label rather than only at the top of a long page.
    """
    lines = [sentence(shipped) for shipped in emitted.sentences]
    note = emitted.applicability_note
    if note is not None:
        lines.append(sentence(note))
    if lines:
        lines.insert(0, Html(f'<p class="register">{escape(REGISTER)}</p>'))
    if not emitted.sentences and not entry.diff_only:
        reason = emitted.unexplained or "no explanation"
        if reason in _NO_TEXT_REASONS:
            reason = _NO_TEXT_WORDS
        lines.append(Html(f'<p class="none">No explanation shipped — {escape(reason)}.</p>'))
    cited = _cited(emitted, entry)
    if cited:
        lines.append(
            Html(f'<p class="cites">{escape(_CITED_LEAD)} {citation_links(cited, entry)}</p>')
        )
        labels = [short_label(item.label, entry) for item in cited]
        if any(label.endswith((", v1", ", v2")) for label in labels):
            lines.append(Html(f'<p class="cites-key small">{escape(_CITES_KEY)}</p>'))
    return lines


def applies_line(change: Change, root: str, magnitude: Html | None = None) -> Html:
    """`Applies from: 2021-05-26`, and the two stated non-answers in the same shape.

    The application clock's answer, on every change block without exception. A block with no
    line here would leave the question to the reader, and the reader's own fill-in is the
    inference this project refuses to make: an application date is published only where it is
    deterministically readable, and `ApplicabilityUnknown` is a value that reaches the output,
    never a silence.

    A real date is `output.markdown`'s own words, so one date says one thing on the site and in
    the changelog. The two non-answers are the site's own: `unchanged` beside a changed
    provision read as "the provision did not change", so it says `no date changed`, and
    `unknown` says `not readable`, keeps its reason and links the definition of the clock. The
    value is still `applies_text`'s, only worded for a page.

    `magnitude` leads the line where the block prints how much moved, as the first fact about
    the change after its heading. Only a real date is wrapped, so the stylesheet can lift it out
    of the muted colour the two non-answers keep.
    """
    value = applies_text(change.applies_from)
    if isinstance(change.applies_from, date):
        shown = Html(f'<span class="date">{escape(value)}</span>')
    elif value == "unchanged":
        shown = escape(_UNCHANGED)
    else:
        reason = value.removeprefix("unknown")
        shown = Html(
            f'{escape(_UNREADABLE + reason)} <a class="define" '
            f'href="{escape(root)}methodology/#applies-from">why</a>'
        )
    lead = Html(f"{magnitude} characters · ") if magnitude is not None else Html("")
    return Html(f'<p class="meta">{lead}{escape(_APPLIES_LEAD)} {shown}</p>')


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
