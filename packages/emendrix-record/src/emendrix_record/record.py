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
unavailable.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

from pydantic import ValidationError

from emendrix_record.models import (
    ActIndex,
    ActRow,
    Catalogue,
    CatalogueAct,
    EventRow,
    ProvisionRow,
    RootIndex,
)
from emendrix_record.payload import ChangeRecord, Payload
from emendrix_record.reads import PERMALINK_UNAVAILABLE, ChangeRead, PayloadRead, Unavailable

__all__ = [
    "INDEX_FILE",
    "PERMALINK_UNAVAILABLE",
    "ChangeRead",
    "PayloadRead",
    "Record",
    "Unavailable",
    "entry_key",
    "row_for",
]

INDEX_FILE: Final = "index.json"
"""The root index's file name, at the top of the changelogs repository."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def entry_key(event: EventRow) -> str:
    """The key the catalogue files an event under: its payload's file name, without `.json`."""
    return PurePosixPath(event.path).stem


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


class Record:
    """The changelogs repository at `changelogs`, and the site catalogue at `catalogue`."""

    def __init__(self, changelogs: Path, catalogue: Path | None) -> None:
        self._root = changelogs
        self._catalogue = catalogue

    # --- files -----------------------------------------------------------------------------

    def _within(self, relative: str) -> Path | Unavailable:
        refused = Unavailable(
            reason=f"refused the path {relative!r}: every path must stay inside the changelogs "
            f"repository"
        )
        pure = PurePosixPath(relative)
        if (
            not relative
            or pure.is_absolute()
            or "\\" in relative
            or PureWindowsPath(relative).drive
            or ".." in pure.parts
            or "\x00" in relative
        ):
            return refused
        root = self._root.resolve()
        target = (root / pure).resolve()
        return target if target.is_relative_to(root) else refused

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

    # --- payloads --------------------------------------------------------------------------

    def payload(self, path: str, sha256: str) -> PayloadRead | Unavailable:
        """The payload at `path`, read now and hashed against the index's `sha256` for it."""
        raw = self._bytes(path)
        if isinstance(raw, Unavailable):
            return raw
        found = _sha256(raw)
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

    # --- the catalogue ---------------------------------------------------------------------

    def catalogue(self) -> Catalogue | Unavailable:
        """The site catalogue, read now; unavailable when this server was given none."""
        if self._catalogue is None:
            return Unavailable(reason=PERMALINK_UNAVAILABLE)
        try:
            return Catalogue.model_validate_json(self._catalogue.read_bytes())
        except (OSError, ValidationError):
            return Unavailable(
                reason="permalink unavailable: the site catalogue this server was given could "
                "not be read"
            )

    def listing(self, corpus: str, key: str) -> CatalogueAct | Unavailable:
        """The catalogue's row for one act: its labels, aliases, domain and page addresses."""
        catalogue = self.catalogue()
        if isinstance(catalogue, Unavailable):
            return catalogue
        for act in catalogue.acts:
            if (act.corpus, act.key) == (corpus, key):
                return act
        return Unavailable(reason=f"permalink unavailable: the catalogue lists no {corpus}/{key}")

    def act_url(self, index: ActIndex) -> str | Unavailable:
        """The act's page, as the catalogue gives it."""
        listing = self.listing(index.corpus, index.key)
        return listing if isinstance(listing, Unavailable) else listing.url

    def event_url(self, index: ActIndex, event: EventRow) -> str | Unavailable:
        """The event's page, as the catalogue gives it."""
        listing = self.listing(index.corpus, index.key)
        if isinstance(listing, Unavailable):
            return listing
        url = listing.events.get(entry_key(event))
        if url is None:
            return Unavailable(
                reason=f"permalink unavailable: the catalogue lists no page for {event.to_version}"
            )
        return url

    def provision_url(self, index: ActIndex, location: str) -> str | Unavailable:
        """The provision's page, as the catalogue gives it, for a top-level location."""
        listing = self.listing(index.corpus, index.key)
        if isinstance(listing, Unavailable):
            return listing
        url = listing.provisions.get(location)
        if url is None:
            return Unavailable(
                reason=f"permalink unavailable: the catalogue lists no page for {location}"
            )
        return url
