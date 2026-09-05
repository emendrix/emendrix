"""The paid repair: a change that shipped with no explanation, asked again from its payload.

A change the model answered about, where the answer was unusable, is the one gap a repair can
close. The other three counted reasons are answers rather than failures: the diff saw no text
to ask about, or the whole difference fell past the prompt's character cap so the two texts
would be identical, and a provider that never answered leaves the entry unfinished, which the
resume path completes on its own. Only the first is selected here, and the other three are
never touched.

**The prompt is rebuilt from the committed payload and nothing is fetched.** Each stored change
carries both verbatim texts, and the context and the prompt are pure functions of a change, the
two versions and the settings, so the model is shown exactly the text the committed page shows.
Re-fetching would run today's parser over a document whose stored text predates a parser fix
and produce an explanation of text no reader can see, which is the failure the citation gate
exists to prevent.

**Two things a payload-only repair cannot do, and both are recorded rather than assumed.** The
coordinate-support sets are computed from the two provision trees, which this holds none of, so
every context carries `coordinates_checked=False` and the gate counts nothing rather than
counting every mention of a coordinate as unsupported. And a citation resolves against the
texts the entry itself carries (`PayloadResolver`) rather than against two whole trees.

**A change asked again records what it was shown, and nothing else does.** The re-ask is a call
this pass watched, over the texts the payload holds, so an evidence digest for that one change
states a fact rather than assuming one. Every sibling keeps the provenance it arrived with, and
an entry that carried none still says so.

**A change that fails again is left exactly as it was found and counted.** Its committed reason
stays: rewriting it would replace a sentence a reader has already seen with the same sentence
written today, and stamping a kind onto a change that predates the field is a migration rather
than a repair. The two cassette faults propagate, because an unrecorded prompt and a cassette
that is not the exchange its name claims are build faults and not answers about a change.

Core types, the committed document and the explain engine. No corpus, no clock, no network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from typing import Final

from emendrix.core import Change, Delta, ProvisionRef
from emendrix.explain import (
    MODEL_FAILED,
    CallUsage,
    ExplainContext,
    ExplainEngine,
    ExplainRun,
    RunStats,
    build_context,
    explainable,
)
from emendrix.gate import Resolution, first_round, second_round
from emendrix.graph.report import CitationRenderer, EmittedChange, build_delta_report
from emendrix.output import ChangelogEntry, EvidenceDigest, digest_of
from emendrix.output.provenance import keys_of, merged
from emendrix.repair.entry import RepairResult, RepairTarget, delta_of, moved, rebuild

__all__ = ["KIND", "PayloadResolver", "needs", "repair", "repair_all", "selected"]

KIND: Final = "explanations"
"""What this repair is called, on the command line and in the record it writes."""

_MODEL_FAILED_KIND: Final = "model_failed"
"""The counted kind of a change the model answered about, unusably."""


class PayloadResolver:
    """The provisions this entry carries text for, which are the provisions the reader sees.

    The offered set is minted from the same refs, so every key the model could legitimately
    cite resolves, and a key from anywhere else is rejected as unknown before resolution is
    asked at all. This is a narrower check than the pipeline's, which resolves against the two
    whole trees: it cannot catch an offered key naming a provision the version does not
    contain, and it answers `UNCHECKABLE` rather than `PRESENT` for anything it was not given.
    """

    def __init__(self, entry: ChangelogEntry) -> None:
        self._present = frozenset(_offered_refs(entry))

    def resolves(self, ref: ProvisionRef) -> Resolution:
        return Resolution.PRESENT if ref in self._present else Resolution.UNCHECKABLE


def selected(entry: ChangelogEntry) -> tuple[int, ...]:
    """Indices of the changes this repair addresses: the ones the model failed on.

    Two tests, because the counted kind is younger than the entries: a change written before
    the field existed carries the curated reason and no kind at all. That reason is safe to
    match on where a library's own error text would not be, because it is one of a small set of
    constants this project curates and an exception's text never reaches a published document.
    """
    return tuple(
        index
        for index, item in enumerate(entry.changes)
        if item.unexplained_kind == _MODEL_FAILED_KIND or item.unexplained.startswith(MODEL_FAILED)
    )


def needs(target: RepairTarget) -> bool:
    """Whether this repair has anything to ask about in one entry."""
    return bool(selected(target.entry))


async def repair(
    target: RepairTarget,
    engine: ExplainEngine,
    *,
    render: CitationRenderer,
    limit: int | None = None,
) -> RepairResult:
    """Ask the model again for the changes of one entry that carry no explanation.

    The selected changes go together, under the engine's own semaphore, which is the one
    concurrency model this project has. `limit` caps how many of them this pass addresses; a
    change it does not reach keeps its committed state and is selected again next time.

    The rebuilt entry rides on the result only when it differs from what is committed, so a
    caller may run this over a whole repository and write nothing where nothing moved.
    """
    entry = target.entry
    indices = selected(entry)[:limit]
    if not indices:
        return RepairResult(target=target)
    resolver = PayloadResolver(entry)
    semaphore = asyncio.Semaphore(engine.settings.max_concurrency)

    async def one(index: int) -> tuple[int, EmittedChange | None, CallUsage]:
        async with semaphore:
            settled, spent = await _explained(entry, index, engine, resolver, render)
            return index, settled, spent

    answers = await asyncio.gather(*(one(index) for index in indices))
    changes = list(entry.changes)
    detail: list[str] = []
    usage = CallUsage()
    repaired = 0
    witnessed: list[int] = []
    for index, settled, spent in answers:
        usage = usage.plus(spent)
        unit = entry.changes[index].change.location.canonical
        if settled is None:
            detail.append(f"{unit}: still unexplained")
            continue
        changes[index] = settled
        repaired += 1
        witnessed.append(index)
        detail.append(f"{unit}: explained")
    rebuilt = rebuild(
        entry,
        delta=delta_of(entry),
        corroboration=entry.corroboration,
        changes=tuple(changes),
        evidence=_witnessed(entry, tuple(changes), witnessed),
    )
    return RepairResult(
        target=target,
        addressed=len(indices),
        repaired=repaired,
        remaining=len(indices) - repaired,
        entry=rebuilt if moved(entry, rebuilt) else None,
        detail=tuple(detail),
        usage=usage,
    )


async def repair_all(
    targets: Sequence[RepairTarget],
    engine: ExplainEngine,
    *,
    render: CitationRenderer,
    limit: int | None = None,
) -> tuple[tuple[RepairResult, ...], int]:
    """One entry at a time, to the change budget, and how many entries were looked at.

    Serial across entries on purpose: the engine already runs the changes of one entry
    concurrently, and a second concurrency model for one effect is one too many.
    """
    results: list[RepairResult] = []
    examined = 0
    budget = limit
    for target in targets:
        if budget is not None and budget <= 0:
            break
        examined += 1
        if not needs(target):
            continue
        found = await repair(target, engine, render=render, limit=budget)
        results.append(found)
        budget = None if budget is None else budget - found.addressed
    return tuple(results), examined


# ------------------------------------------------------------------ the pieces


def _witnessed(
    entry: ChangelogEntry, changes: tuple[EmittedChange, ...], repaired: Sequence[int]
) -> tuple[EvidenceDigest, ...]:
    """The entry's digests, plus one for every change this pass actually asked about again.

    A re-ask is a call this pass watched, over the very texts the payload holds, so recording
    what it was shown asserts nothing it did not see. Every sibling keeps whatever provenance
    it had, which for an entry published before the field existed is none.
    """
    keys = keys_of(item.change for item in changes)
    written = tuple(
        EvidenceDigest(
            location=keys[index][0],
            occurrence=keys[index][1],
            digest=digest_of(changes[index].change),
        )
        for index in repaired
    )
    return merged(entry.evidence, written)


def _context_for(entry: ChangelogEntry, change: Change) -> ExplainContext:
    """The context the explain stage built for this change, rebuilt from the payload.

    No trees and no cap, so `coordinates_checked` is False: the prompt is identical either way
    and the gate then counts nothing rather than counting every mention as unsupported.
    """
    return build_context(change, from_version=entry.from_version, to_version=entry.to_version)


def _offered_refs(entry: ChangelogEntry) -> Iterator[ProvisionRef]:
    """Every provision the entry's own changes could offer a key for."""
    for item in entry.changes:
        if not explainable(item.change):
            continue
        for offered in _context_for(entry, item.change).offered:
            yield offered.ref


