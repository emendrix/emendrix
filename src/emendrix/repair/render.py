"""What a repair prints: the table an operator decides from, and the line it ends on.

Split from `cli.py` for the reason `backfill/render.py` was: a command that reaches into
committed documents is one an operator wants to read the effect of before it writes anything,
and "what an operator sees" is a real seam rather than an arbitrary cut.

**The disputed-flag flips get their own column and their own total.** A unit that stops being
disputed had its explanation written with a line in the prompt saying the signals disagreed, so
that count is what decides whether any committed prose was written under a question that is now
false. It cannot be read off the published record and a dry run is the only way to get it.

**A price is printed with the model and the rates beside it, and with what it leaves out.** An
operator agreeing to spend is agreeing to spend on a named model at a published rate, and a
figure with neither of those on the same line is a number to be taken on trust.

Nothing here reads a clock, a network or a model: it is given the results and it prints them.
"""

from __future__ import annotations

from collections.abc import Sequence

import typer
from pydantic import BaseModel, ConfigDict, Field

from emendrix.explain import rate_for
from emendrix.graph.cli import SummaryFormat
from emendrix.repair.entry import RepairResult, UnitShift, shift_between
from emendrix.repair.evidence import EntryPlan, PassCounts
from emendrix.repair.pricing import Estimate, Selection, estimate_over

__all__ = [
    "RepairSummary",
    "report_estimate",
    "report_pass",
    "report_plan",
    "report_results",
    "report_selection",
    "report_summary",
    "shift_of",
]


