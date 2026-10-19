"""`site build --prune`: delete what a build did not write, and nothing a person placed.

`write_site` never deletes, so without this a page the build stops producing stays served for
as long as the directory lives. Pruning is opt-in because `out` belongs to the operator: a
self-hoster's directory may hold files no build of this tool ever wrote.

What is never pruned, whatever this build wrote:

- a file or directory whose name starts with a dot, at any depth (`.well-known/`, `.htaccess`);
- a search console's verification file at the root, `google<token>.html` or `BingSiteAuth.xml`;
- a stylesheet, script or font at the root under any name this build's asset would take, its
  digest aside (`style.css`, `style.<8 hex>.css`, `search.<8 hex>.js`, `sans-400.<8 hex>.woff2`),
  because a page the edge still holds may link the previous build's asset by its old digest;
- a symbolic link, or anything that is not a regular file. Links are never followed, so nothing
  outside `out` is ever reached, and every path is checked to resolve inside `out` before it is
  removed.

`stale` is the decision and touches no disk; `listing` and `prune` are the side effects, and
`say_pruned` is what `site build` says about them on stderr.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path, PurePath, PurePosixPath
from typing import Final

import typer
from pydantic import BaseModel, ConfigDict

from emendrix.site_.digest import DIGEST_LENGTH, FONTS
from emendrix.site_.markup import count

__all__ = ["PRUNE", "PRUNE_DRY_RUN", "Pruned", "kept", "listing", "prune", "say_pruned", "stale"]

PRUNE: Final = typer.Option(
    "--prune",
    help="After writing, delete every file under --out this build did not write. Never deleted: "
    "dotfiles and dot-directories, google*.html and BingSiteAuth.xml at the root, and earlier "
    "style, search and font files at the root, which a cached page may still link.",
)

PRUNE_DRY_RUN: Final = typer.Option(
    "--prune-dry-run",
    help="Write the site, then list on stderr what --prune would delete, deleting nothing.",
)

_ASSET_NAMES: Final = ("style.css", "search.js", *sorted(FONTS))
"""The unfingerprinted names `fingerprint` and `digest` derive every generated asset name from."""


def _asset_pattern(name: str) -> str:
    stem, _, suffix = name.rpartition(".")
    return rf"{re.escape(stem)}(?:\.[0-9a-f]{{{DIGEST_LENGTH}}})?\.{re.escape(suffix)}"


_KEPT_AT_ROOT: Final = re.compile(
    "|".join(
        (r"google[0-9A-Za-z]+\.html", r"BingSiteAuth\.xml", *map(_asset_pattern, _ASSET_NAMES))
    )
)


class Pruned(BaseModel):
    """What a prune removed, or in a dry run would remove, relative to `out` and sorted."""

    model_config = ConfigDict(frozen=True)

    files: tuple[PurePosixPath, ...]
    directories: tuple[PurePosixPath, ...]


def kept(path: PurePosixPath) -> bool:
    """True for a path no prune may delete, written by this build or not."""
    if any(part.startswith(".") for part in path.parts):
        return True
    return len(path.parts) == 1 and _KEPT_AT_ROOT.fullmatch(path.name) is not None


def stale(
    present: Iterable[PurePosixPath], written: Iterable[PurePosixPath]
) -> tuple[PurePosixPath, ...]:
    """The files of `present` this build did not write and no keep rule covers, sorted."""
    # Compared case-folded: on a case-insensitive disk a write keeps the name already there.
    wrote = {str(path).casefold() for path in written}
    return tuple(sorted(p for p in set(present) if str(p).casefold() not in wrote and not kept(p)))


def listing(out: Path) -> tuple[PurePosixPath, ...]:
    """Every regular file under `out`, relative to it. Links are neither listed nor followed."""
    found: list[PurePosixPath] = []
    for directory, subdirectories, names in os.walk(out, followlinks=False):
        here = Path(directory)
        subdirectories[:] = [d for d in subdirectories if not (here / d).is_symlink()]
        for name in names:
            path = here / name
            if not path.is_symlink() and path.is_file():
                found.append(PurePosixPath(path.relative_to(out).as_posix()))
    return tuple(sorted(found))


def _inside(root: Path, path: Path) -> bool:
    return path.resolve().is_relative_to(root)


def prune(out: Path, written: Iterable[PurePath], *, dry_run: bool) -> Pruned:
    """Delete the stale files under `out`, then the directories that left empty, never `out`.

    Only directories that held a deleted file are considered, so an empty directory a person
    made is left alone. In a dry run nothing is touched and no directory is reported, since
    which would empty depends on deletions that did not happen.
    """
    root = out.resolve()
    doomed = stale(listing(out), (PurePosixPath(path.as_posix()) for path in written))
    if dry_run:
        return Pruned(files=doomed, directories=())
    for relative in doomed:
        path = out / relative
        if not _inside(root, path.parent) or path.is_symlink():
            raise RuntimeError(f"refusing to delete {path}: it does not resolve inside {out}")
    for relative in doomed:
        (out / relative).unlink()
    candidates = {parent for relative in doomed for parent in relative.parents if parent.parts}
    removed: list[PurePosixPath] = []
    # Deepest first, so a directory is looked at only after every one beneath it.
    for relative in sorted(candidates, key=lambda p: (-len(p.parts), p)):
        path = out / relative
        if path.is_symlink() or not path.is_dir() or not _inside(root, path):
            continue
        if not any(path.iterdir()):
            path.rmdir()
            removed.append(relative)
    return Pruned(files=doomed, directories=tuple(sorted(removed)))


def say_pruned(pruned: Pruned, *, dry_run: bool) -> None:
    """One summary line on stderr; in a dry run, every path that would go, one per line."""
    if dry_run:
        typer.echo(
            f"prune (dry run): {count(len(pruned.files), 'file')} would be deleted", err=True
        )
        for path in pruned.files:
            typer.echo(f"  {path}", err=True)
        return
    emptied = len(pruned.directories)
    noun = "directory" if emptied == 1 else "directories"
    typer.echo(f"pruned: {count(len(pruned.files), 'file')}, {emptied} empty {noun}", err=True)
