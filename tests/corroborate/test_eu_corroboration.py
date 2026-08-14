"""Three-way corroboration over the pinned EU transitions: the headline claim, measured.

The structural diff was also measured against the corpus metadata by a standalone script on
2026-08-05 (`scripts/validation/`). This reproduces that a second way through the shipped
code, and adds the third signal: the amending act's own instructions. **If one of these
numbers moves, that is a finding to explain, not a test to update.**

The REACH row is the interesting one and is deliberately not curated out: it is the blanket
amendment where the reference set is the incomplete signal and the diff is right.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import ActId, Delta, ProvisionLocation, Signal, SignalReport, SignalStatus
from emendrix.corroborate import Corroboration, corroborate
from emendrix.diff import compute_delta
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import parse_act
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.instructions import instruction_signal, parse_instructions
from emendrix.eu.modmeta import metadata_signal, parse_branch_modifications
from eu_pins import (
    AI_ACT,
    AI_ACT_V2,
    CLP,
    DIGITAL_OMNIBUS,
    MDR,
    MDR_POSTPONEMENT,
    MDR_V1,
    MDR_V2,
    REACH,
    REACH_2008,
    REACH_2009,
    package,
)

AI_ACT_OJ = AI_ACT
"""The act as published in the OJ is its own version tag (`eu/identifiers.py`)."""


def delta(client: CellarClient, celex: str, before: str, after: str) -> Delta:
    return compute_delta(
        parse_act(package(client, celex, before)).tree,
        parse_act(package(client, celex, after)).tree,
    )


def metadata(client: CellarClient, celex: str, after: date | None, until: date) -> SignalReport:
    """The annotations whose `START_OF_VALIDITY` falls in this version pair's window."""
    notice = parse_branch_modifications(client.branch_notice(Celex.parse(celex)))
    return metadata_signal(notice.between(after, until))


def instructions(client: CellarClient, amender: str, amended: ActId) -> SignalReport:
    return instruction_signal(parse_instructions(package(client, amender, amender)), amended)


@pytest.fixture
def ai_act(client: CellarClient) -> Corroboration:
    return corroborate(
        delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2),
        metadata=metadata(client, AI_ACT, None, date(2026, 7, 27)),
        instructions=instructions(client, DIGITAL_OMNIBUS, act_id(Celex.parse(AI_ACT))),
    )


@pytest.fixture
def mdr(client: CellarClient) -> Corroboration:
    return corroborate(
        delta(client, MDR, MDR_V1, MDR_V2),
        metadata=metadata(client, MDR, date(2017, 5, 5), date(2020, 4, 24)),
        instructions=instructions(client, MDR_POSTPONEMENT, act_id(Celex.parse(MDR))),
    )


@pytest.fixture
def reach(client: CellarClient) -> Corroboration:
    """The CLP transition. Its amending act is 3.3 MB of Formex and is deliberately unpinned,
    so the third signal is `UNAVAILABLE` here, which is not the same as dissent."""
    return corroborate(
        delta(client, REACH, REACH_2008, REACH_2009),
        metadata=metadata(client, REACH, date(2008, 10, 12), date(2009, 1, 20)),
        instructions=SignalReport.unavailable(
            Signal.INSTRUCTION_PARSE, note=f"{CLP} is not pinned: 3.3 MB of Formex"
        ),
    )


# ------------------------------------------------------------------- the flagship


def test_all_three_signals_agree_completely_on_the_flagship(ai_act: Corroboration) -> None:
    """The flagship's F1 = 1.000, now three-way and at unit granularity, annexes included."""
    for pair in ai_act.report.agreements:
        assert (pair.precision, pair.recall, pair.f1) == (1.0, 1.0, 1.0), pair
        assert pair.kind_mismatches == 0
    assert len(ai_act.report.agreements) == 3
    assert [item.count for item in ai_act.report.signals] == [45, 45, 45]


def test_nothing_on_the_flagship_ships_disputed(ai_act: Corroboration) -> None:
    assert ai_act.disputed == 0
    assert ai_act.report.disagreements == ()
    assert ai_act.report.metadata_only_units == ()
    assert len(ai_act.delta.changes) == 45


def test_every_flagship_change_carries_the_metadata_clock(ai_act: Corroboration) -> None:
    """Clock 1: `START_OF_VALIDITY` is where `in_force` comes from, on every change."""
    assert {change.in_force for change in ai_act.delta.changes} == {date(2026, 7, 27)}


def test_every_flagship_change_records_all_three_verdicts(ai_act: Corroboration) -> None:
    for change in ai_act.delta.changes:
        for _, seen in change.signals.observations:
            assert seen.status is SignalStatus.OBSERVED
        assert change.signals.observed_by == (
            Signal.STRUCTURAL_DIFF,
            Signal.CORPUS_METADATA,
            Signal.INSTRUCTION_PARSE,
        )


