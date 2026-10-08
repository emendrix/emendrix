"""The flags every `emendrix repair` verb shares, declared once.

Kept apart from the composition root because they are the one part of it that names no corpus:
the same `--dry-run`, `--limit` and `--repaired-on` read the same way on every verb, and a second
spelling of one flag's help text would be two promises about one behaviour.
"""

from __future__ import annotations

from pathlib import Path

import typer

__all__ = [
    "CASSETTES",
    "CHANGES",
    "DRY",
    "FIXTURE",
    "LIMIT",
    "LIST",
    "REPAIRED",
    "REPO",
    "SUMMARY",
    "WATCHLIST",
]

WATCHLIST = Path("watchlist.toml")

LIST = typer.Option("--watchlist", help="Where the output repository is configured.")
REPO = typer.Option("--output-repo", help="The repository to repair. Required.")
DRY = typer.Option("--dry-run", help="Print what would move, write nothing at all.")
LIMIT = typer.Option("--limit", min=1, help="Stop after this many entries that would change.")
FIXTURE = typer.Option("--fixture-dir", help="Read from a pinned fixture set, never the network.")
REPAIRED = typer.Option(
    "--repaired-on",
    formats=["%Y-%m-%d"],
    help="Date the repair record is stamped with. Defaults to today (UTC).",
)
SUMMARY = typer.Option(
    "--summary", help="The stderr summary: `text` for a person, `json` for a log collector."
)
CHANGES = typer.Option(
    "--limit", min=1, help="Stop after this many changes. Changes are what a call is paid for."
)
CASSETTES = typer.Option("--cassettes", help="How the explain stage meets its cassette store.")
