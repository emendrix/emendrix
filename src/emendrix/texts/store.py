"""`TextStore`: the directory that keeps every stored version's verbatim text.

```
<store>/.emendrix-texts                           the marker: a directory emendrix created
<store>/<corpus>/<slug(key)>/<slug(version)>.jsonl.gz
<store>/<corpus>/<slug(key)>/states.json          versions the adapter answered with a state
```

A version file is immutable: a consolidated text is the same bytes forever, so a file that
exists is replaced only when the caller asks for it (`texts build --rebuild`). Every write goes
to a temporary file in the same directory and is moved into place, so a reader never sees half
a file. The store is not a repository and is never kept inside one: a path within any git
working tree is refused, which is what keeps it out of the changelogs repository and so out of
everything published from it.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from emendrix.core import ProvisionTree
from emendrix.output.json_out import slug
from emendrix.texts.codec import decode, encode, rebuild
from emendrix.texts.model import (
    MARKER_FILE,
    STATES_FILE,
    STORE_SCHEMA,
    VERSION_SUFFIX,
    StatesFile,
    StoredState,
    StoredVersionFile,
    UnreadableVersion,
)

__all__ = [
    "NestedInWorktree",
    "NotAStore",
    "ReadOnlyStore",
    "StoreRefusal",
    "TextStore",
    "inside_worktree",
]

_MARKER_TEXT = f"emendrix text store, layout {STORE_SCHEMA}. Never published; rebuilt on demand.\n"


class StoreRefusal(ValueError):
    """A path the store will not live at. The command line turns it into exit status 2."""


class NestedInWorktree(StoreRefusal):
    """The path is inside a git working tree, where a commit could pick the texts up."""


class NotAStore(StoreRefusal):
    """The path holds something emendrix did not create, or no store at all."""


class ReadOnlyStore(RuntimeError):
    """A write was asked of a store opened for reading."""


def inside_worktree(path: Path) -> Path | None:
    """The nearest of `path` and its ancestors holding a `.git` entry, if any."""
    resolved = path.expanduser().resolve()
    return next((each for each in (resolved, *resolved.parents) if (each / ".git").exists()), None)


def _replace(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        # `mkstemp` creates the file private to its owner; a store file is read like any other.
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


class TextStore:
    """One store directory, opened for writing (`create_or_open`) or reading (`open`)."""

    def __init__(self, root: Path, *, writable: bool) -> None:
        self.root = root
        self.writable = writable

    # ------------------------------------------------------------ opening

    @classmethod
    def create_or_open(cls, path: Path, *, dry_run: bool = False) -> TextStore:
        """The store at `path`, created if absent. Refuses a nested or a foreign directory.

        With `dry_run` every refusal still applies, nothing is created, and the store comes
        back read-only, so a dry run says what a real one would refuse.
        """
        root = path.expanduser().resolve()
        enclosing = inside_worktree(root)
        if enclosing is not None:
            raise NestedInWorktree(
                f"{root} is inside the git working tree at {enclosing}; the text store is never "
                f"kept in a repository, so that no commit can publish it. Point it elsewhere."
            )
        if root.exists() and not root.is_dir():
            raise NotAStore(f"{root} exists and is not a directory.")
        marker = root / MARKER_FILE
        if root.is_dir() and not marker.is_file() and any(root.iterdir()):
            raise NotAStore(
                f"{root} is not empty and carries no {MARKER_FILE}, so emendrix did not create "
                f"it; refusing to write texts among somebody else's files."
            )
        if dry_run:
            return cls(root, writable=False)
        root.mkdir(parents=True, exist_ok=True)
        if not marker.is_file():
            marker.write_text(_MARKER_TEXT, encoding="utf-8")
        return cls(root, writable=True)

    @classmethod
    def open(cls, path: Path) -> TextStore:
        """An existing store, for reading only."""
        root = path.expanduser().resolve()
        if not (root / MARKER_FILE).is_file():
            raise NotAStore(f"{root} is not a text store: it carries no {MARKER_FILE}.")
        return cls(root, writable=False)

    # ------------------------------------------------------------ paths

    def act_dir(self, corpus: str, key: str) -> Path:
        return self.root / slug(corpus) / slug(key)

    def version_path(self, corpus: str, key: str, version: str) -> Path:
        return self.act_dir(corpus, key) / f"{slug(version)}{VERSION_SUFFIX}"

    # ------------------------------------------------------------ reading

    def has(self, corpus: str, key: str, version: str) -> bool:
        """Whether a file exists for this version. A damaged one still counts as present."""
        return self.version_path(corpus, key, version).is_file()

    def versions(self, corpus: str, key: str) -> tuple[str, ...]:
        """Every stored version of one act, as named on disk, sorted as strings."""
        directory = self.act_dir(corpus, key)
        if not directory.is_dir():
            return ()
        names = (
            entry.name.removesuffix(VERSION_SUFFIX)
            for entry in directory.iterdir()
            if entry.is_file() and entry.name.endswith(VERSION_SUFFIX)
        )
        return tuple(sorted(names))

    def acts(self) -> tuple[tuple[str, str], ...]:
        """Every `(corpus, key)` the store holds a directory for, sorted."""
        found: list[tuple[str, str]] = []
        for corpus in self.root.iterdir():
            if not corpus.is_dir() or corpus.name.startswith("."):
                continue
            found.extend(
                (corpus.name, act.name)
                for act in corpus.iterdir()
                if act.is_dir() and not act.name.startswith(".")
            )
        return tuple(sorted(found))

    def read(
        self, corpus: str, key: str, version: str
    ) -> StoredVersionFile | UnreadableVersion | None:
        """Header plus nodes; `None` when no file exists; unreadable when one is damaged."""
        path = self.version_path(corpus, key, version)
        if not path.is_file():
            return None
        try:
            data = path.read_bytes()
        except OSError as error:
            return UnreadableVersion(version=version, detail=f"cannot be read: {error}")
        return decode(data, version)

    def tree(self, corpus: str, key: str, version: str) -> ProvisionTree | UnreadableVersion | None:
        """The stored version as a `ProvisionTree`, versioned as the adapter served it."""
        stored = self.read(corpus, key, version)
        if stored is None or isinstance(stored, UnreadableVersion):
            return stored
        return rebuild(stored)

    def states(self, corpus: str, key: str) -> StatesFile | UnreadableVersion:
        """The act's recorded states; an empty file when none were ever recorded."""
        path = self.act_dir(corpus, key) / STATES_FILE
        if not path.is_file():
            return StatesFile(store_schema=STORE_SCHEMA)
        try:
            return StatesFile.model_validate_json(path.read_bytes())
        except (OSError, ValueError) as error:
            return UnreadableVersion(
                version=STATES_FILE, detail=f"cannot be read or validated: {error}"
            )

    # ------------------------------------------------------------ writing

    def _require_writable(self) -> None:
        if not self.writable:
            raise ReadOnlyStore(f"the text store at {self.root} was opened for reading")

    def write(self, tree: ProvisionTree, *, version: str) -> Path:
        """File `tree` under the version that was asked for, never under the one served.

        The adapter may serve an earlier text for a version it lacks; naming the file by what
        was served would let two requests overwrite each other.
        """
        self._require_writable()
        path = self.version_path(tree.act.corpus, tree.act.key, version)
        _replace(path, encode(tree, version))
        return path

    def record_states(self, corpus: str, key: str, states: Iterable[StoredState]) -> bool:
        """Merge `states` into `states.json` by version, dropping any version now stored.

        A state is an answer about one moment and a later run may get a text instead, so a
        stored version's old state goes. The file is rewritten only when its bytes change, and
        the return value says whether they did.
        """
        self._require_writable()
        current = self.states(corpus, key)
        merged = (
            {}
            if isinstance(current, UnreadableVersion)
            else {state.version: state for state in current.states}
        )
        merged.update((state.version, state) for state in states)
        kept = tuple(
            merged[version] for version in sorted(merged) if not self.has(corpus, key, version)
        )
        path = self.act_dir(corpus, key) / STATES_FILE
        if not kept and not path.is_file():
            return False
        data = StatesFile(store_schema=STORE_SCHEMA, states=kept).model_dump_json(indent=2) + "\n"
        encoded = data.encode("utf-8")
        if path.is_file() and path.read_bytes() == encoded:
            return False
        _replace(path, encoded)
        return True
