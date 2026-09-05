"""Saying that the three sources disagree, in the words a first-time reader already has.

`disputed` is the project's vocabulary and it is correct where it lives: in the JSON, in the
metrics and in `core`. On a page carrying a not-legal-advice disclaimer it is also the worst
available ambiguity, because a newcomer reads "this legal change is disputed" where the tool
means "its three detectors disagree about it". That invites a reader to think emendrix is
making a claim about the law when it is making a claim about itself. So the site spells the
claim out and the stored vocabulary does not move.

Four rules hold this module together:

- **The sentence is read off the signals the change carries**, exactly as the changelog's
  marker is (`output/markdown.py::dispute_text`). Neither restates the other's prose; both
  read the same structured verdicts, so they cannot drift about *what* happened, only about
  how plainly they say it.
- **`UNAVAILABLE` is never named.** A source handed nothing to work with has not dissented,
  and a sentence that listed it among the sources that did not see the change would claim a
  disagreement the status says does not exist. Only `ABSENT` reaches the second half of the
  sentence, and an unavailable source appears nowhere in it at all.
- **A disagreement about kind is not a disagreement about occurrence.** When every source that
  looked found the provision and they named different kinds, the sentence says so; phrasing
  that as one source not seeing the change would be false. Every observing source is named
  there, including one that saw the change and named no kind, so the count of sources in the
  sentence is always the count that looked.
- **One word covered three findings until 2026-09-05, and now three leads do.** A provision
  whose words the comparison read and quoted, which another source merely did not enumerate,
  is not the finding a provision nothing could show at all is, and neither is the outright
  contradiction about kind. Which shape a disagreement has is read from `entries`, the same
  question the published rates are counted by, so the lead over one change, the count line
  under an event and the methodology table cannot tell three stories. **Nothing is graded
  away**: all three still ship, still carry `disputed` in the JSON and still count in the rate,
  and every lead still opens on the words `Sources disagree`.

The reader-facing names are the only place the three signals are translated for a page. They
describe what each source *is* rather than what the code calls it: a comparison of the two
texts, the publisher's own amendment annotations, and the amending act's own instructions.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.core import Signal, SignalObservation, SignalSet, SignalStatus
from emendrix.site_.entries import _shape
from emendrix.site_.markup import count
from emendrix.site_.untouched import TEXTLESS_TAIL

__all__ = [
    "DISPUTED_GLOSS",
    "QUIET_NOTE",
    "SHAPE_CLASS",
    "SHAPE_WORDS",
    "DisputeNote",
    "dispute_note",
    "dispute_shape",
    "named_by",
    "quiet_heading",
]

DISPUTED_GLOSS: Final = (
    "A change marked disputed is one the three sources emendrix checks disagree about. It is "
    "shown rather than dropped, and it says nothing about the law: it is a fact about the "
    "sources. They disagree in more than one way, and each change says which: whether its own "
    "words are on the page, whether there are none to show, or whether the sources that looked "
    "named different kinds of change."
)
"""What the word means, for a page that prints a count of them rather than one of them.

The event page primes a reader with the sentence naming the three sources and then gives each
disagreement its own note through `dispute_note`, and the methodology page explains the same
thing where the loop is described. A count on a card has room for neither, and `36 disputed`
beside `36 provisions` reads as a defect rate to somebody who has met no other page, so this
is the one sentence that travels with a count. It restates the same claim those two make and
adds nothing to it: the stored vocabulary still does not move. The closing sentence is the
one thing it adds, and it is a pointer rather than a claim: the count covers three findings
and the pages that print one of them say which it is.
"""

_SOURCE: Final[dict[Signal, str]] = {
    Signal.STRUCTURAL_DIFF: "the text comparison",
    Signal.CORPUS_METADATA: "the EU's own amendment metadata",
    Signal.INSTRUCTION_PARSE: "the amending act's instructions",
}
"""What each signal is, said to somebody who has never read this repository."""

_UNSEEN: Final[dict[Signal, str]] = {
    Signal.STRUCTURAL_DIFF: "the text comparison finds no difference in the provision's text",
    Signal.CORPUS_METADATA: "the EU's own amendment metadata does not list it",
    Signal.INSTRUCTION_PARSE: "the amending act's instructions do not mention it",
}
"""How each signal says it did not see the change. One clause per source, because the natural
negative differs: metadata lists, instructions mention, and a comparison finds a difference."""

_EVIDENCED_LEAD: Final = "Sources disagree about what is listed, not about the text"
"""The change the comparison read and quoted, which another source did not enumerate.

