"""Change, SignalSet and Delta: what the models refuse to represent."""

import itertools
from collections import Counter
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

from emendrix.core import (
    ApplicabilityUnchanged,
    ApplicabilityUnknown,
    Change,
    ChangeType,
    Delta,
    Signal,
    SignalObservation,
    SignalSet,
    SignalStatus,
    sort_changes,
)
from emendrix.core.changes import DisputeReason
from emendrix.core.identifiers import ActId, ProvisionRef, VersionId
from emendrix.core.location import ProvisionLocation
from emendrix.core.provisions import ProvisionText

ACT = ActId(corpus="test", key="act")
V1 = VersionId("v1")
V2 = VersionId("v2")

SEEN = SignalObservation(status=SignalStatus.OBSERVED)
NOT_SEEN = SignalObservation(status=SignalStatus.ABSENT)
NO_SIGNAL = SignalObservation(status=SignalStatus.UNAVAILABLE)


def ref(location: str, version: VersionId = V2) -> ProvisionRef:
    return ProvisionRef(act=ACT, version=version, location=ProvisionLocation.parse(location))


def change(change_type: ChangeType, location: str = "AR 5", **kwargs: Any) -> Change:
    texts: dict[str, Any] = {}
    if change_type is not ChangeType.INSERTED:
        texts["before"] = ProvisionText("old text")
    if change_type is not ChangeType.DELETED:
        texts["after"] = ProvisionText("new text")
    return Change(change_type=change_type, provision=ref(location), **(texts | kwargs))


def test_inserted_change_rejects_a_before_text() -> None:
    with pytest.raises(ValueError, match="INSERTED"):
        Change(
            change_type=ChangeType.INSERTED,
            provision=ref("AR 4a"),
            before=ProvisionText("old text"),
            after=ProvisionText("new text"),
        )


def test_inserted_change_requires_an_after_text() -> None:
    with pytest.raises(ValueError, match="INSERTED"):
        Change(change_type=ChangeType.INSERTED, provision=ref("AR 4a"))


def test_deleted_change_rejects_an_after_text() -> None:
    with pytest.raises(ValueError, match="DELETED"):
        Change(
            change_type=ChangeType.DELETED,
            provision=ref("AR 12"),
            before=ProvisionText("old text"),
            after=ProvisionText("new text"),
        )


def test_modified_change_requires_both_texts() -> None:
    with pytest.raises(ValueError, match="MODIFIED"):
        Change(
            change_type=ChangeType.MODIFIED,
            provision=ref("AR 5"),
            after=ProvisionText("new text"),
        )


def test_renumbered_change_requires_where_it_came_from() -> None:
    with pytest.raises(ValueError, match="RENUMBERED"):
        change(ChangeType.RENUMBERED)
    renumbered = change(ChangeType.RENUMBERED, previous_location=ProvisionLocation.parse("AR 4"))
    assert renumbered.previous_location is not None


def test_deferred_change_requires_the_new_date() -> None:
    with pytest.raises(ValueError, match="DEFERRED"):
        change(ChangeType.DEFERRED)
    deferred = change(ChangeType.DEFERRED, applies_from=date(2027, 12, 2))
    assert deferred.applies_from == date(2027, 12, 2)


def test_applicability_defaults_to_unknown() -> None:
    assert change(ChangeType.MODIFIED).applies_from == ApplicabilityUnknown()


def test_applicability_states_round_trip_through_json() -> None:
    cases: tuple[Any, ...] = (
        date(2027, 12, 2),
        ApplicabilityUnknown(reason="prose"),
        ApplicabilityUnchanged(),
    )
    for applies_from in cases:
        original = change(ChangeType.MODIFIED, applies_from=applies_from)
        restored = Change.model_validate(original.model_dump())
        assert restored.applies_from == applies_from


def test_disputed_is_derived_from_the_signals() -> None:
    agreeing = SignalSet(structural_diff=SEEN, corpus_metadata=SEEN, instruction_parse=NO_SIGNAL)
    disagreeing = SignalSet(
        structural_diff=SEEN, corpus_metadata=NOT_SEEN, instruction_parse=NO_SIGNAL
    )
    assert change(ChangeType.MODIFIED, signals=agreeing).disputed is False
    assert change(ChangeType.MODIFIED, signals=disagreeing).disputed is True


