"""Pooling scored transitions into the numbers the report publishes.

Split from `metrics.py` at the seam between *scoring one transition* and *summing a corpus of
them*: the first is about one delta, the second about how the corpus is weighted.

**Micro and macro are both published, because they answer different questions.** Micro pools
every unit in the corpus into one precision/recall pair, so a transition that touches forty
provisions counts forty times more than one that touches one: it answers "over all the provisions
this corpus contains, how often do the signals agree?". Macro averages the per-transition F1, so
every transition counts once: it answers "on a randomly chosen amendment, how well does this
do?". Quoting one without the other is how an eval flatters itself.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import Signal
from emendrix.eval_.metrics import CaseResult, ConfusionCell, CoverageStats

__all__ = ["ActMetrics", "EvalMetrics", "PairMetrics", "aggregate"]


class PairMetrics(BaseModel):
    """Two signals held against each other over a whole corpus."""

    model_config = ConfigDict(frozen=True)

    left: Signal
    right: Signal
    cases: int = Field(default=0, ge=0)
    left_units: int = Field(default=0, ge=0)
    right_units: int = Field(default=0, ge=0)
    shared: int = Field(default=0, ge=0)
    micro_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    micro_recall: float = Field(default=0.0, ge=0.0, le=1.0)
    micro_f1: float = Field(default=0.0, ge=0.0, le=1.0)
    macro_f1: float = Field(default=0.0, ge=0.0, le=1.0)


class ActMetrics(BaseModel):
    """One act's slice of the corpus."""

    model_config = ConfigDict(frozen=True)

    act: str
    cases: int = Field(default=0, ge=0)
    cases_scored: int = Field(default=0, ge=0)
    localisation: PairMetrics | None = None
    changes: int = Field(default=0, ge=0)
    disputed: int = Field(default=0, ge=0)
    diff_only_units: int = Field(default=0, ge=0)
    metadata_only_units: int = Field(default=0, ge=0)


class EvalMetrics(BaseModel):
    """Everything the deterministic layers measured over one corpus, in one object."""

    model_config = ConfigDict(frozen=True)

    cases: int = Field(default=0, ge=0)
    cases_scored: int = Field(default=0, ge=0)
    localisation: PairMetrics | None = None
    instruction_agreement: PairMetrics | None = None
    metadata_instruction: PairMetrics | None = None
    classification_accuracy: float | None = None
    classification_units: int = Field(default=0, ge=0)
    confusion: tuple[ConfusionCell, ...] = ()
    changes: int = Field(default=0, ge=0)
    disputed: int = Field(default=0, ge=0)
    diff_only_units: int = Field(default=0, ge=0)
    metadata_only_units: int = Field(default=0, ge=0)
    annotations: int = Field(default=0, ge=0)
    parser: CoverageStats = CoverageStats()
    instruction_cases: int = Field(default=0, ge=0)
    instruction_unread: int = Field(default=0, ge=0)
    per_act: tuple[ActMetrics, ...] = ()

    @property
    def dispute_rate(self) -> float:
        return 0.0 if self.changes == 0 else self.disputed / self.changes


def _f1(precision: float, recall: float) -> float:
    total = precision + recall
    return 0.0 if total == 0 else 2 * precision * recall / total


def _pair(results: tuple[CaseResult, ...], left: Signal, right: Signal) -> PairMetrics | None:
    """Micro (pooled units) and macro (mean per-case F1) for one pairing, or `None` if unscored."""
    scored = [
        pair
        for result in results
        if result.report is not None
        and (pair := result.report.agreement_of(left, right)) is not None
    ]
    if not scored:
        return None
    left_units = sum(item.left_units for item in scored)
    right_units = sum(item.right_units for item in scored)
    shared = sum(item.shared for item in scored)
    precision = 1.0 if left_units == 0 else shared / left_units
    recall = 1.0 if right_units == 0 else shared / right_units
    return PairMetrics(
        left=left,
        right=right,
        cases=len(scored),
        left_units=left_units,
        right_units=right_units,
        shared=shared,
        micro_precision=precision,
        micro_recall=recall,
        micro_f1=_f1(precision, recall),
        macro_f1=sum(item.f1 for item in scored) / len(scored),
    )


def _confusion(results: tuple[CaseResult, ...]) -> tuple[ConfusionCell, ...]:
    totals: dict[tuple[str, str], int] = {}
    for result in results:
        for cell in result.confusion:
            key = (cell.diff, cell.metadata)
            totals[key] = totals.get(key, 0) + cell.count
    return tuple(
        ConfusionCell(diff=diff, metadata=metadata, count=count)
        for (diff, metadata), count in sorted(totals.items())
    )


def _act_metrics(results: tuple[CaseResult, ...]) -> tuple[ActMetrics, ...]:
    acts = sorted({result.act for result in results})
    return tuple(
        ActMetrics(
            act=act,
            cases=len(slice_),
            cases_scored=sum(1 for result in slice_ if result.scored),
            localisation=_pair(slice_, Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA),
            changes=sum(result.changes for result in slice_),
            disputed=sum(result.disputed for result in slice_),
            diff_only_units=sum(result.diff_only_units for result in slice_),
            metadata_only_units=sum(result.metadata_only_units for result in slice_),
        )
        for act in acts
        if (slice_ := tuple(result for result in results if result.act == act))
    )


def aggregate(results: tuple[CaseResult, ...]) -> EvalMetrics:
    """Pool every scored case into the numbers the report publishes."""
    confusion = _confusion(results)
    agreed = sum(cell.count for cell in confusion if cell.diff == cell.metadata)
    total_shared = sum(cell.count for cell in confusion)
    parser = CoverageStats()
    for result in results:
        parser = parser.merge(result.parser)
    return EvalMetrics(
        cases=len(results),
        cases_scored=sum(1 for result in results if result.scored),
        localisation=_pair(results, Signal.STRUCTURAL_DIFF, Signal.CORPUS_METADATA),
        instruction_agreement=_pair(results, Signal.STRUCTURAL_DIFF, Signal.INSTRUCTION_PARSE),
        metadata_instruction=_pair(results, Signal.CORPUS_METADATA, Signal.INSTRUCTION_PARSE),
        classification_accuracy=None if total_shared == 0 else agreed / total_shared,
        classification_units=total_shared,
        confusion=confusion,
        changes=sum(result.changes for result in results),
        disputed=sum(result.disputed for result in results),
        diff_only_units=sum(result.diff_only_units for result in results),
        metadata_only_units=sum(result.metadata_only_units for result in results),
        annotations=sum(result.annotations for result in results),
        parser=parser,
        instruction_cases=sum(1 for r in results if r.instruction_coverage is not None),
        instruction_unread=sum(r.instruction_unread or 0 for r in results),
        per_act=_act_metrics(results),
    )
