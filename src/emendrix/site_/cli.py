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

`--operator`, `--operator-url` and `--contact` are deployment facts of the same kind: who runs
this instance, where to read about them, and where a reader may write. They are the only other
place such a fact enters, the site being otherwise a pure function of committed artifacts, and
they arrive on the command line because a name and an address belong to a deployment and not
to an open-source tree. None of them has a default, because an about page that names nobody is
honest where one that names a placeholder is not.

This module is where the EU corpus is allowed to be named. Which act has an EUR-Lex address is
a corpus capability, not something the pages may know, so the URL is resolved here from the
newest version each act has been consolidated to and handed down as a plain string, the same
way the pipeline's root hands down an adapter. The date each consolidated version speaks as
of is read here for the same reason: only this module may read a version tag, and that date
is what every newest-first list on the site sorts by.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix.core import ActId, VersionId
from emendrix.eu.http import today_utc
from emendrix.eu.identifiers import ConsolidatedId, parse_version_id
from emendrix.eu.links import document_url
from emendrix.eval_.readme_table import latest_report
from emendrix.eval_.report import DEFAULT_REPORT_DIR
from emendrix.eval_.runner import EvalRun
from emendrix.output import ChangelogEntry, resolve_repo_path
from emendrix.output.json_out import slug
from emendrix.site_.build import write_site
from emendrix.site_.clocks import VersionDates, sort_date
from emendrix.site_.inputs import collect_site, read_entries
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


def _version_dates(entries: tuple[ChangelogEntry, ...]) -> VersionDates:
    """The date each EU consolidated version speaks as of, read off its own tag.

    `sort_date` orders every newest-first list by these. An entry outside this corpus, one
    whose version is the OJ act itself rather than a consolidation, or one whose tag does
    not parse gets no entry here and falls back to `event_dated`: an unreadable tag is a
    gap to fall back past, not a reason to fail a build over committed data.
    """
    dated: dict[tuple[ActId, VersionId], date] = {}
    for entry in entries:
        if entry.act.corpus != _EU:
            continue
        try:
            parsed = parse_version_id(entry.to_version)
        except ValueError:
            continue
        if isinstance(parsed, ConsolidatedId):
            dated[(entry.act, entry.to_version)] = parsed.version_date
    return dated


def _eurlex_urls(
    entries: tuple[ChangelogEntry, ...], version_dates: VersionDates
) -> dict[str, str]:
    """One EUR-Lex document URL per EU act, for the version `sort_date` ranks newest.

    Keyed by the act's URL slug, which is what `collect_site` matches on, and ranked by the
    same clock every newest-first list uses, so the link an act shows and the event a reader
    sees as newest cannot name two different versions. An act with no committed event yet
    gets no entry here and no link, because the newest consolidation is exactly the thing
    nothing has recorded for it.
    """
    newest: dict[str, tuple[tuple[str, str], str]] = {}
    for entry in entries:
        if entry.act.corpus != _EU:
            continue
        key = slug(entry.act.key)
        ranked = (sort_date(entry, version_dates).isoformat(), str(entry.to_version))
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

    version_dates = _version_dates(entries)
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
        eurlex_urls=_eurlex_urls(entries, version_dates),
        version_dates=version_dates,
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
