"""Asking again about the changes of one entry whose evidence moved, and splicing the answers.

Split from `evidence.py` at the line the command itself draws: walking a repository to a budget
is one job and correcting one entry is another, and the second is where the money is spent. What
is here is the whole of the paid path, so the mode that must not spend imports none of it.

**A change is asked about as a delta of its own.** That makes the positional pairing the explain
stage and the gate both enforce trivially satisfiable, and it is the honest shape: the unit of
this repair is the change whose evidence moved, not the transition it sits in.

**The gate resolves against the two trees this pass parsed.** A repair working from a payload
can only record that no coordinate check ran; this one holds both versions, so the check runs
and the change is gated exactly as the pipeline gates one.

**A change the model fails on again is put back exactly as it was committed**, its prose and the
text that prose was written about together. Splitting the pair would leave a reader prose about
one text beside another, and would leave the next pass unable to see that the change is still
stale. It is counted, and it is never reported as repaired.

**Only a change this pass asked about records what it was shown.** The call was watched here,
over the very texts it derived, so the digest states a fact rather than assuming one; every
sibling keeps the provenance it arrived with, which for an entry published before the field
existed is none.

Core types, the committed document, the explain engine and the gate. No corpus, no clock.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from emendrix.core import Change, Delta
from emendrix.explain import CallUsage, ExplainEngine, ExplainRun, RunStats, build_context
from emendrix.gate import TreeResolver, first_round, second_round
from emendrix.graph.report import CitationRenderer, EmittedChange, build_delta_report
from emendrix.output import ChangelogEntry, EvidenceDigest, digest_of
from emendrix.output.provenance import ChangeKey, keys_of, merged
from emendrix.repair.corroborate import textless_change
from emendrix.repair.entry import RepairResult, RepairTarget, moved, rebuild
from emendrix.repair.rederive import Derivation, Rederived

__all__ = ["repair"]


async def repair(
    found: Rederived, target: RepairTarget, engine: ExplainEngine, *, render: CitationRenderer
) -> RepairResult:
    """Rebuild one entry from today's parse, asking again only where the evidence moved.

    The rebuilt entry rides on the result only when it differs from what is committed, so a
    caller may run this over a whole repository and write nothing where nothing moved.
    """
    entry, plan, delta = target.entry, found.plan, found.delta
    semaphore = asyncio.Semaphore(engine.settings.max_concurrency)

    async def one(index: int) -> tuple[int, EmittedChange, CallUsage]:
        async with semaphore:
            settled, spent = await _explained(
                entry, delta.changes[index], found.derivation, engine, render
            )
            return index, settled, spent

    answered = await asyncio.gather(*(one(index) for index in plan.asked))
    answers = {index: settled for index, settled, _ in answered}
    usage = CallUsage()
    for _, _, spent in answered:
        usage = usage.plus(spent)
    changes, detail, repaired, witnessed = _rebuilt(entry, delta.changes, answers)
    rebuilt = rebuild(
        entry,
        delta=delta,
        corroboration=found.report,
        changes=changes,
        evidence=_witnessed(entry, changes, witnessed),
    )
    return RepairResult(
        target=target,
        addressed=len(plan.asked),
        repaired=repaired,
        remaining=len(plan.asked) - repaired,
        entry=rebuilt if moved(entry, rebuilt) else None,
        detail=(*detail, *(f"{unit}: withdrawn" for unit in plan.withdrawn)),
        usage=usage,
    )


# ------------------------------------------------------------------ the pieces


def _rebuilt(
    entry: ChangelogEntry, changes: Sequence[Change], answers: dict[int, EmittedChange]
) -> tuple[tuple[EmittedChange, ...], tuple[str, ...], int, tuple[int, ...]]:
    """Today's changes, each carrying the prose it is entitled to, and what that took.

    A change asked about successfully carries the new answer; one that failed again is put back
    exactly as it was committed, evidence and prose together, and a new change that failed is
    the state the pipeline would have shipped it in.
    """
    committed = _by_location(entry)
    keyed = keys_of(changes)
    built: list[EmittedChange] = []
    detail: list[str] = []
    repaired = 0
    witnessed: list[int] = []
    for index, change in enumerate(changes):
        key = keyed[index]
        found = committed.get(key)
        if index in answers:
            settled = answers[index]
            asked = "asked" if found is None else "re-asked"
            if settled.sentences:
                built.append(settled)
                witnessed.append(index)
                repaired += 1
                detail.append(f"{key[0]}: {asked}")
            else:
                built.append(settled if found is None else found)
                detail.append(f"{key[0]}: {asked}, and left as it was")
        elif change.textless:
            built.append(textless_change(change))
            detail.append(f"{key[0]}: no text on either side")
        elif found is not None:
            built.append(found.model_copy(update={"change": change}))
        else:  # pragma: no cover - a change with text is either carried over or asked about
            raise ValueError(f"{key[0]} is neither published nor asked about")
    return tuple(built), tuple(detail), repaired, tuple(witnessed)


def _by_location(entry: ChangelogEntry) -> dict[ChangeKey, EmittedChange]:
    """Every committed change keyed as its evidence is keyed: location, then occurrence."""
    changes = [item.change for item in entry.changes]
    return dict(zip(keys_of(changes), entry.changes, strict=True))


def _witnessed(
    entry: ChangelogEntry, changes: Sequence[EmittedChange], asked: Sequence[int]
) -> tuple[EvidenceDigest, ...]:
    """The entry's digests, plus one for every change this pass was itself shown the text of."""
    keys = keys_of(item.change for item in changes)
    written = tuple(
        EvidenceDigest(
            location=keys[index][0],
            occurrence=keys[index][1],
            digest=digest_of(changes[index].change),
        )
        for index in asked
    )
    return merged(entry.evidence, written)


async def _explained(
    entry: ChangelogEntry,
    change: Change,
    derived: Derivation,
    engine: ExplainEngine,
    render: CitationRenderer,
) -> tuple[EmittedChange, CallUsage]:
    """One change asked about and gated as a delta of its own, over the two trees just parsed.

    The prompt is built from a context with no trees, exactly as the explain stage builds one,
    and the gate is given a context filled from both of them, exactly as the pipeline does.
    So a coordinate check runs here where a payload-only repair could only record that none
    did, and the question the model is asked is the question the loop asks.
    """
    delta = Delta(
        act=entry.act,
        from_version=entry.from_version,
        to_version=entry.to_version,
        changes=(change,),
    )
    cap = engine.settings.text_char_cap
    context = build_context(change, from_version=entry.from_version, to_version=entry.to_version)
    inspected = build_context(
        change,
        from_version=entry.from_version,
        to_version=entry.to_version,
        before_tree=derived.before,
        after_tree=derived.after,
        text_char_cap=cap,
    )
    resolver = TreeResolver(tree for tree in (derived.before, derived.after) if tree is not None)
    answer = await engine.explain_change(change, context)
    usage = answer.usage
    run = ExplainRun(results=(answer,), stats=RunStats.over(engine.settings.model_id, (answer,)))
    gated = first_round(delta, run, (inspected,), resolver, text_char_cap=cap)
    if gated.pending:
        prior = answer.explanation
        if prior is None:  # pragma: no cover - only an explained change is ever pending
            raise ValueError(f"{change.location.canonical} was sent for revision with no answer")
        revised = await engine.revise(change, context, prior, gated.changes[0].complaint)
        usage = usage.plus(revised.usage)
        gated = second_round(gated, delta, {0: revised}, (inspected,), resolver, text_char_cap=cap)
    return build_delta_report(delta, gated, (context,), render).changes[0], usage
