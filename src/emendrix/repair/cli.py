"""`emendrix repair`: correcting one part of entries that are already committed.

```bash
uv run emendrix repair corroboration --dry-run                       # what would move, and no more
uv run emendrix repair corroboration --output-repo ~/regulatory-changelog
uv run emendrix repair corroboration --act 32019R2088 --limit 5      # narrower
uv run emendrix repair explanations --dry-run                        # the selection and the price
uv run emendrix repair explanations --cassettes live --limit 20      # a tranche of the changes
```

This module is the EU composition root for the repair commands: it reads the clock once, here,
and passes the date down as a value, and it is the one module under `repair/` allowed to know
that a CELLAR client and a Formex package exist. Everything below it sees the committed document
and core types only, so the whole package would run over a corpus that is not law.

**A repair is explicitly invoked and is never reached from a resume.** `OutputRepo.holds_finished`
treats a settled change as settled on purpose, and a repair a backfill could trigger would
re-address the same entries on every run for ever.

**`--dry-run` is the same promise `backfill` makes and is kept literally.** It reads, it prints,
and it writes nothing at all: no commit, no file, no record.

**One commit per entry.** Batching would make a single revert impossible to scope and would hide
which act was corrected, and the subject says the entry was repaired rather than emitted.

`corroboration` recomputes the third signal, the parse of the amending act's own instructions,
against the entry's stored delta. That is a disk-cache read where the cache holds the package
and a fetch where it does not, and `--fixture-dir` pins it to a committed fixture set instead.
It calls no model, spends nothing, and carries every committed explanation over untouched.

`explanations` asks the model again for a change that shipped with no explanation because the
answer was unusable, rebuilding the prompt from the entry's own stored texts, so it fetches
nothing at all. This one spends money: `--limit` counts **changes** rather than entries, because
a change is what a call is paid for, and `--dry-run` names and prices them before anything is
sent.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.backfill.inputs import celex_of, delay_of, repository_at, watchlist_at
from emendrix.eu.http import POLITE_DELAY_ENV, POLITE_DELAY_S, today_utc
from emendrix.eu.identifiers import celex_of as celex_for
from emendrix.eu.signals import instruction_signal_for
from emendrix.explain import CassetteMode, ExplainSettings
from emendrix.graph.cli import SummaryFormat
from emendrix.output import GitError, OutputRepo, resolve_repo_path
from emendrix.output.json_out import ChangelogEntry, RepairRecord
from emendrix.repair import explanations as explain_repair
from emendrix.repair.corroborate import KIND, amending_act_of, needs, repair
from emendrix.repair.entry import RepairResult, with_record
from emendrix.repair.pricing import estimate_over, plan
from emendrix.repair.render import (
    report_estimate,
    report_results,
    report_selection,
    report_summary,
)
from emendrix.repair.select import for_act, read_targets
from emendrix.session import adapter_for, deps_for

__all__ = ["app", "corroboration", "explanations"]

app = typer.Typer(
    name="repair",
    help="Correct one part of entries already committed, without touching their siblings.",
    no_args_is_help=True,
)

_WATCHLIST = Path("watchlist.toml")

_LIST = typer.Option("--watchlist", help="Where the output repository is configured.")
_REPO = typer.Option("--output-repo", help="The repository to repair. Required.")
_DRY = typer.Option("--dry-run", help="Print what would move, write nothing at all.")
_ACT = typer.Option("--act", help="Restrict the pass to one CELEX.")
_LIMIT = typer.Option("--limit", min=1, help="Stop after this many entries that would change.")
_FIXTURE = typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network.")
_DELAY = typer.Option(
    "--polite-delay",
    min=0.0,
    help=f"Seconds between network calls. Defaults to {POLITE_DELAY_ENV} or {POLITE_DELAY_S}.",
)
_REPAIRED = typer.Option(
    "--repaired-on",
    formats=["%Y-%m-%d"],
    help="Date the repair record is stamped with. Defaults to today (UTC).",
)
_SUMMARY = typer.Option(
    "--summary", help="The stderr summary: `text` for a person, `json` for a log collector."
)
_CHANGES = typer.Option(
    "--limit", min=1, help="Stop after this many changes. Changes are what a call is paid for."
)
_CASSETTES = typer.Option("--cassettes", help="How the explain stage meets its cassette store.")

_NO_COORDINATES = (
    "no coordinate check ran: this repair holds neither provision tree, so the gate counted "
    "nothing rather than counting every coordinate a sentence names as unsupported."
)
"""Said on every pass and recorded on every entry, so an unrun check never reads as a passed one."""


@app.command("corroboration")
def corroboration(
    watchlist_path: Annotated[Path, _LIST] = _WATCHLIST,
    output_repo: Annotated[Path | None, _REPO] = None,
    dry_run: Annotated[bool, _DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, _LIMIT] = None,
    fixture_dir: Annotated[Path | None, _FIXTURE] = None,
    polite_delay_s: Annotated[float | None, _DELAY] = None,
    repaired_on: Annotated[datetime | None, _REPAIRED] = None,
    summary: Annotated[SummaryFormat, _SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Recompute the third signal on every committed entry that has one, and correct what moved.

    Start with `--dry-run`: it prints what would move, writes nothing and spends nothing. No
    model is called either way, and every committed explanation is carried over untouched.
    """
    watchlist = watchlist_at(watchlist_path)
    wanted = None if act is None else celex_of(act)
    stamp = repaired_on.date() if repaired_on is not None else today_utc()
    delay = delay_of(polite_delay_s)
    repository = _repository(resolve_repo_path(output_repo, watchlist.output.repo_path))
    targets = read_targets(repository.path)
    if wanted is not None:
        targets = for_act(targets, wanted)
    results: list[RepairResult] = []
    examined = 0
    with adapter_for(fixture_dir, stamp, polite_delay_s=delay) as adapter:
        for target in targets:
            # Counted before the candidate test, so `examined` says how many entries this pass
            # actually looked at rather than how many the repository holds: with `--limit` those
            # are different numbers and reporting the second would read as a whole-repository pass.
            examined += 1
            amender = amending_act_of(target.entry) if needs(target) else None
            if amender is None:
                continue
            found = repair(
                target, instruction_signal_for(adapter.client, celex_for(amender), target.entry.act)
            )
            results.append(found)
            if limit is not None and sum(1 for item in results if item.would_change) >= limit:
                break
    report_results(results)
    written = 0 if dry_run else _write_all(repository, results, KIND, stamp, _corroborated_subject)
    if dry_run:
        typer.echo("dry run: nothing written, nothing committed.")
    report_summary(summary, results, kind=KIND, examined=examined, written=written)


