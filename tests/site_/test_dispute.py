"""The disagreement sentence: one phrasing per pattern, one lead per shape, no unavailable source.

Every pattern the committed corpus produces is exercised here by its verdicts alone, because
that is all the wording depends on. Six of them are disagreements about *presence* (one or two
sources found the change and the rest looked and did not) and the seventh is a disagreement
about *kind*, which has to read as one: the sources agreed the provision moved.

The six presence patterns split two ways from 2026-09-05, on whether the one source that
carries text saw the change: a provision whose words are on the page and which another source
did not enumerate is a different finding from a provision nothing could show at all. Three
leads, three shapes, and the shape is the one `site_.entries` counts the published rates by.
Nothing is graded away, which is why every lead still opens on `Sources disagree`.

The expected sentences are written out in full rather than pattern-matched. A wording this
short is only worth testing if the test can be read as the wording.
"""

from __future__ import annotations

import pytest

from emendrix.core import ChangeType, Signal, SignalObservation, SignalSet, SignalStatus
from emendrix.site_.dispute import (
    SHAPE_CLASS,
    SHAPE_WORDS,
    dispute_note,
    dispute_shape,
    named_by,
    quiet_heading,
)
from emendrix.site_.entries import DisputeShapes

OBSERVED = SignalObservation(status=SignalStatus.OBSERVED)
ABSENT = SignalObservation(status=SignalStatus.ABSENT)
UNAVAILABLE = SignalObservation(status=SignalStatus.UNAVAILABLE)

EVIDENCED = "Sources disagree about what is listed, not about the text"
TEXTLESS = "Sources disagree, and there is no text on either side"
KIND = "Sources disagree about the kind of change"

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
        EVIDENCED,
        f"{DIFF} and {PROSE} found this change; {META} does not list it. "
        "All are shown; none is overruled.",
        id="diff-and-prose-not-metadata",
    ),
    pytest.param(
        _set(ABSENT, ABSENT, OBSERVED),
        TEXTLESS,
        f"{PROSE} found this change; {DIFF} finds no difference in the provision's text and "
        f"{META} does not list it. All are shown; none is overruled.",
        id="prose-only",
    ),
    pytest.param(
        _set(OBSERVED, OBSERVED, ABSENT),
        EVIDENCED,
        f"{DIFF} and {META} found this change; {PROSE} do not mention it. "
        "All are shown; none is overruled.",
        id="diff-and-metadata-not-prose",
    ),
    pytest.param(
        _set(ABSENT, OBSERVED, ABSENT),
        TEXTLESS,
        f"{META} found this change; {DIFF} finds no difference in the provision's text and "
        f"{PROSE} do not mention it. All are shown; none is overruled.",
        id="metadata-only",
    ),
    pytest.param(
        _set(OBSERVED, ABSENT, ABSENT),
        EVIDENCED,
        f"{DIFF} found this change; {META} does not list it and {PROSE} do not mention it. "
        "All are shown; none is overruled.",
        id="diff-only",
    ),
    pytest.param(
        _set(ABSENT, OBSERVED, OBSERVED),
        TEXTLESS,
        f"{META} and {PROSE} found this change; {DIFF} finds no difference in the provision's "
        "text. All are shown; none is overruled.",
        id="metadata-and-prose-not-diff",
    ),
]


@pytest.mark.parametrize(("signals", "lead", "detail"), PRESENCE)
def test_each_presence_pattern_names_the_sources_in_plain_words(
    signals: SignalSet, lead: str, detail: str
) -> None:
    """The detail is the sources, unchanged by the grading; the lead is which shape it is."""
    note = dispute_note(signals)
    assert note.lead == lead
    assert note.detail == detail
    assert note.text == f"{lead} — {detail}"


