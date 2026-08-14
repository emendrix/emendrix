"""Testing the meter before trusting the measurements, on a corpus that is not law.

A harness that reports 1.000 is only worth reading if it also reports the right number when
something is wrong. So the scorer is exercised on the toy corpus against a synthetic
labelled set, in four shapes:

- a perfect pipeline, which must score exactly 1.000 and produce no dispute;
- a diff broken to lose one unit, which must lose exactly the recall that costs;
- a labelled set missing one unit the diff found, which must lose exactly that precision and
  count the unit as diff-only rather than as an error;
- a labelled set that disagrees about the *kind* of one change, which must leave localisation
  untouched and move classification alone.

Nothing here imports the EU adapter: `emendrix.eval_.metrics` and `.aggregate` are corpus-
agnostic on purpose, and this file is what proves it.
"""

from __future__ import annotations

from datetime import date

import pytest

from emendrix.core import (
    ChangeType,
    Delta,
    ProvisionLocation,
    ProvisionTree,
    Signal,
    SignalClaim,
    SignalReport,
)
from emendrix.corroborate import Corroboration, corroborate
from emendrix.diff import compute_delta
from emendrix.eval_.aggregate import aggregate
from emendrix.eval_.metrics import CaseResult, score
from toy_corpus import HOUSE_RULES, V1, V2, ToyCorpusAdapter

CHANGED = {
    "AR 2": ChangeType.MODIFIED,
    "AR 3": ChangeType.DELETED,
    "AR 4": ChangeType.INSERTED,
    "AN I": ChangeType.MODIFIED,
}
"""What actually differs between the toy's two versions: the synthetic ground truth."""


def tree(version: str) -> ProvisionTree:
    fetched = ToyCorpusAdapter(observed_on=date(2026, 8, 6)).fetch_version(
        HOUSE_RULES, V1 if version == "v1" else V2
    )
    assert isinstance(fetched, ProvisionTree)
    return fetched


@pytest.fixture
def delta() -> Delta:
    return compute_delta(tree("v1"), tree("v2"))


def labels(**overrides: ChangeType | None) -> SignalReport:
    """The synthetic reference set, with units dropped (`None`) or relabelled by keyword."""
    claimed = {**CHANGED, **{key.replace("_", " "): value for key, value in overrides.items()}}
    return SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=tuple(
            SignalClaim(location=ProvisionLocation.parse(unit), change_type=kind)
            for unit, kind in claimed.items()
            if kind is not None
        ),
    )


def scored(delta: Delta, metadata: SignalReport) -> CaseResult:
    return score("toy@v2", corroborate(delta, metadata=metadata))


def localisation(result: CaseResult) -> tuple[float, float, float]:
    assert result.report is not None
    pair = result.report.agreement_of(Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA)
    assert pair is not None
    return round(pair.precision, 3), round(pair.recall, 3), round(pair.f1, 3)


# ------------------------------------------------------------------ the perfect case


def test_the_toy_diff_finds_exactly_the_four_units_that_differ(delta: Delta) -> None:
    assert {change.unit.canonical for change in delta.changes} == set(CHANGED)


def test_a_perfect_pipeline_scores_exactly_one(delta: Delta) -> None:
    result = scored(delta, labels())
    assert localisation(result) == (1.0, 1.0, 1.0)
    assert result.disputed == 0
    assert (result.diff_only_units, result.metadata_only_units) == (0, 0)


def test_a_perfect_pipeline_aggregates_to_one(delta: Delta) -> None:
    metrics = aggregate((scored(delta, labels()),))
    assert metrics.localisation is not None
    assert (metrics.localisation.micro_f1, metrics.localisation.macro_f1) == (1.0, 1.0)
    assert metrics.classification_accuracy == 1.0
    assert metrics.classification_units == 4
    assert metrics.dispute_rate == 0.0


# ------------------------------------------------------------------- a broken diff


