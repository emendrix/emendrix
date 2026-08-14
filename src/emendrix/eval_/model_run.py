"""Running the pinned subset through explain and gate — the model layer's harness.

The pipeline here is the shipped one, called through `graph.stages`: explain → gate → revise →
settle. Nothing in this module re-implements the retry policy or the fallback, because a harness
that measures its own copy of the pipeline measures nothing (`runner.py` says the same about the
deterministic layers, for the same reason).

Two seams are deliberate. The delta comes from `runner.prepare_case`, so the model layer explains
*the delta the deterministic layer scored* rather than a second one of its own; and the subset is
applied with `subset.restrict`, which names any pinned unit the delta has stopped containing
instead of quietly shrinking the denominator underneath a published rate.

No clock and no network: the observation date is passed in, and every document comes from the
committed fixtures. In `CassetteMode.REPLAY` — the default, and the only mode CI runs — no
provider client is constructed at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from emendrix.core import CorpusAdapter, Delta, ProvisionText
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eval_.corpus import CorpusCase, EvalCorpus
from emendrix.eval_.judge import Triple, judge_model, sample
from emendrix.eval_.judgements import replay
from emendrix.eval_.metrics import CaseResult
from emendrix.eval_.model_metrics import (
    SUBSET_CASSETTE_DIR,
    ChangeOutcome,
    ModelCaseResult,
    ModelMetrics,
    pool,
)
from emendrix.eval_.runner import CorpusReader, EvalRun, prepare_case, version_id
from emendrix.eval_.signoff import latest_signoff, review_status
from emendrix.eval_.subset import restrict
from emendrix.eval_.worksheet import worksheet_path, write_worksheet
from emendrix.explain import (
    CassetteMode,
    CassetteStore,
    ExplainContext,
    ExplainEngine,
    ExplainRun,
    ExplainSettings,
    cap_text,
    contexts_for_delta,
    header_block,
)
from emendrix.gate import GatedChange, GatedDelta
from emendrix.graph import stages
from emendrix.graph.deps import PipelineDeps
from emendrix.graph.state import ActRun
from emendrix.watch.events import AmendmentEvent

__all__ = ["SubsetRun", "attach_model_layer", "replay_engine", "run_subset"]


def replay_engine(model_id: str | None = None) -> ExplainEngine:
    """The engine `emendrix eval run` uses: the subset's cassettes, replay only, no key.

    Replay is not a flag the caller may forget here — a model-layer number produced by calling a
    provider during an eval run would be unreproducible by anyone reading the report.
    """
    settings = ExplainSettings(cassette_mode=CassetteMode.REPLAY, cassette_dir=SUBSET_CASSETTE_DIR)
    if model_id is not None:
        settings = settings.model_copy(update={"model_id": model_id})
    return ExplainEngine(settings, cassettes=CassetteStore(SUBSET_CASSETTE_DIR))


@dataclass(frozen=True)
class SubsetRun:
    """What one model-layer run produced: the numbers, and the triples the judge may sample."""

    metrics: ModelMetrics
    triples: tuple[Triple, ...]


def _event(case: CorpusCase, observed_on: date) -> AmendmentEvent:
    """The event `emendrix explain` would synthesise for this transition, rebuilt offline."""
    return AmendmentEvent(
        act=act_id(Celex.parse(case.act)),
        target_version=version_id(case, case.to_version),
        new_version=version_id(case, case.to_version),
        previous_version=version_id(case, case.from_version),
        trigger="eval: pinned explanation subset",
        observed_on=observed_on,
    )


def _text(value: ProvisionText | None) -> str:
    """The verbatim side of a change, or empty where the change has none."""
    return "" if value is None else str(value)


def _outcome(case_id: str, delta: Delta, gated: GatedDelta, index: int) -> ChangeOutcome:
    change, ruled = delta.changes[index], gated.changes[index]
    explanation = ruled.explanation
    sentences = () if explanation is None else explanation.sentences
    note = None if explanation is None else explanation.applicability_note
    all_sentences = (*sentences, *((note,) if note is not None else ()))
    return ChangeOutcome(
        case_id=case_id,
        unit=change.location.canonical,
        change_type=change.change_type,
        outcome=ruled.outcome,
        sentences=len(all_sentences),
        citations=sum(len(item.citations) for item in all_sentences),
        citations_rejected=sum(len(failure.citations) for failure in ruled.failures),
        fallback_sentences=sum(1 for item in all_sentences if item.fallback),
        retried=bool(ruled.complaint),
        replayed=False,
        synthetic=False,
        reason="" if ruled.unavailable is None else ruled.unavailable.reason,
    )


def _triple(
    case_id: str,
    delta: Delta,
    ruled: GatedChange,
    index: int,
    context: ExplainContext | None,
    settings: ExplainSettings,
) -> Triple | None:
    """One judgeable triple, or `None` for a change that shipped no sentences at all.

    The caps are the explain settings' own, so every text on the triple is a text the model read,
    marker and all. Anything that audits these sentences (the LLM judge, the human worksheet) is
    then auditing the evidence the model had rather than a shorter prefix of it, which is the
    difference between measuring faithfulness and measuring how long the provision happened to be.

    `context` is the same `ExplainContext` the prompt was built from, so the surrounding-provision
    block travels with the triple when the prompt carried one. It is empty for every change in
    this corpus, because `ExplainContext.surrounding_text` is `None` throughout it; carrying it
    anyway is what stops the judge ruling on evidence it was not shown, the first time a caller
    supplies the text.

    `header` comes from `header_block`, the same value `build_prompt` printed, so what the judge
    and the reviewer read is the writer's header byte for byte rather than a reconstruction that
    could drift from it.
    """
    explanation = ruled.explanation
    if explanation is None:
        return None
    change = delta.changes[index]
    note = explanation.applicability_note
    texts = tuple(
        item.text for item in (*explanation.sentences, *((note,) if note is not None else ()))
    )
    surrounding = None if context is None else context.surrounding_text
    return Triple(
        case_id=case_id,
        unit=change.location.canonical,
        outcome=ruled.outcome.value,
        change_type=change.change_type.value,
        before=cap_text(_text(change.before), settings.text_char_cap)[0],
        after=cap_text(_text(change.after), settings.text_char_cap)[0],
        context=(
            "" if surrounding is None else cap_text(surrounding, settings.context_char_cap)[0]
        ),
        header=header_block(change),
        sentences=texts,
        fallback=explanation.fallbacks > 0,
    )


async def _run_case(
    deps: PipelineDeps, case: CorpusCase, delta: Delta, before: ActRun
) -> tuple[GatedDelta, GatedDelta, ExplainRun]:
    """explain → gate → (revise → settle), and both rounds' verdicts. The shipped path."""
    run = await stages.explain(deps, before.model_copy(update={"delta": delta}))
    run = stages.gate(deps, run)
    first = run.gated
    if first is None:  # pragma: no cover - a delta always produces a gated round
        raise RuntimeError(f"{case.id}: the gate produced nothing to measure")
    if first.pending:
        run = await stages.revise(deps, run)
        run = stages.settle(deps, run)
    settled = run.gated
    explained = run.explained
    if settled is None or explained is None:  # pragma: no cover - same
        raise RuntimeError(f"{case.id}: the retry cycle did not settle")
    return first, settled, explained


