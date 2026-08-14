"""Saying that the three sources disagree, in the words a first-time reader already has.

`disputed` is the project's vocabulary and it is correct where it lives: in the JSON, in the
metrics and in `core`. On a page carrying a not-legal-advice disclaimer it is also the worst
available ambiguity, because a newcomer reads "this legal change is disputed" where the tool
means "its three detectors disagree about it". That invites a reader to think emendrix is
making a claim about the law when it is making a claim about itself. So the site spells the
claim out and the stored vocabulary does not move.

Three rules hold this module together:

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

The reader-facing names are the only place the three signals are translated for a page. They
describe what each source *is* rather than what the code calls it: a comparison of the two
texts, the publisher's own amendment annotations, and the amending act's own instructions.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.core import Signal, SignalObservation, SignalSet, SignalStatus

__all__ = ["DisputeNote", "dispute_note"]

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

_PRESENCE_LEAD: Final = "Sources disagree"
_KIND_LEAD: Final = "Sources disagree about the kind of change"


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
    """
    observations = signals.observations
    observed = tuple(signal for signal, seen in observations if seen.observed)
    unseen = tuple(signal for signal, seen in observations if seen.status is SignalStatus.ABSENT)
    if unseen:
        return DisputeNote(lead=_PRESENCE_LEAD, detail=_presence(observed, unseen))
    return DisputeNote(lead=_KIND_LEAD, detail=_kind(observations))


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
