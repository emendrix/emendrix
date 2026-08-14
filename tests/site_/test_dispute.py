"""The disagreement sentence: one phrasing per pattern, and no unavailable source in it.

Every pattern the committed corpus produces is exercised here by its verdicts alone, because
that is all the wording depends on. Six of them are disagreements about *presence* (one or two
sources found the change and the rest looked and did not) and the seventh is a disagreement
about *kind*, which has to read as one: the sources agreed the provision moved.

The expected sentences are written out in full rather than pattern-matched. A wording this
short is only worth testing if the test can be read as the wording.
"""

from __future__ import annotations

import pytest

from emendrix.core import ChangeType, Signal, SignalObservation, SignalSet, SignalStatus
from emendrix.site_.dispute import dispute_note

OBSERVED = SignalObservation(status=SignalStatus.OBSERVED)
ABSENT = SignalObservation(status=SignalStatus.ABSENT)
UNAVAILABLE = SignalObservation(status=SignalStatus.UNAVAILABLE)

DIFF = "the text comparison"
META = "the EU's own amendment metadata"
PROSE = "the amending act's instructions"

_NAMES = {
    Signal.STRUCTURAL_DIFF: DIFF,
    Signal.CORPUS_METADATA: META,
    Signal.INSTRUCTION_PARSE: PROSE,
}


def _set(diff: SignalObservation, meta: SignalObservation, prose: SignalObservation) -> SignalSet:
    return SignalSet(structural_diff=diff, corpus_metadata=meta, instruction_parse=prose)


# ------------------------------------------------------------------ the seven patterns

PRESENCE = [
    pytest.param(
        _set(OBSERVED, ABSENT, OBSERVED),
        f"{DIFF} and {PROSE} found this change; {META} does not list it. "
        "All are shown; none is overruled.",
        id="diff-and-prose-not-metadata",
    ),
    pytest.param(
        _set(ABSENT, ABSENT, OBSERVED),
        f"{PROSE} found this change; {DIFF} finds no difference in the provision's text and "
        f"{META} does not list it. All are shown; none is overruled.",
        id="prose-only",
    ),
    pytest.param(
        _set(OBSERVED, OBSERVED, ABSENT),
        f"{DIFF} and {META} found this change; {PROSE} do not mention it. "
        "All are shown; none is overruled.",
        id="diff-and-metadata-not-prose",
    ),
    pytest.param(
        _set(ABSENT, OBSERVED, ABSENT),
        f"{META} found this change; {DIFF} finds no difference in the provision's text and "
        f"{PROSE} do not mention it. All are shown; none is overruled.",
        id="metadata-only",
    ),
    pytest.param(
        _set(OBSERVED, ABSENT, ABSENT),
        f"{DIFF} found this change; {META} does not list it and {PROSE} do not mention it. "
        "All are shown; none is overruled.",
        id="diff-only",
    ),
    pytest.param(
        _set(ABSENT, OBSERVED, OBSERVED),
        f"{META} and {PROSE} found this change; {DIFF} finds no difference in the provision's "
        "text. All are shown; none is overruled.",
        id="metadata-and-prose-not-diff",
    ),
]


@pytest.mark.parametrize(("signals", "detail"), PRESENCE)
def test_each_presence_pattern_names_the_sources_in_plain_words(
    signals: SignalSet, detail: str
) -> None:
    note = dispute_note(signals)
    assert note.lead == "Sources disagree"
    assert note.detail == detail
    assert note.text == f"Sources disagree — {detail}"


def test_a_kind_mismatch_reads_as_a_disagreement_about_kind_not_about_occurrence() -> None:
    """Every source saw the provision. Saying one of them missed it would be false."""
    signals = _set(
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)),
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)),
        UNAVAILABLE,
    )
    note = dispute_note(signals)
    assert note.lead == "Sources disagree about the kind of change"
    assert note.detail == (
        f"they agree this provision changed and disagree about how: {DIFF} called it MODIFIED "
        f"and {META} called it INSERTED. Both are shown; neither is overruled."
    )
    for phrase in ("does not list it", "do not mention it", "finds no difference"):
        assert phrase not in note.text


def test_a_source_that_saw_the_change_and_named_no_kind_is_still_named() -> None:
    """An unreadable role code leaves a source observing with nothing to say about the kind.

    That is a counted coverage gap, not an absence. Leaving it out of the sentence would let a
    reader count two sources where three looked, and would close on the wrong promise.
    """
    note = dispute_note(
        _set(
            SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)),
            SignalObservation(status=SignalStatus.OBSERVED),
            SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)),
        )
    )
    assert note.detail == (
        f"they agree this provision changed and disagree about how: {DIFF} called it MODIFIED, "
        f"{META} found it without naming a kind and {PROSE} called it INSERTED. "
        "All are shown; none is overruled."
    )


# ------------------------------------------------------------------ what may never be said


def test_an_unavailable_source_is_never_listed_among_the_ones_that_did_not_see_it() -> None:
    """A source handed nothing to work with has not dissented, so it is named nowhere.

    This is the shape corrected in the corpus on 2026-08-12: metadata handed no annotations at
    all was reported available, which left every unit `ABSENT`, and a sentence built from that
    would report a dissent the status says does not exist.
    """
    for missing in (Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA, Signal.INSTRUCTION_PARSE):
        rest = [signal for signal in Signal if signal is not missing]
        signals = SignalSet.model_validate(
            {
                missing.value: UNAVAILABLE,
                rest[0].value: OBSERVED,
                rest[1].value: ABSENT,
            }
        )
        text = dispute_note(signals).text
        assert _NAMES[missing] not in text, missing
        assert text.endswith("Both are shown; neither is overruled.")


def test_the_two_source_case_reads_as_the_wording_the_site_ships() -> None:
    """The worked example, in full: one source found it, one did not, one could not look."""
    assert dispute_note(_set(OBSERVED, ABSENT, UNAVAILABLE)).text == (
        "Sources disagree — the text comparison found this change; the EU's own amendment "
        "metadata does not list it. Both are shown; neither is overruled."
    )


def test_every_signal_has_a_phrasing_so_a_new_one_cannot_ship_without_words() -> None:
    """A fourth signal added to `core` must be given prose here, not left to render blank."""
    for signal in Signal:
        every = _set(OBSERVED, OBSERVED, OBSERVED).model_copy(update={signal.value: ABSENT})
        text = dispute_note(every).text
        assert _NAMES[signal] in text, signal
        assert "  " not in text and "; ." not in text
