"""What the corroborator does with agreement, dissent and silence, on the toy corpus.

Core types only, no law: these are the scenarios the merge has to get right, written against
the second implementor of the seam so that nothing here can accidentally depend on EU
vocabulary. The real-corpus numbers live in `test_eu_corroboration.py`.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import (
    ActId,
    ChangeType,
    Delta,
    ProvisionLocation,
    Signal,
    SignalClaim,
    SignalReport,
    SignalStatus,
)
from emendrix.corroborate import agreement, corroborate
from emendrix.corroborate.report import SignalUnits
from emendrix.diff import compute_delta
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

OBSERVED_ON = date(2026, 8, 6)
IN_FORCE = date(2026, 6, 1)
AMENDER_ONE = ActId(corpus="toy", key="amender-1")
AMENDER_TWO = ActId(corpus="toy", key="amender-2")


@pytest.fixture
def delta() -> Delta:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON)
    before = adapter.fetch_version(HOUSE_RULES, V1)
    after = adapter.fetch_version(HOUSE_RULES, V2)
    assert not isinstance(before, Exception)
    return compute_delta(before, after)  # type: ignore[arg-type]


def claim(
    location: str,
    kind: ChangeType | None = None,
    in_force: date | None = None,
    amending_act: ActId | None = None,
) -> SignalClaim:
    return SignalClaim(
        location=ProvisionLocation.parse(location),
        change_type=kind,
        in_force=in_force,
        amending_act=amending_act,
    )


def report(signal: Signal, *claims: SignalClaim) -> SignalReport:
    return SignalReport(signal=signal, claims=claims)


def units(delta: Delta) -> set[str]:
    return {change.unit.canonical for change in delta.changes}


# ------------------------------------------------------------------- the baseline


def test_the_toy_delta_is_what_the_scenarios_are_built_on(delta: Delta) -> None:
    """`AR 2` modified, `AR 3` deleted, `AR 4` inserted, `AN I` modified."""
    assert units(delta) == {"AR 2", "AR 3", "AR 4", "AN I"}
    assert delta.summary.disputed == 0


def test_a_signal_nobody_supplied_is_unavailable_and_never_dissents(delta: Delta) -> None:
    """The whole point of `UNAVAILABLE`: a corpus with no metadata is not disagreeing."""
    merged = corroborate(delta)
    assert merged.disputed == 0
    for change in merged.delta.changes:
        assert change.signals.corpus_metadata.status is SignalStatus.UNAVAILABLE
        assert change.signals.instruction_parse.status is SignalStatus.UNAVAILABLE
        assert change.signals.structural_diff.observed
    assert merged.report.agreements == ()


# ---------------------------------------------------------------- full agreement


def test_full_agreement_produces_no_disputes(delta: Delta) -> None:
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 2 PA 1", ChangeType.MODIFIED, in_force=IN_FORCE),
        claim("AR 3", ChangeType.DELETED, in_force=IN_FORCE),
        claim("AR 4", ChangeType.INSERTED, in_force=IN_FORCE),
        claim("AN I SLOT 2", ChangeType.MODIFIED, in_force=IN_FORCE),
    )
    merged = corroborate(delta, metadata=metadata)
    assert merged.disputed == 0
    assert merged.report.disagreements == ()
    pair = merged.report.agreement_of(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA)
    assert pair is not None
    assert (pair.precision, pair.recall, pair.f1) == (1.0, 1.0, 1.0)
    assert pair.kind_mismatches == 0


def test_the_metadata_clock_lands_on_every_change_it_covers(delta: Delta) -> None:
    """Clock 1: `in_force` is the corpus's, not the diff's; the diff cannot see it."""
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 2", ChangeType.MODIFIED, in_force=IN_FORCE),
    )
    merged = corroborate(delta, metadata=metadata)
    stamped = {c.unit.canonical: c.in_force for c in merged.delta.changes}
    assert stamped["AR 2"] == IN_FORCE
    assert stamped["AR 4"] is None


def test_a_deeper_claim_is_counted_under_its_unit(delta: Delta) -> None:
    """`AR 2 PA 1 PTA (a)` is a claim about `AR 2`, and the vocabularies elide segments."""
    metadata = report(Signal.CORPUS_METADATA, claim("AR 2 PA 1 PTA (a)", ChangeType.INSERTED))
    merged = corroborate(delta, metadata=metadata)
    change = next(c for c in merged.delta.changes if c.unit.canonical == "AR 2")
    assert change.signals.corpus_metadata.observed
    # Inserting a point *into* `AR 2` is a modification of `AR 2`, not an insertion of it.
    assert change.signals.corpus_metadata.change_types == (ChangeType.MODIFIED,)
    assert change.disputed is False


# ------------------------------------------------------------------- disagreement


def test_a_unit_the_diff_missed_is_appended_disputed_and_textless(delta: Delta) -> None:
    """Never silently dropped. The diff carries the text, so this change has none."""
    metadata = report(Signal.CORPUS_METADATA, claim("AR 9", ChangeType.MODIFIED, in_force=IN_FORCE))
    merged = corroborate(delta, metadata=metadata)
    assert "AR 9" in units(merged.delta)
    extra = next(c for c in merged.delta.changes if c.unit.canonical == "AR 9")
    assert extra.before is None and extra.after is None
    assert extra.change_type is ChangeType.MODIFIED
    assert extra.in_force == IN_FORCE
    assert extra.signals.structural_diff.status is SignalStatus.ABSENT
    assert extra.disputed
    assert merged.report.metadata_only_units == (ProvisionLocation.parse("AR 9"),)


def test_an_appended_change_lands_among_its_neighbours(delta: Delta) -> None:
    """The diff's document order is preserved and the extra is placed inside it, not after it.

    A changelog reader reads in document order; a clump of corroboration-only changes at the
    end would be the one place nothing is where it belongs.
    """
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 9", ChangeType.MODIFIED),
        claim("AR 1", ChangeType.MODIFIED),
    )
    merged = corroborate(delta, metadata=metadata)
    assert [change.location.canonical for change in merged.delta.changes] == [
        "AR 1",
        "AR 2",
        "AR 3",
        "AR 4",
        "AR 9",
        "AN I",
    ]


def test_the_diffs_own_order_survives_corroboration(delta: Delta) -> None:
    before = [change.location.canonical for change in delta.changes]
    after = [change.location.canonical for change in corroborate(delta).delta.changes]
    assert after == before


def test_a_unit_only_the_diff_saw_is_disputed_with_a_reason(delta: Delta) -> None:
    metadata = report(Signal.CORPUS_METADATA, claim("AR 2", ChangeType.MODIFIED))
    merged = corroborate(delta, metadata=metadata)
    assert merged.disputed == 3
    reasons = {d.unit.canonical: d.reason for d in merged.report.disagreements}
    assert reasons["AR 4"] == "seen by structural_diff, not by corpus_metadata"
    disagreement = next(d for d in merged.report.disagreements if d.unit.canonical == "AR 4")
    assert disagreement.observed_by == (Signal.STRUCTURAL_DIFF,)
    assert disagreement.absent_from == (Signal.CORPUS_METADATA,)


def test_a_kind_mismatch_is_a_dispute_even_when_both_signals_saw_it(delta: Delta) -> None:
    """The diff says `AR 4` was inserted; a signal that says it was deleted is dissent."""
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 2", ChangeType.MODIFIED),
        claim("AR 3", ChangeType.DELETED),
        claim("AR 4", ChangeType.DELETED),
        claim("AN I", ChangeType.MODIFIED),
    )
    merged = corroborate(delta, metadata=metadata)
    change = next(c for c in merged.delta.changes if c.unit.canonical == "AR 4")
    assert change.signals.corpus_metadata.observed
    assert change.disputed
    disagreement = next(d for d in merged.report.disagreements if d.unit.canonical == "AR 4")
    assert disagreement.reason == "signals disagree on the kind of change"
    assert dict(disagreement.kinds)[Signal.CORPUS_METADATA] == (ChangeType.DELETED,)
    pair = merged.report.agreement_of(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA)
    assert pair is not None
    assert pair.f1 == 1.0  # the *units* agree perfectly; the classification does not
    assert pair.kind_mismatches == 1


def test_a_signal_that_names_no_kind_never_disagrees_about_one(delta: Delta) -> None:
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 2"),
        claim("AR 3"),
        claim("AR 4"),
        claim("AN I"),
    )
    merged = corroborate(delta, metadata=metadata)
    assert merged.disputed == 0


def test_two_signals_that_both_saw_a_unit_in_one_of_several_ways_agree(delta: Delta) -> None:
    """One unit can carry several claims: inserted points beside replaced ones."""
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 2", ChangeType.MODIFIED),
        claim("AR 2 PA 4", ChangeType.INSERTED),
    )
    merged = corroborate(delta, metadata=metadata)
    change = next(c for c in merged.delta.changes if c.unit.canonical == "AR 2")
    assert change.signals.corpus_metadata.change_types == (ChangeType.MODIFIED,)
    assert change.disputed is False


# ----------------------------------------------------------------- three signals


def test_all_three_signals_are_recorded_and_scored_pairwise(delta: Delta) -> None:
    metadata = report(
        Signal.CORPUS_METADATA,
        claim("AR 2", ChangeType.MODIFIED),
        claim("AR 3", ChangeType.DELETED),
        claim("AR 4", ChangeType.INSERTED),
        claim("AN I", ChangeType.MODIFIED),
    )
    instructions = report(
        Signal.INSTRUCTION_PARSE,
        claim("AR 2", ChangeType.MODIFIED),
        claim("AR 3", ChangeType.DELETED),
        claim("AR 4", ChangeType.INSERTED),
    )
    merged = corroborate(delta, metadata=metadata, instructions=instructions)
    assert [item.signal for item in merged.report.signals] == [
        Signal.STRUCTURAL_DIFF,
        Signal.CORPUS_METADATA,
        Signal.INSTRUCTION_PARSE,
    ]
    assert len(merged.report.agreements) == 3
    against_prose = merged.report.agreement_of(Signal.STRUCTURAL_DIFF, Signal.INSTRUCTION_PARSE)
    assert against_prose is not None
    assert against_prose.precision == 0.75
    assert against_prose.recall == 1.0
    # `AN I` is seen by the diff and the metadata but not by the instruction parse.
    assert merged.disputed == 1


def test_an_explicitly_unavailable_signal_takes_no_part_in_the_scores(delta: Delta) -> None:
    merged = corroborate(
        delta,
        metadata=SignalReport.unavailable(Signal.CORPUS_METADATA, note="no metadata published"),
    )
    assert merged.disputed == 0
    assert merged.report.agreements == ()
    change = merged.delta.changes[0]
    assert change.signals.corpus_metadata.detail == "no metadata published"


# ------------------------------------------------------------------ the amending act


def test_a_change_carries_every_act_a_signal_names_as_amending_it(delta: Delta) -> None:
    """Two annotations of one unit by two acts ship as two entries, deduplicated, in order."""
    merged = corroborate(
        delta,
        metadata=report(
            Signal.CORPUS_METADATA,
            claim("AR 2", ChangeType.MODIFIED, amending_act=AMENDER_ONE),
            claim("AR 2", ChangeType.MODIFIED, amending_act=AMENDER_ONE),
            claim("AR 2", ChangeType.MODIFIED, amending_act=AMENDER_TWO),
        ),
    )
    change = next(c for c in merged.delta.changes if c.unit.canonical == "AR 2")
    assert change.amending_acts == (AMENDER_ONE, AMENDER_TWO)


def test_a_change_no_signal_attributes_carries_an_empty_tuple(delta: Delta) -> None:
    """The honest value when nothing names an amender. Never guessed from the diff."""
    merged = corroborate(delta)
    assert all(change.amending_acts == () for change in merged.delta.changes)


def test_an_appended_change_carries_the_amending_act_that_named_its_unit(delta: Delta) -> None:
    """A unit only the metadata saw still ships knowing which act amended it."""
    merged = corroborate(
        delta,
        metadata=report(
            Signal.CORPUS_METADATA,
            claim("AR 9", ChangeType.MODIFIED, amending_act=AMENDER_ONE),
        ),
    )
    appended = next(c for c in merged.delta.changes if c.unit.canonical == "AR 9")
    assert appended.disputed
    assert appended.amending_acts == (AMENDER_ONE,)


# ------------------------------------------------------------- the published claims


def test_the_report_publishes_each_signals_claims_at_the_depth_they_were_made(
    delta: Delta,
) -> None:
    """The corpus annotates sub-provisions, and the report publishes them at that depth."""
    merged = corroborate(
        delta,
        metadata=report(
            Signal.CORPUS_METADATA,
            claim("AR 2 PA 1", ChangeType.MODIFIED, amending_act=AMENDER_ONE),
        ),
    )
    published = next(
        item for item in merged.report.signals if item.signal is Signal.CORPUS_METADATA
    )
    assert published.units == (ProvisionLocation.parse("AR 2"),)
    assert [c.location.canonical for c in published.claims] == ["AR 2 PA 1"]
    assert published.claims[0].amending_act == AMENDER_ONE


def test_the_structural_diff_publishes_no_claims_because_it_publishes_the_changes(
    delta: Delta,
) -> None:
    """Its claims would be a second copy of the delta, which is the thing to avoid."""
    merged = corroborate(delta)
    diff = next(item for item in merged.report.signals if item.signal is Signal.STRUCTURAL_DIFF)
    assert diff.claims == ()
    assert diff.units


# ---------------------------------------------------------------------- the metric


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (("AR 1", "AR 2"), ("AR 1", "AR 2"), (1.0, 1.0, 1.0)),
        (("AR 1",), ("AR 1", "AR 2"), (1.0, 0.5)),
        ((), (), (1.0, 1.0, 1.0)),
        ((), ("AR 1",), (1.0, 0.0, 0.0)),
    ],
)
def test_agreement_is_directional_and_defined_on_empty_sets(
    left: tuple[str, ...], right: tuple[str, ...], expected: tuple[float, ...]
) -> None:
    def side(signal: Signal, names: tuple[str, ...]) -> SignalUnits:
        return SignalUnits(
            signal=signal, units=tuple(ProvisionLocation.parse(name) for name in names)
        )

    scored = agreement(side(Signal.STRUCTURAL_DIFF, left), side(Signal.CORPUS_METADATA, right))
    assert scored.precision == expected[0]
    assert scored.recall == expected[1]


def test_the_merged_delta_is_byte_stable(delta: Delta) -> None:
    """Changelogs are diffed in git, so two runs must serialise identically."""
    metadata = report(Signal.CORPUS_METADATA, claim("AR 9", ChangeType.MODIFIED))
    first = corroborate(delta, metadata=metadata)
    second = corroborate(delta, metadata=metadata)
    assert first.model_dump_json() == second.model_dump_json()
