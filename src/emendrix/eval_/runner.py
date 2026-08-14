"""Running the committed corpus — offline, from pinned documents, on every push.

There is no network in this module and no clock in it either. Every document a case needs was
pinned by `build.py` and committed; a document that is missing is a *programming* error and the
run says so, naming the fetch command, rather than quietly reaching for a socket. That is what
makes "CI runs the full deterministic eval" true rather than aspirational.

Per case the pipeline is exactly the shipped one, adapter → parse → diff → signals → corroborate,
and then `metrics.score`. Nothing here reimplements a stage, because a harness that measures its
own copy of the pipeline measures nothing.

The metadata window is `(date(A), date(B)]`, with no lower bound when A is the act as published: a
version pair can fold in several amending acts and one amending act's changes can be split across
dates. The third signal is read only where `build.py` decided one amending act could supply it;
elsewhere it is `UNAVAILABLE`, which is silence and not dissent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, Signal, SignalReport, Unavailable, VersionId
from emendrix.corroborate import Corroboration, corroborate
from emendrix.diff import compute_delta
from emendrix.eu.cache import FixtureMissing
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import Formex4Parser, ParsedAct
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.instructions import instruction_signal, parse_instructions
from emendrix.eu.modmeta import ModificationSet, metadata_signal, parse_branch_modifications
from emendrix.eu.packages import FormexPackage
from emendrix.eval_.aggregate import EvalMetrics, aggregate
from emendrix.eval_.corpus import CorpusCase, EvalCorpus
from emendrix.eval_.judge import FaithfulnessReport
from emendrix.eval_.metrics import CaseResult, CoverageStats, score, unavailable
from emendrix.eval_.model_metrics import ModelMetrics

__all__ = [
    "CorpusReader",
    "EvalRun",
    "PreparedCase",
    "prepare_case",
    "run_case",
    "run_corpus",
    "version_id",
]

FETCH_HINT = (
    "run `uv run python -m emendrix.eu.fetch_fixtures` to pin the documents the corpus names"
)


class EvalRun(BaseModel):
    """One complete run of the deterministic eval: what was measured, on what, at what revision."""

    model_config = ConfigDict(frozen=True)

    run_date: date = Field(description="Passed in at the CLI boundary. The one clock read.")
    revision: str = Field(default="unknown", description="Git revision the corpus was scored at.")
    corpus_built_on: date
    corpus_transitions_possible: int = Field(default=0, ge=0)
    corpus_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    metrics: EvalMetrics
    cases: tuple[CaseResult, ...] = ()
    model: ModelMetrics | None = Field(
        default=None,
        description="The model layer over the pinned subset, or None when it was not run.",
    )
    faithfulness: FaithfulnessReport | None = Field(
        default=None,
        description="The sampled faithfulness layer, replayed from committed judgements.",
    )

    @property
    def slug(self) -> str:
        """`2026-08-06-a1b2c3d` — the report filename stem. Date from the CLI, sha from git."""
        return f"{self.run_date.isoformat()}-{self.revision}"


def version_id(case: CorpusCase, version: str) -> VersionId:
    """A case's version string as a `VersionId` — the act's own CELEX for the OJ text."""
    return Celex.parse(case.act).version if version == case.act else VersionId(version)


class CorpusReader:
    """Holds what is shared between cases of one act: the branch notice, parsed once."""

    def __init__(self, client: CellarClient, parser: Formex4Parser | None = None) -> None:
        self.client = client
        self.parser = parser if parser is not None else Formex4Parser()
        self._mods: dict[str, ModificationSet] = {}

    def modifications(self, celex: str) -> ModificationSet:
        found = self._mods.get(celex)
        if found is None:
            found = parse_branch_modifications(self.client.branch_notice(Celex.parse(celex)))
            self._mods[celex] = found
        return found

    def version(self, celex: str, version: VersionId) -> ParsedAct | Unavailable:
        fetched = self.client.fetch_formex(Celex.parse(celex), version)
        if isinstance(fetched, FormexPackage):
            return self.parser.read_version(fetched)
        return fetched

    def instructions(self, celex: str, amended: ActId) -> tuple[SignalReport, float, int] | None:
        """The third signal for one amending act, with its coverage. `None` if it has no text."""
        parsed = Celex.parse(celex)
        fetched = self.client.fetch_formex(parsed, parsed.version)
        if not isinstance(fetched, FormexPackage):
            return None
        read = parse_instructions(fetched)
        return instruction_signal(read, amended), read.coverage, len(read.unread)


def _coverage(*parsed: ParsedAct) -> CoverageStats:
    total = CoverageStats()
    for item in parsed:
        report = item.coverage
        total = total.merge(
            CoverageStats(
                documents=report.documents,
                documents_unreadable=report.documents_unreadable,
                units=report.units,
                nodes=report.nodes,
                containers_flattened=report.containers_flattened,
                unmapped_identifiers=report.unmapped_identifiers,
                heading_mismatches=report.heading_mismatches,
                unreadable_dates=report.unreadable_dates,
                unknown_elements=report.unknown_total,
            )
        )
    return total


@dataclass(frozen=True)
class PreparedCase:
    """One transition run through the shipped pipeline, before anything is scored.

    A plain dataclass rather than a pydantic model on purpose: it holds two whole provision
    trees, it never crosses a serialisation boundary, and re-validating megabytes to hand them
    between two functions in one process would be ceremony with a cost.
    """

    before: ParsedAct
    after: ParsedAct
    corroboration: Corroboration
    annotations: int
    instruction_coverage: float | None = None
    instruction_unread: int | None = None


def prepare_case(reader: CorpusReader, case: CorpusCase) -> PreparedCase | CaseResult:
    """Run one transition through parse → diff → signals → corroborate, and stop there.

    Split out of `run_case` so the model layer (`model_metrics.py`) explains and gates *the
    delta this harness scores* rather than a second delta of its own — a harness that measures
    its own copy of the pipeline measures nothing. A `CaseResult` comes back instead when a
    document was unreadable: a counted first-class state, never an exception.
    """
    before = reader.version(case.act, version_id(case, case.from_version))
    if not isinstance(before, ParsedAct):
        return _state(case, before, "from")
    after = reader.version(case.act, version_id(case, case.to_version))
    if not isinstance(after, ParsedAct):
        return _state(case, after, "to")

    window = reader.modifications(case.act).between(
        None if case.from_original else case.from_date, case.to_date
    )
    amended = act_id(Celex.parse(case.act))
    third = (
        None
        if case.instruction_source is None
        else reader.instructions(case.instruction_source, amended)
    )
    instructions = (
        third[0]
        if third is not None
        else SignalReport.unavailable(
            Signal.INSTRUCTION_PARSE,
            note=case.instruction_note or "no amending act pinned for this window",
        )
    )
    corroboration = corroborate(
        compute_delta(before.tree, after.tree),
        metadata=metadata_signal(
            window, note=f"{len(window)} annotations in ({case.from_date}, {case.to_date}]"
        ),
        instructions=instructions,
    )
    return PreparedCase(
        before=before,
        after=after,
        corroboration=corroboration,
        annotations=len(window),
        instruction_coverage=None if third is None else third[1],
        instruction_unread=None if third is None else third[2],
    )


def run_case(reader: CorpusReader, case: CorpusCase) -> CaseResult:
    """Score one transition. An unavailable document is a counted state, never an exception."""
    prepared = prepare_case(reader, case)
    if isinstance(prepared, CaseResult):
        return prepared
    return score(
        case.id,
        prepared.corroboration,
        annotations=prepared.annotations,
        parser=_coverage(prepared.before, prepared.after),
        instruction_coverage=prepared.instruction_coverage,
        instruction_unread=prepared.instruction_unread,
        instruction_note=case.instruction_note,
    )


def _state(case: CorpusCase, state: Unavailable, side: str) -> CaseResult:
    """A first-class state as a counted, unscored case. `ConsolidationPending` names no version."""
    named = getattr(state, "version", None)
    return unavailable(
        case.id,
        case.act,
        case.from_version,
        case.to_version,
        state=state.state,
        detail=f"{side} version {named or ''}: {state.detail}".strip(),
    )


def run_corpus(
    reader: CorpusReader,
    corpus: EvalCorpus,
    *,
    run_date: date,
    revision: str = "unknown",
    only: str | None = None,
) -> EvalRun:
    """Score every case (or one, with `only`) and pool the result."""
    cases = corpus.cases if only is None else tuple(c for c in corpus.cases if c.id == only)
    if only is not None and not cases:
        raise LookupError(f"no such transition in the corpus: {only}")
    try:
        results = tuple(run_case(reader, case) for case in cases)
    except FixtureMissing as missing:  # a document nobody pinned: loud, and actionable
        raise FixtureMissing(f"{missing}\n{FETCH_HINT}") from missing
    return EvalRun(
        run_date=run_date,
        revision=revision,
        corpus_built_on=corpus.built_on,
        corpus_transitions_possible=corpus.transitions_possible,
        corpus_coverage=corpus.coverage,
        metrics=aggregate(results),
        cases=results,
    )
