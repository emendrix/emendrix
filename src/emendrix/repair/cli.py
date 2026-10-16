"""`emendrix repair`: correcting one part of entries that are already committed.

```bash
uv run emendrix repair corroboration --dry-run                  # what would move, and no more
uv run emendrix repair explanations --cassettes live --limit 20 # a tranche of the changes
uv run emendrix repair unexplained --dry-run                    # notes quoting a library
uv run emendrix repair evidence --dry-run                       # stale evidence, and the price
uv run emendrix repair signals --dry-run                        # the signal rules, as counts
uv run emendrix repair tables --dry-run                         # table entries, per act
```

This module is the EU composition root for the repair commands: it reads the clock once, here,
and passes the date down as a value, and it is the one module under `repair/` allowed to know
that a CELLAR client and a Formex package exist. Everything below it sees the committed document
and core types only, so the whole package would run over a corpus that is not law.

**A repair is explicitly invoked and is never reached from a resume**, because
`OutputRepo.holds_finished` treats a settled change as settled on purpose. **`--dry-run` reads,
prints, and writes nothing at all.**

`corroboration` recomputes the third signal, the parse of the amending act's own instructions,
against the entry's stored delta: a cache read, or a fetch where the cache lacks the package, and
`--fixture-dir` pins it to a committed fixture set. Its window is read off the entry's own
version pair (`window_of`). It calls no model and carries every explanation over untouched.

`explanations` asks the model again for a change that shipped with no explanation because the
answer was unusable, rebuilding the prompt from the entry's own stored texts, so it fetches
nothing. It spends money: `--limit` counts **changes**, and `--dry-run` prices them first.

`unexplained` restates a note that quoted the provider library's own error text and stamps the
counted kind beside it; `signals` rebuilds both second opinions from the claims an entry already
carries, under today's rules. Both read the committed document alone: no network, no model.

`evidence` re-parses both versions and re-derives the delta, because its defect is in the stored
text itself; it asks again only where evidence moved, so `--limit` counts changes. `tables`
(`cli_entries.py`) re-parses both to set the keyed diff of table entries on published changes,
and takes its stamp (`stamp_of`) and profiled units (`profiled_units`) from here.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import Annotated

import typer

from emendrix.backfill.inputs import celex_of, delay_of, watchlist_at
from emendrix.eu.http import POLITE_DELAY_ENV, POLITE_DELAY_S, today_utc
from emendrix.eu.identifiers import ConsolidatedId, parse_identifier
from emendrix.eu.identifiers import celex_of as celex_for
from emendrix.eu.instructions import Window
from emendrix.eu.signals import committed_metadata, instruction_signal_for
from emendrix.eu.substances.profiles import PROFILES
from emendrix.explain import CassetteMode, ExplainSettings
from emendrix.graph.cli import SummaryFormat
from emendrix.output import ChangelogEntry, OutputRepo, resolve_repo_path
from emendrix.repair import evidence as evidence_repair
from emendrix.repair import explanations as explain_repair
from emendrix.repair import options as opt
from emendrix.repair import signals as signals_repair
from emendrix.repair import unexplained as unexplained_repair
from emendrix.repair.commit import (
    NO_COORDINATES,
    corroborated_subject,
    explained_subject,
    finish,
    rederived_subject,
    repository,
    restated_subject,
    signalled_subject,
    write_all,
)
from emendrix.repair.corroborate import KIND, amending_act_of, needs, repair
from emendrix.repair.entry import RepairResult, RepairTarget
from emendrix.repair.pricing import estimate_over, plan
from emendrix.repair.render import (
    report_estimate,
    report_pass,
    report_plan,
    report_results,
    report_selection,
    report_summary,
    report_tallies,
    report_withheld,
)
from emendrix.repair.select import for_act, read_targets, walk
from emendrix.session import adapter_for, deps_for

__all__ = [
    "app",
    "corroboration",
    "evidence",
    "explanations",
    "signals",
    "unexplained",
    "window_of",
]

app = typer.Typer(
    name="repair",
    help="Correct one part of entries already committed, without touching their siblings.",
    no_args_is_help=True,
)

_ACT = typer.Option("--act", help="Restrict the pass to one CELEX.")
_DELAY = typer.Option(
    "--polite-delay",
    min=0.0,
    help=f"Seconds between network calls. Defaults to {POLITE_DELAY_ENV} or {POLITE_DELAY_S}.",
)


def stamp_of(repaired_on: datetime | None) -> date:
    """The date a pass stamps on what it repaired: the operator's, else today's (UTC)."""
    return repaired_on.date() if repaired_on is not None else today_utc()


def profiled_units() -> dict[str, frozenset[str]]:
    """Each act whose tables are read as entries, and the units those tables sit in."""
    return {act: frozenset(p.unit for p in profiles) for act, profiles in PROFILES.items()}


def window_of(entry: ChangelogEntry) -> Window | None:
    """The consolidation window `(after, until]` an entry was published for, read off the entry.

    A consolidated identifier is `<celex>-<YYYYMMDD>`, so the published pair carries both dates,
    with no fetch, no clock and no inventory that may have moved since. A `from_version` that is
    not a consolidation has no lower bound; `None` where `to_version` is not one either.
    """
    until = parse_identifier(str(entry.to_version))
    if not isinstance(until, ConsolidatedId):
        return None
    after = parse_identifier(str(entry.from_version))
    start = after.version_date if isinstance(after, ConsolidatedId) else None
    return start, until.version_date


def _opened(
    watchlist_path: Path, output_repo: Path | None, act: str | None
) -> tuple[OutputRepo, tuple[RepairTarget, ...]]:
    """The repository a pass writes into and the entries it walks, opened before it reads one."""
    repo = repository(resolve_repo_path(output_repo, watchlist_at(watchlist_path).output.repo_path))
    targets = read_targets(repo.path)
    return repo, targets if act is None else for_act(targets, celex_of(act))


@app.command("corroboration")
def corroboration(
    watchlist_path: Annotated[Path, opt.LIST] = opt.WATCHLIST,
    output_repo: Annotated[Path | None, opt.REPO] = None,
    dry_run: Annotated[bool, opt.DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, opt.LIMIT] = None,
    fixture_dir: Annotated[Path | None, opt.FIXTURE] = None,
    polite_delay_s: Annotated[float | None, _DELAY] = None,
    repaired_on: Annotated[datetime | None, opt.REPAIRED] = None,
    summary: Annotated[SummaryFormat, opt.SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Recompute the third signal on every committed entry that has one, and correct what moved.

    Start with `--dry-run`: it prints what would move, writes nothing and spends nothing. No
    model is called either way, and every committed explanation is carried over untouched.
    """
    stamp = stamp_of(repaired_on)
    repo, targets = _opened(watchlist_path, output_repo, act)
    with adapter_for(fixture_dir, stamp, polite_delay_s=delay_of(polite_delay_s)) as adapter:

        def corrected(target: RepairTarget) -> RepairResult:
            amender = amending_act_of(target.entry)
            assert amender is not None, "`needs` admits only an entry naming one amending act"
            signal = instruction_signal_for(
                adapter.client, celex_for(amender), target.entry.act, window=window_of(target.entry)
            )
            return repair(target, signal)

        results, examined = walk(targets, needs, corrected, limit=limit)
    finish(repo, results, examined, KIND, corroborated_subject, stamp, dry_run, summary)


