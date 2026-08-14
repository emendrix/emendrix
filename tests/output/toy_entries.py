"""Changelog entries built on the toy corpus, so the renderers are tested on no law at all.

The output package is generic by design: it renders `graph.report.EmittedDelta`, which knows
nothing about any corpus, and these fixtures are how that stays true rather than merely
claimed. Every entry here comes from `tests/toy_corpus.py`: a flat's house rules, four
provisions, one location code outside the vocabulary, and citations pointing at
`example.invalid`.

The real-corpus rendering is the golden file in `test_markdown.py`, which is the MDR
transition through the whole shipped command.
"""

from __future__ import annotations

from datetime import date

from emendrix.core import Delta, ProvisionLocation, Signal, SignalClaim, SignalReport
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.explain import NO_EVIDENCE_PAST_CAP
from emendrix.gate import GateOutcome
from emendrix.graph.report import EmittedChange, EmittedDelta, EmittedSentence
from emendrix.output import ChangelogEntry, diff_only_entry
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED_ON = date(2026, 8, 6)
"""Passed in everywhere; nothing in the output package may read a clock."""

ADAPTER = ToyCorpusAdapter(observed_on=OBSERVED_ON)


def toy_delta() -> Delta:
    """The house rules, v1 → v2: one modification, one deletion, two insertions."""
    before = ADAPTER.fetch_version(HOUSE_RULES, V1)
    after = ADAPTER.fetch_version(HOUSE_RULES, V2)
    assert not isinstance(before, Exception) and not isinstance(after, Exception)
    return compute_delta(before, after)  # type: ignore[arg-type]


def toy_entry() -> ChangelogEntry:
    """The diff-only entry: what `emendrix diff --markdown` produces."""
    return diff_only_entry(toy_delta(), detected_on=OBSERVED_ON)


def disputed_delta() -> Delta:
    """The transition corroborated against a metadata signal that names one extra unit.

    `AR 9` exists in neither version, so the structural diff is `ABSENT` on it and the merge
    ships it `disputed` with no text at all: the case the changelog must render and mark
    rather than drop.
    """
    delta = toy_delta()
    metadata = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(
            *(
                SignalClaim(location=change.unit, change_type=change.change_type)
                for change in delta.changes
            ),
            SignalClaim(location=ProvisionLocation.parse("AR 9")),
        ),
    )
    return corroborate(delta, metadata=metadata).delta


def disputed_entry() -> ChangelogEntry:
    return diff_only_entry(disputed_delta(), detected_on=OBSERVED_ON)


def no_evidence_entry() -> ChangelogEntry:
    """An entry whose one change was never sent to the model, because the cap emptied its prompt.

    The reason is the shipped constant, not a copy of it, so the rendering test reads back exactly
    what a reader would see. The entry still carries both verbatim texts, which is the point: a
    change is never dropped for the cap's benefit.
    """
    delta = toy_delta()
    first, *rest = delta.changes
    return ChangelogEntry.of(
        EmittedDelta(
            act=delta.act,
            from_version=delta.from_version,
            to_version=delta.to_version,
            summary=delta.summary,
            changes=(
                EmittedChange(
                    change=first,
                    outcome=GateOutcome.UNEXPLAINED,
                    unexplained=NO_EVIDENCE_PAST_CAP,
                ),
                *(EmittedChange(change=change, outcome=GateOutcome.UNEXPLAINED) for change in rest),
            ),
        ),
        detected_on=OBSERVED_ON,
    )


def explained_entry() -> ChangelogEntry:
    """An entry carrying prose: the first sentence the model wrote, the rest the gate did.

    The words are inventions of this fixture. What is under test is the *rendering of the two
    provenances*; nothing in this suite asserts anything about explanation quality.
    """
    delta = toy_delta()
    changes = tuple(
        EmittedChange(
            change=change,
            outcome=GateOutcome.FALLBACK if index else GateOutcome.PASSED,
            sentences=(
                EmittedSentence(
                    text="Something about this provision changed.",
                    fallback=bool(index),
                    citations=(ADAPTER.render_citation(change.provision),),
                ),
            ),
        )
        for index, change in enumerate(delta.changes)
    )
    return ChangelogEntry.of(
        EmittedDelta(
            act=delta.act,
            from_version=delta.from_version,
            to_version=delta.to_version,
            summary=delta.summary,
            changes=changes,
        ),
        detected_on=OBSERVED_ON,
    )