class RepairSummary(BaseModel):
    """One repair pass as counts alone, for a log stream rather than for a reader.

    The same reasoning as `backfill.render.BackfillSummary`: the entries are the whole answer
    and the wrong thing to log, so the line a collector keeps is bounded by how many entries a
    pass examined and never by how much is inside them.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    examined: int = Field(ge=0)
    would_change: int = Field(default=0, ge=0)
    changes_repaired: int = Field(default=0, ge=0)
    changes_remaining: int = Field(default=0, ge=0)
    units_gained: int = Field(default=0, ge=0)
    units_dropped: int = Field(default=0, ge=0)
    disputed_flipped: int = Field(default=0, ge=0)
    written: int = Field(default=0, ge=0, description="Entries committed. Zero on a dry run.")


def shift_of(result: RepairResult) -> UnitShift:
    """What one result would move. An empty shift where the entry did not change at all."""
    rebuilt = result.entry
    return UnitShift() if rebuilt is None else shift_between(result.target.entry, rebuilt)


def report_results(results: Sequence[RepairResult]) -> None:
    """One line per entry that would change, then the totals. Nothing is written by any of it."""
    for result in results:
        if result.entry is None:
            continue
        shift = shift_of(result)
        entry = result.target.entry
        typer.echo(
            f"{entry.act.key}: {entry.from_version} -> {entry.to_version} · "
            f"{len(shift.gained)} units gained · {len(shift.dropped)} units dropped · "
            f"{len(shift.disputed_flipped)} disputed flags flipped · "
            f"{result.repaired} changes repaired"
        )
        for line in result.detail:
            typer.echo(f"  {line}")


def report_summary(
    format_: SummaryFormat,
    results: Sequence[RepairResult],
    *,
    kind: str,
    examined: int,
    written: int = 0,
) -> RepairSummary:
    """The closing line, and the same counts as one JSON object where a collector wants them.

    Returned as well as printed, because a caller that has just written a repository wants the
    totals it reports to be the totals it printed rather than a second count of the same thing.
    """
    shifts = [shift_of(result) for result in results]
    totals = RepairSummary(
        kind=kind,
        examined=examined,
        would_change=sum(1 for result in results if result.entry is not None),
        changes_repaired=sum(result.repaired for result in results),
        changes_remaining=sum(result.remaining for result in results),
        units_gained=sum(len(shift.gained) for shift in shifts),
        units_dropped=sum(len(shift.dropped) for shift in shifts),
        disputed_flipped=sum(len(shift.disputed_flipped) for shift in shifts),
        written=written,
    )
    typer.echo(
        f"examined {totals.examined} entries · {totals.would_change} would change · "
        f"{totals.changes_repaired} changes repaired · {totals.changes_remaining} not repaired · "
        f"{totals.units_gained} units gained · {totals.units_dropped} units dropped · "
        f"{totals.disputed_flipped} disputed flags flipped"
    )
    if format_ is SummaryFormat.JSON:
        typer.echo(totals.model_dump_json(), err=True)
    return totals


def report_selection(selections: Sequence[Selection]) -> None:
    """One line per entry a repair would address, then the changes it would ask about.

    The changes are named rather than counted, because the selection is the thing a wrong
    predicate would get wrong, and a count cannot show that.
    """
    for item in selections:
        typer.echo(
            f"{item.act}: {item.from_version} -> {item.to_version} · "
            f"{len(item.units)} changes · {item.prompt_chars} prompt characters"
        )
        for unit in item.units:
            typer.echo(f"  {unit}")


def report_estimate(format_: SummaryFormat, estimate: Estimate) -> Estimate:
    """What a selection would cost, the model and the rates that price it, and what it omits.

    Returned as well as printed for the reason `report_summary` is: a caller reporting the
    total wants the one it printed rather than a second computation of the same thing.
    """
    rate = rate_for(estimate.model_id)
    priced = (
        "unpriced (no published rate on file)"
        if estimate.cost_usd is None or rate is None
        else f"about ${estimate.cost_usd:.4f} at ${rate.input_per_mtok:.2f} in and "
        f"${rate.output_per_mtok:.2f} out per 1M tokens (checked {rate.checked_on})"
    )
    typer.echo(
        f"{estimate.changes} changes in {estimate.entries} entries · "
        f"{estimate.prompt_chars} prompt characters · about {estimate.usage.input_tokens} input "
        f"and {estimate.usage.output_tokens} output tokens · {estimate.model_id} · {priced}"
    )
    typer.echo(
        "that price is a floor: one call per change, so it counts neither the gate's one retry "
        "nor a schema repair, and each of those is a further request."
    )
    if format_ is SummaryFormat.JSON:
        typer.echo(estimate.model_dump_json(), err=True)
    return estimate


def report_pass(counts: PassCounts) -> None:
    """What a pass could not read, and why it stopped early if it did.

    Printed by both modes and never folded into a total: a transition nobody could re-derive is
    a coverage gap, and a pass that reports only what it managed to look at reads as a pass over
    everything.
    """
    if counts.underivable:
        typer.echo(f"{len(counts.underivable)} transitions could not be re-derived today:")
        for note in counts.underivable:
            typer.echo(f"  {note}")
    if counts.stopped:
        typer.echo(counts.stopped)


def report_plan(
    format_: SummaryFormat, plans: Sequence[EntryPlan], counts: PassCounts, *, model_id: str
) -> Estimate:
    """What re-deriving the corpus would correct, and what asking again about it would cost.

    The figures answer different questions and are never summed: a change re-asked is one whose
    evidence moved, a change added is one today's parse finds and the entry does not, a change
    withdrawn is one it no longer finds at all, and a change carried is one whose sentences this
    pass would leave exactly as they are. The corrected are the carried whose stored text moved
    anyway, which a recorded digest settles without a call, and they cost nothing.
    """
    for item in plans:
        entry, plan = item.target.entry, item.plan
        typer.echo(
            f"{entry.act.key}: {entry.from_version} -> {entry.to_version} · "
            f"{len(plan.reasked)} re-asked · {len(plan.added)} added · "
            f"{len(plan.withdrawn)} withdrawn · {len(plan.carried)} carried · "
            f"{len(plan.restored)} texts corrected unasked"
        )
        for unit in () if item.selection is None else item.selection.units:
            typer.echo(f"  {unit}: asked again")
        for unit in plan.withdrawn:
            typer.echo(f"  {unit}: withdrawn")
    typer.echo(
        f"examined {counts.examined} entries · {len(plans)} would be corrected · "
        f"{sum(len(item.plan.reasked) for item in plans)} changes re-asked · "
        f"{sum(len(item.plan.added) for item in plans)} added · "
        f"{sum(len(item.plan.withdrawn) for item in plans)} withdrawn · "
        f"{sum(len(item.plan.carried) for item in plans)} carried · "
        f"{sum(len(item.plan.restored) for item in plans)} texts corrected unasked · "
        f"{sum(len(item.plan.emptied) for item in plans)} newly with no text on either side"
    )
    report_pass(counts)
    typer.echo("dry run: nothing written, nothing asked, no engine built.")
    selections = [item.selection for item in plans if item.selection is not None]
    return report_estimate(format_, estimate_over(selections, model_id=model_id))