@app.command("explanations")
def explanations(
    watchlist_path: Annotated[Path, opt.LIST] = opt.WATCHLIST,
    output_repo: Annotated[Path | None, opt.REPO] = None,
    dry_run: Annotated[bool, opt.DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, opt.CHANGES] = None,
    cassettes: Annotated[CassetteMode | None, opt.CASSETTES] = None,
    repaired_on: Annotated[datetime | None, opt.REPAIRED] = None,
    summary: Annotated[SummaryFormat, opt.SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Ask the model again for every committed change that shipped with no explanation.

    Start with `--dry-run`: it names every change it would ask about, prices them, builds no
    engine and spends nothing. A real pass calls the model, so it needs `--cassettes live` and
    a key unless every prompt it rebuilds is already recorded. Nothing is fetched either way,
    and no sibling explanation is re-asked for.
    """
    stamp = stamp_of(repaired_on)
    repo, targets = _opened(watchlist_path, output_repo, act)
    kind = explain_repair.KIND
    settings = ExplainSettings.from_env()
    if dry_run:
        # No engine at all: a process holding no provider client cannot spend.
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
    watchlist_path: Annotated[Path, opt.LIST] = opt.WATCHLIST,
    output_repo: Annotated[Path | None, opt.REPO] = None,
    dry_run: Annotated[bool, opt.DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, opt.LIMIT] = None,
    repaired_on: Annotated[datetime | None, opt.REPAIRED] = None,
    summary: Annotated[SummaryFormat, opt.SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Restate every committed note that quoted the provider library instead of the reader.

    Start with `--dry-run`: it prints the notes it would restate and the ones it would count
    and leave. No model is called either way, nothing is fetched, and every explanation, every
    verbatim text and every note this project curated is carried over untouched.
    """
    stamp = stamp_of(repaired_on)
    repo, targets = _opened(watchlist_path, output_repo, act)
    results, examined = walk(
        targets, unexplained_repair.needs, unexplained_repair.repair, limit=limit
    )
    kind = unexplained_repair.KIND
    finish(
        repo, results, examined, kind, restated_subject, stamp, dry_run, summary, report_withheld
    )


@app.command("signals")
def signals(
    watchlist_path: Annotated[Path, opt.LIST] = opt.WATCHLIST,
    output_repo: Annotated[Path | None, opt.REPO] = None,
    dry_run: Annotated[bool, opt.DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, opt.LIMIT] = None,
    repaired_on: Annotated[datetime | None, opt.REPAIRED] = None,
    summary: Annotated[SummaryFormat, opt.SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Bring every committed entry with a corroboration block under today's signal rules.

    Start with `--dry-run`: it prints, per act and in total, the rows and the disputes before
    and after. Nothing is fetched and no model is called either way, and every committed
    explanation is carried over untouched.
    """
    stamp = stamp_of(repaired_on)
    repo, targets = _opened(watchlist_path, output_repo, act)

    corrected = partial(signals_repair.repair, normalise_metadata=committed_metadata)
    results, examined = walk(targets, signals_repair.needs, corrected, limit=limit)
    kind = signals_repair.KIND
    finish(
        repo, results, examined, kind, signalled_subject, stamp, dry_run, summary, report_tallies
    )


@app.command("evidence")
def evidence(
    watchlist_path: Annotated[Path, opt.LIST] = opt.WATCHLIST,
    output_repo: Annotated[Path | None, opt.REPO] = None,
    dry_run: Annotated[bool, opt.DRY] = False,
    act: Annotated[str | None, _ACT] = None,
    limit: Annotated[int | None, opt.CHANGES] = None,
    cassettes: Annotated[CassetteMode | None, opt.CASSETTES] = None,
    fixture_dir: Annotated[Path | None, opt.FIXTURE] = None,
    polite_delay_s: Annotated[float | None, _DELAY] = None,
    repaired_on: Annotated[datetime | None, opt.REPAIRED] = None,
    summary: Annotated[SummaryFormat, opt.SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Rebuild every entry whose stored evidence a later parser fix has corrected.

    Start with `--dry-run`: it re-parses both versions of every entry, names and prices the
    changes whose evidence moved, builds no engine and spends nothing. A real pass asks about
    those changes and only those, so it needs `--cassettes live` and a key.
    """
    stamp = stamp_of(repaired_on)
    repo, targets = _opened(watchlist_path, output_repo, act)
    settings = ExplainSettings.from_env()
    with adapter_for(fixture_dir, stamp, polite_delay_s=delay_of(polite_delay_s)) as adapter:
        if dry_run:
            # No engine at all: a process holding no provider client cannot spend, however
            # much it goes on to read.
            plans, counts = evidence_repair.plan_over(targets, adapter, settings, limit=limit)
            report_plan(summary, plans, counts, model_id=settings.model_id)
            return
        results, counts = asyncio.run(
            evidence_repair.repair_all(
                targets,
                adapter,
                deps_for(adapter, stamp, cassettes).engine,
                render=adapter.render_citation,
                limit=limit,
            )
        )
    report_results(results)
    report_pass(counts)
    kind = evidence_repair.KIND
    written = write_all(repo, results, kind, stamp, rederived_subject, coordinates_checked=True)
    report_summary(summary, results, kind=kind, examined=counts.examined, written=written)


from emendrix.repair import cli_entries  # noqa: E402, F401  (mounts `tables` on `app`)
