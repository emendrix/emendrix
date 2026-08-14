"""`emendrix backfill`: the loop over an act's history rather than over a poll window.

```bash
uv run emendrix backfill --dry-run                              # what it would run, and no more
uv run emendrix backfill --output-repo ~/regulatory-changelog   # then this
uv run emendrix backfill --since 2023-01-01 --act 32017R0745    # narrower, and cheaper
```

The watcher answers "what changed since the last time I looked?", the right question every day
after the first and the wrong one on the first. Backfill asks the other one: every consecutive
pair of readable versions each watched act has published, run through the same graph
`emendrix explain` uses and committed into the same output repository. This module is the EU
composition root for that; everything under it is generic over any corpus.

**`--dry-run` stops at the tree notices.** It reads which versions exist, prints what it would
run, and builds no explain engine, so it needs no API key and spends nothing. The count it prints
is the number of model-explained deltas an operator is agreeing to pay for, and seeing that count
before paying for it is the whole point of the mode. A dry run also takes no lock and writes
nothing at all, the ledger included, so it is the thing to run while a real backfill is going.

**An output repository is required unless this is a dry run.** `emendrix run` may print its
report and write nothing, which is reasonable for one poll; three hundred reports on a terminal
are not an artifact anybody wants, so the absence is refused before the first fetch. It is opened
once for the whole run: per invocation is right for a poll and wrong for three hundred
transitions.

**A real run holds `<ledger>.lock` for its whole length, and the resume unit is one whole
transition.** `backfill/ledger.py` states both rules and what each of them costs.

**Ctrl-C prints the totals and exits 130.** An interruption is an instruction rather than a
fault, so the run reports what it earned instead of unwinding through a traceback, and the
transition in flight stays out of the ledger and runs again next time.

**`--summary json` is the tranche's own account of what it spent.** One line on stderr, bounded
by the transitions selected and never by the changes inside them, which is the property that
lets it survive a log collector's line cap; the token counts ride on it because a run whose
cost can only be guessed at is not one an operator can size the next tranche from.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.backfill.emitted import emitted_keys
from emendrix.backfill.inputs import (
    celex_of,
    delay_of,
    ledger_read_only,
    reported,
    repository_at,
    watchlist_at,
)
from emendrix.backfill.ledger import (
    DEFAULT_LEDGER,
    DEFAULT_RETRY_LIMIT,
    LedgerBusy,
    ledger_lock,
    load_ledger,
    save_ledger,
)
from emendrix.backfill.plan import Transition, TransitionPlan, plan_transitions
from emendrix.backfill.render import already_emitted, report_plans, report_summary, usage_of
from emendrix.backfill.runner import run_transitions
from emendrix.core import ActId
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.http import POLITE_DELAY_ENV, POLITE_DELAY_S, today_utc
from emendrix.explain import CallUsage, CassetteMode
from emendrix.graph import RunReport
from emendrix.graph.cli import SummaryFormat
from emendrix.output import GitError, OutputRepo, entries_for, resolve_repo_path
from emendrix.session import adapter_for, deps_for
from emendrix.watch.config import Watchlist

__all__ = ["backfill"]

_WATCHLIST = Path("watchlist.toml")

_LIST = typer.Option("--watchlist", help="The acts to back-fill.")
_REPO = typer.Option("--output-repo", help="Commit into this repository; required unless dry.")
_DRY = typer.Option("--dry-run", help="List what would run, spend nothing, write nothing.")
_ACT = typer.Option("--act", help="Restrict the run to one CELEX already on the watchlist.")
_LEDGER = typer.Option("--ledger", help="The resume record.")
_LIMIT = typer.Option("--limit", min=1, help="Stop after this many transitions. Run in tranches.")
_DELAY = typer.Option(
    "--polite-delay",
    min=0.0,
    help=f"Seconds between network calls. Defaults to {POLITE_DELAY_ENV} or {POLITE_DELAY_S}.",
)
_FIXTURE = typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network.")
_CASSETTES = typer.Option("--cassettes", help="How the explain stage meets its cassette store.")
_SINCE = typer.Option(
    "--since",
    formats=["%Y-%m-%d"],
    help="Skip transitions whose later version predates this date.",
)
_RETRIES = typer.Option(
    "--retry-limit",
    help="Give up on a transition after this many failed tries. 0 never gives up.",
)
_OBSERVED = typer.Option(
    "--observed-on",
    formats=["%Y-%m-%d"],
    help="Date the first-class states are stamped with. Defaults to today (UTC).",
)
_SUMMARY = typer.Option(
    "--summary", help="The stderr summary: `text` for a person, `json` for a log collector."
)


def backfill(
    watchlist_path: Annotated[Path, _LIST] = _WATCHLIST,
    output_repo: Annotated[Path | None, _REPO] = None,
    dry_run: Annotated[bool, _DRY] = False,
    since: Annotated[datetime | None, _SINCE] = None,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, _LIMIT] = None,
    polite_delay_s: Annotated[float | None, _DELAY] = None,
    ledger_path: Annotated[Path, _LEDGER] = DEFAULT_LEDGER,
    retry_limit: Annotated[int, _RETRIES] = DEFAULT_RETRY_LIMIT,
    fixture_dir: Annotated[Path | None, _FIXTURE] = None,
    cassettes: Annotated[CassetteMode | None, _CASSETTES] = None,
    observed_on: Annotated[datetime | None, _OBSERVED] = None,
    summary: Annotated[SummaryFormat, _SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Run the loop over every historical transition of every watched act.

    Start with `--dry-run`: it prints what would run, writes nothing and costs nothing.
    """
    watchlist = watchlist_at(watchlist_path)
    stamp = observed_on.date() if observed_on is not None else today_utc()
    cutoff = since.date() if since is not None else None
    delay = delay_of(polite_delay_s)
    repo_path = resolve_repo_path(output_repo, watchlist.output.repo_path)
    if repo_path is None and not dry_run:
        typer.echo(
            "a backfill's product is a committed changelog: give --output-repo, set "
            "EMENDRIX_OUTPUT_REPO or [output] repo_path, or pass --dry-run.",
            err=True,
        )
        raise typer.Exit(code=2)

    repository = repository_at(repo_path)
    if dry_run:
        with adapter_for(fixture_dir, stamp, polite_delay_s=delay) as adapter:
            plans = _plans(adapter, watchlist, act=act, cutoff=cutoff)
        present = emitted_keys(repository, plans)
        chosen = report_plans(
            plans,
            ledger_read_only(ledger_path),
            retry_limit,
            emitted=present,
            limit=limit,
        )
        typer.echo("dry run: nothing fetched beyond the version lists, nothing written.")
        # An operator reads this summary before paying, so it carries the selection and an
        # explicit `emitted: 0` rather than being skipped as if nothing happened.
        report_summary(summary, selected=len(chosen), already=already_emitted(plans, present))
        return

    # The lock is taken before the first fetch and released however the run ends, so a refusal
    # costs nothing and an interruption leaves nothing behind to clear.
    try:
        with (
            ledger_lock(ledger_path),
            adapter_for(fixture_dir, stamp, polite_delay_s=delay) as adapter,
        ):
            plans = _plans(adapter, watchlist, act=act, cutoff=cutoff)
            present = emitted_keys(repository, plans)
            chosen = report_plans(
                plans,
                reported(load_ledger(ledger_path)),
                retry_limit,
                emitted=present,
                limit=limit,
            )
            done_before = already_emitted(plans, present)
            if not chosen:
                typer.echo("nothing to do: every selected transition is settled or given up on.")
                report_summary(summary, selected=0, already=done_before)
                return
            _execute_all(
                adapter, chosen, stamp, cassettes, ledger_path, repository, summary, done_before
            )
    except LedgerBusy as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


