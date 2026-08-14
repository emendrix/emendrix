"""Scoring one transition, and aggregating a corpus of them. No corpus vocabulary, no I/O.

Everything here takes a `Corroboration` — the object the deterministic pipeline already
produces — and turns it into numbers. That is deliberate: the meter can then be tested on the
toy corpus with a synthetic labelled set (`tests/eval/test_runner_toy.py`), which is the only
way to know that a perfect pipeline scores 1.000 because it is perfect and not because the
harness cannot subtract.

Four things are measured, and they are not the same kind of claim (the rigour table in
`prose.py`):

- **Localisation**, the structural diff against the corpus's modification metadata: precision,
  recall and F1 over the set of top-level provisions each names (article-or-annex granularity).
  Micro pools every unit in the corpus; macro averages the per-transition F1 so that a big
  transition cannot drown a small one. Both are published, because they answer different
  questions.
- **Classification**, of the units both signals name, the share the two label the same way under
  the comparison convention of `core.claims` (`DEFERRED`/`RENUMBERED` compare as `MODIFIED`).
- **Disputes**, changes the signals disagree about, as a share of changes shipped.
- **Coverage**, what the parsers could not account for, and how much of the corpus was scored.

**Diff-only units are reported as their own class, never as false positives.** CELLAR annotates a
blanket amendment once and does not enumerate where it lands, so a unit only the diff names
may be the reference set being incomplete rather than the diff being wrong. The number appears
in the report next to the precision it explains.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ChangeType, Signal, SignalStatus, comparable_kind
from emendrix.corroborate import Corroboration, CorroborationReport

__all__ = [
    "NO_COVERAGE",
    "CaseResult",
    "ConfusionCell",
    "CoverageStats",
    "score",
    "unavailable",
]


class CoverageStats(BaseModel):
    """What the parsers could not account for, summed over every document a run read."""

    model_config = ConfigDict(frozen=True)

    documents: int = Field(default=0, ge=0)
    documents_unreadable: int = Field(default=0, ge=0)
    units: int = Field(default=0, ge=0)
    nodes: int = Field(default=0, ge=0)
    containers_flattened: int = Field(default=0, ge=0)
    unmapped_identifiers: int = Field(default=0, ge=0)
    heading_mismatches: int = Field(default=0, ge=0)
    unreadable_dates: int = Field(default=0, ge=0)
    unknown_elements: int = Field(default=0, ge=0)

    def merge(self, other: CoverageStats) -> CoverageStats:
        return CoverageStats(
            documents=self.documents + other.documents,
            documents_unreadable=self.documents_unreadable + other.documents_unreadable,
            units=self.units + other.units,
            nodes=self.nodes + other.nodes,
            containers_flattened=self.containers_flattened + other.containers_flattened,
            unmapped_identifiers=self.unmapped_identifiers + other.unmapped_identifiers,
            heading_mismatches=self.heading_mismatches + other.heading_mismatches,
            unreadable_dates=self.unreadable_dates + other.unreadable_dates,
            unknown_elements=self.unknown_elements + other.unknown_elements,
        )

    @property
    def clean(self) -> bool:
        return not (self.unknown_elements or self.unmapped_identifiers or self.documents_unreadable)


NO_COVERAGE: Final = CoverageStats()
"""Nothing measured — the default for a scorer that was handed no parser report."""


class ConfusionCell(BaseModel):
    """One (diff says, reference says) pair and how often it occurred on a shared unit."""

    model_config = ConfigDict(frozen=True)

    diff: str
    metadata: str
    count: int = Field(ge=0)


class CaseResult(BaseModel):
    """One transition, scored. Carries the corroboration report verbatim — disagreements included.

    A case the corpus could not supply a document for is not an error and not a zero: `scored` is
    false, `state` names the first-class state that says why, and the aggregate counts it as
    unscored rather than as a failure.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    act: str
    from_version: str
    to_version: str
    scored: bool = True
    state: str | None = None
    detail: str = ""
    report: CorroborationReport | None = None
    changes: int = Field(default=0, ge=0)
    unchanged_units: int = Field(default=0, ge=0)
    disputed: int = Field(default=0, ge=0)
    diff_only_units: int = Field(default=0, ge=0)
    metadata_only_units: int = Field(default=0, ge=0)
    annotations: int = Field(default=0, ge=0)
    confusion: tuple[ConfusionCell, ...] = ()
    parser: CoverageStats = NO_COVERAGE
    instruction_coverage: float | None = None
    instruction_unread: int | None = None
    instruction_note: str = ""

    def agreement(self, left: Signal, right: Signal) -> tuple[int, int, int] | None:
        """`(left units, right units, shared)` for one pairing, or `None` if it was not scored."""
        if self.report is None:
            return None
        pair = self.report.agreement_of(left, right)
        return None if pair is None else (pair.left_units, pair.right_units, pair.shared)


def _kind_label(kinds: tuple[ChangeType, ...]) -> str:
    """How a signal's verdict on one unit prints: one kind, or `MIXED` when it claims several."""
    if not kinds:
        return "NONE"
    return kinds[0].value if len(kinds) == 1 else "MIXED"


def score(
    case_id: str,
    corroboration: Corroboration,
    *,
    annotations: int = 0,
    parser: CoverageStats = NO_COVERAGE,
    instruction_coverage: float | None = None,
    instruction_unread: int | None = None,
    instruction_note: str = "",
) -> CaseResult:
    """Turn one corroborated delta into a scored case. Pure: no corpus, no I/O, no clock."""
    delta = corroboration.delta
    confusion: dict[tuple[str, str], int] = {}
    diff_only = 0
    for change in delta.changes:
        diff_seen = change.signals.structural_diff
        meta_seen = change.signals.corpus_metadata
        if diff_seen.status is SignalStatus.OBSERVED and meta_seen.status is SignalStatus.ABSENT:
            diff_only += 1
        if not (diff_seen.status is SignalStatus.OBSERVED and meta_seen.observed):
            continue
        key = (comparable_kind(change.change_type).value, _kind_label(meta_seen.change_types))
        confusion[key] = confusion.get(key, 0) + 1
    return CaseResult(
        case_id=case_id,
        act=delta.act.key,
        from_version=str(delta.from_version),
        to_version=str(delta.to_version),
        report=corroboration.report,
        changes=len(delta.changes),
        unchanged_units=delta.unchanged_units,
        disputed=corroboration.disputed,
        diff_only_units=diff_only,
        metadata_only_units=len(corroboration.report.metadata_only_units),
        annotations=annotations,
        confusion=tuple(
            ConfusionCell(diff=diff, metadata=metadata, count=count)
            for (diff, metadata), count in sorted(confusion.items())
        ),
        parser=parser,
        instruction_coverage=instruction_coverage,
        instruction_unread=instruction_unread,
        instruction_note=instruction_note,
    )


def unavailable(
    case_id: str, act: str, from_version: str, to_version: str, *, state: str, detail: str
) -> CaseResult:
    """A case whose text the corpus did not supply. A state, counted — never an exception."""
    return CaseResult(
        case_id=case_id,
        act=act,
        from_version=from_version,
        to_version=to_version,
        scored=False,
        state=state,
        detail=detail,
    )
