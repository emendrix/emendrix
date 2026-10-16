"""One change of an amendment event as Markdown: the block under each headline.

This module knows how one `Change` and the prose that survived the gate are written down;
`markdown.py` knows how an entry's header, title and disclaimer frame the blocks, and
re-exports the names below so every importer keeps one address for them. The small renderings
the site reuses (`applies_text`, `short_label`, `dispute_text`) live here because the block is
where they are first needed.

The rules the block keeps are the format's, stated in `markdown.py`'s docstring: verbatim
quotes framed and visibly capped, applicability on the headline, the type as fact, a disputed
change marked with what disagreed, the gate's sentences told apart from the model's. One line
is deterministic detail of a newer kind: a unit holding a profiled table says how many of its
keyed entries moved, read off `Change.table_entries`, which no model ever saw.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from emendrix.core import (
    Applicability,
    Change,
    Citation,
    EntryChange,
    EntryDelta,
    Signal,
    SignalStatus,
)
from emendrix.core.changes import DisputeReason
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output.json_out import ChangelogEntry

__all__ = [
    "FALLBACK_PREFIX",
    "KEY_SAMPLE",
    "QUOTE_CHAR_CAP",
    "REASON_PHRASES",
    "TRUNCATION_MARKER",
    "applies_text",
    "change_block",
    "dispute_text",
    "short_label",
    "table_entries_line",
]

QUOTE_CHAR_CAP: Final = 1500
"""How much of a provision a `before`/`after` block quotes before the marker takes over.

Twice the gate's sentence cap (`gate.QUOTE_CHAR_CAP` = 600) and for a different job: that one
replaces a sentence, this one *is* the evidence a reader checks the sentence against. An annex
of 12,000 characters is still not a changelog entry, so there is a cap, and every use of it says
so in the text with the number of characters dropped.
"""

TRUNCATION_MARKER: Final = "[…truncated by emendrix: {dropped} characters omitted…]"

KEY_SAMPLE: Final = 10
"""How many entry keys the table-entries line names before it says how many more there are."""

_SIGNAL_NAMES: Final[dict[Signal, str]] = {
    Signal.STRUCTURAL_DIFF: "the structural diff",
    Signal.CORPUS_METADATA: "corpus metadata",
    Signal.INSTRUCTION_PARSE: "the instruction parse",
}

REASON_PHRASES: Final[dict[DisputeReason, str]] = {
    DisputeReason.KIND_MISMATCH: "the kinds named share nothing",
    DisputeReason.TEXTLESS_BOTH_OTHERS: "no text, named by both signals that carry none",
    DisputeReason.TEXTLESS_METADATA_ONLY: "no text, named by corpus metadata alone",
    DisputeReason.TEXTLESS_INSTRUCTION_ONLY: "no text, named by the instruction parse alone",
    DisputeReason.BOTH_OTHERS_SILENT: "found by the structural diff alone",
    DisputeReason.METADATA_SILENT: "corpus metadata is silent",
    DisputeReason.INSTRUCTION_SILENT: "the instruction parse is silent",
}
"""`Change.dispute_reason` in words, printed after the marker. Says which signal saw what."""

FALLBACK_PREFIX: Final = (
    "Quoted verbatim by the citation gate — the model's own sentence did not resolve:"
)
"""Said in the text, because a sentence the gate wrote and one the model wrote are different
kinds of claim. The site's act pages mark the same sentences with the same words
(`site_/pages/act_event.py`)."""


# ------------------------------------------------------------------ small renderings


def applies_text(applies: Applicability) -> str:
    """`applies_from` in words. `unknown` is an answer and says why when it knows."""
    if isinstance(applies, date):
        return applies.isoformat()
    if applies.kind == "unchanged":
        return "unchanged"
    return f"unknown ({applies.reason})" if applies.reason else "unknown"


def short_label(label: str, entry: ChangelogEntry) -> str:
    """`Art. 4, 02024R1689-20260727` → `Art. 4, v2`, with the mapping printed in the header."""
    for tag, short in ((entry.to_version, "v2"), (entry.from_version, "v1")):
        suffix = f", {tag}"
        if label.endswith(suffix):
            return f"{label[: -len(suffix)]}, {short}"
    return label


def _links(citations: tuple[Citation, ...], entry: ChangelogEntry) -> str:
    return " ".join(f"[{short_label(item.label, entry)}]({item.url})" for item in citations)


def _sentence(sentence: EmittedSentence, entry: ChangelogEntry) -> str:
    """One shipped sentence with its citations, on one line.

    Whitespace inside the *sentence* is collapsed: it is prose, it is one line by construction,
    and folding it guarantees no generated line can ever begin with one of `changelog.py`'s
    sentinels. The verbatim quotes below are untouched; those are the ones the "verbatim means
    verbatim" rule is about.
    """
    text = " ".join(sentence.text.split())
    body = f"*{FALLBACK_PREFIX}* {text}" if sentence.fallback else text
    links = _links(sentence.citations, entry)
    return f"{body} {links}".rstrip()


def _quote(text: str) -> list[str]:
    """A verbatim text as a Markdown blockquote, capped visibly and otherwise untouched.

    Every line is prefixed, including lines inside the legal text, which is what makes a
    sentinel collision structurally impossible: `changelog.py` anchors its markers at the
    start of a line and no line of quoted text starts there.
    """
    body = text
    if len(body) > QUOTE_CHAR_CAP:
        dropped = len(body) - QUOTE_CHAR_CAP
        body = body[:QUOTE_CHAR_CAP].rstrip() + " " + TRUNCATION_MARKER.format(dropped=dropped)
    lines = [f"> {line}".rstrip() for line in body.splitlines()]
    return lines or [">"]


def dispute_text(change: Change) -> str:
    """What disagreed, in words. Read off the signals the change actually carries.

    A source that saw the change and named no kind (an unlabelled role code, counted) still
    looked, so it gets a clause of its own, as it does on the page (`site_/dispute.py`). The
    two renderers read the same verdicts and may differ only in how plainly they say them.
    """
    observed = [
        _SIGNAL_NAMES[signal] for signal, seen in change.signals.observations if seen.observed
    ]
    absent = [
        _SIGNAL_NAMES[signal]
        for signal, seen in change.signals.observations
        if seen.status is SignalStatus.ABSENT
    ]
    if absent:
        seen = ", ".join(observed) or "no signal"
        return f"seen by {seen}, not by {', '.join(absent)}"
    kinds = ", ".join(
        f"{_SIGNAL_NAMES[signal]} says {'/'.join(sorted(seen.change_types))}"
        if seen.change_types
        else f"{_SIGNAL_NAMES[signal]} names no kind"
        for signal, seen in change.signals.observations
        if seen.observed
    )
    return f"the signals disagree on the kind of change — {kinds}"


def _key_name(change: EntryChange, labels: dict[tuple[str, int], str | None]) -> str:
    """`Index No 603-148-00-X`, or the entry's own name in quotes where the name is the key."""
    label = labels.get((change.container.canonical, change.table))
    if label is not None:
        return f"{label} {change.key}"
    entry = change.after if change.after is not None else change.before
    name = entry.name if entry is not None and entry.name is not None else change.key
    return f'"{name}"'


