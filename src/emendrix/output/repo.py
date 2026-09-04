"""The output git repository: open-or-init, write two files, commit, never push.

The product claim of this project is that *your regulatory dependencies get the same review
workflow as your code dependencies*. That claim is cashed here and nowhere else: a run of the
loop ends as a commit in a repository somebody can diff, review in a pull request, and blame.

```
<repo>/.emendrix-output                              this repository is one emendrix created
<repo>/README.md
<repo>/eu/32017R0745/CHANGELOG.md                     newest entry first, rewritten in place
<repo>/eu/32017R0745/changes/02017R0745-20200424.json  the same event, structured
```

Three policies, each of which is a decision rather than an implementation detail:

**The repository is the user's.** emendrix creates it if it is absent, commits into it, and
*never pushes*. Where it lives, who it belongs to and where it is mirrored are not this tool's
business.

**It must be a repository emendrix made.** Two refusals enforce that, and both are needed. A
path *inside* an existing working tree is refused, which covers an output path inside the
emendrix checkout and every other case of that shape without this module having to know what
"the project repository" is. A path that *is* an existing repository without emendrix's own
`MARKER_FILE` in it is refused too, and that is not redundant: the first rule looks only at
strict ancestors, because after the first write the output repository legitimately has a `.git`
of its own.

**Re-emitting an event is a no-op.** The rendered bytes are compared with what is already on
disk before anything is written, and nothing is committed when nothing was staged. A cron
entry that runs this hourly produces one commit per amendment, not one per hour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel, ConfigDict

from emendrix.core import ActId, VersionId
from emendrix.output.changelog import MARKER, changelog_text, repo_readme
from emendrix.output.git import GitError, commit, git, init_repo, staged
from emendrix.output.json_out import ChangelogEntry, payload_for

__all__ = [
    "MARKER_FILE",
    "ForeignRepository",
    "NestedRepository",
    "OutputRepo",
    "WriteResult",
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


class WriteResult(BaseModel):
    """What one `write` did — enough for the CLI to say it in one line, and for a test to check."""

    model_config = ConfigDict(frozen=True)

    act: str
    changelog: Path
    payload: Path
    initialised: bool = False
    unchanged: bool = False
    revision: str = ""
    message: str = ""

    @property
    def committed(self) -> bool:
        return bool(self.revision)


def _enclosing_worktree(path: Path) -> Path | None:
    """The nearest *strict* ancestor of `path` that is a git working tree, if there is one."""
    return next((parent for parent in path.parents if (parent / ".git").exists()), None)


class OutputRepo:
    """One local git repository holding one directory per act. Opened, never pushed."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def open(cls, path: Path) -> Self:
        """Resolve, refuse any path emendrix may not write in, and create it if it is absent.

        Two refusals, because there are two ways to end up committing into a repository nobody
        asked emendrix to touch: a path *inside* one, and a path that *is* one.
        """
        resolved = path.expanduser().resolve()
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
        return cls(resolved)

    def act_dir(self, entry: ChangelogEntry) -> Path:
        return self.path / entry.act_dir

    def holds(self, act: ActId, version: VersionId) -> bool:
        """Whether the entry a transition into `version` would write is already here.

        This is the whole resume mechanism a batch job needs, and it needs no state of its own:
        the path is a pure function of the act and the version it produced, so a run that lost
        its ledger, or never had one because the container is new, still declines to pay a
        second time for work that is on disk. It answers about the *version*, not the pair, and
        that is deliberate: two different starting versions produce one file, and re-running the
        other pair would overwrite a committed entry with a differently-based one rather than
        add anything.
        """
        return (self.path / payload_for(act, version)).is_file()

    def holds_finished(self, act: ActId, version: VersionId) -> bool:
        """Whether the entry here is one a re-run would have nothing to add to.

        `holds` asks whether the file exists, which is the right question for everything except
        one case: an entry written while the provider was refusing calls carries changes nobody
        ever asked the model about. The file's existence is the whole resume record, so without
        this an installation that ran out of credit mid-backfill would publish the gap once and
        then skip past it for ever.

        Unreadable or unexpected JSON answers `True`, the same as a plain `holds`. A file this
        cannot parse is a reason to leave an entry alone and look at it, never a reason to spend
        on rewriting it on every run.
        """
        path = self.path / payload_for(act, version)
        if not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            changes = payload["changes"]
        except (OSError, ValueError, KeyError, TypeError):
            return True
        return not any(
            isinstance(change, dict) and change.get("unexplained_kind") == "provider_unavailable"
            for change in changes
        )

    def entry_for(self, act: ActId, version: VersionId | str) -> ChangelogEntry | None:
        """The committed entry for one transition, validated, or None when there is none.

        `holds` answers whether a file is here and `holds_finished` reads one field out of it by
        hand. A caller that means to rebuild an entry needs the document itself, and needs a
        document that does not validate to be loud rather than skipped.
        """
        path = self.path / payload_for(act, version)
        if not path.is_file():
            return None
        try:
            return ChangelogEntry.model_validate_json(path.read_bytes())
        except ValueError as error:
            raise ValueError(f"{path} is not a changelog document emendrix wrote: {error}") from (
                error
            )

    def write(self, entry: ChangelogEntry, *, message: str | None = None) -> WriteResult:
        """Write one amendment event and commit it. Idempotent: identical bytes → no commit.

        `message` replaces the emit subject `message_for` builds. A commit that repaired part of
        a committed entry is not an emission of it, and a subject that says otherwise is the one
        place a reader of `git log` would be misled.
        """
        initialised = self._ensure_repository()
        changelog = self.act_dir(entry) / "CHANGELOG.md"
        payload = self.act_dir(entry) / "changes" / f"{entry.key}.json"
        previous = _read(changelog)
        rendered = changelog_text(previous, entry)
        document = entry.to_json()
        if not initialised and previous == rendered and _read(payload) == document:
            return WriteResult(
                act=str(entry.act), changelog=changelog, payload=payload, unchanged=True
            )
        payload.parent.mkdir(parents=True, exist_ok=True)
        changelog.write_text(rendered, encoding="utf-8")
        payload.write_text(document, encoding="utf-8")
        return self._commit(entry, changelog, payload, initialised=initialised, message=message)

    # ------------------------------------------------------------------ the git half

    def _ensure_repository(self) -> bool:
        created = init_repo(self.path)
        if created:
            (self.path / "README.md").write_text(repo_readme(), encoding="utf-8")
            (self.path / MARKER_FILE).write_text(_marker_text(), encoding="utf-8")
        return created

    def _commit(
        self,
        entry: ChangelogEntry,
        changelog: Path,
        payload: Path,
        *,
        initialised: bool,
        message: str | None = None,
    ) -> WriteResult:
        """Stage exactly this act's directory (plus, on a fresh repo, its two root files).

        Paths are given relative to the repository root and after `--`, so nothing outside it
        can be staged even if a path ever arrived containing something surprising.
        """
        targets = [str(self.act_dir(entry).relative_to(self.path))]
        if initialised:
            targets.extend(("README.md", MARKER_FILE))
        git("add", "--", *targets, cwd=self.path)
        subject = self.message_for(entry) if message is None else message
        if not staged(self.path):
            return WriteResult(
                act=str(entry.act), changelog=changelog, payload=payload, unchanged=True
            )
        return WriteResult(
            act=str(entry.act),
            changelog=changelog,
            payload=payload,
            initialised=initialised,
            revision=commit(self.path, subject),
            message=subject,
        )

    @staticmethod
    def message_for(entry: ChangelogEntry) -> str:
        """`32017R0745: 02017R0745-20170505 -> 02017R0745-20200424 (9 changes)`.

        The subject names the transition rather than the amending act, because no stage of the
        loop resolves an amending act's identifier: an event names the consolidation that
        appeared, not what caused it. The transition is also what the entry is about and what a
        reader would search for.
        """
        return (
            f"{entry.act.key}: {entry.from_version} -> {entry.to_version} "
            f"({len(entry.changes)} changes)"
        )


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _marker_text() -> str:
    return (
        f"emendrix output repository {MARKER}\n"
        "\n"
        "This file marks the repository as one emendrix created and may commit into. Without it\n"
        "emendrix refuses to write here, which is the point: a path naming somebody else's\n"
        "repository would otherwise be indistinguishable from this one, and a mis-scoped commit\n"
        "is the one mistake this tool must not be able to make.\n"
    )
