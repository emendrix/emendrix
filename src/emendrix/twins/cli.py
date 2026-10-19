"""`emendrix twins build`: the twin map of each configured pair of acts, committed when it moves.

The composition root of `twins/`, and the one module in it allowed to name the corpus: it reads
the watchlist, resolves the text store and the changelog repository, and decides which stored
version of an act is the newest, which takes reading the corpus's version identifiers. Every
other module in the package sees core types only.

The map is built from each act's newest stored version and nothing else: no network, no
model, no clock. A pair naming an act that is not watched, or one with no readable stored
version, is a counted refusal in the summary, never a crash; the exit status is 0 whenever the
run completes and 2 when it cannot start.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field

from emendrix import DISCLAIMER
from emendrix.core import ActId, ProvisionTree
from emendrix.eu.identifiers import Celex, ConsolidatedId
from emendrix.graph.cli import SummaryFormat
from emendrix.output.config import OUTPUT_REPO_ENV, resolve_repo_path
from emendrix.output.git import GitError
from emendrix.output.repo import OutputRepo
from emendrix.texts.config import TEXT_STORE_ENV, resolve_store_path
from emendrix.texts.model import UnreadableVersion
from emendrix.texts.store import StoreRefusal, TextStore
from emendrix.twins.build import twin_map
from emendrix.twins.model import TwinMap, ordered
from emendrix.twins.write import NotARepository, open_repository, path_for, write_twin_map
from emendrix.watch.config import Watchlist, load_watchlist

__all__ = ["PairOutcome", "TwinsSummary", "app", "build"]

app = typer.Typer(
    name="twins",
    help="Pair the provisions of two acts by textual similarity and commit the twin map.",
    no_args_is_help=True,
)

Outcome = Literal["written", "unchanged", "would_write", "refused"]


class PairOutcome(BaseModel):
    """What happened to one pair of acts."""

    model_config = ConfigDict(frozen=True)

    acts: tuple[str, str] = Field(description="The two keys, lower first.")
    outcome: Outcome
    detail: str = Field(default="", description="Why a pair was refused, in one line.")
    path: str = ""
    revision: str = ""
    versions: tuple[str, str] = ("", "")
    pairs: int = 0
    identical: int = 0
    withheld: int = 0
    unpaired: tuple[int, int] = (0, 0)


class TwinsSummary(BaseModel):
    """The run, pair by pair, and its totals."""

    model_config = ConfigDict(frozen=True)

    dry_run: bool
    pairs: tuple[PairOutcome, ...]

    def count(self, outcome: Outcome) -> int:
        return sum(1 for pair in self.pairs if pair.outcome == outcome)


@app.callback()
def main() -> None:
    """Keep `emendrix twins` a group, so `build` is spelled out."""


def _refuse(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code=2)


def _requested(watchlist: Watchlist, chosen: list[str] | None) -> list[tuple[str, str]]:
    if not chosen:
        return [pair.key for pair in watchlist.twins]
    requested: list[tuple[str, str]] = []
    for raw in chosen:
        parts = [part.strip() for part in raw.split(",")]
        try:
            if len(parts) != 2:
                raise ValueError(f"--pair takes two CELEX numbers joined by a comma, not {raw!r}")
            low, high = sorted(Celex.parse(part).value for part in parts)
        except ValueError as error:
            raise _refuse(str(error)) from error
        if low == high:
            raise _refuse(f"--pair {raw!r} names one act twice")
        requested.append((low, high))
    return list(dict.fromkeys(requested))


def _rank(version: str) -> tuple[int, str]:
    """Consolidations by date, after the act as published, whose identifier carries no date."""
    try:
        return (1, ConsolidatedId.parse(version).version_date.isoformat())
    except ValueError:
        return (0, version)


def _newest(store: TextStore, act: ActId) -> ProvisionTree | str:
    """The act's newest stored version as a tree, or why there is none."""
    versions = store.versions(act.corpus, act.key)
    if not versions:
        return f"{act.key} has no stored version; run `emendrix texts build` first"
    version = max(versions, key=_rank)
    tree = store.tree(act.corpus, act.key, version)
    if isinstance(tree, UnreadableVersion):
        return f"{act.key} {version} is unreadable: {tree.detail}"
    if tree is None:
        return f"{act.key} {version} vanished from the store while it was read"
    return tree


def _refused(acts: tuple[str, str], detail: str) -> PairOutcome:
    return PairOutcome(acts=acts, outcome="refused", detail=detail)


