"""What an operator typed, turned into values — or into a message and a non-zero exit.

Split from `cli.py` because a long-running batch command has an unusual number of ways to be
*asked* to do something impossible, and they share one rule worth stating once: **every one of
them is refused before the first fetch, with a sentence naming what is wrong**. A watchlist that
does not parse, a CELEX that is not one, a delay that is not a number, a repository emendrix may
not write in: all of them cost nothing to discover and would cost real money to discover late,
after three hundred model calls.

The one exception to "no exceptions" in this project is deliberate and holds here: the first-class
states are what the *corpus* reported and the output carries. These are an environment being wrong
before any work starts, and a `typer.Exit(2)` is the honest shape for that.

Nothing here reads a clock, a network or a model.
"""

from __future__ import annotations

from pathlib import Path

import typer

from emendrix.backfill.ledger import Ledger, LedgerLoad, load_ledger
from emendrix.eu.http import polite_delay
from emendrix.eu.identifiers import Celex
from emendrix.output import GitError, OutputRepo
from emendrix.watch.config import Watchlist, load_watchlist

__all__ = ["celex_of", "delay_of", "ledger_read_only", "reported", "repository_at", "watchlist_at"]


def watchlist_at(path: Path) -> Watchlist:
    """The one hand-written input in the system, so a bad one gets a message, not a traceback."""
    try:
        return load_watchlist(path)
    except (FileNotFoundError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


def celex_of(act: str) -> str:
    """`--act` as the corpus spells it, or a message and a non-zero exit."""
    try:
        return Celex.parse(act).value
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


def delay_of(flag: float | None) -> float:
    """How long to wait between fetches, resolved before anything is fetched.

    Resolved here rather than left to the adapter so that a mistyped environment variable is a
    message and a non-zero exit, like a bad watchlist: backfill is the command that turns the
    delay up, and an operator who asked for one and silently got the default would find out
    from the other end's rate limiter.
    """
    try:
        return polite_delay(flag)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


def repository_at(path: Path | None) -> OutputRepo | None:
    """The output repository, opened before the first fetch so a refusal costs nothing.

    Opened for a dry run too, and not only because a dry run reads it to say what is already
    done: a path emendrix may not write in is worth being told about while nothing has been
    spent, rather than after the first three hundred model calls.
    """
    if path is None:
        return None
    try:
        return OutputRepo.open(path)
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


def ledger_read_only(path: Path) -> Ledger:
    """A dry run consults the ledger and never writes it, a corrupt one included."""
    return reported(load_ledger(path, set_aside=False))


def reported(loaded: LedgerLoad) -> Ledger:
    """Say so when the record could not be read: losing it silently is what costs trust."""
    if loaded.recovered:
        typer.echo(loaded.detail, err=True)
    return loaded.ledger
