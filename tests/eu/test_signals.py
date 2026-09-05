"""The two second opinions the loop asks the EU adapter for, per version pair.

Read from the pinned fixture set, so these assertions are about what the corpus published and
not about what a network happened to answer. The MDR is the act to test this on because its
seven consolidations put every availability case in one notice: a pair the corpus annotated
nowhere, a pair it annotated once, and a pair it annotated twenty-six times.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import ActId, Signal, SignalReport, VersionId
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex
from emendrix.eu.signals import EuSignalSource, instruction_signal_for
from eu_pins import MDR

MDR_ACT = ActId(corpus="eu", key=MDR)


@pytest.fixture
def source(client: CellarClient) -> EuSignalSource:
    return EuSignalSource(client)


def both(
    source: EuSignalSource, from_version: str, to_version: str
) -> tuple[SignalReport, SignalReport]:
    """Both reports for one MDR pair. This adapter always answers with two, never with `None`.

    `TransitionSignals` allows `None` for a corpus that holds neither capability, and the
    narrowing is done here so every assertion below reads as one line about one number.
    """
    pair = source.signals_for(MDR_ACT, VersionId(from_version), VersionId(to_version))
    assert pair.metadata is not None and pair.instructions is not None
    return pair.metadata, pair.instructions


def test_a_pair_the_corpus_annotated_nowhere_yields_two_unavailable_signals(
    source: EuSignalSource,
) -> None:
    """The act as published against the consolidation dated the same day.

    Nothing can have amended the act before it existed, so neither second opinion has anything
    to say about this pair and both say so. Until the definition was corrected on 2026-08-12 the
    metadata report came back available with zero claims, which left every unit the structural
    diff found here `ABSENT` and shipped all fifteen of them `disputed` against a reference set
    that was never published. Both notes are kept, because a stated absence is worth more than a
    bare `False`.
    """
    metadata, instructions = both(source, MDR, "02017R0745-20170505")
    assert metadata.signal is Signal.CORPUS_METADATA
    assert metadata.available is False
    assert metadata.note == "0 annotations in (the act itself, 2017-05-05]"
    assert instructions.available is False
    assert instructions.note == "no amending act in this window"


def test_a_pair_the_corpus_did_annotate_yields_an_available_reference_set(
    source: EuSignalSource,
) -> None:
    """The postponement: 26 annotations over 9 units, and the prose of one amending act."""
    metadata, instructions = both(source, "02017R0745-20170505", "02017R0745-20200424")
    assert metadata.available is True
    assert len(metadata.units) == 9
    assert metadata.note == "26 annotations in (2017-05-05, 2020-04-24]"
    assert instructions.available is True


def test_a_single_annotation_is_still_a_reference_set(source: EuSignalSource) -> None:
    """The rule turns on the window being annotated at all, not on how richly.

    One claim is enough for the units the diff finds beyond it to be real disagreements, which
    is what keeps the blanket-amendment finding intact: a source that under-enumerates where an
    amendment lands is dissenting, a source that never spoke is not.
    """
    metadata, _ = both(source, "02017R0745-20200424", "02017R0745-20230311")
    assert metadata.available is True
    assert len(metadata.units) == 1


def test_a_pair_the_tree_notice_does_not_date_yields_no_metadata_signal(
    source: EuSignalSource,
) -> None:
    """Guessing a window would quietly widen or narrow the reference set, so it is refused.

    The note names the version rather than the rule, so the reason survives into the output.
    """
    metadata, instructions = both(source, MDR, "02017R0745-19000101")
    assert metadata.available is False
    assert metadata.note is not None and "02017R0745-19000101" in metadata.note
    assert instructions.available is False


def test_the_window_reaches_the_third_signal_and_not_only_the_second(
    source: EuSignalSource,
) -> None:
    """`32024R1860` orders MDR Article 10a into existence from 10 January 2025.

    The consolidation that ends on 9 July 2024 reads the same amending act, reads all six of
    the units it names for the MDR, and claims the five whose date the act does not put after
    the window. Before the window reached this signal it claimed all six, so the reader of a
    version of 9 July 2024 was told a provision it does not contain had changed in it.
    """
    metadata, instructions = both(source, "02017R0745-20230320", "02017R0745-20240709")
    assert metadata.note == "18 annotations in (2023-03-20, 2024-07-09]"
    assert instructions.available is True
    assert [unit.canonical for unit in instructions.units] == [
        "AR 34",
        "AR 78",
        "AR 120",
        "AR 122",
        "AR 123",
    ]


def test_the_signal_note_says_what_the_window_left_out_and_what_it_could_not_date(
    source: EuSignalSource,
) -> None:
    """Both counts ride in the payload, so an empty signal and a scoped one are told apart
    without leaving it. The undated thirteen are claimed, which is why the note names them."""
    _, instructions = both(source, "02017R0745-20230320", "02017R0745-20240709")
    assert instructions.note == (
        "32024R1860, 1.000 of its instruction clauses read, "
        "1 dated outside the window, 13 undated and claimed"
    )


def test_the_composition_root_hands_the_parse_the_act_s_own_published_dates(
    source: EuSignalSource,
) -> None:
    """`32020R0561` gives its own text no day and its notice publishes one: 24 April 2020.

    The note is where that shows: every one of its instructions is dated now, where the act's
    own words dated none of them. The notice is fetched here, in the composition root, and
    reaches the parse as a value.
    """
    _, instructions = both(source, "02017R0745-20170505", "02017R0745-20200424")
    assert instructions.note == (
        "32020R0561, 1.000 of its instruction clauses read, "
        "0 dated outside the window, 0 undated and claimed"
    )
    assert len(instructions.units) == 9


def test_the_same_amending_act_claims_different_units_in_two_windows(
    client: CellarClient,
) -> None:
    """One act, read once, claimed twice: the replay this scoping exists to stop.

    `instruction_signal_for` is the composition root's own entry point, and the window is the
    only thing that differs between these two calls. The MDR's 2024 amender is the pinned act
    that carries the shape: one of its points is deferred by its own final provisions and the
    rest are dated nowhere, so the later window gains the deferred unit and keeps the undated
    ones rather than exchanging one set for another.
    """
    early, late = (
        instruction_signal_for(
            client, Celex.parse("32024R1860"), MDR_ACT, window=(date(2023, 3, 20), until)
        )
        for until in (date(2024, 7, 9), date(2025, 1, 10))
    )
    early_units = {unit.canonical for unit in early.units}
    late_units = {unit.canonical for unit in late.units}
    assert late_units - early_units == {"AR 10a"}
    assert early_units < late_units