The words the provision gained and lost are on the page directly below this line, so the lead
says what the disagreement is actually about: a reference set's granularity. A blanket
amendment is annotated once and the provisions it lands on are not enumerated, and this is
what that looks like one change at a time. It is a footnote about a reference set and not a
warning about the text, and it still opens on `Sources disagree`.
"""

_TEXTLESS_LEAD: Final = "Sources disagree, and there is no text on either side"
"""The unit another source named and the comparison never saw, so nothing can be shown for it.

Said in the lead rather than left to the row below, because a reader who opens one of these
finds no words at all, and a lead that promised a disagreement about text would be promising
evidence that does not exist. `diffview` says the same thing inside the row, in the
changelog's own sentence.
"""

_KIND_LEAD: Final = "Sources disagree about the kind of change"
"""The outright contradiction: every source that looked found the provision and they named
different things. The loudest of the three, and the only one this pass left exactly as it was."""

_LEADS: Final[dict[str, str]] = {
    "evidenced": _EVIDENCED_LEAD,
    "no_text": _TEXTLESS_LEAD,
    "kind": _KIND_LEAD,
}
"""The lead each shape gets, so one function decides which of the three a change is.

`dispute_note` reads its shape from `dispute_shape` and looks the lead up here rather than
asking the verdicts a second question of its own. A second discriminator would be free to
answer differently from the one the counts are taken with, which is exactly what a reader
would then see: a lead about text over a change the count line filed under no text.
"""

SHAPE_WORDS: Final[dict[str, str]] = {
    "evidenced": "found in the text",
    "no_text": "named with no text",
    "kind": "called different kinds",
}
"""Each shape as the count line prints it, in the order the methodology table lists them.

A count line has one clause per shape and no room for a lead, so these are the short forms of
the three leads above and say the same thing in the same order. The keys are `DisputeShapes`'
own field names, which is asserted rather than assumed: a fourth shape added to that model
without words here would print a count nobody could read.
"""

SHAPE_CLASS: Final[dict[str, str]] = {
    "evidenced": "disp-text",
    "no_text": "disp-none",
    "kind": "disp-kind",
}
"""Each shape as the class its change block carries, which is what grades the badge.

Weight and border, never a hue: the sheet spends colour on diffs, disputes and links, and all
three of these keep the one disputed colour. The class rides on the block, and the sheet
reaches the badge through it, because the pill itself is minted in `pages/prose.py` for four
callers and three of them are not a change block at all. **It is the event page's block that
carries it today**: a provision page states the same change with the same lead and the plain
disputed pill, so the two pages grade a disagreement in words alike and in weight only on one
of them. Grading both means giving the pill the shape and passing it at every call site.
"""

QUIET_NOTE: Final = (
    "Each row carries the provision and the source that named it, and opens in place from the "
    "§ link at its end. None was dropped and every one still counts in the disputed total "
    "above."
)
"""What the collapsed list is and how to open one of it, said above the rows themselves.

