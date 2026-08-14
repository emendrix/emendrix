"""Subprocess git, scoped so it can only ever touch the repository it was pointed at.

The tool commits via subprocess git, and the embarrassing failure mode is obvious once
stated: a mis-scoped `git add` committing emendrix's own source into the output repository, or
the changelog into emendrix. Three things make that impossible here rather than unlikely:

- **Explicit `cwd`, always.** Nothing in this module runs git in the process's working
  directory.
- **A scrubbed environment.** `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` are removed from
  the inherited environment before every call: a parent process (a git hook, an IDE, a CI
  runner) exporting one of those would otherwise silently redirect every command here.
- **A ceiling.** `GIT_CEILING_DIRECTORIES` is set to the repository's parent, so a discovery
  walk cannot climb out of it. Combined with `repo.py`'s refusal to operate inside an existing
  working tree, git can only ever see the repository emendrix created.

The author identity is set per call (`emendrix <emendrix@localhost>`) rather than written into
the repository's config: the repository is the user's, and a tool that edits `user.email` in
somebody's repo has overstepped.

Failure here is an ordinary error and is raised. That is not a breach of the first-class-states
rule: `ConsolidationPending`, `EnglishUnavailable`, `Disputed` and `ApplicabilityUnknown` are
answers the *corpus* gave, and "git is not installed" is not an answer about legislation.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Final

__all__ = ["AUTHOR_EMAIL", "AUTHOR_NAME", "GitError", "commit", "git", "init_repo", "staged"]

AUTHOR_NAME: Final = "emendrix"
AUTHOR_EMAIL: Final = "emendrix@localhost"

_SCRUBBED: Final = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY")


class GitError(RuntimeError):
    """git could not do what it was asked. Carries the command and everything it printed."""


def _environment(cwd: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key not in _SCRUBBED}
    environment["GIT_CEILING_DIRECTORIES"] = str(cwd.parent)
    environment["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    environment["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    environment["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    environment["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL
    return environment


def git(*arguments: str, cwd: Path) -> str:
    """Run one git command in `cwd` and return its stdout. Raises `GitError` on any failure."""
    try:
        # Fixed argv, no shell, explicit cwd, scrubbed environment.
        finished = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            env=_environment(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as error:
        raise GitError(
            "git is not on PATH; the changelog output repository is a git repository "
            "and emendrix commits into it with the git command line"
        ) from error
    except subprocess.CalledProcessError as error:
        printed = (error.stderr or error.stdout or "").strip()
        raise GitError(f"git {' '.join(arguments)} failed in {cwd}: {printed}") from error
    return finished.stdout


def init_repo(path: Path) -> bool:
    """Make `path` a git repository if it is not one already. True when it had to be created."""
    if (path / ".git").exists():
        return False
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-b", "main", cwd=path)
    return True


def staged(path: Path) -> tuple[str, ...]:
    """The paths currently staged for commit, so an empty commit is never attempted."""
    listed = git("diff", "--cached", "--name-only", cwd=path)
    return tuple(line for line in listed.splitlines() if line)


def commit(path: Path, message: str) -> str:
    """Commit whatever is staged and return the new revision.

    The commit's timestamp is git's own and is read from the system clock. That is metadata
    about when a commit happened rather than part of any rendered artifact, and the rule the
    project holds is that no *output* depends on a clock. The files being committed here were
    rendered without one, which is why re-running an event produces no diff.
    """
    git("commit", "--message", message, cwd=path)
    return git("rev-parse", "HEAD", cwd=path).strip()