def test_the_flagship_insertions_are_insertions_to_all_three_signals(
    ai_act: Corroboration,
) -> None:
    """`4a`, `60a`, `75a` to `75d` and `AN XIV`, classified the same way by three sources."""
    inserted = {
        change.unit.canonical
        for change in ai_act.delta.changes
        if change.signals.corpus_metadata.change_types == ("INSERTED",)
    }
    assert inserted == {"AR 4a", "AR 60a", "AR 75a", "AR 75b", "AR 75c", "AR 75d", "AN XIV"}


# ------------------------------------------------------------------ a second act


def test_the_mdr_postponement_agrees_three_ways_as_well(mdr: Corroboration) -> None:
    """The MDR row, with the third signal added: 9 units, no dissent, one date."""
    assert [item.count for item in mdr.report.signals] == [9, 9, 9]
    for pair in mdr.report.agreements:
        assert (pair.precision, pair.recall, pair.f1) == (1.0, 1.0, 1.0), pair
    assert mdr.disputed == 0
    assert {change.in_force for change in mdr.delta.changes} == {date(2020, 4, 24)}


def test_every_mdr_change_names_the_act_that_postponed_it(mdr: Corroboration) -> None:
    """The one amender of this transition is Regulation (EU) 2020/561, structured not parsed.

    Both signals name it: the branch notice's annotations and the amending act's own
    instructions. `ActId` hashes on `(corpus, key)`, so it appears once per change.
    """
    expected = (ActId(corpus="eu", key=MDR_POSTPONEMENT),)
    assert all(change.amending_acts == expected for change in mdr.delta.changes)


def test_a_deferral_is_not_a_disagreement_with_a_replacement(mdr: Corroboration) -> None:
    """`DEFERRED` refines `MODIFIED`; the metadata's `R` is not dissenting from it."""
    deferred = [c for c in mdr.delta.changes if c.change_type.value == "DEFERRED"]
    assert len(deferred) == 6
    assert all(not change.disputed for change in deferred)
    assert all(change.signals.corpus_metadata.change_types == ("MODIFIED",) for change in deferred)


# ------------------------------------------------- the reference set being wrong


def test_the_blanket_amendment_disagrees_and_ships_the_disagreement(
    reach: Corroboration,
) -> None:
    """CELLAR annotates "throughout the text" once and does not enumerate where it lands.

    The diff finds 40 units, the annotations name 9. That is a defect in the *reference* set,
    and the corroborator's job is to publish it, not to resolve it.
    """
    pair = reach.report.agreement_of(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA)
    assert pair is not None
    assert (pair.left_units, pair.right_units, pair.shared) == (40, 9, 8)
    assert round(pair.precision, 3) == 0.200
    assert round(pair.recall, 3) == 0.889
    assert round(pair.f1, 3) == 0.327
    assert pair.kind_mismatches == 0


def test_nothing_is_dropped_when_the_signals_disagree(reach: Corroboration) -> None:
    """32 units only the diff saw, 1 only the metadata named: 33 disputed, 0 lost."""
    assert len(reach.delta.changes) == 41
    assert reach.disputed == 33
    assert len(reach.report.disagreements) == 33


def test_a_unit_the_diff_cannot_key_still_ships(reach: Corroboration) -> None:
    """`TIT XI` is a title, not an article or an annex, so it has no diff-side unit.

    Discarding such a unit is forbidden, and it is the difference between counting 8 metadata
    units on this transition and counting 9. Here it is a metadata-only change: a location, a
    kind, no text, and `disputed`.
    """
    assert reach.report.metadata_only_units == (ProvisionLocation.parse("TIT XI"),)
    stray = next(c for c in reach.delta.changes if c.unit.canonical == "TIT XI")
    assert stray.before is None and stray.after is None
    assert stray.signals.structural_diff.status is SignalStatus.ABSENT
    assert stray.disputed
    assert stray.in_force == date(2009, 1, 20)


def test_an_unpinned_amending_act_is_silence_not_dissent(reach: Corroboration) -> None:
    """Only one pair is scored, because only two signals were computable."""
    assert len(reach.report.agreements) == 1
    for change in reach.delta.changes:
        assert change.signals.instruction_parse.status is SignalStatus.UNAVAILABLE


# ------------------------------------------------------------------- determinism


def test_the_corroborated_flagship_is_byte_stable(client: CellarClient) -> None:
    computed = delta(client, AI_ACT, AI_ACT_OJ, AI_ACT_V2)
    signal = metadata(client, AI_ACT, None, date(2026, 7, 27))
    assert (
        corroborate(computed, metadata=signal).model_dump_json()
        == corroborate(computed, metadata=signal).model_dump_json()
    )
