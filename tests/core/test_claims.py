"""`SignalClaim` / `SignalReport`: the comparison convention, and what it refuses to assume."""

from datetime import date

import pytest

from emendrix.core import (
    COMPARABLE_KIND,
    ActId,
    ChangeType,
    ProvisionLocation,
    Signal,
    SignalClaim,
    SignalReport,
    comparable_kind,
)


def claim(location: str, kind: ChangeType | None = None, **kwargs: object) -> SignalClaim:
    return SignalClaim(
        location=ProvisionLocation.parse(location),
        change_type=kind,
        in_force=kwargs.get("in_force"),  # type: ignore[arg-type]
    )


def test_every_change_type_has_a_comparison_kind() -> None:
    """A new change type must decide how it is compared; the table is what forces that."""
    assert set(COMPARABLE_KIND) == set(ChangeType)


@pytest.mark.parametrize(
    ("change_type", "expected"),
    [
        (ChangeType.INSERTED, ChangeType.INSERTED),
        (ChangeType.MODIFIED, ChangeType.MODIFIED),
        (ChangeType.DELETED, ChangeType.DELETED),
        (ChangeType.DEFERRED, ChangeType.MODIFIED),
        (ChangeType.RENUMBERED, ChangeType.MODIFIED),
    ],
)
def test_refinements_of_modified_compare_as_modified(
    change_type: ChangeType, expected: ChangeType
) -> None:
    """`DEFERRED` and `RENUMBERED` are refinements only the diff can make."""
    assert comparable_kind(change_type) is expected


def test_only_a_claim_about_the_unit_itself_can_insert_it() -> None:
    """Inserting a point *into* Article 5 is a modification of Article 5, not an insertion."""
    assert claim("AR 4a", ChangeType.INSERTED).unit_kind is ChangeType.INSERTED
    deep = claim("AR 5 PA 1 ALN 1 PTA (bb)", ChangeType.INSERTED)
    assert deep.unit.canonical == "AR 5"
    assert deep.unit_kind is ChangeType.MODIFIED
    assert claim("AR 5 PA 4", ChangeType.DELETED).unit_kind is ChangeType.MODIFIED


def test_a_claim_that_names_no_kind_stays_silent_about_it() -> None:
    assert claim("AR 5").unit_kind is None


def test_a_claim_can_name_the_act_that_amended_the_provision() -> None:
    """The amending act is structured, not flattened into the audit string."""
    amender = ActId(corpus="test", key="amending-act")
    claimed = SignalClaim(
        location=ProvisionLocation.parse("AR 5"),
        change_type=ChangeType.MODIFIED,
        amending_act=amender,
    )
    assert claimed.amending_act == amender


def test_a_claim_names_no_amending_act_by_default() -> None:
    """A signal that does not know which act amended the provision says so by carrying None."""
    assert SignalClaim(location=ProvisionLocation.parse("AR 5")).amending_act is None


def test_a_report_collapses_its_claims_to_units_in_canonical_order() -> None:
    report = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(
            claim("AN III", ChangeType.MODIFIED),
            claim("AR 10 PA 1", ChangeType.MODIFIED),
            claim("AR 4", ChangeType.MODIFIED),
            claim("AR 10 PA 2", ChangeType.INSERTED),
        ),
    )
    assert [unit.canonical for unit in report.units] == ["AR 4", "AR 10", "AN III"]
    assert report.kinds_by_unit()["AR 10"] == frozenset({ChangeType.MODIFIED})


def test_a_unit_can_carry_more_than_one_kind() -> None:
    report = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(claim("AR 4", ChangeType.INSERTED), claim("AR 4", ChangeType.MODIFIED)),
    )
    assert report.kinds_by_unit()["AR 4"] == frozenset({ChangeType.INSERTED, ChangeType.MODIFIED})


def test_the_earliest_date_a_signal_gives_a_unit_wins() -> None:
    report = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(
            claim("AR 4", ChangeType.MODIFIED, in_force=date(2027, 1, 1)),
            claim("AR 4 PA 1", ChangeType.MODIFIED, in_force=date(2026, 7, 27)),
            claim("AR 9", ChangeType.MODIFIED),
        ),
    )
    dates = report.in_force_by_unit()
    assert dates["AR 4"] == date(2026, 7, 27)
    assert "AR 9" not in dates


def test_an_unavailable_signal_is_not_an_empty_one() -> None:
    report = SignalReport.unavailable(Signal.INSTRUCTION_PARSE, note="no amending act pinned")
    assert report.available is False
    assert report.claims == ()
    assert report.note == "no amending act pinned"
