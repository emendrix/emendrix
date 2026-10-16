"""`emendrix repair tables`: the keyed diff of table entries on every published change.

Kept apart from `cli.py`, which is the composition root and the one module under `repair/`
allowed to name the corpus or read the clock: this command takes its stamp (`stamp_of`) and the
profiled acts and units (`profiled_units`) from there, and its adapter from the session, and is
mounted on the same `app` by the import at the end of `cli.py`.

**Nothing is asked of any model, and every explanation is carried over.** The pass re-parses
both versions of each entry it addresses through the adapter's cache, one parse per version, and
sets `table_entries` on the changes to a profiled unit; every other field keeps its bytes but
the schema version, which becomes `1.3`, and the record of the repair, which is appended. One
commit per entry rewritten, then one per profiled act for its register, written from the act's
newest published version. `--dry-run` reads and prints, per act, what would move, and writes
nothing; `--fixture-dir` pins every read to a committed fixture set, never the network.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.backfill.inputs import delay_of
from emendrix.graph.cli import SummaryFormat
from emendrix.graph.report import RegisterSnapshot
from emendrix.output import OutputRepo, register_for
from emendrix.repair import options as opt
from emendrix.repair.cli import _ACT, _DELAY, _opened, app, profiled_units, stamp_of
from emendrix.repair.commit import finish
from emendrix.repair.entries import (
    KIND,
    by_act,
    needs,
    newest_targets,
    repair,
    snapshot_for,
    tabled_subject,
)
from emendrix.repair.entry import RepairResult, RepairTarget
from emendrix.repair.rederive import Trees
from emendrix.repair.select import walk
from emendrix.session import adapter_for

__all__ = ["report_tables", "tables"]


@app.command("tables")
def tables(
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
    """Set the keyed diff of table entries on every published change to a profiled table.

    Start with `--dry-run`: it prints, per act, the entries it would rewrite, the changes gaining
    table entries and what those entries did, and writes nothing. Nothing is asked of any model
    either way, and every explanation, sentence and signal is carried over untouched. After the
    entries, each profiled act's register is written from its newest published version.
    """
    started = time.monotonic()
    stamp = stamp_of(repaired_on)
    repo, targets = _opened(watchlist_path, output_repo, act)
    profiled = profiled_units()
    with adapter_for(fixture_dir, stamp, polite_delay_s=delay_of(polite_delay_s)) as adapter:
        trees = Trees(adapter)
        results, examined = walk(
            targets,
            lambda target: needs(target, profiled),
            lambda target: repair(target, trees, profiled),
            limit=limit,
        )
        snapshots = [
            (target, snapshot_for(target, trees)) for target in newest_targets(targets, profiled)
        ]
    counted = Counter(
        target.entry.act.key for target in targets[:examined] if target.entry.act.key in profiled
    )

    def tally(found: Sequence[RepairResult]) -> None:
        report_tables(found, counted, summary)

    finish(repo, results, examined, KIND, tabled_subject, stamp, dry_run, summary, tally)
    _registers(repo, snapshots, dry_run)
    typer.echo(f"elapsed {time.monotonic() - started:.1f} s")


def report_tables(
    results: Sequence[RepairResult], examined: Counter[str], summary: SummaryFormat
) -> None:
    """Per act and in total: entries, changes gaining table entries, and what the entries did.

    Typography-only amendments are printed apart from the others and whitespace-only pairs are
    printed as the non-changes they are. Every version that could not be re-derived is named.
    """
    acts, total = by_act(results, examined)
    for item in (*acts, total):
        typer.echo(
            f"{item.act}: {item.examined} entries examined · {item.rewritten} rewritten · "
            f"{item.gaining} changes gaining table entries ({item.empty} with no keyed entry "
            f"moved) · {item.unmatched} unmatched · {item.underivable} entries underivable · "
            f"entry changes {item.added} added, {item.removed} removed, "
            f"{item.amended - item.typography_only} amended, {item.typography_only} amended in "
            f"typography only · {item.whitespace_only} whitespace only · gaps "
            f"{item.unrecognised_tables} unrecognised tables, {item.unkeyed_rows} unkeyed rows, "
            f"{item.failed_check_digits} failed check digits, {item.unpaired} unpaired keys"
        )
    notes = [line for result in results for line in result.detail]
    if notes:
        typer.echo(f"{len(notes)} entries could not be re-derived today:")
        for note in notes:
            typer.echo(f"  {note}")
    if summary is SummaryFormat.JSON:
        typer.echo(total.model_dump_json(), err=True)


def _registers(
    repo: OutputRepo,
    snapshots: Sequence[tuple[RepairTarget, RegisterSnapshot | str]],
    dry_run: bool,
) -> None:
    """Each profiled act's register, from its newest published version, one commit per act."""
    for target, snapshot in snapshots:
        entry = target.entry
        if isinstance(snapshot, str):
            typer.echo(f"register {entry.act.key}: not written, {snapshot}")
            continue
        register = register_for(snapshot)
        count = f"{len(register.entries)} entries of {register.version}"
        if dry_run:
            typer.echo(f"register {entry.act.key}: {count} (dry run: not written)")
            continue
        written = repo.write_register(register)
        state = "unchanged" if not written.revision else f"committed {written.revision[:7]}"
        if not written.newest:
            state = "not the newest entry, left as it is"
        typer.echo(f"register {entry.act.key}: {count}, {state}")
