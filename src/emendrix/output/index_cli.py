"""`emendrix index rebuild`: every index file of a changelogs repository, from its payloads.

`OutputRepo.write` keeps the index current on every commit it makes, but rebuilds only the act it
writes and reads every other act's index as it stands. A repository written before the index
existed, a hand-edited act index, or history work done on the repository outside emendrix (a
re-root, a fast-forward) is brought back to what its payloads say by this command, in one commit.

It reads only the repository's own files: no network, no clock, no model, and so no date to be
given. The repository is `--output-repo`, else `EMENDRIX_OUTPUT_REPO`, and it is opened through
`OutputRepo.open`, so a path inside another working tree and a repository emendrix did not
create are both refused. `watchlist.toml` is not read: it would bring the corpus's identifier
rules into a package that knows no corpus, and a command run once by an operator can be told.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from emendrix.output.config import resolve_repo_path
from emendrix.output.git import GitError, commit, git, staged
from emendrix.output.index import index_files
from emendrix.output.repo import INDEX_SUBJECT, OutputRepo

__all__ = ["app", "rebuild"]

app = typer.Typer(
    name="index",
    help="Maintain the change index a changelogs repository carries.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Keep `emendrix index` a group, so `rebuild` is spelled out and a later verb can join it."""


def _repository(flag: Path | None) -> OutputRepo:
    path = resolve_repo_path(flag)
    if path is None:
        typer.echo(
            "the index is built from a repository's committed entries: give --output-repo "
            "or set EMENDRIX_OUTPUT_REPO.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        repo = OutputRepo.open(path)
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    if not (repo.path / ".git").exists():
        typer.echo(f"{repo.path} is not a repository emendrix has written to.", err=True)
        raise typer.Exit(code=2)
    return repo


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


@app.command("rebuild")
def rebuild(
    output_repo: Annotated[
        Path | None, typer.Option("--output-repo", help="The repository to index.")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print which files would change, write nothing.")
    ] = False,
) -> None:
    """Rebuild every index file from the committed payloads and commit what moved, once.

    Idempotent: over a repository whose index is current it writes nothing and commits nothing.
    """
    repo = _repository(output_repo)
    try:
        files = index_files(repo.path)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    moved = {path: text for path, text in files.items() if _read(repo.path / path) != text}
    if not moved:
        typer.echo(f"the index of {repo.path} is current; nothing to write.")
        return
    for path, text in moved.items():
        verb = "would write" if dry_run else "wrote"
        typer.echo(f"{verb} {path} ({len(text.encode('utf-8'))} bytes)")
        if not dry_run:
            (repo.path / path).write_text(text, encoding="utf-8")
    if dry_run:
        return
    try:
        git("add", "--", *moved, cwd=repo.path)
        if staged(repo.path):
            typer.echo(f"committed {commit(repo.path, INDEX_SUBJECT)[:12]}: {INDEX_SUBJECT}")
    except GitError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