async def run_subset(
    reader: CorpusReader,
    corpus: EvalCorpus,
    *,
    engine: ExplainEngine,
    adapter: CorpusAdapter,
    observed_on: date,
) -> SubsetRun:
    """Explain and gate every pinned change, in the corpus's own order. Replay by default.

    A transition whose documents cannot be read is recorded as an unscored case carrying the
    first-class state, exactly as the deterministic runner does — a corpus that lost a fixture
    must not silently shrink the set a published rate is computed over.
    """
    subset = corpus.explain_subset
    if subset is None:
        return SubsetRun(metrics=ModelMetrics(model_id=engine.settings.model_id), triples=())
    deps = PipelineDeps(adapter=adapter, engine=engine, observed_on=observed_on)
    results: list[ModelCaseResult] = []
    triples: list[Triple] = []
    for pinned in subset.cases:
        case = corpus.case(pinned.case_id)
        if case is None:
            raise LookupError(f"the subset names {pinned.case_id}, which the corpus does not hold")
        prepared = prepare_case(reader, case)
        if isinstance(prepared, CaseResult):
            results.append(_unavailable(pinned.case_id, case, prepared, len(pinned.units)))
            continue
        delta, missing = restrict(prepared.corroboration.delta, pinned.units)
        run = ActRun(
            event=_event(case, observed_on), before=prepared.before.tree, after=prepared.after.tree
        )
        first, settled, explained = await _run_case(deps, case, delta, run)
        # The same call `stages.explain` makes, and pure, so this rebuilds exactly the contexts
        # the prompts were built from rather than a second set that might differ.
        contexts = contexts_for_delta(delta)
        outcomes = tuple(
            _outcome(case.id, delta, settled, index).model_copy(
                update={"replayed": result.replayed, "synthetic": result.synthetic}
            )
            for index, result in enumerate(explained.results)
        )
        triples.extend(
            item
            for index, ruled in enumerate(settled.changes)
            if (item := _triple(case.id, delta, ruled, index, contexts[index], engine.settings))
            is not None
        )
        results.append(
            ModelCaseResult(
                case_id=case.id,
                act=case.act,
                units=len(pinned.units),
                missing_units=missing,
                first_round=first.stats,
                settled=settled.stats,
                explain=explained.stats,
                outcomes=outcomes,
            )
        )
    return SubsetRun(metrics=pool(engine.settings.model_id, tuple(results)), triples=tuple(triples))


def _unavailable(case_id: str, case: CorpusCase, result: CaseResult, units: int) -> ModelCaseResult:
    return ModelCaseResult(
        case_id=case_id,
        act=case.act,
        units=units,
        scored=False,
        state=result.state,
        detail=result.detail,
    )


def attach_model_layer(
    result: EvalRun, subset: SubsetRun | None, *, directory: Path, write: bool
) -> EvalRun:
    """Attach the model layer and the replayed faithfulness sample, and write the worksheet.

    The worksheet goes beside the report rather than into a fixed directory, so a run whose
    report is thrown away — CI's — does not write a review sheet into the checkout. Nothing is
    judged here: `judge.replay` reads committed verdicts off disk and calls nobody.

    This is also the only place `human_review` is ever set, and it is set from a committed
    sign-off whose digest still matches this exact sample. `replay` stays unable to claim a
    review happened, which is the property the field exists to protect; resolving the claim here
    keeps it in the one function that holds both the sample and the report.
    """
    if subset is None:
        return result
    triples = sample(subset.triples)
    sheet = worksheet_path(result.run_date, directory)
    faithfulness = replay(
        triples, judge_model=judge_model(), worksheet=sheet.as_posix()
    ).model_copy(update={"human_review": review_status(latest_signoff(), triples)})
    if write:
        write_worksheet(
            triples,
            faithfulness,
            run_date=result.run_date,
            revision=result.revision,
            directory=directory,
        )
    return result.model_copy(update={"model": subset.metrics, "faithfulness": faithfulness})
