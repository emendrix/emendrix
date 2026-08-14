"""One function per stage of the loop. All but the last take an `ActRun` and return a fuller one.

The nodes in `nodes.py` are adapters onto these; these are adapters onto the packages that do
the work. Nothing here implements a stage: `diff.compute_delta`, `corroborate.corroborate`,
`ExplainEngine.explain_delta` and `gate.first_round` are the stages, and a rule that belongs to
one of them but lives in this file instead is a rule in the wrong package.

`emit` is the exception to the shape and has to be: a report is about the whole run rather than
one act, so it reads the state and returns the document `report.py` defines. It lives here
rather than in `report.py` because it is the only part of EMIT that knows what an `ActRun` is,
and `report.py` must not — the document types are imported by `state.py`.

Two things this module *does* own, both orchestration rather than domain:

- **which trees the gate resolves against** — the two this run fetched, and no others
  (`TreeResolver`), so the check is against text on disk and never a network call;
- **the shape of the one revision** — the failed changes, each with the gate's own complaint,
  run concurrently under the same semaphore size the explain stage uses for its batch.

The determinism invariant, restated where it can be checked: `fetch` is the only function here
that may reach the (cached) corpus, `explain` and `revise` the only ones that may await a
model, and none of them reads a clock.
"""

from __future__ import annotations

import asyncio

from emendrix.core import Delta, ProvisionTree
from emendrix.corroborate import corroborate
from emendrix.diff import compute_delta
from emendrix.explain import (
    ExplainContext,
    ExplainedChange,
    ExplainRun,
    RunStats,
    contexts_for_delta,
)
from emendrix.gate import GatedDelta, GateStats, TreeResolver, first_round, second_round
from emendrix.graph.deps import PipelineDeps
from emendrix.graph.report import EmittedDelta, RunReport, SkippedAct, build_delta_report
from emendrix.graph.state import ActRun, PipelineState
from emendrix.watch.events import AmendmentEvent

__all__ = [
    "corroborate_run",
    "emit",
    "explain",
    "fetch",
    "gate",
    "localise",
    "revise",
    "settle",
]

_NO_PREVIOUS = "the corpus lists no earlier version of this act to compare against"
_NO_VERSION = "the watcher reported no fetchable version"


def fetch(deps: PipelineDeps, event: AmendmentEvent) -> ActRun:
    """FETCH: both sides of the transition, or the first-class state that says why not.

    The only function in this module allowed to reach the corpus, and it reaches it through the
    adapter's disk cache. An event that is not `ready` never gets here with text — it carries
    `ConsolidationPending` or `EnglishUnavailable` and passes straight through.
    """
    target = event.new_version
    if target is None:
        return ActRun(
            event=event,
            unavailable=event.unavailable,
            note="" if event.unavailable is not None else _NO_VERSION,
        )
    if event.previous_version is None:
        return ActRun(event=event, note=_NO_PREVIOUS)
    before = deps.adapter.fetch_version(event.act, event.previous_version)
    if not isinstance(before, ProvisionTree):
        return ActRun(event=event, unavailable=before)
    after = deps.adapter.fetch_version(event.act, target)
    if not isinstance(after, ProvisionTree):
        return ActRun(event=event, before=before, unavailable=after)
    return ActRun(event=event, before=before, after=after)


def localise(run: ActRun) -> ActRun:
    """DELTA: the structural diff, pure and byte-stable, over the two fetched trees."""
    if run.before is None or run.after is None:
        return run
    return run.model_copy(update={"delta": compute_delta(run.before, run.after)})


def corroborate_run(deps: PipelineDeps, run: ActRun) -> ActRun:
    """CORROBORATE: hold the diff against the corpus's other signals, if it has any.

    No `SignalSource` means both other signals are `UNAVAILABLE`, which is silence and never
    dissent — the delta comes through unchanged and nothing ships `disputed` for it.
    """
    delta = run.delta
    if delta is None:
        return run
    signals = (
        None
        if deps.signals is None
        else deps.signals.signals_for(delta.act, delta.from_version, delta.to_version)
    )
    merged = corroborate(
        delta,
        metadata=None if signals is None else signals.metadata,
        instructions=None if signals is None else signals.instructions,
    )
    return run.model_copy(update={"delta": merged.delta, "corroboration": merged.report})


async def explain(deps: PipelineDeps, run: ActRun) -> ActRun:
    """EXPLAIN: the one stage that awaits a model, over the whole delta at once."""
    delta = run.delta
    if delta is None:
        return run
    explained = await deps.engine.explain_delta(delta, contexts_for_delta(delta))
    return run.model_copy(update={"explained": explained})


def gate(deps: PipelineDeps, run: ActRun) -> ActRun:
    """GATE, first round: check every citation against the set the change was offered.

    `deps` is here for one number, the explain settings' character cap, which the gate needs to
    ask whether an applicability note quotes the text the model was shown. The gate holds no
    settings of its own on purpose, so the cap travels from the stage that built the prompt.
    """
    delta, explained = run.delta, run.explained
    if delta is None or explained is None:
        return run
    gated = first_round(
        delta,
        explained,
        _checked_contexts(deps, run, delta),
        _resolver(run),
        text_char_cap=deps.engine.settings.text_char_cap,
    )
    return run.model_copy(update={"gated": gated})