def test_an_unavailable_signal_is_not_a_dispute() -> None:
    signals = SignalSet(
        structural_diff=SEEN, corpus_metadata=NO_SIGNAL, instruction_parse=NO_SIGNAL
    )
    assert signals.disagreement is False
    assert signals.observed_by == (Signal.STRUCTURAL_DIFF,)


def test_disputed_cannot_contradict_the_signals() -> None:
    disagreeing = SignalSet(structural_diff=SEEN, corpus_metadata=NOT_SEEN)
    with pytest.raises(ValueError, match="contradicts the signals"):
        change(ChangeType.MODIFIED, signals=disagreeing, disputed=False)


def test_disputed_cannot_be_asserted_without_signals_to_back_it() -> None:
    with pytest.raises(ValueError, match="contradicts the signals"):
        change(ChangeType.MODIFIED, disputed=True)


def test_signals_that_name_incompatible_kinds_are_a_dispute() -> None:
    """Presence is not the only thing to disagree about: so is *what happened*."""
    signals = SignalSet(
        structural_diff=SignalObservation(
            status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)
        ),
        corpus_metadata=SignalObservation(
            status=SignalStatus.OBSERVED, change_types=(ChangeType.DELETED,)
        ),
    )
    assert signals.disagreement is True
    overlapping = SignalSet(
        structural_diff=SignalObservation(
            status=SignalStatus.OBSERVED, change_types=(ChangeType.MODIFIED,)
        ),
        corpus_metadata=SignalObservation(
            status=SignalStatus.OBSERVED,
            change_types=(ChangeType.MODIFIED, ChangeType.INSERTED),
        ),
    )
    assert overlapping.disagreement is False


def test_a_signal_that_names_no_kind_never_disagrees_about_one() -> None:
    signals = SignalSet(
        structural_diff=SignalObservation(
            status=SignalStatus.OBSERVED, change_types=(ChangeType.INSERTED,)
        ),
        corpus_metadata=SEEN,
    )
    assert signals.disagreement is False


def test_a_change_the_diff_did_not_see_may_carry_no_text() -> None:
    """The diff is the only signal carrying text, so a unit only another names has none.

    That is what lets the corroborator append a diff *miss* to the delta instead of dropping it.
    """
    metadata_only = Change(
        change_type=ChangeType.MODIFIED,
        provision=ref("AR 12"),
        signals=SignalSet(structural_diff=NOT_SEEN, corpus_metadata=SEEN),
    )
    assert metadata_only.before is None and metadata_only.after is None
    assert metadata_only.disputed is True
    # Everywhere else the requirement stands, including when no signal has spoken yet.
    with pytest.raises(ValueError, match="MODIFIED"):
        Change(change_type=ChangeType.MODIFIED, provision=ref("AR 12"))


# ------------------------------------------------------------------ dispute_reason

_KINDS: tuple[tuple[ChangeType, ...], ...] = (
    (),
    (ChangeType.MODIFIED,),
    (ChangeType.INSERTED,),
    (ChangeType.MODIFIED, ChangeType.INSERTED),
)


def _every_signal_set() -> list[SignalSet]:
    """Every combination of three statuses, and of named kinds for each observing signal."""
    sets = []
    for statuses in itertools.product(SignalStatus, repeat=3):
        options = [_KINDS if status is SignalStatus.OBSERVED else ((),) for status in statuses]
        for kinds in itertools.product(*options):
            diff, meta, prose = (
                SignalObservation(status=status, change_types=named)
                for status, named in zip(statuses, kinds, strict=True)
            )
            sets.append(
                SignalSet(structural_diff=diff, corpus_metadata=meta, instruction_parse=prose)
            )
    return sets


def _status(seen: SignalObservation, *wanted: SignalStatus) -> bool:
    return seen.status in wanted


_O, _A, _U = SignalStatus.OBSERVED, SignalStatus.ABSENT, SignalStatus.UNAVAILABLE