# ------------------------------------------------------------------ the pieces


def _plans(
    adapter: EuCorpusAdapter, watchlist: Watchlist, *, act: str | None, cutoff: date | None
) -> tuple[TransitionPlan, ...]:
    """One plan per watched act, in the order the file lists them.

    `--act` filters the watchlist and never extends it, so a CELEX that parses but is not
    watched selects nothing and the total reads zero. The watchlist stays the single answer to
    which acts this installation cares about.
    """
    wanted = None if act is None else celex_of(act)
    plans: list[TransitionPlan] = []
    for entry in watchlist.acts:
        if wanted is not None and entry.celex != wanted:
            continue
        identity: ActId = entry.act
        plans.append(
            plan_transitions(identity, adapter.discover_versions(identity), not_before=cutoff)
        )
    return tuple(plans)


def _execute_all(
    adapter: EuCorpusAdapter,
    transitions: tuple[Transition, ...],
    observed_on: date,
    cassettes: CassetteMode | None,
    ledger_path: Path,
    repository: OutputRepo | None,
    summary: SummaryFormat,
    done_before: int,
) -> None:
    """Run every transition, committing and recording after each one.

    The commit happens before the ledger row, so a run that dies between them redoes the
    transition next time and rewrites bytes that have not changed, which the output repository
    treats as a no-op. The other order would mark a transition done that never reached the
    changelog, and the whole point of the record is that it never claims more than it did.

    The ledger is re-read here rather than reusing anything read before the lock was taken:
    between the two, another run may have finished. It is one small file, and under the lock the
    read is race-free.

    `KeyboardInterrupt` is caught here and nowhere below: the loop lets it through so that one
    keypress does not become three hundred recorded failures, and this is where the run says what
    it earned before exiting 130. The transition in flight is deliberately not recorded, and runs
    again from its first fetch next time.
    """
    ledger = reported(load_ledger(ledger_path))
    deps = deps_for(adapter, observed_on, cassettes)
    counts: dict[str, int] = {"emitted": 0, "skipped": 0, "failed": 0}
    usage = CallUsage()
    finished = 0
    interrupted = False
    try:
        for outcome in run_transitions(deps, transitions, observed_on=observed_on):
            counts[outcome.status] += 1
            if outcome.report is not None:
                usage = usage.plus(usage_of(outcome.report))
            if repository is not None and outcome.report is not None:
                _write(repository, outcome.report)
            ledger = ledger.record(outcome.attempt)
            save_ledger(ledger_path, ledger)
            finished += 1
            pct = finished * 100 // len(transitions)
            detail = f": {outcome.detail}" if outcome.detail else ""
            typer.echo(
                f"[{finished}/{len(transitions)} {pct}%] {outcome.transition.label} "
                f"{outcome.status}{detail}"
            )
    except KeyboardInterrupt:
        interrupted = True
    typer.echo(
        f"done: {counts['emitted']} emitted · {counts['skipped']} skipped · "
        f"{counts['failed']} failed · ledger at {ledger_path}"
    )
    # Emitted on interruption too: what a truncated tranche spent is exactly what its
    # operator decides the next tranche with.
    report_summary(
        summary,
        selected=len(transitions),
        already=done_before,
        emitted=counts["emitted"],
        skipped=counts["skipped"],
        failed=counts["failed"],
        usage=usage,
    )
    if counts["failed"]:
        typer.echo("re-run the same command to retry the failures.", err=True)
    if interrupted:
        pending = transitions[finished].label if finished < len(transitions) else "nothing"
        typer.echo(
            f"interrupted during {pending}; it was not recorded and runs again from the start "
            f"next time. Re-run the same command to carry on.",
            err=True,
        )
        raise typer.Exit(code=130)


def _write(repository: OutputRepo, report: RunReport) -> None:
    """Commit one transition's entries. A git failure ends the run: the next one would too."""
    try:
        for entry in entries_for(report):
            written = repository.write(entry)
            if not written.unchanged:
                typer.echo(f"  {written.changelog}: committed {written.revision[:7]}")
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