async def _explained(
    entry: ChangelogEntry,
    index: int,
    engine: ExplainEngine,
    resolver: PayloadResolver,
    render: CitationRenderer,
) -> tuple[EmittedChange | None, CallUsage]:
    """One change asked again and gated as a delta of its own, or None when it failed again.

    A one-change delta makes the positional pairing the explain stage and the gate both
    enforce trivially satisfiable, and it is the honest shape: the unit of repair is the
    change. The cap handed to the gate is the one that built the prompt, or the applicability
    note would be checked against a text nobody was shown.
    """
    change = entry.changes[index].change
    context = _context_for(entry, change)
    delta = Delta(
        act=entry.act,
        from_version=entry.from_version,
        to_version=entry.to_version,
        changes=(change,),
    )
    cap = engine.settings.text_char_cap
    answer = await engine.explain_change(change, context)
    usage = answer.usage
    run = ExplainRun(results=(answer,), stats=RunStats.over(engine.settings.model_id, (answer,)))
    gated = first_round(delta, run, (context,), resolver, text_char_cap=cap)
    if gated.pending:
        prior = answer.explanation
        if prior is None:  # pragma: no cover - only an explained change is ever pending
            raise ValueError(f"{change.location.canonical} was sent for revision with no answer")
        revised = await engine.revise(change, context, prior, gated.changes[0].complaint)
        usage = usage.plus(revised.usage)
        gated = second_round(gated, delta, {0: revised}, (context,), resolver, text_char_cap=cap)
    settled = build_delta_report(delta, gated, (context,), render).changes[0]
    return (settled if settled.sentences else None), usage
