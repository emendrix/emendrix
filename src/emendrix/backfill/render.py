"""What a backfill prints: the table an operator decides from, and the line it ends on.

Split from `cli.py` because the command sits close to the module cap once the lock and the
interruption path are in it, and because "what an operator sees" is a real seam rather than an
arbitrary cut.

The rule this module exists to keep is that **settled and given-up-on are counted separately**.
They mean opposite things, one is work finished and the other is work abandoned, and folding the
second into the first is exactly how a permanently failing act vanishes from a summary that
reads as though everything is fine.

Nothing here reads a clock, a network or a model: it is given the plans, the ledger and the
counts, and it prints them.
"""

from __future__ import annotations

import typer
from pydantic import BaseModel, ConfigDict, Field

from emendrix.backfill.ledger import Ledger
from emendrix.backfill.plan import Transition, TransitionPlan
from emendrix.explain import CallUsage
from emendrix.graph import RunReport
from emendrix.graph.cli import SummaryFormat

__all__ = ["BackfillSummary", "already_emitted", "report_plans", "report_summary", "usage_of"]


class BackfillSummary(BaseModel):
    """One tranche as counts alone, for a log stream rather than for a reader.

    The same reasoning as `graph.report.RunSummary`, restated for a backfill: the reports are
    the whole answer and the wrong thing to log, so the line a collector keeps is bounded by
    how many transitions a run selected and never by how much changed inside them.
    `already_emitted` is what the output repository held before the run started, made visible
    so a tranche's log never reads as though history shrank between runs.
    """

    model_config = ConfigDict(frozen=True)

    transitions_selected: int = Field(ge=0)
    emitted: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    already_emitted: int = Field(default=0, ge=0)
    explain: CallUsage = CallUsage()


def usage_of(report: RunReport) -> CallUsage:
    """One report's summed explain usage. All zeroes when nothing reached the model."""
    total = CallUsage()
    for delta in report.deltas:
        if delta.explain is not None:
            total = total.plus(delta.explain.usage)
    return total


def already_emitted(plans: tuple[TransitionPlan, ...], present: frozenset[str]) -> int:
    """How many planned transitions the output repository held before this run started."""
    return sum(1 for plan in plans for item in plan.transitions if item.key in present)


def report_summary(
    format_: SummaryFormat,
    *,
    selected: int,
    already: int,
    emitted: int = 0,
    skipped: int = 0,
    failed: int = 0,
    usage: CallUsage | None = None,
) -> None:
    """The one line a collector keeps, on stderr so the report stream stays clean.

    Text mode prints nothing here: the table and the `done:` line have already said it all,
    and a person does not want the same counts twice.
    """
    if format_ is not SummaryFormat.JSON:
        return
    tranche = BackfillSummary(
        transitions_selected=selected,
        emitted=emitted,
        skipped=skipped,
        failed=failed,
        already_emitted=already,
        explain=usage if usage is not None else CallUsage(),
    )
    typer.echo(tranche.model_dump_json(), err=True)


def report_plans(
    plans: tuple[TransitionPlan, ...],
    ledger: Ledger,
    retry_limit: int,
    *,
    emitted: frozenset[str] = frozenset(),
    limit: int | None = None,
) -> tuple[Transition, ...]:
    """Print one line per act plus its selected transitions, and return what this run will do.

    Two things are excluded and counted rather than run: what the ledger has settled or given up
    on, and what the output repository already holds (`emitted`). A transition already in the
    repository is *done*, whatever the ledger says, so it is counted with the finished work and
    never with the abandoned.

    `limit` then takes the first N of what is left, oldest first, so history can be read in
    tranches. What the limit held back is printed rather than implied: a cap nobody mentions
    reads as "that was all of it", which is the one thing an operator running tranches must not
    conclude. The selection is deterministic, so the next run continues where this one stopped
    without needing to be told where that was.
    """
    settled, abandoned = ledger.done, ledger.exhausted(retry_limit)
    chosen: list[Transition] = []
    for plan in plans:
        remaining = [
            item
            for item in plan.transitions
            if item.key not in settled and item.key not in abandoned and item.key not in emitted
        ]
        gave_up = [item for item in plan.transitions if item.key in abandoned - emitted]
        in_repo = len([item for item in plan.transitions if item.key in emitted])
        found = f" ({in_repo} of them already in the output repository)" if in_repo else ""
        chosen.extend(remaining)
        typer.echo(
            f"{plan.act}: {plan.versions} versions · {plan.readable} readable · "
            f"{len(plan.transitions)} in window · {len(plan.before_cutoff)} before the cutoff · "
            f"{len(plan.transitions) - len(remaining) - len(gave_up)} already done{found} · "
            f"{len(gave_up)} given up on"
        )
        for item in remaining:
            bridged = f" (bridging {', '.join(item.bridged)})" if item.bridged else ""
            typer.echo(f"  {item.key}  {item.label}{bridged}")
        for item in gave_up:
            typer.echo(
                f"  {item.key}  {item.label}  given up after {retry_limit} tries "
                f"(--retry-limit 0 keeps trying)"
            )
    kept = tuple(chosen) if limit is None else tuple(chosen[:limit])
    typer.echo(f"total: {len(kept)} selected across {len(plans)} acts")
    if len(kept) < len(chosen):
        typer.echo(
            f"--limit {limit}: {len(chosen) - len(kept)} more are outstanding; "
            f"re-run the same command for the next tranche."
        )
    return kept
