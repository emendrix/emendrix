"""`emendrix texts build|show`: the text store, filled from the corpus and read by an operator.

The composition root of `texts/`, and the one module in it allowed to name the corpus: it reads
the watchlist, builds the adapter through `emendrix.session.adapter_for`, and takes the one
sanctioned clock read when `--observed-on` is not given. Everything else in the package sees
core types only and would fill a store from the toy corpus unchanged.

`build` writes nothing outside the store, commits nothing and calls no model. `show` reads one
stored version and prints its unit list, or one node's text verbatim; it is an operator's
inspection tool and no published surface reads it.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from emendrix import DISCLAIMER
from emendrix.backfill.inputs import delay_of
from emendrix.core import ActId, ProvisionLocation
from emendrix.eu.http import POLITE_DELAY_ENV, POLITE_DELAY_S, today_utc
from emendrix.eu.identifiers import Celex, act_id
from emendrix.graph.cli import SummaryFormat
from emendrix.session import adapter_for
from emendrix.texts.build import ActBuild, BuildSummary, build_store
from emendrix.texts.config import TEXT_STORE_ENV, resolve_store_path
from emendrix.texts.model import StoredVersionFile, UnreadableVersion
from emendrix.texts.store import StoreRefusal, TextStore
from emendrix.watch.config import Watchlist, load_watchlist

__all__ = ["app", "build", "show"]

app = typer.Typer(
    name="texts",
    help="Keep the verbatim text of every stored version beside the changelogs, unpublished.",
    no_args_is_help=True,
)

_NO_STORE = (
    f"no text store is configured: give --text-store, set {TEXT_STORE_ENV} or set "
    "[output] text_store_path in the watchlist."
)
_STORE = typer.Option("--text-store", help=f"The store directory. Else {TEXT_STORE_ENV}.")
_LIST = typer.Option("--watchlist", help="The acts to store, and [output] text_store_path.")


@app.callback()
def main() -> None:
    """Keep `emendrix texts` a group, so `build` and `show` are spelled out."""


def _refuse(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code=2)


def _watchlist(path: Path) -> Watchlist:
    try:
        return load_watchlist(path)
    except (FileNotFoundError, ValueError) as error:
        raise _refuse(str(error)) from error


def _acts(watchlist: Watchlist, chosen: list[str] | None) -> list[ActId]:
    watched = {entry.celex: entry.act for entry in watchlist.acts}
    if not chosen:
        return list(watched.values())
    acts: list[ActId] = []
    for raw in chosen:
        try:
            celex = Celex.parse(raw).value
        except ValueError as error:
            raise _refuse(str(error)) from error
        if celex not in watched:
            raise _refuse(f"{celex} is not on the watchlist; the store keeps watched acts only.")
        acts.append(watched[celex])
    return acts


@app.command("build")
def build(
    watchlist_path: Annotated[Path, _LIST] = Path("watchlist.toml"),
    text_store: Annotated[Path | None, _STORE] = None,
    act: Annotated[
        list[str] | None, typer.Option("--act", help="Store only this CELEX; repeatable.")
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="Stop after writing this many files.")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="List and count; fetch no text, write nothing.")
    ] = False,
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="Fetch and write stored versions again.")
    ] = False,
    fixture_dir: Annotated[
        Path | None,
        typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network."),
    ] = None,
    polite_delay_s: Annotated[
        float | None,
        typer.Option(
            "--polite-delay",
            min=0.0,
            help=f"Seconds between network calls. Defaults to {POLITE_DELAY_ENV} or "
            f"{POLITE_DELAY_S}.",
        ),
    ] = None,
    observed_on: Annotated[
        datetime | None,
        typer.Option(
            "--observed-on",
            formats=["%Y-%m-%d"],
            help="Date the first-class states are stamped with. Defaults to today (UTC).",
        ),
    ] = None,
    summary: Annotated[
        SummaryFormat,
        typer.Option("--summary", help="The stderr summary: `text` or `json`."),
    ] = SummaryFormat.TEXT,
) -> None:
    """Store every listed version of every watched act that the store lacks.

    Idempotent: a second run over an unchanged listing writes nothing and says so. A version
    answered with a state lands in that act's `states.json`; a fetch that raised is counted and
    retried by the next run. The exit status is 0 whenever the run completes.
    """
    stamp = observed_on.date() if observed_on is not None else today_utc()
    watchlist = _watchlist(watchlist_path)
    path = resolve_store_path(text_store, watchlist.output.text_store_path)
    if path is None:
        raise _refuse(_NO_STORE)
    acts = _acts(watchlist, act)
    try:
        store = TextStore.create_or_open(path, dry_run=dry_run)
    except StoreRefusal as error:
        raise _refuse(str(error)) from error
    reading = (
        f"the pinned fixtures at {fixture_dir}, offline"
        if fixture_dir is not None
        else "the disk cache, then the network for whatever it lacks or holds expired"
    )
    with adapter_for(fixture_dir, stamp, polite_delay_s=delay_of(polite_delay_s)) as adapter:
        result = build_store(adapter, store, acts, limit=limit, dry_run=dry_run, rebuild=rebuild)
    _report(result.model_copy(update={"reading": reading}), store, summary)


def _report(result: BuildSummary, store: TextStore, summary: SummaryFormat) -> None:
    if summary is SummaryFormat.JSON:
        typer.echo(result.model_dump_json(), err=True)
        return
    verb = "would read" if result.dry_run else "read"
    typer.echo(f"{verb} {result.reading}; store {store.root}", err=True)
    for record in (*result.acts, result.total):
        typer.echo(_line(record), err=True)
        for failure in record.failures:
            typer.echo(f"    {failure}", err=True)
    if result.dry_run:
        typer.echo(f"dry run: {result.total.left} versions would be fetched.", err=True)
    elif result.total.written == 0:
        typer.echo(
            "wrote nothing: every listed version already has a file, or answered otherwise.",
            err=True,
        )


def _line(record: ActBuild) -> str:
    states = ", ".join(f"{count} {tag}" for tag, count in record.states.items()) or "none"
    listing = f" · {record.listing_failed} listings failed" if record.listing_failed else ""
    return (
        f"{record.act}: {record.listed} listed · {record.already_stored} already stored · "
        f"{record.written} written · states {states} · {record.fetch_failed} fetches failed · "
        f"{record.left} left{listing}"
    )


@app.command("show")
def show(
    celex: Annotated[str, typer.Argument(help="CELEX of the act, e.g. 32017R0745.")],
    version: Annotated[str, typer.Argument(help="The stored version, e.g. 02017R0745-20250110.")],
    coordinate: Annotated[
        str | None, typer.Argument(help="One node's location, e.g. 'AR 10 PA 9'.")
    ] = None,
    text_store: Annotated[Path | None, _STORE] = None,
    watchlist_path: Annotated[Path, _LIST] = Path("watchlist.toml"),
) -> None:
    """Print a stored version's header and unit list, or one node's text verbatim."""
    configured = (
        _watchlist(watchlist_path).output.text_store_path if watchlist_path.is_file() else None
    )
    path = resolve_store_path(text_store, configured)
    if path is None:
        raise _refuse(_NO_STORE)
    try:
        store = TextStore.open(path)
        identity = act_id(Celex.parse(celex))
    except (StoreRefusal, ValueError) as error:
        raise _refuse(str(error)) from error
    stored = store.read(identity.corpus, identity.key, version)
    if stored is None:
        raise _refuse(f"{identity.key} {version} is not in the store at {store.root}.")
    if isinstance(stored, UnreadableVersion):
        raise _refuse(f"{identity.key} {version} is unreadable: {stored.detail}")
    if coordinate is None:
        _print_units(stored)
    else:
        _print_node(stored, coordinate)
    typer.echo(DISCLAIMER, err=True)


def _print_units(stored: StoredVersionFile) -> None:
    header = stored.header
    typer.echo(
        f"{header.key} {header.version} (served {header.served_version}) · language "
        f"{header.language or 'unstated'} · {header.nodes} nodes · {header.units} units"
    )
    for node in stored.nodes:
        if node.parent is None:
            typer.echo(f"{node.location}" + (f"  {node.heading}" if node.heading else ""))


def _print_node(stored: StoredVersionFile, coordinate: str) -> None:
    try:
        canonical = ProvisionLocation.parse(coordinate).canonical
    except ValueError as error:
        raise _refuse(str(error)) from error
    for node in stored.nodes:
        if node.location == canonical:
            typer.echo(node.text)
            return
    raise _refuse(f"{stored.header.version} holds no node at {canonical}.")