_TABLE: tuple[tuple[DisputeReason, Callable[[SignalSet], bool]], ...] = (
    (
        DisputeReason.KIND_MISMATCH,
        lambda s: not any(_status(seen, _A) for _, seen in s.observations),
    ),
    (
        DisputeReason.TEXTLESS_BOTH_OTHERS,
        lambda s: (
            _status(s.structural_diff, _A)
            and _status(s.corpus_metadata, _O)
            and _status(s.instruction_parse, _O)
        ),
    ),
    (
        DisputeReason.TEXTLESS_METADATA_ONLY,
        lambda s: (
            _status(s.structural_diff, _A)
            and _status(s.corpus_metadata, _O)
            and _status(s.instruction_parse, _A, _U)
        ),
    ),
    (
        DisputeReason.TEXTLESS_INSTRUCTION_ONLY,
        lambda s: (
            _status(s.structural_diff, _A)
            and _status(s.corpus_metadata, _A, _U)
            and _status(s.instruction_parse, _O)
        ),
    ),
    (
        DisputeReason.BOTH_OTHERS_SILENT,
        lambda s: (
            _status(s.structural_diff, _O)
            and _status(s.corpus_metadata, _A)
            and _status(s.instruction_parse, _A)
        ),
    ),
    (
        DisputeReason.METADATA_SILENT,
        lambda s: (
            _status(s.structural_diff, _O)
            and _status(s.corpus_metadata, _A)
            and _status(s.instruction_parse, _O, _U)
        ),
    ),
    (
        DisputeReason.INSTRUCTION_SILENT,
        lambda s: (
            _status(s.structural_diff, _O)
            and _status(s.instruction_parse, _A)
            and _status(s.corpus_metadata, _O, _U)
        ),
    ),
)
"""The reason table, spelled out as written: first match wins, the diff observed or absent."""


def test_every_disputed_signal_set_gets_exactly_the_code_the_table_gives() -> None:
    """Exhaustive over statuses and kinds; an undisputed set gets no code at all.

    The table is written for the two states the diff takes inside the loop, observed or absent,
    and over those it is matched exactly. A diff that is unavailable (only a hand-built set has
    one) is read as observing: the textless codes would promise a change no text was found
    for, and such a change carries text, so the silent signal is named instead.
    """
    sets = _every_signal_set()
    reached: Counter[DisputeReason] = Counter()
    for signals in sets:
        reason = signals.reason
        if not signals.disagreement:
            assert reason is None, signals
            continue
        assert reason is not None, signals
        reached[reason] += 1
        if signals.structural_diff.status is _U:
            silent = [signal for signal, seen in signals.observations if seen.status is _A]
            expected = {
                (Signal.CORPUS_METADATA,): DisputeReason.METADATA_SILENT,
                (Signal.INSTRUCTION_PARSE,): DisputeReason.INSTRUCTION_SILENT,
                (): DisputeReason.KIND_MISMATCH,
            }[tuple(silent)]
            assert reason is expected, signals
            continue
        matched = [code for code, applies in _TABLE if applies(signals)]
        assert matched, signals
        assert reason is matched[0], signals
    assert set(reached) == set(DisputeReason)


def test_a_change_carries_its_reason_and_serialises_it() -> None:
    silent = SignalSet(structural_diff=SEEN, corpus_metadata=NOT_SEEN, instruction_parse=SEEN)
    disputed = change(ChangeType.MODIFIED, signals=silent)
    assert disputed.dispute_reason is DisputeReason.METADATA_SILENT
    assert disputed.model_dump(mode="json")["dispute_reason"] == "metadata_silent"
    assert change(ChangeType.MODIFIED).dispute_reason is None
    assert change(ChangeType.MODIFIED).model_dump()["dispute_reason"] is None


def test_a_missing_reason_is_filled_and_a_matching_one_is_accepted() -> None:
    silent = SignalSet(structural_diff=SEEN, corpus_metadata=NOT_SEEN, instruction_parse=SEEN)
    stored = change(ChangeType.MODIFIED, signals=silent).model_dump(mode="json")
    assert Change.model_validate(stored).dispute_reason is DisputeReason.METADATA_SILENT
    del stored["dispute_reason"]
    assert Change.model_validate(stored).dispute_reason is DisputeReason.METADATA_SILENT


