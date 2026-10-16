"""The git half of the output repository: the two refusals, creating it, and one commit.

Split from `repo.py` when the register joined the files a write places. That module decides
which files an event writes and whether their bytes moved; this one decides whether a path may
be written in at all and turns what was staged into a commit. The behaviour is the one
`repo.py` documents, unchanged by the move.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from emendrix.output.changelog import MARKER, repo_readme
from emendrix.output.git import GitError, commit, git, init_repo, staged

__all__ = [
    "MARKER_FILE",
    "ForeignRepository",
    "NestedRepository",
    "commit_paths",
    "ensure_repository",
    "refuse_foreign",
]

MARKER_FILE: Final = ".emendrix-output"
"""Written and committed when emendrix creates the repository, and required ever after.

It is what distinguishes "the repository emendrix made for this" from "a repository", and
without that distinction the guard below would be half a guard: refusing a path *inside*
somebody's working tree while accepting the working tree itself.
"""


class NestedRepository(GitError):
    """The configured path lies inside an existing working tree, so emendrix refuses it."""


class ForeignRepository(GitError):
    """The configured path is already a git repository that emendrix did not create."""


def _enclosing_worktree(path: Path) -> Path | None:
    """The nearest *strict* ancestor of `path` that is a git working tree, if there is one."""
    return next((parent for parent in path.parents if (parent / ".git").exists()), None)


def refuse_foreign(resolved: Path) -> None:
    """Raise when `resolved` is inside a working tree, or is a repository emendrix did not make.

    Two refusals, because there are two ways to end up committing into a repository nobody
    asked emendrix to touch: a path *inside* one, and a path that *is* one.
    """
    enclosing = _enclosing_worktree(resolved)
    if enclosing is not None:
        raise NestedRepository(
            f"{resolved} is inside the git working tree at {enclosing}; the emendrix output "
            f"repository must be a repository of its own, so that a commit of one can never "
            f"pick up files of the other. Point --output-repo somewhere outside it."
        )
    if (resolved / ".git").exists() and not (resolved / MARKER_FILE).is_file():
        raise ForeignRepository(
            f"{resolved} is already a git repository and carries no {MARKER_FILE}, so it is "
            f"not one emendrix created; refusing to commit into somebody else's repository. "
            f"Point --output-repo at a new path, or add {MARKER_FILE} if this really is an "
            f"emendrix output repository."
        )


def ensure_repository(path: Path) -> bool:
    """Create the repository with its README and marker when absent. True when it was created."""
    created = init_repo(path)
    if created:
        (path / "README.md").write_text(repo_readme(), encoding="utf-8")
        (path / MARKER_FILE).write_text(_marker_text(), encoding="utf-8")
    return created


def commit_paths(path: Path, targets: list[str], subject: str, *, initialised: bool) -> str:
    """Stage `targets` and, on a fresh repository, its root files; commit; return the revision.

    Paths are given relative to the repository root and after `--`, so nothing outside it can
    be staged even if a path ever arrived containing something surprising. An empty string
    means nothing was staged and nothing was committed.
    """
    if initialised:
        targets = [*targets, "README.md", MARKER_FILE]
    git("add", "--", *targets, cwd=path)
    if not staged(path):
        return ""
    return commit(path, subject)


def _marker_text() -> str:
    return (
        f"emendrix output repository {MARKER}\n"
        "\n"
        "This file marks the repository as one emendrix created and may commit into. Without it\n"
        "emendrix refuses to write here, which is the point: a path naming somebody else's\n"
        "repository would otherwise be indistinguishable from this one, and a mis-scoped commit\n"
        "is the one mistake this tool must not be able to make.\n"
    )
