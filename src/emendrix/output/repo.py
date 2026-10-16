"""The output git repository: open-or-init, write an entry and the index, commit, never push.

The product claim of this project is that *your regulatory dependencies get the same review
workflow as your code dependencies*. That claim is cashed here and nowhere else: a run of the
loop ends as a commit in a repository somebody can diff, review in a pull request, and blame.

```
<repo>/.emendrix-output                              this repository is one emendrix created
<repo>/README.md
<repo>/index.json                                     one row per act
<repo>/eu/32017R0745/CHANGELOG.md                     newest entry first, rewritten in place
<repo>/eu/32017R0745/changes/02017R0745-20200424.json  the same event, structured
<repo>/eu/32017R0745/index.json                       every event and changed provision, no text
<repo>/eu/32008R1272/register.json                    the newest version's table entries, whole
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

The index rides the entry's commit, so every commit is self-consistent. Only the written act's
index is rebuilt from its payloads and every other act's is read as it stands, since rebuilding
them all per write would make a backfill quadratic; `emendrix index rebuild` repairs a stale one.
The register of an act whose tables are read as entries rides it too when the entry is the act's
newest, so a backfill writing history underneath leaves a newer register where it is.

The git half, the two refusals and the commit itself, is in `repo_git.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel, ConfigDict

from emendrix.core import ActId, VersionId
from emendrix.output.changelog import changelog_text
from emendrix.output.index import act_index, root_index
from emendrix.output.index import render as render_index
from emendrix.output.index_model import INDEX_FILE, ActIndex
from emendrix.output.json_out import ChangelogEntry, payload_for, slug
from emendrix.output.register import Register, register_path, render_register
from emendrix.output.repo_git import (
    MARKER_FILE,
    ForeignRepository,
    NestedRepository,
    commit_paths,
    ensure_repository,
    refuse_foreign,
)

__all__ = [
    "INDEX_SUBJECT",
    "MARKER_FILE",
    "ForeignRepository",
    "NestedRepository",
    "OutputRepo",
    "RegisterResult",
    "WriteResult",
]

INDEX_SUBJECT: Final = "index the repository"
"""The subject of a commit that moved the index and no entry."""


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


class RegisterResult(BaseModel):
    """What one `write_register` did: placed and committed, already current, or not the newest."""

    model_config = ConfigDict(frozen=True)

    act: str
    path: Path
    newest: bool = True
    unchanged: bool = False
    revision: str = ""
    message: str = ""


class OutputRepo:
    """One local git repository holding one directory per act. Opened, never pushed."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def open(cls, path: Path) -> Self:
        """Resolve, refuse any path emendrix may not write in (`refuse_foreign`), or create it."""
        resolved = path.expanduser().resolve()
        refuse_foreign(resolved)
        return cls(resolved)

    def act_dir(self, entry: ChangelogEntry) -> Path:
        return self.path / entry.act_dir

    def holds(self, act: ActId, version: VersionId) -> bool:
        """Whether the entry a transition into `version` would write is already here.

        The whole resume mechanism a batch job needs: the path is a pure function of the act and
        the version, so a run that lost its ledger still declines to pay twice. It answers about
        the *version*, not the pair, because two starting versions produce one file.
        """
        return (self.path / payload_for(act, version)).is_file()

    def holds_finished(self, act: ActId, version: VersionId) -> bool:
        """Whether the entry here is one a re-run would have nothing to add to.

        An entry written while the provider was refusing calls carries changes nobody asked the
        model about, and without this a backfill that ran out of credit would skip past the gap
        for ever. Unreadable or unexpected JSON answers `True`, the same as a plain `holds`: a
        file this cannot parse is a reason to look at it, never to spend on it every run.
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

        A document that does not validate is loud rather than skipped.
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

    def write(
        self,
        entry: ChangelogEntry,
        *,
        register: Register | None = None,
        message: str | None = None,
    ) -> WriteResult:
        """Write one amendment event and commit it. Idempotent: identical bytes → no commit.

        `register` is placed in the same commit when its version is the act's newest entry once
        this one is written, and left out otherwise. `message` replaces the emit subject
        `message_for` builds. A commit that repaired part of a committed entry is not an
        emission of it, and a subject that says otherwise is the one place a reader of
        `git log` would be misled.
        """
        initialised = ensure_repository(self.path)
        changelog = self.act_dir(entry) / "CHANGELOG.md"
        payload = self.act_dir(entry) / "changes" / f"{entry.key}.json"
        previous = _read(changelog)
        rendered = changelog_text(previous, entry)
        document = entry.to_json()
        current = not initialised and previous == rendered and _read(payload) == document
        if not current:
            payload.parent.mkdir(parents=True, exist_ok=True)
            changelog.write_text(rendered, encoding="utf-8")
            payload.write_text(document, encoding="utf-8")
        placed = register is not None and self._place(register) is True
        indexed = self._index(entry.act_dir)
        if current and not indexed and not placed:
            return WriteResult(
                act=str(entry.act), changelog=changelog, payload=payload, unchanged=True
            )
        if current and message is None:
            message = _registered(register) if placed and register is not None else INDEX_SUBJECT
        subject = self.message_for(entry) if message is None else message
        targets = [str(self.act_dir(entry).relative_to(self.path)), *indexed]
        revision = commit_paths(self.path, targets, subject, initialised=initialised)
        if not revision:
            return WriteResult(
                act=str(entry.act), changelog=changelog, payload=payload, unchanged=True
            )
        return WriteResult(
            act=str(entry.act),
            changelog=changelog,
            payload=payload,
            initialised=initialised,
            revision=revision,
            message=subject,
        )

    def write_register(self, register: Register, *, message: str | None = None) -> RegisterResult:
        """Place one act's register on its own and commit it, when it is of the newest entry.

        For a pass that brings a repository's registers up to date after its entries: one
        commit per act, never one per entry, because a register can run to megabytes.
        """
        path = self.path / register_path(_act_of(register))
        placed = self._place(register)
        if placed is None:
            return RegisterResult(act=register.key, path=path, newest=False, unchanged=True)
        subject = _registered(register) if message is None else message
        relative = path.relative_to(self.path).as_posix()
        revision = commit_paths(self.path, [relative], subject, initialised=False)
        if not revision:
            return RegisterResult(act=register.key, path=path, unchanged=True)
        return RegisterResult(act=register.key, path=path, revision=revision, message=subject)

    def _place(self, register: Register) -> bool | None:
        """Write the register when its version is the act's newest entry: True if bytes moved.

        `None` when it is not the newest, which leaves a newer register where it is. Newest is
        the greatest entry key, the order `changelog.py` sorts entries of one act by.
        """
        path = self.path / register_path(_act_of(register))
        changes = path.parent / "changes"
        keys = [item.stem for item in changes.glob("*.json")] if changes.is_dir() else []
        if not keys or max(keys) != slug(register.version):
            return None
        text = render_register(register)
        if _read(path) == text:
            return False
        path.write_text(text, encoding="utf-8")
        return True

    def _index(self, act_dir: str) -> tuple[str, ...]:
        """Rebuild `act_dir`'s index and the root's; return the paths whose bytes moved.

        Another act's is built from its payloads only when it has none: a repository that
        predates the index.
        """
        files: dict[str, str] = {}
        acts: list[ActIndex] = []
        for changes in sorted(self.path.glob("*/*/changes")):
            if not changes.is_dir() or not any(changes.glob("*.json")):
                continue
            name = changes.parent.relative_to(self.path).as_posix()
            stored = changes.parent / INDEX_FILE
            if name == act_dir or not stored.is_file():
                acts.append(act_index(self.path, name))
                files[f"{name}/{INDEX_FILE}"] = render_index(acts[-1])
            else:
                acts.append(ActIndex.model_validate_json(stored.read_bytes()))
        files[INDEX_FILE] = render_index(root_index(acts))
        moved = tuple(path for path, text in files.items() if _read(self.path / path) != text)
        for path in moved:
            (self.path / path).write_text(files[path], encoding="utf-8")
        return moved

    @staticmethod
    def message_for(entry: ChangelogEntry) -> str:
        """`32017R0745: 02017R0745-20170505 -> 02017R0745-20200424 (9 changes)`.

        The subject names the transition rather than the amending act, because no stage of the
        loop resolves an amending act's identifier: an event names the consolidation that
        appeared, not what caused it.
        """
        return (
            f"{entry.act.key}: {entry.from_version} -> {entry.to_version} "
            f"({len(entry.changes)} changes)"
        )


def _act_of(register: Register) -> ActId:
    return ActId(corpus=register.corpus, key=register.key)


def _registered(register: Register) -> str:
    """`32008R1272: register of 02008R1272-20250901 (4312 entries)`."""
    return f"{register.key}: register of {register.version} ({len(register.entries)} entries)"


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None
