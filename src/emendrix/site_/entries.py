"""The committed changelog repository: read off disk, put in the site's one order, counted.

Split out of `inputs.py` on 2026-09-03, when that module reached the size cap while gaining
the act's published-document link and the roster's kinds. The seam is the one the two halves
already had: this module turns files into `ChangelogEntry` values, orders them and rolls them
up, and knows nothing about acts, labels or pages; `inputs.py` resolves what the site renders
and never touches the filesystem.

Ordering lives here rather than beside the pages because two builds of one repository state
have to produce one tree, and the rule that makes them is a property of the events themselves:
newest first by `sort_date`, the consolidated version's own date where the corpus resolved
one, else the detection date, with the version tag breaking a shared date. Why the two clocks
may never share a sort key is `clocks`' own story.

The rollup landed here on 2026-09-05, when the site started publishing rates about the corpus
a reader is browsing rather than only about the labelled subset the eval harness scores. It is
the same seam: a question asked of the committed entries and of nothing else. Nothing here
re-decides anything. Whether a change carries text, whether the signals disagreed and which of
them saw it are verdicts earlier stages reached and stored, and this module only counts them.

The rates come with their wording attached, in `CorpusRow`, on the same rule `eval_` publishes
its own rows under: the result and the sentence saying what it does not mean are fields of one
frozen object, so no page can print half of a measure and no caveat can be softened on one
surface and not the next. The rows carry plain text and no markup; escaping is the page's.

No clock, no network, no model: a rate on the page is a rollup of committed documents, and two
builds of one repository state produce the same numbers.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import SignalSet, SignalStatus
from emendrix.output import ChangelogEntry
from emendrix.site_.clocks import VersionDates, sort_date

__all__ = [
    "CorpusCounts",
    "CorpusRow",
    "DisputeShapes",
    "corpus_counts",
    "corpus_rows",
    "counted",
    "read_entries",
    "share",
    "sorted_entries",
]


def read_entries(root: Path) -> tuple[ChangelogEntry, ...]:
    """Every committed event in one output repository, in sorted path order.

    The layout and the documents are the output repository writer's own, so a file that does
    not validate means the repository was edited by hand or written by a different version of
    the schema: loud, named, and not something to skip quietly.
    """
    entries: list[ChangelogEntry] = []
    for path in sorted(root.glob("*/*/changes/*.json")):
        try:
            entries.append(ChangelogEntry.model_validate_json(path.read_bytes()))
        except ValueError as error:
            raise ValueError(f"{path} is not a changelog document emendrix wrote: {error}") from (
                error
            )
    return tuple(entries)


def sorted_entries(
    entries: list[ChangelogEntry], version_dates: VersionDates
) -> tuple[ChangelogEntry, ...]:
    """One act's events, newest first by `sort_date`, the version tag breaking a shared date."""
    return tuple(
        sorted(
            entries,
            key=lambda e: (sort_date(e, version_dates).isoformat(), e.key),
            reverse=True,
        )
    )


class DisputeShapes(BaseModel):
    """The shapes a disagreement takes, counted over the changes that ship marked `disputed`.

    Every disputed change falls in exactly one of the three, and which one is read off the
    verdicts the change carries, the same verdicts `site_.dispute` writes its per-change
    sentence from, so a count and the sentence beside it cannot tell different stories.

    The split is worth making because one number covers facts a reader would weigh
    differently: a provision whose text the comparison read and quoted, which another source
    merely did not enumerate, is not the same finding as a provision nothing could show at all.
    Naming them changes no verdict and withdraws no claim; all three still ship, still carry
    `disputed` in the JSON, and still count in the rate.
    """

    model_config = ConfigDict(frozen=True)

    evidenced: int = Field(
        default=0, ge=0, description="The text comparison saw it; another source did not list it."
    )
    no_text: int = Field(
        default=0, ge=0, description="The text comparison did not see it; another source named it."
    )
    kind: int = Field(
        default=0, ge=0, description="Every source that looked saw it, naming different kinds."
    )

    @property
    def total(self) -> int:
        """Every disagreement, whatever its shape. Equals the disputed count it was built from."""
        return self.evidenced + self.no_text + self.kind


class CorpusCounts(BaseModel):
    """What the committed entries one build renders come to, counted at the change.

    The unit is the change rather than the touched unit, so one denominator carries every
    figure the page prints. These are deliberately not the entries' own `EntryCounts`, which
    split touched *units* three ways: a unit holding both a change the comparison read and one
    it did not is substantive there and is two changes here, so the two answer different
    questions and are expected to read different numbers.
    """

    model_config = ConfigDict(frozen=True)

    events: int = Field(default=0, ge=0, description="Committed events this build renders.")
    changes: int = Field(default=0, ge=0, description="Changes across those events.")
    textless: int = Field(default=0, ge=0, description="Changes with no text on either side.")
    with_text: int = Field(default=0, ge=0, description="Changes carrying text on either side.")
    disputed: int = Field(default=0, ge=0, description="Changes the three sources disagree about.")
    explained: int = Field(default=0, ge=0, description="Changes shipping at least one sentence.")
    explained_with_text: int = Field(
        default=0, ge=0, description="Of the changes carrying text, those shipping a sentence."
    )
    shapes: DisputeShapes = DisputeShapes()


def share(part: int, whole: int) -> float | None:
    """The share, or `None` where there is nothing to take a share of.

    A rate over an empty corpus is not zero, and a page that printed `0.000` for one would be
    stating a measurement nobody made. `None` is the answer a renderer has to say out loud.
    """
    return None if whole == 0 else part / whole