@pytest.fixture
def blinded(monkeypatch: pytest.MonkeyPatch) -> Delta:
    """The diff with one insertion surgically removed: a regression, staged."""
    from emendrix.diff import api, tree_diff

    def blind(before: ProvisionTree, after: ProvisionTree) -> tree_diff.UnitDiff:
        found = tree_diff.diff_units(before, after)
        kept = tuple(item for item in found.matches if item.change_type is not ChangeType.INSERTED)
        return found.model_copy(update={"matches": kept})

    monkeypatch.setattr(api, "diff_units", blind)
    return compute_delta(tree("v1"), tree("v2"))


def test_a_diff_that_lost_a_unit_loses_exactly_that_recall(blinded: Delta) -> None:
    """3 of 4 named, all 3 correct: precision 1.000, recall 0.750, F1 0.857."""
    result = scored(blinded, labels())
    assert localisation(result) == (1.0, 0.75, 0.857)
    assert result.metadata_only_units == 1
    assert result.diff_only_units == 0
    assert result.disputed == 1


def test_the_unit_the_broken_diff_missed_still_ships(blinded: Delta) -> None:
    """Never dropped: it ships with a location, a kind and no text."""
    merged = corroborate(blinded, metadata=labels())
    stray = next(c for c in merged.delta.changes if c.unit.canonical == "AR 4")
    assert (stray.before, stray.after) == (None, None)
    assert stray.change_type is ChangeType.INSERTED
    assert stray.disputed


# ------------------------------------------------- a reference set missing a unit


def test_a_reference_set_missing_a_unit_loses_precision_and_says_where(delta: Delta) -> None:
    """The blanket-amendment shape, in miniature: the diff is right and scores 0.750."""
    result = scored(delta, labels(AN_I=None))
    assert localisation(result) == (0.75, 1.0, 0.857)
    assert result.diff_only_units == 1
    assert result.metadata_only_units == 0


def test_diff_only_units_are_counted_apart_from_the_confusion_matrix(delta: Delta) -> None:
    metrics = aggregate((scored(delta, labels(AN_I=None)),))
    assert metrics.diff_only_units == 1
    assert metrics.classification_units == 3
    assert metrics.classification_accuracy == 1.0


# -------------------------------------------------------- a disagreement of kind


def test_a_kind_disagreement_moves_classification_and_not_localisation(delta: Delta) -> None:
    result = scored(delta, labels(AR_2=ChangeType.INSERTED))
    assert localisation(result) == (1.0, 1.0, 1.0)
    metrics = aggregate((result,))
    assert metrics.classification_accuracy == 0.75
    assert {(cell.diff, cell.metadata): cell.count for cell in metrics.confusion} == {
        ("DELETED", "DELETED"): 1,
        ("INSERTED", "INSERTED"): 1,
        ("MODIFIED", "INSERTED"): 1,
        ("MODIFIED", "MODIFIED"): 1,
    }
    assert result.disputed == 1


# ----------------------------------------------------------- micro versus macro


def test_macro_weights_transitions_and_micro_weights_units(delta: Delta) -> None:
    """One perfect four-unit case beside one that is entirely wrong on a single unit.

    Micro sees 4 shared of 4 named and 5 referenced, so F1 0.889. Macro averages 1.000 and
    0.000, so 0.500. Same corpus, same two cases, and quoting either alone would mislead.
    """
    small = compute_delta(tree("v1"), tree("v1"))
    wrong = SignalReport(
        signal=Signal.CORPUS_METADATA,
        claims=(SignalClaim(location=ProvisionLocation.parse("AR 9")),),
    )
    metrics = aggregate(
        (scored(delta, labels()), score("toy@v1", corroborate(small, metadata=wrong)))
    )
    assert metrics.localisation is not None
    assert round(metrics.localisation.micro_f1, 3) == 0.889
    assert round(metrics.localisation.macro_f1, 3) == 0.5


def test_an_unavailable_signal_is_not_a_pairing(delta: Delta) -> None:
    """A signal that could not be computed does not dissent, and is not scored either."""
    merged: Corroboration = corroborate(delta, metadata=labels())
    metrics = aggregate((score("toy@v2", merged),))
    assert metrics.instruction_agreement is None
    assert metrics.localisation is not None