Written before the layout was, and the layout follows it: a row that could not be described
honestly in one sentence would be a row that should not have been collapsed. It says the two
things a reader has to be able to check, that nothing left the page and that nothing left the
count, and then how to see one whole.
"""


def quiet_heading(number: int) -> str:
    """`36 provisions named with no text to show`, over the list of the rows that are.

    The tail is `untouched.TEXTLESS_TAIL` rather than a fourth phrasing of it: the same words
    head an event's card, its `<title>` and its description, and a list heading that said it
    differently would read as a different class of row.

    `provision` is the honest noun here and not the looser one an index of change blocks needs.
    A change with no text is appended by `corroborate.merge` at the top-level unit, one per
    unit and never for a unit the comparison already produced a change for, so the rows are in
    one-to-one correspondence with provisions and this number is the `with no text` figure on
    the count line above, reached by counting the rows themselves.
    """
    return f"{count(number, 'provision')} {TEXTLESS_TAIL}"


def dispute_shape(signals: SignalSet) -> str:
    """Which of the three shapes one disagreement has, for a change that carries one.

    Delegated to the rollup that counts the published rates rather than decided again here.
    Two answers to this question would let a badge, a count line and a table disagree with one
    another about the same change, which is the whole failure this grading exists to end.

    Only meaningful for a change that ships `disputed`; on a set the sources agree about it
    reports `kind`, there being no absent source to read the presence shapes off.
    """
    return _shape(signals)


def named_by(signals: SignalSet) -> str:
    """The sources that did see this change, in the reader's words, for a row with no text.

    An `UNAVAILABLE` source is not among them, by the rule this module holds throughout: it was
    handed nothing and named nothing. A change with no text exists only because some source
    named it, so the tuple is never empty in practice; the empty reading says what an empty
    reading means rather than leaving a sentence with a hole in it.
    """
    return _names(signals.observed_by) or "no source this document records"


class DisputeNote(BaseModel):
    """One disagreement in plain words, split where the page wants to emphasise it.

    Two fields rather than one string because the lead is the part a reader scans for and the
    page sets it apart; joining them here keeps the two halves from being punctuated
    differently by each caller.
    """

    model_config = ConfigDict(frozen=True)

    lead: str
    detail: str

    @property
    def text(self) -> str:
        return f"{self.lead} — {self.detail}"


def dispute_note(signals: SignalSet) -> DisputeNote:
    """The sentence for one change's verdicts. Takes the verdicts, not the change.

    A `SignalSet` is the whole input: the wording depends on nothing else about the change, and
    a function of the verdicts alone can be exercised over every pattern the corpus produces
    without building a change around each one.

    The lead is the shape and the detail is the sources, which is why the two are separate
    fields: the shapes are three and the patterns of source verdicts are seven, and a page that
    set one string apart would be emphasising whichever half the wording happened to open on.
    The discriminator between the two presence leads is the same one `dispute_shape` reads,
    the text-carrying source having seen the change or not.
    """
    observations = signals.observations
    observed = tuple(signal for signal, seen in observations if seen.observed)
    unseen = tuple(signal for signal, seen in observations if seen.status is SignalStatus.ABSENT)
    shape = dispute_shape(signals)
    detail = _kind(observations) if shape == "kind" else _presence(observed, unseen)
    return DisputeNote(lead=_LEADS[shape], detail=detail)


def _presence(observed: tuple[Signal, ...], unseen: tuple[Signal, ...]) -> str:
    """One source or two found the change; the rest looked and did not."""
    found = f"{_names(observed)} found this change" if observed else "no source found this change"
    missed = " and ".join(_UNSEEN[signal] for signal in unseen)
    return f"{found}; {missed}. {_closing(len(observed) + len(unseen))}"


def _kind(observations: tuple[tuple[Signal, SignalObservation], ...]) -> str:
    """Every source that looked found the provision, and they named different kinds.

    Every observing source gets a clause, including one that saw the change and named no kind
    at all. That is a real and counted state: a role code the annotations use and this project
    has no label for leaves a source observing with nothing to say about the kind. Dropping it
    here would leave a reader counting two sources on a page where three looked.
    """
    claims = [
        f"{_SOURCE[signal]} called it {'/'.join(sorted(seen.change_types))}"
        if seen.change_types
        else f"{_SOURCE[signal]} found it without naming a kind"
        for signal, seen in observations
        if seen.observed
    ]
    if not claims:
        return "the sources that saw this provision do not agree on what kind of change it is."
    return (
        "they agree this provision changed and disagree about how: "
        f"{_and(claims)}. {_closing(len(claims))}"
    )


def _names(signals: tuple[Signal, ...]) -> str:
    return _and([_SOURCE[signal] for signal in signals])


def _and(parts: list[str]) -> str:
    """`a`, `a and b`, `a, b and c`. There are three signals, so the list never runs longer."""
    if len(parts) < 2:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _closing(named: int) -> str:
    """The promise the whole marker exists to make: both readings ship, neither is picked."""
    if named == 2:
        return "Both are shown; neither is overruled."
    return "All are shown; none is overruled."