async def revise(deps: PipelineDeps, run: ActRun) -> ActRun:
    """The one retry: re-ask for exactly the changes the gate rejected. It does not judge them.

    The answers are parked on the run and the *gate* rules on them (`settle`), because a stage
    that both asks the model again and decides whether the answer is acceptable would be the
    model marking its own homework.

    Bounded twice over — one revision per change, ever (`MAX_GATE_RETRIES` in `state.py`), and
    no more concurrent calls than the explain stage's own semaphore allows.
    """
    delta, gated, explained = run.delta, run.gated, run.explained
    if delta is None or gated is None or explained is None or not gated.pending:
        return run
    contexts = contexts_for_delta(delta)
    semaphore = asyncio.Semaphore(deps.engine.settings.max_concurrency)

    async def one(index: int) -> tuple[int, ExplainedChange]:
        async with semaphore:
            return index, await _revise_one(deps, delta, gated, explained, index, contexts[index])

    answers = await asyncio.gather(*(one(index) for index in gated.pending))
    return run.model_copy(update={"revisions": tuple(answers)})


def settle(deps: PipelineDeps, run: ActRun) -> ActRun:
    """GATE, second round: rule on the revisions, and every change gets a final answer.

    Takes `deps` for the same one number `gate` does, and for the same reason.
    """
    delta, gated, explained = run.delta, run.gated, run.explained
    if delta is None or gated is None or explained is None or not run.revisions:
        return run
    revised = dict(run.revisions)
    return run.model_copy(
        update={
            "gated": second_round(
                gated,
                delta,
                revised,
                _checked_contexts(deps, run, delta),
                _resolver(run),
                text_char_cap=deps.engine.settings.text_char_cap,
            ),
            "explained": _merge(explained, revised),
            "revisions": (),
        }
    )


async def _revise_one(
    deps: PipelineDeps,
    delta: Delta,
    gated: GatedDelta,
    explained: ExplainRun,
    index: int,
    context: ExplainContext | None,
) -> ExplainedChange:
    """One rejected change, re-asked with the gate's own complaint attached."""
    prior = explained.results[index].explanation
    if prior is None or context is None:  # pragma: no cover - only explained changes are pending
        raise ValueError(f"change {index} was sent for revision without a prior explanation")
    return await deps.engine.revise(
        delta.changes[index], context, prior, gated.changes[index].complaint
    )


def _merge(explained: ExplainRun, revised: dict[int, ExplainedChange]) -> ExplainRun:
    """The explain run with the revisions folded in, and both calls' tokens counted.

    A retry costs real money, so its usage is added to the first call's rather than replacing
    it, the same reason `explain/results.py` makes usage a field and not a log line.
    """
    results = list(explained.results)
    for index, answer in revised.items():
        results[index] = answer.model_copy(
            update={"usage": results[index].usage.plus(answer.usage)}
        )
    return ExplainRun(
        results=tuple(results), stats=RunStats.over(explained.stats.model_id, tuple(results))
    )


def emit(deps: PipelineDeps, state: PipelineState) -> RunReport:
    """EMIT: every run assembled into one typed document. Pure, ordered, byte-stable.

    A run that produced no delta is not dropped — it appears in `skipped` carrying the
    first-class state or the note that says why, because a watched act nobody could diff is a
    result and an empty report with a silent hole in it is not.

    The only thing this needs from the corpus is `render_citation`, passed as a function, which
    is where an opaque key finally becomes a URL (`report.py`).
    """
    deltas: list[EmittedDelta] = []
    skipped: list[SkippedAct] = []
    totals = GateStats()
    for run in state.runs:
        if run.delta is None or run.gated is None:
            skipped.append(
                SkippedAct(
                    act=run.act,
                    target_version=run.event.target_version,
                    reason=run.blocked or "no gated delta",
                )
            )
            continue
        totals = totals.plus(run.gated.stats)
        deltas.append(
            build_delta_report(
                run.delta,
                run.gated,
                contexts_for_delta(run.delta),
                deps.adapter.render_citation,
                corroboration=run.corroboration,
                explain=None if run.explained is None else run.explained.stats,
            )
        )
    return RunReport(
        observed_on=state.observed_on,
        poll=state.poll,
        deltas=tuple(deltas),
        skipped=tuple(skipped),
        gate=totals,
    )


def _resolver(run: ActRun) -> TreeResolver:
    """Resolution against exactly the two trees this run fetched. No network, no clock."""
    return TreeResolver(tree for tree in (run.before, run.after) if tree is not None)


def _checked_contexts(
    deps: PipelineDeps, run: ActRun, delta: Delta
) -> tuple[ExplainContext | None, ...]:
    """Contexts with the coordinate-support sets filled from this run's two trees.

    Only the gate's two rounds need them: the prompt does not read the sets, so `explain`
    builds its contexts bare, and the offered keys, which are what the two stages must agree
    on, are a pure function of the delta either way. The cap is the explain settings' own,
    for the same reason `gate` passes it to the note check: the sets describe the text the
    model was shown or they describe nothing.
    """
    return contexts_for_delta(
        delta,
        before_tree=run.before,
        after_tree=run.after,
        text_char_cap=deps.engine.settings.text_char_cap,
    )