def test_a_kind_mismatch_reads_as_a_disagreement_about_kind_not_about_occurrence() -> None:
    """Every source saw the provision. Saying one of them missed it would be false."""
    signals = _set(
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)),
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)),
        UNAVAILABLE,
    )
    note = dispute_note(signals)
    assert note.lead == KIND
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
        "Sources disagree about what is listed, not about the text — the text comparison found "
        "this change; the EU's own amendment metadata does not list it. Both are shown; "
        "neither is overruled."
    )


def test_every_signal_has_a_phrasing_so_a_new_one_cannot_ship_without_words() -> None:
    """A fourth signal added to `core` must be given prose here, not left to render blank."""
    for signal in Signal:
        every = _set(OBSERVED, OBSERVED, OBSERVED).model_copy(update={signal.value: ABSENT})
        text = dispute_note(every).text
        assert _NAMES[signal] in text, signal
        assert "  " not in text and "; ." not in text


# ------------------------------------------------------------------ the three shapes


def test_each_shape_gets_its_own_lead_and_they_all_open_on_the_same_three_words() -> None:
    """Built from the verdicts rather than from a fixture that happens to carry them.

    The three leads are the whole of the grading a reader sees first, so they are asserted
    against the shapes directly: the comparison saw it and another source did not list it, the
    comparison never saw it, and every source that looked named a different kind. Each still
    opens on `Sources disagree`, because grading a disagreement is not the same as softening
    one, and the count line and the methodology table print the same three names.
    """
    kinds = (
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)),
        SignalObservation(status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)),
        UNAVAILABLE,
    )
    for signals, shape, lead in (
        (_set(OBSERVED, ABSENT, UNAVAILABLE), "evidenced", EVIDENCED),
        (_set(ABSENT, OBSERVED, UNAVAILABLE), "no_text", TEXTLESS),
        (_set(*kinds), "kind", KIND),
    ):
        assert dispute_shape(signals) == shape
        assert dispute_note(signals).lead == lead
        assert lead.startswith("Sources disagree")


def test_no_lead_names_a_source_at_all_so_none_can_name_an_unavailable_one() -> None:
    """The rule this module holds throughout, asserted over the leads as well as the details.

    A lead is chosen from the shape and the shape is read from statuses, so the one way a lead
    could name a source that was handed nothing is by naming a source at all. None does.
    """
    for lead in (EVIDENCED, TEXTLESS, KIND):
        for name in _NAMES.values():
            assert name not in lead, lead


def test_the_shapes_the_page_words_are_the_shapes_the_rates_are_counted_by() -> None:
    """One question, one answer: the badge, the count line and the published table agree.

    `DisputeShapes` is what the site publishes a rate for each of, and the two maps here are
    what a page prints for one change. A fourth shape added to that model would land in a page
    with no words and no class for it, which is what this catches.
    """
    fields = set(DisputeShapes.model_fields)
    assert set(SHAPE_WORDS) == fields
    assert set(SHAPE_CLASS) == fields
    assert len(set(SHAPE_CLASS.values())) == len(fields)


def test_a_row_with_no_text_names_the_source_that_named_it_and_never_a_silent_one() -> None:
    """The one line such a row is reduced to has to carry the source, so it is read off here."""
    assert named_by(_set(ABSENT, OBSERVED, UNAVAILABLE)) == META
    assert named_by(_set(ABSENT, OBSERVED, OBSERVED)) == f"{META} and {PROSE}"
    assert DIFF not in named_by(_set(ABSENT, OBSERVED, UNAVAILABLE))


def test_the_heading_over_the_gathered_rows_counts_them_and_says_what_they_are() -> None:
    """The same words the event's card, title and description use for the same class of row.

    The noun is `provision` and the number is the rows, which is not a licence taken: such a
    change is appended at the top-level unit, one per unit and never for a unit the comparison
    already produced a change for, so a row and a provision are the same thing here.
    """
    assert quiet_heading(1) == "1 provision named with no text to show"
    assert quiet_heading(36) == "36 provisions named with no text to show"