def _shape(signals: SignalSet) -> str:
    """Which shape one disagreement is, from the verdicts alone.

    `UNAVAILABLE` is not a dissent, so only `ABSENT` tells the two presence shapes apart, and a
    disagreement with no absent source at all is one about kind. The structural diff is the
    only signal that carries text, which is what makes it the discriminator between a change a
    reader can see the words of and one nothing could show.
    """
    if not any(seen.status is SignalStatus.ABSENT for _, seen in signals.observations):
        return "kind"
    return "evidenced" if signals.structural_diff.observed else "no_text"


def corpus_counts(entries: Iterable[ChangelogEntry]) -> CorpusCounts:
    """Roll committed entries up into the figures the site publishes about its own corpus.

    Pure and total: it reads what earlier stages decided and decides nothing itself. An empty
    corpus counts to zeroes, which `share` turns into a stated non-answer rather than a rate.
    """
    events = changes = textless = disputed = explained = explained_with_text = 0
    shapes: Counter[str] = Counter()
    for entry in entries:
        events += 1
        for emitted in entry.changes:
            change = emitted.change
            changes += 1
            prose = bool(emitted.sentences)
            if prose:
                explained += 1
            if change.textless:
                textless += 1
            elif prose:
                explained_with_text += 1
            if change.disputed:
                disputed += 1
                shapes[_shape(change.signals)] += 1
    return CorpusCounts(
        events=events,
        changes=changes,
        textless=textless,
        with_text=changes - textless,
        disputed=disputed,
        explained=explained,
        explained_with_text=explained_with_text,
        shapes=DisputeShapes(
            evidenced=shapes["evidenced"], no_text=shapes["no_text"], kind=shapes["kind"]
        ),
    )


class CorpusRow(BaseModel):
    """One published rate: what it is, what it came out as, over what, and what it is not.

    The same shape the eval harness's own rows have, and for the same reason: the result and
    the sentence qualifying it are fields of one frozen object, so no renderer can print a
    number without the caveat that says what it does not mean. The strings are plain text and
    are escaped by whichever page prints them.
    """

    model_config = ConfigDict(frozen=True)

    measure: str
    result: str
    n: str
    meaning: str


def counted(number: int, noun: str) -> str:
    """`4,948 changes`. `markup.count` says the same without the thousands separator, which a
    corpus-wide n needs and a count of provisions on one page does not."""
    return f"{number:,} {noun}" if number == 1 else f"{number:,} {noun}s"


def _rate(part: int, whole: int) -> str:
    """`1,034 (0.404)`: a count and its share, or the count alone where there is no share."""
    taken = share(part, whole)
    return f"{part:,}" if taken is None else f"{part:,} ({taken:.3f})"


def corpus_rows(counts: CorpusCounts) -> tuple[CorpusRow, ...]:
    """The rates the site publishes about its own corpus, generated from the counts alone.

    The three shapes are indented under the rate they divide and take their share of the
    disputed total rather than of every change, so they read as parts of one number. Naming
    them withdraws nothing: all three ship, all three carry `disputed` in the JSON, and all
    three count in the rate above them.
    """
    changes = counted(counts.changes, "change")
    disputed = counted(counts.disputed, "disputed change")
    shapes = counts.shapes
    return (
        CorpusRow(
            measure="Changes the sources disagree about",
            result=_rate(counts.disputed, counts.changes),
            n=changes,
            meaning="At least one of the three sources emendrix checks named the change and "
            "another did not, or two of them named different kinds of change. `disputed` is a "
            "fact about the detectors and not a statement about the law: nothing is dropped for "
            "it and nothing is overruled. The three rows below say what each disagreement is.",
        ),
        CorpusRow(
            measure="…of those, found in the text and not listed elsewhere",
            result=_rate(shapes.evidenced, counts.disputed),
            n=disputed,
            meaning="The provision's own words are on the page, before and after. What disagrees "
            "is a reference set's granularity: a blanket amendment is annotated once and the "
            "provisions it lands on are not enumerated. **Not a change nobody could corroborate.**",
        ),
        CorpusRow(
            measure="…of those, named elsewhere with no difference in the text",
            result=_rate(shapes.no_text, counts.disputed),
            n=disputed,
            meaning="Nothing to quote on either side, so the row carries a location and the "
            "source that named it. Where neither an amending act nor its notice says when one of "
            "its instructions takes effect, that instruction is claimed in every consolidation "
            "window the act touches, so some of these are one instruction counted more than "
            "once.",
        ),
        CorpusRow(
            measure="…of those, found by every source that looked, called different things",
            result=_rate(shapes.kind, counts.disputed),
            n=disputed,
            meaning="The outright contradiction of the three: an insertion against a replacement, "
            "say. The smallest class in the corpus, and the one worth reading first.",
        ),
        CorpusRow(
            measure="Changes with no text on either side",
            result=_rate(counts.textless, counts.changes),
            n=changes,
            meaning="Neither a before nor an after text. Such a change exists only because a "
            "source other than the text comparison named a provision that comparison did not, so "
            "every one of them is also a disagreement above. **Not a change whose text is "
            "withheld**: there is none to show, and the row says so instead of disappearing.",
        ),
        CorpusRow(
            measure="Changes carrying an explanation",
            result=_rate(counts.explained, counts.changes),
            n=changes,
            meaning=f"Prose that survived the citation gate. Of the {counts.with_text:,} changes "
            f"carrying text at all, {_rate(counts.explained_with_text, counts.with_text)} do; a "
            "change with no text is never sent to a model, because there would be no evidence to "
            "write about. **Coverage, not quality**: whether the sentences are faithful is the "
            "sampled row below, and prose written before a later parser fix corrected the text it "
            "describes is left visible rather than quietly withdrawn.",
        ),
    )