def _one(
    keys: tuple[str, str],
    watched: dict[str, ActId],
    store: TextStore,
    repo: OutputRepo,
    *,
    dry_run: bool,
) -> PairOutcome:
    missing = [key for key in keys if key not in watched]
    if missing:
        return _refused(keys, f"not on the watchlist's [[acts]]: {', '.join(missing)}")
    act_a, act_b = ordered(watched[keys[0]], watched[keys[1]])
    trees = (_newest(store, act_a), _newest(store, act_b))
    reasons = [tree for tree in trees if isinstance(tree, str)]
    if reasons:
        return _refused(keys, "; ".join(reasons))
    tree_a, tree_b = (tree for tree in trees if isinstance(tree, ProvisionTree))
    document = twin_map(tree_a, tree_b)
    written = write_twin_map(repo, document, dry_run=dry_run)
    outcome: Outcome = "unchanged" if written.unchanged else "would_write" if dry_run else "written"
    return _counted(document, keys, outcome, written.revision or "")


def _counted(
    document: TwinMap, keys: tuple[str, str], outcome: Outcome, revision: str
) -> PairOutcome:
    return PairOutcome(
        acts=keys,
        outcome=outcome,
        path=path_for(document),
        revision=revision,
        versions=(document.a.version, document.b.version),
        pairs=len(document.pairs),
        identical=sum(1 for pair in document.pairs if pair.identical),
        withheld=sum(1 for pair in document.pairs if pair.passages_withheld),
        unpaired=(len(document.unpaired_a), len(document.unpaired_b)),
    )


@app.command("build")
def build(
    watchlist_path: Annotated[
        Path, typer.Option("--watchlist", help="The acts, the \\[\\[twins]] pairs and \\[output].")
    ] = Path("watchlist.toml"),
    text_store: Annotated[
        Path | None,
        typer.Option("--text-store", help=f"The text store to read. Else {TEXT_STORE_ENV}."),
    ] = None,
    output_repo: Annotated[
        Path | None,
        typer.Option("--output-repo", help=f"The changelog repository. Else {OUTPUT_REPO_ENV}."),
    ] = None,
    pair: Annotated[
        list[str] | None,
        typer.Option("--pair", help="Two CELEX numbers, `A,B`; repeatable. Default: [[twins]]."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Say what would change; write nothing.")
    ] = False,
    summary: Annotated[
        SummaryFormat, typer.Option("--summary", help="The stderr summary: `text` or `json`.")
    ] = SummaryFormat.TEXT,
) -> None:
    """Build each pair's twin map from the newest stored texts; commit it when its bytes move."""
    try:
        watchlist = load_watchlist(watchlist_path)
    except (FileNotFoundError, ValueError) as error:
        raise _refuse(str(error)) from error
    store_path = resolve_store_path(text_store, watchlist.output.text_store_path)
    repo_path = resolve_repo_path(output_repo, watchlist.output.repo_path)
    if store_path is None:
        raise _refuse(
            f"no text store is configured: give --text-store, set {TEXT_STORE_ENV} or set "
            "[output] text_store_path in the watchlist."
        )
    if repo_path is None:
        raise _refuse(
            f"no changelog repository is configured: give --output-repo, set {OUTPUT_REPO_ENV} "
            "or set [output] repo_path in the watchlist."
        )
    keys = _requested(watchlist, pair)
    try:
        store = TextStore.open(store_path)
        repo = open_repository(repo_path)
    except (StoreRefusal, NotARepository, GitError) as error:
        raise _refuse(str(error)) from error
    watched = {entry.celex: entry.act for entry in watchlist.acts}
    outcomes = tuple(_one(each, watched, store, repo, dry_run=dry_run) for each in keys)
    _report(TwinsSummary(dry_run=dry_run, pairs=outcomes), summary)


def _report(result: TwinsSummary, summary: SummaryFormat) -> None:
    if summary is SummaryFormat.JSON:
        typer.echo(result.model_dump_json(), err=True)
        return
    if not result.pairs:
        typer.echo(
            "no pair to build: the watchlist has no [[twins]] block and no --pair.", err=True
        )
    for outcome in result.pairs:
        typer.echo(_line(outcome), err=True)
    totals = ", ".join(
        f"{result.count(kind)} {kind.replace('_', ' ')}"
        for kind in ("written", "unchanged", "would_write", "refused")
    )
    typer.echo(f"{'dry run: ' if result.dry_run else ''}{totals}", err=True)
    typer.echo(DISCLAIMER, err=True)


def _line(outcome: PairOutcome) -> str:
    name = f"{outcome.acts[0]} and {outcome.acts[1]}"
    if outcome.outcome == "refused":
        return f"{name}: refused, {outcome.detail}"
    commit = f" · commit {outcome.revision[:12]}" if outcome.revision else ""
    return (
        f"{name}: {outcome.outcome.replace('_', ' ')} {outcome.path} · at "
        f"{outcome.versions[0]} and {outcome.versions[1]} · {outcome.pairs} twins "
        f"({outcome.identical} identical, {outcome.withheld} withheld) · unpaired "
        f"{outcome.unpaired[0]} and {outcome.unpaired[1]}{commit}"
    )
