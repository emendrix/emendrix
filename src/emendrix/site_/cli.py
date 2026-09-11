"""`emendrix site build --out site/`: the composition root of the published site.

```bash
uv run emendrix site build --out site/                       # from the configured output repo
uv run emendrix site build --out site/ \\
    --changelogs ~/regulatory-changelog \\
    --repo-url https://example.invalid/emendrix \\
    --site-url https://changes.example.invalid
```

Like every other root in this project it reads the clock once, here, and passes the date down
as a value; nothing under it asks what time it is, which is what makes two builds of one set of
artifacts produce identical bytes.

Where the changelogs come from follows the same precedence the rest of the tool uses for the
output repository: `--changelogs` > `EMENDRIX_OUTPUT_REPO` > `[output] repo_path` in
`watchlist.toml` (`output/config.py`). The site reads exactly the repository `run` writes, and
two ways of naming one path is one too many. With none of the three set the site still builds
and says no repository was configured, because a site that crashes on a fresh checkout is worse
than one that admits what it was given.

`--site-url` is the one address the generator cannot infer. Pages link relative to themselves
and need none, but a feed's links are absolute by definition, so without it no feed file is
written and the feeds page says why.

`--operator`, `--operator-url`, `--contact` and `--watch-state` are deployment facts of the
same kind: who runs this instance, where to read about them, where a reader may write, and the
file the poller on this instance writes its own record into. They are the only place such a
fact enters, the site being otherwise a pure function of committed artifacts, and they arrive
on the command line because they belong to a deployment and not to an open-source tree. None
of them has a default, because an about page that names nobody is honest where one that names
a placeholder is not, and a page that would rather say nothing than say something wrong is the
same rule applied to a date.

Which corpus published a document is read in `site_.boundary`, the module this one was split
from when it reached the size cap: that module turns the identifiers a changelog recorded into
labels and addresses, and this one composes a build out of what it returns.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.eu.http import today_utc
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.report import DEFAULT_REPORT_DIR
from emendrix.eval_.runner import EvalRun
from emendrix.output import resolve_repo_path
from emendrix.site_ import boundary
from emendrix.site_.build import write_site
from emendrix.site_.entries import read_entries
from emendrix.site_.inputs import collect_site
from emendrix.site_.markup import count
from emendrix.site_.polled import read_polled
from emendrix.watch.config import Watchlist, load_watchlist

__all__ = ["app", "build"]

app = typer.Typer(
    name="site",
    help="Generate the static site from committed artifacts.",
    no_args_is_help=True,
)

_WATCHLIST = Path("watchlist.toml")

_WATCH_STATE = typer.Option(
    "--watch-state",
    help="The poller's state file; with it the site says when the corpus was last checked.",
)


def _watchlist(path: Path) -> Watchlist | None:
    """The watchlist if there is one. Its absence is a mode, not an error.

    With a watchlist the site shows the acts it names, under the labels, domains and aliases it
    gives them, including acts nothing has happened to yet. Without one, which is the normal
    state of a fresh checkout since `watchlist.toml` is gitignored, every act found in the
    changelog repository is shown instead.
    """
    return load_watchlist(path) if path.is_file() else None


@app.command("build")
def build(
    out: Annotated[
        Path, typer.Option("--out", help="Directory the site is written into; created if absent.")
    ] = Path("site"),
    changelogs: Annotated[
        Path | None,
        typer.Option("--changelogs", help="The output git repository holding the changelogs."),
    ] = None,
    report: Annotated[
        Path | None,
        typer.Option("--report", help="Report JSON to publish. Defaults to the newest committed."),
    ] = None,
    report_dir: Annotated[
        Path, typer.Option("--report-dir", help="Where committed reports are read from.")
    ] = DEFAULT_REPORT_DIR,
    watchlist_path: Annotated[
        Path, typer.Option("--watchlist", help="The acts to show, and their labels.")
    ] = _WATCHLIST,
    home_limit: Annotated[
        int, typer.Option("--home-limit", min=1, help="How many events the front page lists.")
    ] = 20,
    repo_url: Annotated[
        str, typer.Option("--repo-url", help="Public https:// home of the source, for links.")
    ] = "",
    changelogs_url: Annotated[
        str,
        typer.Option(
            "--changelogs-url", help="Public https:// home of the changelog data, for links."
        ),
    ] = "",
    site_url: Annotated[
        str,
        typer.Option("--site-url", help="Public https:// base of the site. Without it, no feeds."),
    ] = "",
    operator: Annotated[
        str, typer.Option("--operator", help="Who runs this instance, for the about page.")
    ] = "",
    operator_url: Annotated[
        str,
        typer.Option(
            "--operator-url", help="Public https:// page of the operator, for the about page."
        ),
    ] = "",
    contact: Annotated[
        str,
        typer.Option("--contact", help="Address readers may write to, for the about page."),
    ] = "",
    watch_state: Annotated[Path | None, _WATCH_STATE] = None,
    generated_on: Annotated[
        datetime | None,
        typer.Option(
            "--generated-on",
            formats=["%Y-%m-%d"],
            help="Date printed on every page. Defaults to today (UTC).",
        ),
    ] = None,
) -> None:
    """Write the whole site from the committed changelogs and the committed eval report.

    Deterministic: the same artifacts and the same date produce the same bytes, which is what
    lets a golden test assert the tree rather than assert around it.

    `--contact` is checked for shape and nothing more: one `@` and no whitespace. That is not
    RFC 5322 and is not meant to be, since the only thing a generator can usefully refuse is
    a value that would render a broken `mailto:`; whether the address receives mail is a
    question only a message can answer.

    `--watch-state` is not checked at all. A path that holds nothing readable answers with no
    record and the about page says nothing about polling, because a build that failed over a
    file it was handed as a courtesy would take the whole site down for a fact it can live
    without.
    """
    for name, value in (
        ("--repo-url", repo_url),
        ("--changelogs-url", changelogs_url),
        ("--site-url", site_url),
        ("--operator-url", operator_url),
    ):
        if value and not value.startswith("https://"):
            typer.echo(f"{name} must be an https:// URL; got {value!r}", err=True)
            raise typer.Exit(code=2)
    if contact and (contact.count("@") != 1 or any(c.isspace() for c in contact)):
        typer.echo(
            f"--contact must be an address with one @ and no spaces; got {contact!r}", err=True
        )
        raise typer.Exit(code=2)
    try:
        watchlist = _watchlist(watchlist_path)
        chosen = report if report is not None else latest_report(report_dir)
        run = EvalRun.model_validate_json(chosen.read_bytes())
        root = resolve_repo_path(
            changelogs, None if watchlist is None else watchlist.output.repo_path
        )
        entries = read_entries(root) if root is not None and root.is_dir() else ()
    except (FileNotFoundError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    version_dates = boundary.version_dates(entries)
    amending_numbers, amending_urls = boundary.amending(entries)
    site = collect_site(
        generated_on=generated_on.date() if generated_on is not None else today_utc(),
        run=run,
        report=chosen,
        entries=entries,
        watchlist=watchlist,
        configured=root is not None,
        repo_url=repo_url,
        changelogs_url=changelogs_url,
        # Joined with a single separator wherever a feed builds an absolute link, so the base
        # carries none of its own.
        site_url=site_url.rstrip("/"),
        operator=operator,
        operator_url=operator_url,
        contact=contact,
        eurlex_urls=boundary.eurlex_urls(entries, version_dates),
        published_urls=boundary.published_urls(watchlist),
        kinds=boundary.kinds(watchlist),
        amending_numbers=amending_numbers,
        amending_urls=amending_urls,
        version_dates=version_dates,
        polled=read_polled(watch_state),
    )
    written = write_site(out, site, home_limit=home_limit)
    pages = sum(1 for path in written if path.suffix == ".html")
    # The sitemap is an `.xml` file at the site root and is not a feed, so the feeds are counted
    # by where they live rather than by their extension.
    feeds = sum(1 for path in written if path.suffix == ".xml" and path.parts[0] == "feeds")
    typer.echo(
        f"{out}: {count(pages, 'page')}, {count(feeds, 'feed')}, "
        f"{count(len(site.acts), 'act')}, "
        f"numbers from {chosen} ({run.run_date.isoformat()}, {run.revision})"
    )
