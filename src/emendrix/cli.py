"""`emendrix` on the command line: `diff`, `watch`, `explain`, `run`, `backfill`, `repair`,
`eval`, `site`.

This module is the composition root for `diff`, the one place allowed to know that the EU
adapter, the disk cache and the diff engine exist at the same time. It reads the observation
date once, at the boundary, and passes it down as a value; nothing below it ever asks what time
it is. `watch`, `run`, `explain`, `backfill`, `repair` and `eval` are each their own package's
root, mounted here.

`emendrix repair <kind>` is the one command that reaches into entries already committed. It is
always invoked explicitly, never reached from a resume, and it corrects one part of an entry
while every other entry in that act's changelog keeps its bytes. `--dry-run` prints what would
move and writes nothing. `corroboration` recomputes the third signal and spends nothing;
`explanations` asks the model again for a change that shipped without one, rebuilding the prompt
from the entry's own stored texts, and its `--dry-run` prices the work before any of it is sent.

`emendrix diff <act> <from> <to>` fetches two versions through the cache and prints the delta,
as a plain structural dump, as the serialised `core.Delta` (`--json`), or as the changelog
entry with no prose in it (`--markdown`). All three are byte-stable across runs, with no
timestamp, no set iteration order and no wall clock, because changelogs are diffed in git.

Versions are named the way the corpus names them: `32024R1689` is the act as published in the
Official Journal, `02024R1689-20260727` a consolidation. `--fixture-dir` points the fetch path
at a pinned fixture set instead of the disk cache, which is how the command runs with no
network at all.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix import DISCLAIMER
from emendrix.backfill.cli import backfill as backfill_command
from emendrix.core import ActId, Change, ChangeType, Delta, ProvisionTree, VersionId
from emendrix.diff import compute_delta
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureResponseCache, ResponseCache
from emendrix.eu.http import today_utc
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eval_.cli import app as eval_app
from emendrix.graph.cli import explain as explain_command
from emendrix.graph.cli import run as run_command
from emendrix.output import diff_only_entry, render_standalone
from emendrix.repair.cli import app as repair_app
from emendrix.site_.cli import app as site_app
from emendrix.watch.cli import watch

__all__ = ["DISCLAIMER", "app", "render_text"]

app = typer.Typer(
    name="emendrix",
    help="Watch EU legislation, diff it provision by provision, explain what changed.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(eval_app, name="eval")
app.add_typer(repair_app, name="repair")
app.add_typer(site_app, name="site")
app.command("watch")(watch)
app.command("run")(run_command)
app.command("explain")(explain_command)
app.command("backfill")(backfill_command)

_MARKERS = {
    ChangeType.INSERTED: "+",
    ChangeType.DELETED: "-",
    ChangeType.MODIFIED: "~",
    ChangeType.RENUMBERED: ">",
    ChangeType.DEFERRED: "@",
}


@app.callback()
def main() -> None:
    """Keep `emendrix` a multi-command app whatever it happens to hold today.

    `site` sits beside `diff`, `watch`, `eval`, `run`, `explain`, `backfill` and `repair`;
    without this callback Typer would collapse a single command into the root and every one of
    those would change the invocation of the others.
    """


@app.command()
def diff(
    act: Annotated[str, typer.Argument(help="CELEX of the act, e.g. 32024R1689.")],
    from_version: Annotated[str, typer.Argument(help="Version to compare from.")],
    to_version: Annotated[str, typer.Argument(help="Version to compare to.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit the delta as JSON.")] = False,
    as_markdown: Annotated[
        bool,
        typer.Option("--markdown", help="Render the changelog entry, without any explanations."),
    ] = False,
    fixture_dir: Annotated[
        Path | None,
        typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network."),
    ] = None,
    observed_on: Annotated[
        datetime | None,
        typer.Option(
            "--observed-on",
            formats=["%Y-%m-%d"],
            help="Date the first-class states are stamped with. Defaults to today (UTC).",
        ),
    ] = None,
) -> None:
    """Diff two versions of one act and print what changed.

    Three renderings of one answer: the plain structural dump, `--json` (the serialised
    `core.Delta`), and `--markdown` (the changelog entry with no prose in it). Diff-only is a
    first-class product mode, because the deterministic half of the loop is the half with
    measured numbers behind it, so `--markdown` calls no model and needs no API key.
    """
    if as_json and as_markdown:
        typer.echo("--json and --markdown are two renderings; pick one.", err=True)
        raise typer.Exit(code=2)
    cache: ResponseCache | None = None if fixture_dir is None else FixtureResponseCache(fixture_dir)
    stamp = observed_on.date() if observed_on is not None else today_utc()
    identity = act_id(Celex.parse(act))
    with EuCorpusAdapter.build(observed_on=stamp, cache=cache) as adapter:
        before = _tree(adapter, identity, VersionId(from_version))
        after = _tree(adapter, identity, VersionId(to_version))
    delta = compute_delta(before, after)
    if as_markdown:
        typer.echo(render_standalone(diff_only_entry(delta, detected_on=stamp)))
        return
    typer.echo(delta.model_dump_json(indent=2) if as_json else render_text(delta))


def _tree(adapter: EuCorpusAdapter, act: ActId, version: VersionId) -> ProvisionTree:
    """Fetch one version, or report the first-class state that says why there is none.

    An `Unavailable` is an answer rather than a crash, but there is nothing to diff against it,
    so the command states it and stops with a non-zero status.
    """
    fetched = adapter.fetch_version(act, version)
    if isinstance(fetched, ProvisionTree):
        return fetched
    typer.echo(f"{version}: {fetched.state} — {fetched.detail or 'no English structured text'}")
    raise typer.Exit(code=2)


def render_text(delta: Delta) -> str:
    """The plain structural dump: one line per change, then its detail. Byte-stable."""
    summary = delta.summary
    lines = [
        f"{delta.act} {delta.from_version} -> {delta.to_version}",
        f"{summary.inserted} inserted · {summary.modified} modified · {summary.deleted} deleted"
        f" · {summary.renumbered} renumbered · {summary.deferred} deferred",
        f"{summary.touched_units} touched units · {summary.unchanged_units} unchanged"
        f" · {summary.disputed} disputed",
        "",
    ]
    for change in delta.changes:
        lines.extend(_change_lines(change))
    lines.extend(("", DISCLAIMER))
    return "\n".join(lines)


def _change_lines(change: Change) -> list[str]:
    heading = f" — {change.heading}" if change.heading else ""
    lines = [
        f"{_MARKERS[change.change_type]} {change.change_type.value:<10} "
        f"{change.location.canonical}{heading}"
    ]
    if change.previous_location is not None:
        lines.append(f"    was: {change.previous_location.canonical}")
    if change.changed_within:
        inside = ", ".join(location.canonical for location in change.changed_within)
        lines.append(f"    within: {inside}")
    if change.dates_removed or change.dates_added:
        lines.append(f"    dates: -{_dates(change.dates_removed)} +{_dates(change.dates_added)}")
    lines.append(f"    applies from: {_applicability(change)}")
    return lines


def _dates(values: tuple[date, ...]) -> str:
    return "[" + ", ".join(value.isoformat() for value in values) + "]"


def _applicability(change: Change) -> str:
    applies = change.applies_from
    if isinstance(applies, date):
        return applies.isoformat()
    if applies.kind == "unchanged":
        return "unchanged"
    return f"unknown ({applies.reason})" if applies.reason else "unknown"
