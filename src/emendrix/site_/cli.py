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
written and the feeds page says why. It is also the only place a deployment fact enters: the
site is otherwise a pure function of committed artifacts.

This module is where the EU corpus is allowed to be named. Which act has an EUR-Lex address is
a corpus capability, not something the pages may know, so the URL is resolved here from the
newest version each act has been consolidated to and handed down as a plain string, the same
way the pipeline's root hands down an adapter.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.eu.http import today_utc
from emendrix.eu.links import document_url
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.report import DEFAULT_REPORT_DIR
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, resolve_repo_path
from emendrix.output.json_out import slug
from emendrix.site_.build import write_site
from emendrix.site_.inputs import collect_site, event_dated, read_entries
from emendrix.site_.markup import count
from emendrix.watch.config import Watchlist, load_watchlist

__all__ = ["app", "build"]

app = typer.Typer(
    name="site",
    help="Generate the static site from committed artifacts.",
    no_args_is_help=True,
)

_WATCHLIST = Path("watchlist.toml")

_EU = "eu"
"""The one corpus with a published document URL scheme. Others simply get no link."""


def _watchlist(path: Path) -> Watchlist | None:
    """The watchlist if there is one. Its absence is a mode, not an error.

    With a watchlist the site shows the acts it names, under the labels, domains and aliases it
    gives them, including acts nothing has happened to yet. Without one, which is the normal
    state of a fresh checkout since `watchlist.toml` is gitignored, every act found in the
    changelog repository is shown instead.
    """
    return load_watchlist(path) if path.is_file() else None


def _eurlex_urls(entries: tuple[ChangelogEntry, ...]) -> dict[str, str]:
    """One EUR-Lex document URL per EU act, for the newest version it was consolidated to.

    Keyed by the act's URL slug, which is what `collect_site` matches on. An act with no
    committed event yet gets no entry here and no link, because the newest consolidation is
    exactly the thing nothing has recorded for it.
    """
    newest: dict[str, tuple[tuple[str, str], str]] = {}
    for entry in entries:
        if entry.act.corpus != _EU:
            continue
        key = slug(entry.act.key)
        ranked = (event_dated(entry).isoformat(), str(entry.to_version))
        if key not in newest or ranked > newest[key][0]:
            newest[key] = (ranked, document_url(entry.to_version))
    return {key: url for key, (_, url) in newest.items()}


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
    """
    for name, value in (
        ("--repo-url", repo_url),
        ("--changelogs-url", changelogs_url),
        ("--site-url", site_url),
    ):
        if value and not value.startswith("https://"):
            typer.echo(f"{name} must be an https:// URL; got {value!r}", err=True)
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
        eurlex_urls=_eurlex_urls(entries),
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
