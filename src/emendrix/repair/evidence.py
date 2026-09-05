"""The fetching repair: an explanation written about text a later parser fix has corrected.

**This is the one repair that fetches, and its siblings must not.** `explanations` rebuilds its
prompt from the committed payload precisely so that it never describes a document the page does
not show, and `corroboration` recomputes a signal and never touches stored text at all. Both are
right, and neither can fix this: pointed at a change whose stored text a parser fix has since
corrected, the first would faithfully ask again about the same corrupted text and the second
would carry it over untouched. The defect is *in* the stored evidence, so the corrected evidence
has to be read from the corpus, which is why this verb parses both versions again and re-derives
the delta before it decides anything.

What it does with the result, per change (`staleness.compare` decides which is which, and
`reask.repair` carries it out):

- **the evidence still reads as the evidence published**: the explanation, its gate decision and
  its citations are carried over untouched. This is the common case and it costs nothing;
- **the evidence moved**: the model is asked again, about the corrected text, and the answer is
  gated as the pipeline gates one;
- **today's delta has no such change**: it is withdrawn and counted. A parser fix that stops
  producing a difference legitimately removes a change;
- **today's delta has a change the entry does not**: it is asked about and counted apart from
  the re-asked, because the two answer different questions.

**An entry is rebuilt only where that comparison found something to correct.** A pass over a
whole repository must be the size of the problem: an entry whose every change still reads as
what it was published with is not rewritten, not committed and not paid for.

**A limited pass starts an entry or it does not, and never asks about half of one.** Writing the
corrected text under a change nobody re-explained would leave prose about one text beside
another, and would leave the next pass unable to see that the change is still stale, so a budget
that cannot cover an entry stops the pass instead of splitting it.

The corpus is reached only through the adapter, and only in `rederive`. Nothing here reads a
clock, and what one entry costs is `reask`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import CorpusAdapter
from emendrix.explain import ExplainEngine, ExplainSettings
from emendrix.graph.report import CitationRenderer
from emendrix.repair.entry import RepairResult, RepairTarget
from emendrix.repair.pricing import Selection, selection_for
from emendrix.repair.reask import repair
from emendrix.repair.rederive import Trees, read
from emendrix.repair.staleness import EvidencePlan

__all__ = ["KIND", "EntryPlan", "PassCounts", "plan_over", "repair_all"]

KIND: Final = "evidence"
"""What this repair is called, on the command line and in the record it writes."""

_BUDGET = "stopped before {act} {version}: it would ask about {asked} changes, {left} left"
"""Said where a limited pass declines to start an entry it cannot pay for all of."""


class PassCounts(BaseModel):
    """What one pass looked at beyond the entries it has something to say about."""

    model_config = ConfigDict(frozen=True)

    examined: int = Field(default=0, ge=0)
    underivable: tuple[str, ...] = Field(
        default=(), description="One note per transition today's parse could not produce."
    )
    stopped: str = Field(default="", description="Why the pass ended early. Empty if it did not.")


class EntryPlan(BaseModel):
    """One published entry held against today's parse, with what asking again would cost."""

    model_config = ConfigDict(frozen=True)

    target: RepairTarget
    plan: EvidencePlan
    selection: Selection | None = Field(
        default=None, description="The prompts a pass would send. None where it would send none."
    )


def plan_over(
    targets: Sequence[RepairTarget],
    adapter: CorpusAdapter,
    settings: ExplainSettings,
    *,
    limit: int | None = None,
) -> tuple[tuple[EntryPlan, ...], PassCounts]:
    """Every entry a pass would correct, with its prompts built and measured. No engine at all.

    The prompts are built and thrown away, which is the point of building them: it costs
    nothing and it is the only honest way to say how much text a pass would pay to send.
    """
    trees = Trees(adapter)
    plans: list[EntryPlan] = []
    counts = PassCounts()
    budget = limit
    for target in targets:
        counts = counts.model_copy(update={"examined": counts.examined + 1})
        found, note = read(target, trees)
        if found is None:
            counts = counts.model_copy(update={"underivable": (*counts.underivable, note)})
            continue
        if not found.plan.moves:
            continue
        stop = _refused(target, found.plan, budget)
        if stop:
            counts = counts.model_copy(update={"stopped": stop})
            break
        asked = tuple(found.delta.changes[index] for index in found.plan.asked)
        plans.append(
            EntryPlan(
                target=target,
                plan=found.plan,
                selection=selection_for(target.entry, asked, settings) if asked else None,
            )
        )
        budget = None if budget is None else budget - len(asked)
    return tuple(plans), counts


async def repair_all(
    targets: Sequence[RepairTarget],
    adapter: CorpusAdapter,
    engine: ExplainEngine,
    *,
    render: CitationRenderer,
    limit: int | None = None,
) -> tuple[tuple[RepairResult, ...], PassCounts]:
    """One entry at a time, to the change budget, and what the pass looked at to find them.

    Serial across entries, as `explanations` is: the engine already runs the changes of one
    entry concurrently and a second concurrency model for one effect is one too many.

    `limit` counts changes asked about, and an entry is either asked about in full or not
    started. Asking about half of one would write the corrected text under every change it did
    not reach, and a change whose text is corrected and whose prose is not is a change the next
    pass can no longer tell is stale.
    """
    trees = Trees(adapter)
    results: list[RepairResult] = []
    counts = PassCounts()
    budget = limit
    for target in targets:
        counts = counts.model_copy(update={"examined": counts.examined + 1})
        found, note = read(target, trees)
        if found is None:
            counts = counts.model_copy(update={"underivable": (*counts.underivable, note)})
            continue
        if not found.plan.moves:
            continue
        stop = _refused(target, found.plan, budget)
        if stop:
            counts = counts.model_copy(update={"stopped": stop})
            break
        results.append(await repair(found, target, engine, render=render))
        budget = None if budget is None else budget - len(found.plan.asked)
    return tuple(results), counts


# ------------------------------------------------------------------ the pieces


def _refused(target: RepairTarget, plan: EvidencePlan, budget: int | None) -> str:
    """Why a limited pass declines to start this entry, or empty where it can pay for it."""
    if budget is None or len(plan.asked) <= budget:
        return ""
    return _BUDGET.format(
        act=target.entry.act.key,
        version=target.entry.to_version,
        asked=len(plan.asked),
        left=budget,
    )
