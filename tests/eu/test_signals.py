"""The two second opinions the loop asks the EU adapter for, per version pair.

Read from the pinned fixture set, so these assertions are about what the corpus published and
not about what a network happened to answer. The MDR is the act to test this on because its
seven consolidations put every availability case in one notice: a pair the corpus annotated
nowhere, a pair it annotated once, and a pair it annotated twenty-six times.
"""

from __future__ import annotations

import pytest

from emendrix.core import ActId, Signal, SignalReport, VersionId
from emendrix.eu.cellar import CellarClient
from emendrix.eu.signals import EuSignalSource
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
