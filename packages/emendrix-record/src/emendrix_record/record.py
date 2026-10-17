"""The published record, read off disk into a reader's models, so no caller ever sees bytes.

Two inputs, both given: the directory of a changelogs repository, and optionally the
`api/v1/catalogue.json` a site build wrote. Every file is read when it is asked for and dropped
after: the repository is rewritten underneath a running reader every hour, and a copy held
across calls would answer from a record that has since moved on.

Paths come from the index and are resolved under the repository root; one that is absolute,
climbs with `..` or resolves outside the root through a link is refused. A payload's bytes are
hashed and compared with the `sha256` its index row states, and a mismatch is reported in the
result rather than hidden, because it means the volume is mid-write. Every failure is a value,
`Unavailable`, carrying a sentence a caller can repeat. The sentences speak of "this server"
because every reader of the record so far answers over the network.

Nothing here builds an address. A permalink is read out of the catalogue or reported
unavailable. The catalogue and the substance files beside it are read by `SiteFiles`
(`site_files.py`), which `Record` extends: they are the site build's files, not the record's.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Final

from pydantic import ValidationError

from emendrix_record.models import (
    ActIndex,
    ActRow,
    EventRow,
    ProvisionRow,
    Register,
    RootIndex,
)
from emendrix_record.payload import ChangeRecord, Payload
from emendrix_record.reads import (
    PERMALINK_UNAVAILABLE,
    ChangeRead,
    PayloadRead,
    SubstanceRead,
    Unavailable,
)
from emendrix_record.site_files import SUBSTANCES_FILE, SiteFiles, entry_key, inside, sha256_of

__all__ = [
    "INDEX_FILE",
    "PERMALINK_UNAVAILABLE",
    "REGISTER_FILE",
    "SUBSTANCES_FILE",
    "ChangeRead",
    "PayloadRead",
    "Record",
    "SubstanceRead",
    "Unavailable",
    "entry_key",
    "row_for",
]

INDEX_FILE: Final = "index.json"
"""The root index's file name, at the top of the changelogs repository."""

REGISTER_FILE: Final = "register.json"
"""An act's register, beside its act index, for an act whose tables are read as entries."""


def _unit(index: ActIndex, location: str) -> str | None:
    """The key the act index files `location` under: the shortest key it extends word by word."""
    words = location.split(" ")
    for size in range(1, len(words) + 1):
        candidate = " ".join(words[:size])
        if candidate in index.provisions:
            return candidate
    return None


def row_for(
    index: ActIndex, event: EventRow, changes: tuple[ChangeRecord, ...], position: int
) -> ProvisionRow | None:
    """The index row of the change at `position` in the payload.

    The index files one row per change under its top-level unit, in payload order, so the row
    is the n-th of the event's rows under that unit, where n counts the payload's changes
    filed under the same unit up to this one.
    """
    unit = _unit(index, changes[position].change.provision.location)
    if unit is None:
        return None
    ordinal = sum(
        1 for change in changes[:position] if _unit(index, change.change.provision.location) == unit
    )
    rows = [row for row in index.provisions[unit] if row.version == event.to_version]
    return rows[ordinal] if ordinal < len(rows) else None


