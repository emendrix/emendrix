"""A twin map into the changelog repository: written only when its bytes move, then committed.

The map lives at the repository root under `twins/`, beside the per-act directories, so no
index, register or page glob that reads `<corpus>/<act>/...` ever meets it. The repository is
opened through `OutputRepo.open`, which refuses a path inside another working tree and a
repository emendrix did not create; a path that is not a repository yet is refused here too,
because creating the changelog repository is the loop's job and not this command's.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId
from emendrix.output.repo import OutputRepo
from emendrix.output.repo_git import commit_paths
from emendrix.twins.build import render
from emendrix.twins.model import TwinMap, twins_path

__all__ = [
    "NotARepository",
    "TwinWrite",
    "open_repository",
    "path_for",
    "subject_for",
    "write_twin_map",
]


class NotARepository(ValueError):
    """The output path holds no git repository yet, and this command never creates one."""


class TwinWrite(BaseModel):
    """What one write did: the path, and the commit it made, or that the bytes were current."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description="The map's path relative to the repository root.")
    revision: str | None = Field(default=None, description="The commit made, if one was.")
    unchanged: bool = Field(description="True when the file already held these bytes.")


def subject_for(document: TwinMap) -> str:
    """`twins: 32017R0745 and 32017R0746 at 02017R0745-20250110 and 02017R0746-20250110`."""
    a, b = document.a, document.b
    return f"twins: {a.key} and {b.key} at {a.version} and {b.version}"


def path_for(document: TwinMap) -> str:
    return twins_path(
        ActId(corpus=document.a.corpus, key=document.a.key),
        ActId(corpus=document.b.corpus, key=document.b.key),
    )


def open_repository(path: Path) -> OutputRepo:
    """The changelog repository at `path`, refused unless emendrix already created it there."""
    repo = OutputRepo.open(path)
    if not (repo.path / ".git").exists():
        raise NotARepository(
            f"{repo.path} is not a git repository yet; the changelog repository is created by "
            "the loop's first write, and a twin map is committed only into an existing one."
        )
    return repo


def write_twin_map(repo: OutputRepo, document: TwinMap, *, dry_run: bool = False) -> TwinWrite:
    """Place the map and commit just that path. Identical bytes: nothing written or committed.

    With `dry_run` nothing is written and `unchanged` still says whether a write would move
    the file.
    """
    relative = path_for(document)
    target = repo.path / relative
    text = render(document)
    current = target.is_file() and target.read_text(encoding="utf-8") == text
    if current or dry_run:
        return TwinWrite(path=relative, unchanged=current)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    revision = commit_paths(repo.path, [relative], subject_for(document), initialised=False)
    return TwinWrite(path=relative, revision=revision or None, unchanged=not revision)