@pytest.mark.parametrize("stored", ["instruction_silent", "kind_mismatch", None])
def test_a_reason_cannot_contradict_the_signals(stored: str | None) -> None:
    silent = SignalSet(structural_diff=SEEN, corpus_metadata=NOT_SEEN, instruction_parse=SEEN)
    with pytest.raises(ValueError, match=r"dispute_reason=.*contradicts the signals"):
        change(ChangeType.MODIFIED, signals=silent, dispute_reason=stored)


def test_a_reason_cannot_be_asserted_without_signals_to_back_it() -> None:
    with pytest.raises(ValueError, match=r"dispute_reason=.*contradicts the signals"):
        change(ChangeType.MODIFIED, dispute_reason="metadata_silent")


def test_a_copy_with_new_signals_reads_its_reason_off_them() -> None:
    """Corroboration stamps signals with `model_copy`, which skips validation; the reason must
    follow the signals anyway, which is why it is computed rather than stored."""
    plain = change(ChangeType.MODIFIED)
    stamped = plain.model_copy(
        update={"signals": SignalSet(structural_diff=SEEN, instruction_parse=NOT_SEEN)}
    )
    assert stamped.dispute_reason is DisputeReason.INSTRUCTION_SILENT


def test_unit_is_the_top_level_provision() -> None:
    assert change(ChangeType.MODIFIED, "AR 5 PA 1 ALN 1 PTA (bb)").unit.canonical == "AR 5"


def test_sort_changes_is_deterministic() -> None:
    unordered = (
        change(ChangeType.MODIFIED, "AN III"),
        change(ChangeType.MODIFIED, "AR 10"),
        change(ChangeType.MODIFIED, "AR 4"),
    )
    assert [c.location.canonical for c in sort_changes(unordered)] == ["AR 4", "AR 10", "AN III"]


def test_delta_summary_counts_what_it_holds() -> None:
    delta = Delta(
        act=ACT,
        from_version=V1,
        to_version=V2,
        unchanged_units=77,
        changes=(
            change(ChangeType.INSERTED, "AR 4a"),
            change(ChangeType.MODIFIED, "AR 5"),
            change(ChangeType.MODIFIED, "AR 5 PA 1"),
            change(
                ChangeType.MODIFIED,
                "AN III",
                signals=SignalSet(structural_diff=SEEN, corpus_metadata=NOT_SEEN),
            ),
        ),
    )
    summary = delta.summary
    assert (summary.inserted, summary.modified, summary.deleted) == (1, 3, 0)
    # Three changes, but `AR 5` and `AR 5 PA 1` are one unit of change.
    assert summary.touched_units == 3
    assert summary.unchanged_units == 77
    assert summary.disputed == 1


def test_delta_serialises_its_summary() -> None:
    delta = Delta(act=ACT, from_version=V1, to_version=V2)
    dumped = delta.model_dump()
    assert dumped["summary"]["touched_units"] == 0
    assert list(dumped["summary"]) == [
        "inserted",
        "modified",
        "deleted",
        "renumbered",
        "deferred",
        "touched_units",
        "unchanged_units",
        "disputed",
    ]


def test_a_delta_refuses_changes_from_another_act() -> None:
    other = ProvisionRef(
        act=ActId(corpus="test", key="other"),
        version=V2,
        location=ProvisionLocation.parse("AR 1"),
    )
    stray = Change(
        change_type=ChangeType.MODIFIED,
        provision=other,
        before=ProvisionText("old text"),
        after=ProvisionText("new text"),
    )
    with pytest.raises(ValueError, match="carries changes of"):
        Delta(act=ACT, from_version=V1, to_version=V2, changes=(stray,))


def test_act_identity_ignores_the_display_name() -> None:
    """A caller that knows the act's title names the same act as one that does not."""
    titled = ActId(corpus="test", key="act", display_name="An act")
    bare = ActId(corpus="test", key="act")
    assert titled == bare
    assert len({titled, bare}) == 1
    delta = Delta(
        act=titled, from_version=V1, to_version=V2, changes=(change(ChangeType.MODIFIED),)
    )
    assert delta.act.display_name == "An act"