@app.command("explanations")
def explanations(
    watchlist_path: Annotated[Path, _LIST] = _WATCHLIST,
    output_repo: Annotated[Path | None, _REPO] = None,
    dry_run: Annotated[bool, _DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, _CHANGES] = None,
    cassettes: Annotated[CassetteMode | None, _CASSETTES] = None,
    repaired_on: Annotated[datetime | None, _REPAIRED] = None,
    summary: Annotated[SummaryFormat, _SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Ask the model again for every committed change that shipped with no explanation.

    Start with `--dry-run`: it names every change it would ask about, prices them, builds no
    engine and spends nothing. A real pass calls the model, so it needs `--cassettes live` and
    a key unless every prompt it rebuilds is already recorded. Nothing is fetched either way,
    and no sibling explanation is re-asked for.
    """
    watchlist = watchlist_at(watchlist_path)
    wanted = None if act is None else celex_of(act)
    stamp = repaired_on.date() if repaired_on is not None else today_utc()
    repository = _repository(resolve_repo_path(output_repo, watchlist.output.repo_path))
    targets = read_targets(repository.path)
    if wanted is not None:
        targets = for_act(targets, wanted)
    kind = explain_repair.KIND
    settings = ExplainSettings.from_env()
    if dry_run:
        # No engine at all, exactly as `backfill --dry-run` builds none: the mode's whole
        # promise is that it cannot spend, and a process holding no provider client cannot.
        selections, examined = plan(targets, settings, limit=limit)
        report_selection(selections)
        typer.echo(_NO_COORDINATES)
        typer.echo(f"examined {examined} entries · dry run: nothing written, nothing asked.")
        report_estimate(summary, estimate_over(selections, model_id=settings.model_id))
        return
    with adapter_for(None, stamp) as adapter:
        results, examined = asyncio.run(
            explain_repair.repair_all(
                targets,
                deps_for(adapter, stamp, cassettes).engine,
                render=adapter.render_citation,
                limit=limit,
            )
        )
    report_results(results)
    typer.echo(_NO_COORDINATES)
    written = _write_all(repository, results, kind, stamp, _explained_subject)
    report_summary(summary, results, kind=kind, examined=examined, written=written)


# ------------------------------------------------------------------ the pieces


def _repository(path: Path | None) -> OutputRepo:
    """The repository to repair, opened before anything is read, or a message and exit 2."""
    if path is None:
        typer.echo(
            "a repair addresses entries that are already committed: give --output-repo, set "
            "EMENDRIX_OUTPUT_REPO or [output] repo_path.",
            err=True,
        )
        raise typer.Exit(code=2)
    opened = repository_at(path)
    if opened is None:  # pragma: no cover - `repository_at` returns None only for None
        raise typer.Exit(code=2)
    return opened


Subject = Callable[[ChangelogEntry, RepairResult], str]
"""How one repair kind names its commit. The count phrase is the only part that differs."""


def _write_all(
    repository: OutputRepo,
    results: Sequence[RepairResult],
    kind: str,
    repaired_on: date,
    subject: Subject,
) -> int:
    """Commit each repaired entry on its own, with what the pass did recorded on it.

    A git failure ends the pass, because the next entry's commit would fail the same way.

    `coordinates_checked` is False for every repair this command carries, and it is passed
    rather than left to a default: neither repair holds the two provision trees the
    coordinate-support sets are computed from, so the check did not run and an unrun check may
    not read on a published entry as one that passed.
    """
    written = 0
    try:
        for result in results:
            rebuilt = result.entry
            if rebuilt is None:
                continue
            stamped = with_record(
                rebuilt,
                RepairRecord(
                    kind=kind,
                    repaired_on=repaired_on,
                    addressed=result.addressed,
                    repaired=result.repaired,
                    remaining=result.remaining,
                    usage=result.usage,
                    coordinates_checked=False,
                ),
            )
            outcome = repository.write(stamped, message=subject(stamped, result))
            if not outcome.unchanged:
                written += 1
                typer.echo(f"  {outcome.changelog}: committed {outcome.revision[:7]}")
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    return written


def _corroborated_subject(entry: ChangelogEntry, result: RepairResult) -> str:
    """`32019R2088: 02019R2088-20260702 corroboration repaired (2 changes)`."""
    return _message(entry, f"{KIND} repaired ({result.repaired} changes)")


def _explained_subject(entry: ChangelogEntry, result: RepairResult) -> str:
    """`32013R0575: 02013R0575-20140101 explanations repaired (3 of 4 changes)`.

    Both counts, because a change that failed again is part of what the pass did and a subject
    naming only the successes would read as though every gap had been closed.
    """
    phrase = f"{explain_repair.KIND} repaired ({result.repaired} of {result.addressed} changes)"
    return _message(entry, phrase)


def _message(entry: ChangelogEntry, phrase: str) -> str:
    """The subject and the one line saying what did not move.

    The subject says what was repaired rather than what was emitted, because a reader of
    `git log` would otherwise be told an amendment was detected on the day a correction ran.
    """
    return (
        f"{entry.act.key}: {entry.to_version} {phrase}\n"
        "\n"
        "The verbatim texts, the sibling explanations and the detection date did not move."
    )