def table_entries_line(delta: EntryDelta) -> str:
    """The keyed table rows that moved, counted, with the first keys named.

    The keys come in the delta's own order, which is table position then natural key order,
    so the line never re-sorts anything. The parenthesis appears only when it counts something.
    """
    if not delta.changes:
        return "Table entries: none changed."
    typography = delta.typography_only
    noted = f" ({typography} only in spacing, dash forms or accents)" if typography else ""
    counts = (
        f"{delta.count('added')} added, {delta.count('amended')} amended{noted}, "
        f"{delta.count('removed')} removed"
    )
    labels = {(table.container.canonical, table.table): table.key_label for table in delta.tables}
    named = ", ".join(_key_name(change, labels) for change in delta.changes[:KEY_SAMPLE])
    more = len(delta.changes) - KEY_SAMPLE
    return f"Table entries: {counts}: {named}" + (f" and {more} more" if more > 0 else "")


# ------------------------------------------------------------------ the block


def _headline(change: Change) -> str:
    heading = f" — {change.heading}" if change.heading else ""
    was = "" if change.previous_location is None else f" (was {change.previous_location.human})"
    return (
        f"**{change.change_type.value} · {change.location.human}{was}{heading}** · "
        f"applies from: {applies_text(change.applies_from)}"
    )


def _detail(change: Change) -> list[str]:
    """The one-line detail under a headline: finer coordinates, dates that moved, the amender.

    The amending act is the bare identifier its corpus published, in the order corroboration
    claimed it: an official title needs the adapter, which `output/` does not import.
    """
    parts: list[str] = []
    if change.changed_within:
        inside = ", ".join(f"`{item.canonical}`" for item in change.changed_within)
        parts.append(f"*within* {inside}")
    if change.dates_removed or change.dates_added:
        moved = " ".join(
            [
                *(f"-{value.isoformat()}" for value in change.dates_removed),
                *(f"+{value.isoformat()}" for value in change.dates_added),
            ]
        )
        parts.append(f"*dates* {moved}")
    if change.amending_acts:
        named = ", ".join(f"`{act.key}`" for act in change.amending_acts)
        parts.append(f"*amended by* {named}")
    return ["", " · ".join(parts)] if parts else []


def _prose(emitted: EmittedChange, entry: ChangelogEntry) -> list[str]:
    lines: list[str] = []
    for sentence in emitted.sentences:
        lines.extend(("", _sentence(sentence, entry)))
    note = emitted.applicability_note
    if note is not None:
        lines.extend(("", f"*Applicability:* {_sentence(note, entry)}"))
    if not emitted.sentences and not entry.diff_only:
        reason = emitted.unexplained or "no explanation"
        lines.extend(("", f"*No explanation shipped — {reason}.*"))
    return lines


def _texts(change: Change, entry: ChangelogEntry) -> list[str]:
    lines: list[str] = []
    if change.before is not None:
        lines.extend(("", f"*before* (`{entry.from_version}`)", "", *_quote(change.before)))
    if change.after is not None:
        lines.extend(("", f"*after* (`{entry.to_version}`)", "", *_quote(change.after)))
    if change.textless:
        lines.extend(
            (
                "",
                "*No text on either side: this unit was named by a signal that carries no "
                "text, and only the structural diff carries any.*",
            )
        )
    return lines


def change_block(emitted: EmittedChange, entry: ChangelogEntry) -> list[str]:
    """One change: headline, detail, the dispute marker, the entry line, prose, both texts."""
    change = emitted.change
    lines = ["", _headline(change), *_detail(change)]
    if change.dispute_reason is not None:
        reason = REASON_PHRASES[change.dispute_reason]
        lines.extend(("", f"**DISPUTED** — {reason}: {dispute_text(change)}"))
    if change.table_entries is not None:
        lines.extend(("", table_entries_line(change.table_entries)))
    lines.extend(_prose(emitted, entry))
    lines.extend(_texts(change, entry))
    return lines
