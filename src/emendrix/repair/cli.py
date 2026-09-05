"""`emendrix repair`: correcting one part of entries that are already committed.

```bash
uv run emendrix repair corroboration --dry-run                       # what would move, and no more
uv run emendrix repair corroboration --output-repo ~/regulatory-changelog
uv run emendrix repair corroboration --act 32019R2088 --limit 5      # narrower
uv run emendrix repair explanations --dry-run                        # the selection and the price
uv run emendrix repair explanations --cassettes live --limit 20      # a tranche of the changes
uv run emendrix repair unexplained --dry-run                         # notes quoting a library
```

This module is the EU composition root for the repair commands: it reads the clock once, here,
and passes the date down as a value, and it is the one module under `repair/` allowed to know
that a CELLAR client and a Formex package exist. Everything below it sees the committed document
and core types only, so the whole package would run over a corpus that is not law. What each
verb does with a result once it has one is `commit.py`, which is the same in every case.

**A repair is explicitly invoked and is never reached from a resume.** `OutputRepo.holds_finished`
treats a settled change as settled on purpose, and a repair a backfill could trigger would
re-address the same entries on every run for ever.

**`--dry-run` is the same promise `backfill` makes and is kept literally.** It reads, it prints,
and it writes nothing at all: no commit, no file, no record.

`corroboration` recomputes the third signal, the parse of the amending act's own instructions,
against the entry's stored delta. That is a disk-cache read where the cache holds the package
and a fetch where it does not, and `--fixture-dir` pins it to a committed fixture set instead.
It calls no model, spends nothing, and carries every committed explanation over untouched. The
consolidation window the signal is scoped to is read off the entry's own version pair
(`window_of`), so a repair scopes exactly the window that was published and needs neither a
fetch nor a clock to know which one that is.

`explanations` asks the model again for a change that shipped with no explanation because the
answer was unusable, rebuilding the prompt from the entry's own stored texts, so it fetches
nothing at all. This one spends money: `--limit` counts **changes** rather than entries, because
a change is what a call is paid for, and `--dry-run` names and prices them before anything is
sent.

`unexplained` restates a note that quoted the provider library's own error text, which entries
written before the curated reasons existed carry, and stamps the counted kind that goes with it.
It reads the committed document and nothing else: no model, no network, no key.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.backfill.inputs import celex_of, delay_of, watchlist_at
from emendrix.eu.http import POLITE_DELAY_ENV, POLITE_DELAY_S, today_utc
from emendrix.eu.identifiers import ConsolidatedId, parse_identifier
from emendrix.eu.identifiers import celex_of as celex_for
from emendrix.eu.instructions import Window
from emendrix.eu.signals import instruction_signal_for
from emendrix.explain import CassetteMode, ExplainSettings
from emendrix.graph.cli import SummaryFormat
from emendrix.output import ChangelogEntry, resolve_repo_path
from emendrix.repair import explanations as explain_repair
from emendrix.repair import unexplained as unexplained_repair
from emendrix.repair.commit import (
    NO_COORDINATES,
    corroborated_subject,
    explained_subject,
    repository,
    restated_subject,
    write_all,
)
from emendrix.repair.corroborate import KIND, amending_act_of, needs, repair
from emendrix.repair.entry import RepairResult
from emendrix.repair.pricing import estimate_over, plan
from emendrix.repair.render import (
    report_estimate,
    report_results,
    report_selection,
    report_summary,
)
from emendrix.repair.select import for_act, read_targets
from emendrix.session import adapter_for, deps_for

__all__ = ["app", "corroboration", "explanations", "unexplained", "window_of"]

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


def window_of(entry: ChangelogEntry) -> Window | None:
    """The consolidation window `(after, until]` an entry was published for, read off the entry.

    A consolidated version identifier is `<celex>-<YYYYMMDD>`, so the pair of versions the
    document already names carries the two dates, and a repair needs no fetch and no clock to
    know which window it is scoping the third signal to. That is the right source here: it
    scopes exactly the window that was published, rather than a window recomputed from a
    version inventory that may have moved since.

    A `from_version` that is not a consolidation has no lower bound, because it is the act as
    published in the Official Journal and everything annotated up to the later version belongs
    to the pair. `None` only where `to_version` is not a consolidation either, which is a caller
    holding no dates at all: the whole act is claimed, and the signal's note counts the nothing
    the unbounded window excluded.
    """
    until = parse_identifier(str(entry.to_version))
    if not isinstance(until, ConsolidatedId):
        return None
    after = parse_identifier(str(entry.from_version))
    start = after.version_date if isinstance(after, ConsolidatedId) else None
    return start, until.version_date


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
    repo = repository(resolve_repo_path(output_repo, watchlist.output.repo_path))
    targets = read_targets(repo.path)
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
                target,
                instruction_signal_for(
                    adapter.client,
                    celex_for(amender),
                    target.entry.act,
                    window=window_of(target.entry),
                ),
            )
            results.append(found)
            if limit is not None and sum(1 for item in results if item.would_change) >= limit:
                break
    report_results(results)
    written = 0 if dry_run else write_all(repo, results, KIND, stamp, corroborated_subject)
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
    repo = repository(resolve_repo_path(output_repo, watchlist.output.repo_path))
    targets = read_targets(repo.path)
    if wanted is not None:
        targets = for_act(targets, wanted)
    kind = explain_repair.KIND
    settings = ExplainSettings.from_env()
    if dry_run:
        # No engine at all, exactly as `backfill --dry-run` builds none: the mode's whole
        # promise is that it cannot spend, and a process holding no provider client cannot.
        selections, examined = plan(targets, settings, limit=limit)
        report_selection(selections)
        typer.echo(NO_COORDINATES)
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
    typer.echo(NO_COORDINATES)
    written = write_all(repo, results, kind, stamp, explained_subject)
    report_summary(summary, results, kind=kind, examined=examined, written=written)


@app.command("unexplained")
def unexplained(
    watchlist_path: Annotated[Path, _LIST] = _WATCHLIST,
    output_repo: Annotated[Path | None, _REPO] = None,
    dry_run: Annotated[bool, _DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, _LIMIT] = None,
    repaired_on: Annotated[datetime | None, _REPAIRED] = None,
    summary: Annotated[SummaryFormat, _SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Restate every committed note that quoted the provider library instead of the reader.

    Start with `--dry-run`: it prints the notes it would restate and the ones it would count
    and leave. No model is called either way, nothing is fetched, and every explanation, every
    verbatim text and every note this project curated is carried over untouched.
    """
    watchlist = watchlist_at(watchlist_path)
    wanted = None if act is None else celex_of(act)
    stamp = repaired_on.date() if repaired_on is not None else today_utc()
    kind = unexplained_repair.KIND
    repo = repository(resolve_repo_path(output_repo, watchlist.output.repo_path))
    targets = read_targets(repo.path)
    if wanted is not None:
        targets = for_act(targets, wanted)
    results: list[RepairResult] = []
    examined = 0
    for target in targets:
        examined += 1
        if not unexplained_repair.needs(target):
            continue
        results.append(unexplained_repair.repair(target))
        if limit is not None and sum(1 for item in results if item.would_change) >= limit:
            break
    report_results(results)
    left = sum(result.remaining for result in results)
    if left:
        noun = "note" if left == 1 else "notes"
        typer.echo(f"{left} {noun} {unexplained_repair.WITHHELD_NOTE}")
    written = 0 if dry_run else write_all(repo, results, kind, stamp, restated_subject)
    if dry_run:
        typer.echo("dry run: nothing written, nothing committed.")
    report_summary(summary, results, kind=kind, examined=examined, written=written)