class Record(SiteFiles):
    """The changelogs repository at `changelogs`, and the site catalogue at `catalogue`."""

    def __init__(self, changelogs: Path, catalogue: Path | None) -> None:
        super().__init__(catalogue)
        self._root = changelogs

    # --- files -----------------------------------------------------------------------------

    def _within(self, relative: str) -> Path | Unavailable:
        return inside(self._root, relative, "the changelogs repository")

    def _bytes(self, relative: str) -> bytes | Unavailable:
        path = self._within(relative)
        if isinstance(path, Unavailable):
            return path
        try:
            return path.read_bytes()
        except OSError:
            return Unavailable(
                reason=f"{relative} could not be read from the changelogs repository"
            )

    # --- the index -------------------------------------------------------------------------

    def root(self) -> RootIndex | Unavailable:
        """The root index, read now."""
        raw = self._bytes(INDEX_FILE)
        if isinstance(raw, Unavailable):
            return raw
        try:
            return RootIndex.model_validate_json(raw)
        except ValidationError:
            return Unavailable(reason=f"{INDEX_FILE} is not a change index this server can read")

    def act_row(self, act: str) -> ActRow | Unavailable:
        """The root index's row for `act`, named by its key or by `corpus/key`."""
        root = self.root()
        if isinstance(root, Unavailable):
            return root
        rows = [row for row in root.acts if act in (row.key, f"{row.corpus}/{row.key}")]
        if not rows:
            return Unavailable(reason=f"the record holds no act {act!r}")
        if len(rows) > 1:
            named = ", ".join(f"{row.corpus}/{row.key}" for row in rows)
            return Unavailable(reason=f"{act!r} names more than one act ({named}); give corpus/key")
        return rows[0]

    def act(self, act: str) -> ActIndex | Unavailable:
        """The act index of `act`, named by its key or by `corpus/key`, read now."""
        row = self.act_row(act)
        if isinstance(row, Unavailable):
            return row
        raw = self._bytes(row.index)
        if isinstance(raw, Unavailable):
            return raw
        try:
            return ActIndex.model_validate_json(raw)
        except ValidationError:
            return Unavailable(reason=f"{row.index} is not an act index this server can read")

    @staticmethod
    def event(index: ActIndex, version: str) -> EventRow | Unavailable:
        """The event of `index` that produced `version`, named by version or by entry key."""
        for event in index.events:
            if version in (event.to_version, entry_key(event)):
                return event
        return Unavailable(
            reason=f"the record holds no event of {index.corpus}/{index.key} producing {version!r}"
        )

    def register(self, corpus: str, key: str) -> Register | Unavailable:
        """The act's register, read now: every table entry of the newest version it holds.

        Only an act whose tables the corpus reads as entries has one, so its absence is said
        as that and never as "no entries".
        """
        row = self.act_row(f"{corpus}/{key}")
        if isinstance(row, Unavailable):
            return row
        path = str(PurePosixPath(row.index).with_name(REGISTER_FILE))
        raw = self._bytes(path)
        if isinstance(raw, Unavailable):
            return Unavailable(reason=f"the record holds no register for {row.corpus}/{row.key}")
        try:
            return Register.model_validate_json(raw)
        except ValidationError:
            return Unavailable(reason=f"{path} is not a register this server can read")

    # --- payloads --------------------------------------------------------------------------

    def payload(self, path: str, sha256: str) -> PayloadRead | Unavailable:
        """The payload at `path`, read now and hashed against the index's `sha256` for it."""
        raw = self._bytes(path)
        if isinstance(raw, Unavailable):
            return raw
        found = sha256_of(raw)
        try:
            payload = Payload.model_validate_json(raw)
        except ValidationError:
            return Unavailable(reason=f"{path} is not a changelog payload this server can read")
        return PayloadRead(
            path=path,
            sha256=found,
            indexed_sha256=sha256,
            matches_index=found == sha256,
            payload=payload,
        )

    def change(
        self, act: str, version: str, location: str, occurrence: int = 1
    ) -> ChangeRead | Unavailable:
        """The `occurrence`-th change at `location` (from 1) in the event producing `version`.

        Changes are counted over their own location in payload order, as the index counts
        them, so an index row's `occurrence` selects the change it describes.
        """
        index = self.act(act)
        if isinstance(index, Unavailable):
            return index
        event = self.event(index, version)
        if isinstance(event, Unavailable):
            return event
        read = self.payload(event.path, event.sha256)
        if isinstance(read, Unavailable):
            return read
        changes = read.payload.changes
        positions = [
            position
            for position, change in enumerate(changes)
            if change.change.provision.location == location
        ]
        if not 1 <= occurrence <= len(positions):
            return Unavailable(
                reason=f"the event producing {event.to_version} of {index.corpus}/{index.key} "
                f"holds {len(positions)} change(s) at {location!r}, so occurrence {occurrence} "
                f"names none"
            )
        position = positions[occurrence - 1]
        return ChangeRead(
            event=event,
            location=location,
            occurrence=occurrence,
            row=row_for(index, event, changes, position),
            sha256=read.sha256,
            matches_index=read.matches_index,
            change=changes[position],
        )
