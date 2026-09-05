"""Rendering one amendment event as Markdown, the primary artifact of the whole project.

What the format *forces* is the reason for every decision below:

- **Every sentence carries a citation**, and the citation is a link. They were rendered to
  `Citation` objects by the adapter at emit time (`graph/report.py`); nothing here invents a
  URL, and nothing here re-derives one. Labels are compacted against the two version tags of
  this entry (`Art. 4, v2`) with the mapping stated once in the header, because a full
  consolidated identifier in every bracket costs more readability than it buys precision.
- **`before`/`after` are verbatim.** They come from the stored `ProvisionText` untouched. The
  only things done to them are a `> ` prefix per line, which is Markdown framing rather than a
  change to the text, and a character cap whose every use is *visibly marked*: a silently
  truncated "verbatim" quote is worse than a long one (`QUOTE_CHAR_CAP`).
- **Applicability is separate and first-class**, on the change's own headline, because "in
  force" and "applies to you" are different questions and `unknown` is an answer.
- **The change type comes from the diff**, never from a model, so it is printed as fact.
- **A disputed change is rendered and marked, never dropped**, and the marker says *what*
  disagreed ("seen by the structural diff, not by corpus metadata"), because that transparency
  is the product's honesty made visible.
- **A sentence the gate wrote is visually distinct from one the model wrote.** The gate's
  verbatim fallback is correct by construction and the model's prose is not; a reader who
  cannot tell them apart has lost the more useful half of that distinction.

No clock, no corpus, no model: `detected_on` arrives on the entry, and two runs of one event
produce identical bytes.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from emendrix.core import Applicability, Change, Citation, Signal, SignalStatus
from emendrix.graph.report import EmittedChange, EmittedSentence
from emendrix.output.disclaimer import MARKDOWN_DISCLAIMER
from emendrix.output.json_out import ChangelogEntry

__all__ = [
    "FALLBACK_PREFIX",
    "QUOTE_CHAR_CAP",
    "TITLE_CAP",
    "TRUNCATION_MARKER",
    "applies_text",
    "dispute_text",
    "render_entry",
    "render_standalone",
    "short_label",
    "short_title",
]

QUOTE_CHAR_CAP: Final = 1500
"""How much of a provision a `before`/`after` block quotes before the marker takes over.

Twice the gate's sentence cap (`gate.QUOTE_CHAR_CAP` = 600) and for a different job: that one
replaces a sentence, this one *is* the evidence a reader checks the sentence against. An annex
of 12,000 characters is still not a changelog entry, so there is a cap, and every use of it says
so in the text with the number of characters dropped.
"""

TRUNCATION_MARKER: Final = "[…truncated by emendrix: {dropped} characters omitted…]"

TITLE_CAP: Final = 120
"""Where an act's official title is cut in the heading, visibly, with `[…]`.

Official EU titles are one long sentence (the MDR's is 266 characters, naming the four
directives it amends) and an H2 that wide is not a heading. The cut is marked and the full title
is in the JSON document's `act.display_name`, uncut.
"""

_SIGNAL_NAMES: Final[dict[Signal, str]] = {
    Signal.STRUCTURAL_DIFF: "the structural diff",
    Signal.CORPUS_METADATA: "corpus metadata",
    Signal.INSTRUCTION_PARSE: "the instruction parse",
}

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


def short_title(title: str) -> str:
    """An act's name for a heading, cut at `TITLE_CAP` and marked when it is cut."""
    if len(title) <= TITLE_CAP:
        return title
    return f"{title[:TITLE_CAP].rsplit(' ', 1)[0].rstrip(' ,;')} […]"


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

    A source that saw the change and named no kind is still a source that looked, so it gets a
    clause of its own. That state is real and counted: a role code the annotations use and this
    project has no label for leaves a signal observing with nothing to say about the kind.
    Dropping it would print two sources on a change three looked at, and would put this marker
    out of step with the page's (`site_/dispute.py`), which names it. The two renderers read
    the same verdicts and may differ only in how plainly they say them.
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


# ------------------------------------------------------------------ the blocks


def _headline(change: Change) -> str:
    heading = f" — {change.heading}" if change.heading else ""
    was = "" if change.previous_location is None else f" (was {change.previous_location.human})"
    return (
        f"**{change.change_type.value} · {change.location.human}{was}{heading}** · "
        f"applies from: {applies_text(change.applies_from)}"
    )


def _detail(change: Change) -> list[str]:
    """The one-line detail under a headline: finer coordinates, dates that moved, the amender.

    The amending act is printed as the bare identifier its corpus published, in the order
    corroboration claimed it. This package renders whatever corpus the loop ran on and holds
    no corpus knowledge, so turning `32020R0561` into an official title is not its job:
    that needs the adapter, which `output/` deliberately does not import.
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


def _change_block(emitted: EmittedChange, entry: ChangelogEntry) -> list[str]:
    change = emitted.change
    lines = ["", _headline(change), *_detail(change)]
    if change.disputed:
        lines.extend(("", f"**DISPUTED** — {dispute_text(change)}"))
    lines.extend(_prose(emitted, entry))
    lines.extend(_texts(change, entry))
    return lines


def _header(entry: ChangelogEntry) -> list[str]:
    counts, summary = entry.counts, entry.summary
    in_force = ", ".join(value.isoformat() for value in entry.in_force) or "not stated"
    lines = [
        f"## {short_title(entry.title)}",
        f"### `{entry.from_version}` → `{entry.to_version}`",
        "",
        f"- **Act** `{entry.act}` · **In force** {in_force} · "
        f"**Detected** {entry.detected_on.isoformat()}",
        f"- **Touched** {counts.touched} provisions — {counts.substantive} substantive · "
        f"{counts.date_only} date-only · {counts.textless} with no text · "
        f"**{counts.disputed} disputed**",
        f"- **Diff** {summary.inserted} inserted · {summary.modified} modified · "
        f"{summary.deleted} deleted · {summary.renumbered} renumbered · "
        f"{summary.deferred} deferred · {summary.unchanged_units} unchanged",
    ]
    if entry.diff_only:
        lines.append(
            "- **Diff only** — the explain stage did not run, so this entry carries the "
            "structural facts and the verbatim texts and no prose"
        )
    else:
        lines.append(
            f"- **Gate** {counts.quoted} sentences quoted verbatim · "
            f"{counts.unexplained} changes shipped without an explanation"
        )
    lines.extend(
        (
            f"- **Citations** `v1` = `{entry.from_version}` · `v2` = `{entry.to_version}`",
            "",
            "---",
        )
    )
    return lines


def render_entry(entry: ChangelogEntry) -> str:
    """One amendment event as Markdown, newline-terminated. Deterministic and byte-stable."""
    lines = list(_header(entry))
    for emitted in entry.changes:
        lines.extend(_change_block(emitted, entry))
    return "\n".join(lines).rstrip() + "\n"


def render_standalone(entry: ChangelogEntry) -> str:
    """The same entry printed on its own — `emendrix diff --markdown` — carrying the disclaimer.

    Inside a `CHANGELOG.md` the disclaimer sits once at the top of the file (`changelog.py`);
    printed on its own an entry has no file around it, and no user-facing output of this
    project ships without the disclaimer.
    """
    return f"{render_entry(entry)}\n{MARKDOWN_DISCLAIMER}\n"
