"""The files a site build wrote beside the record: its catalogue and its substance files.

`Record` reads both halves; this one holds the half that lives in the site's `api/v1/`
directory rather than in the changelogs repository, because a server can run without it and
every read here then says so. The catalogue is the one source of a page address. The substance
files sit beside it: `substances.json`, the list of every number an entry prints, and
`substances/<scheme>-<value>.json`, one number's entries and changes. A path under that
directory is refused exactly as a path under the repository is.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

from pydantic import ValidationError

from emendrix_record.models import ActIndex, Catalogue, CatalogueAct, EventRow
from emendrix_record.reads import PERMALINK_UNAVAILABLE, SubstanceRead, Unavailable
from emendrix_record.substances import SubstanceFile, SubstanceIndex

__all__ = ["SUBSTANCES_FILE", "SiteFiles", "entry_key", "inside", "sha256_of"]

SUBSTANCES_FILE: Final = "substances.json"
"""The site build's list of numbers, beside its catalogue."""


def sha256_of(raw: bytes) -> str:
    """Hex sha256 of bytes as read."""
    return hashlib.sha256(raw).hexdigest()


def entry_key(event: EventRow) -> str:
    """The key the catalogue files an event under: its payload's file name, without `.json`."""
    return PurePosixPath(event.path).stem


def inside(root: Path, relative: str, where: str) -> Path | Unavailable:
    """`relative` under `root`, or refused when it is absolute, climbs, or resolves outside."""
    refused = Unavailable(
        reason=f"refused the path {relative!r}: every path must stay inside {where}"
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
    base = root.resolve()
    target = (base / pure).resolve()
    return target if target.is_relative_to(base) else refused


class SiteFiles:
    """The site catalogue at `catalogue`, and the substance files in its directory."""

    def __init__(self, catalogue: Path | None) -> None:
        self._catalogue = catalogue

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

    # --- the substance files, beside the catalogue -----------------------------------------

    def _site_bytes(self, relative: str) -> bytes | Unavailable:
        if self._catalogue is None:
            return Unavailable(
                reason="the substance files are unavailable: this server was given no site "
                "catalogue, and they are read beside it"
            )
        path = inside(self._catalogue.parent, relative, "the site catalogue's directory")
        if isinstance(path, Unavailable):
            return path
        try:
            return path.read_bytes()
        except OSError:
            return Unavailable(reason=f"{relative} could not be read beside the site catalogue")

    def substances(self) -> SubstanceIndex | Unavailable:
        """The list of every number an entry in the record prints, read now."""
        raw = self._site_bytes(SUBSTANCES_FILE)
        if isinstance(raw, Unavailable):
            return raw
        try:
            return SubstanceIndex.model_validate_json(raw)
        except ValidationError:
            return Unavailable(reason=f"{SUBSTANCES_FILE} is not a list this server can read")

    def substance(self, scheme: str, value: str) -> SubstanceRead | Unavailable:
        """One number's file, `substances/<scheme>-<value>.json`, read now and hashed."""
        relative = f"substances/{scheme}-{value}.json"
        raw = self._site_bytes(relative)
        if isinstance(raw, Unavailable):
            return raw
        try:
            document = SubstanceFile.model_validate_json(raw)
        except ValidationError:
            return Unavailable(reason=f"{relative} is not a substance file this server can read")
        return SubstanceRead(path=relative, sha256=sha256_of(raw), document=document)
