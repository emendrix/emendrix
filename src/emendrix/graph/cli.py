"""`emendrix run` and `emendrix explain`, the two commands that drive the whole loop.

The wiring they share lives in `emendrix.session`. Two ways into one graph, which is the point
of the arrangement:

```bash
uv run emendrix run --once                              # poll the watchlist, then diff what came
uv run emendrix explain 32024R1689 02024R1689-20240712 02024R1689-20260727
uv run emendrix run --once --fixture-dir tests/fixtures/eu --state-file /tmp/s.json \\
    --since 2026-08-05T10:00:00 --until 2026-08-05T10:05:00     # offline, end to end
```

`run` enters at WATCH; `explain` skips it and supplies the event itself
(`build_pipeline(watch=False)`). Everything after that node is identical, so the manual path
cannot drift from the scheduled one — the failure mode where a tool's demo works and its cron
job does not.

This module is the only one in `graph/` that knows the corpus is the EU: it names the shared
composition root that constructs the adapter, the signal source and the explain engine. It is
also the only one in `graph/` that reads a clock. Both facts are the same fact: a command
boundary is where the impure things are allowed to be named, so that nothing below it has to
be.

Output is the typed `RunReport` as JSON, on stdout or to `--json-out`, with a one-line summary
of both stages' counts on stderr, deliberately the whole answer rather than a rendering of it.

That summary has two readers and `--summary` picks which. `text` is the default and is for a
person. `json` is for a log collector, and exists because the report itself cannot be logged:
one real transition of nine changes is roughly 200 kB, which a collector either splits into
dozens of unparseable fragments or, compacted, drops whole for exceeding its line cap. The
summary is bounded by acts rather than by changes, so it survives the trip either way.
With an output repository configured (`--output-repo`, `EMENDRIX_OUTPUT_REPO`, or `[output]
repo_path` in `watchlist.toml` — that precedence, stated in `output/config.py`) each act's
transition is *also* written into that repository as `CHANGELOG.md` + `changes/*.json` and
committed. Nothing is ever pushed: the repository is the user's.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from emendrix.eu.feed import DEFAULT_CHANNEL
from emendrix.eu.http import today_utc
from emendrix.eu.identifiers import Celex, act_id
from emendrix.explain import CassetteMode
from emendrix.graph.report import RunReport, summarise_run
from emendrix.graph.state import PipelineState
from emendrix.output import GitError, OutputRepo, entries_for, resolve_repo_path
from emendrix.session import adapter_for, deps_for, execute, manual_event
from emendrix.watch.cli import DATE_FORMATS
from emendrix.watch.config import load_watchlist
from emendrix.watch.source import FeedWatchSource
from emendrix.watch.state import default_state_path

__all__ = ["SummaryFormat", "explain", "run", "summarise"]


class SummaryFormat(StrEnum):
    """Who the stderr summary is written for: a person, or a log collector.

    Explicit rather than inferred from `isatty`, because the two readers want different things
    and a deployment can say which it is. Guessing would also make the output of a piped run
    depend on how it was invoked, which is precisely the sort of thing that is discovered
    months later in a dashboard that has been quietly empty.
    """

    TEXT = "text"
    JSON = "json"


_WATCHLIST = Path("watchlist.toml")

_FIXTURE = typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network.")
_JSON_OUT = typer.Option("--json-out", help="Write the typed report here instead of stdout.")
_CASSETTES = typer.Option(
    "--cassettes", help="How the explain stage meets its cassette store: replay, record or live."
)
_OBSERVED = typer.Option(
    "--observed-on",
    formats=["%Y-%m-%d"],
    help="Date the first-class states are stamped with. Defaults to today (UTC).",
)
_OUTPUT_REPO = typer.Option(
    "--output-repo",
    help="Commit the changelog into this git repository; created if absent, never pushed.",
)
_SUMMARY = typer.Option(
    "--summary", help="The stderr summary: `text` for a person, `json` for a log collector."
)


def run(
    once: Annotated[
        bool, typer.Option("--once/--loop", help="One poll. `--loop` is not implemented.")
    ] = True,
    since: Annotated[
        datetime | None,
        typer.Option("--since", formats=DATE_FORMATS, help="Window start. Defaults to the cursor."),
    ] = None,
    until: Annotated[
        datetime | None,
        typer.Option("--until", formats=DATE_FORMATS, help="Window end. Defaults to midnight."),
    ] = None,
    watchlist_path: Annotated[
        Path, typer.Option("--watchlist", help="The acts to watch.")
    ] = _WATCHLIST,
    state_file: Annotated[
        Path | None,
        typer.Option("--state-file", help="Where the seen-state lives. Defaults to user data."),
    ] = None,
    channel: Annotated[
        str, typer.Option("--channel", help="Notification channel segment.")
    ] = DEFAULT_CHANNEL,
    fixture_dir: Annotated[Path | None, _FIXTURE] = None,
    json_out: Annotated[Path | None, _JSON_OUT] = None,
    cassettes: Annotated[CassetteMode | None, _CASSETTES] = None,
    observed_on: Annotated[datetime | None, _OBSERVED] = None,
    output_repo: Annotated[Path | None, _OUTPUT_REPO] = None,
    summary: Annotated[SummaryFormat, _SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Run the whole loop once: poll, fetch, diff, corroborate, explain, gate, emit.

    The cron-able command. With an output repository configured it ends in a git commit per
    amended act; with none, it prints the typed report and writes nothing.
    """
    if not once:
        typer.echo("`--loop` is not implemented; use a cron entry around `--once`.", err=True)
        raise typer.Exit(code=2)
    try:
        watchlist = load_watchlist(watchlist_path)
    except (FileNotFoundError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    stamp = observed_on.date() if observed_on is not None else today_utc()
    end = until if until is not None else datetime.combine(stamp, datetime.min.time())
    with adapter_for(fixture_dir, stamp) as adapter:
        source = FeedWatchSource(
            adapter,
            watchlist=watchlist,
            state_path=state_file if state_file is not None else default_state_path(),
            channel=channel,
            notice=lambda message: typer.echo(message, err=True),
        )
        report = execute(
            deps_for(adapter, stamp, cassettes, watcher=source),
            PipelineState(
                observed_on=stamp,
                window=source.window(since=since, until=end, observed_on=stamp),
            ),
            watch=True,
        )
    _emit(report, json_out, resolve_repo_path(output_repo, watchlist.output.repo_path), summary)


def explain(
    act: Annotated[str, typer.Argument(help="CELEX of the act, e.g. 32024R1689.")],
    from_version: Annotated[str, typer.Argument(help="Version to compare from.")],
    to_version: Annotated[str, typer.Argument(help="Version to compare to.")],
    fixture_dir: Annotated[Path | None, _FIXTURE] = None,
    json_out: Annotated[Path | None, _JSON_OUT] = None,
    cassettes: Annotated[CassetteMode | None, _CASSETTES] = None,
    observed_on: Annotated[datetime | None, _OBSERVED] = None,
    output_repo: Annotated[Path | None, _OUTPUT_REPO] = None,
    summary: Annotated[SummaryFormat, _SUMMARY] = SummaryFormat.TEXT,
) -> None:
    """Run the loop over one named transition, skipping the feed. The manual trigger.

    Writes to the output repository on the same terms `run` does, minus the file: there is no
    watchlist on this path, so `--output-repo` and `EMENDRIX_OUTPUT_REPO` are the two sources.
    """
    stamp = observed_on.date() if observed_on is not None else today_utc()
    identity = act_id(Celex.parse(act))
    with adapter_for(fixture_dir, stamp) as adapter:
        report = execute(
            deps_for(adapter, stamp, cassettes),
            PipelineState(
                observed_on=stamp,
                events=(
                    manual_event(
                        identity,
                        from_version,
                        to_version,
                        stamp,
                        trigger="manual: emendrix explain",
                    ),
                ),
            ),
            watch=False,
        )
    _emit(report, json_out, resolve_repo_path(output_repo), summary)


def _emit(
    report: RunReport,
    json_out: Path | None,
    repo_path: Path | None = None,
    summary: SummaryFormat = SummaryFormat.TEXT,
) -> None:
    """The typed report, byte-stable, plus the counts a human reads first.

    The summary is on stderr in both formats, so `--summary json` does not disturb the report
    on stdout and the two can be read by two different things at once: a deployment writes the
    report to `--json-out` on a volume and lets the collector have the line on stderr.
    """
    payload = report.model_dump_json(indent=2)
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(payload + "\n", encoding="utf-8")
    else:
        typer.echo(payload)
    if summary is SummaryFormat.JSON:
        typer.echo(summarise_run(report).model_dump_json(), err=True)
    else:
        typer.echo(summarise(report), err=True)
    if repo_path is not None:
        _write_changelog(report, repo_path)


def _write_changelog(report: RunReport, repo_path: Path) -> None:
    """Commit every act's transition into the output repository, one commit each.

    Reported on stderr beside the summary, so the JSON on stdout stays parseable. A git
    failure — no git on PATH, a path inside somebody else's working tree — is a message and a
    non-zero exit, not a traceback: by this point the report has already been printed, and the
    run genuinely did the work it was asked to do.
    """
    try:
        repository = OutputRepo.open(repo_path)
        for entry in entries_for(report):
            written = repository.write(entry)
            state = "unchanged" if written.unchanged else f"committed {written.revision[:7]}"
            typer.echo(f"{written.changelog}: {state}", err=True)
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


def summarise(report: RunReport) -> str:
    """One line per act plus the run's totals. Deterministic; no timing, no clock."""
    lines = [
        f"{delta.act} {delta.from_version} -> {delta.to_version}: "
        f"{delta.summary.touched_units} touched · {delta.summary.disputed} disputed · "
        f"{delta.gate.passed_first} passed, {delta.gate.passed_on_retry} on retry, "
        f"{delta.gate.fallback} quoted, {delta.gate.unexplained} unexplained"
        for delta in report.deltas
    ]
    lines.extend(
        f"skipped {item.act} {item.target_version or ''}: {item.reason}" for item in report.skipped
    )
    gate = report.gate
    lines.append(
        f"gate: {gate.changes} changes · {gate.citations} citations · "
        f"{gate.citations_rejected} rejected · {gate.retries} sent back for revision"
    )
    return "\n".join(lines)
