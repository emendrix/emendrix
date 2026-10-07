"""The directory `--comparison-cache` names: one file per stored comparison, read and written.

The directory is tool-owned and disposable. Every file in it is an answer this tool computed and
can compute again, so deleting the directory costs one slow build and nothing else, and nothing
should be put in it by hand. It should not be shared with the HTTP response cache's directory
either, so that neither tool ever iterates the other's files.

An entry lives at `<dir>/<key[:2]>/<key>.json`, written with sorted keys, compact separators and
a trailing newline, so one comparison is always the same bytes. A write goes to a temporary file
of its own in the same directory and is renamed into place, which makes two builders writing one
key at once safe: each rename is atomic, both write identical bytes, and the worst a race costs
is the comparison being computed twice.

Nothing here may fail a build. An entry that is missing, unreadable, truncated or of another
schema reads as absent and is computed again, which is the tolerance `polled.read_polled`
applies to the poller's state file. A directory that cannot be written raises `StoreUnwritable`
once, so the command line can say so and carry on with the site it has already got.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emendrix.site_.comparisons import Stored

__all__ = ["Read", "StoreUnwritable", "read_stored", "write_stored"]


class StoreUnwritable(Exception):
    """The comparison directory could not be written; the build goes on without saving."""


def _path(directory: Path, key: str) -> Path:
    return directory / key[:2] / f"{key}.json"


class Read(BaseModel):
    """What a read found: the entries that parsed, and the keys whose file was there but not."""

    model_config = ConfigDict(frozen=True)

    found: dict[str, Stored] = Field(description="Every requested key whose entry parsed.")
    unreadable: tuple[str, ...] = Field(
        description="Requested keys with a file that could not be read or parsed, in order."
    )


def read_stored(directory: Path, keys: Iterable[str]) -> Read:
    """The stored entries for these keys that could be read; any other key is simply absent.

    A key with no file is absent and nothing more. A key whose file is there and cannot be used
    is absent too, and is also named in `unreadable`, so a build can count it as rejected.
    """
    found: dict[str, Stored] = {}
    unreadable: list[str] = []
    for key in keys:
        try:
            found[key] = Stored.model_validate_json(_path(directory, key).read_bytes())
        except (FileNotFoundError, NotADirectoryError):
            continue
        except (OSError, ValueError):
            unreadable.append(key)
    return Read(found=found, unreadable=tuple(unreadable))


def _encode(stored: Stored) -> bytes:
    payload = stored.model_dump(mode="json", by_alias=True)
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_stored(directory: Path, entries: Mapping[str, Stored]) -> int:
    """Write each entry atomically under its key and return how many were written.

    Stops at the first failure and raises `StoreUnwritable`, leaving no temporary file behind.
    """
    written = 0
    for key in sorted(entries):
        target = _path(directory, key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(
                dir=target.parent, prefix=f".{key}.", suffix=".tmp"
            )
        except OSError as error:
            raise StoreUnwritable(f"{directory}: {error}") from error
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(_encode(entries[key]))
            os.replace(temporary, target)
        except BaseException as error:
            Path(temporary).unlink(missing_ok=True)
            if isinstance(error, OSError):
                raise StoreUnwritable(f"{directory}: {error}") from error
            raise
        written += 1
    return written
