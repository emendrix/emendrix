"""What an act, a version and a pointer into one are.

`ActId` and `VersionId` are opaque, corpus-scoped handles: the core never interprets
them, it only passes them back to the adapter that minted them. A `ProvisionRef` is
the three coordinates every citation and every change needs: which act, which version
of it, and where inside.

Deliberately unaware of: identifier syntax of any particular corpus, how versions are
discovered, and what "in force" means. Those live behind the adapter seam.
"""

from __future__ import annotations

from datetime import date
from typing import NewType

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core.location import ProvisionLocation

__all__ = ["ActId", "ProvisionRef", "VersionDescriptor", "VersionId"]

VersionId = NewType("VersionId", str)
"""An opaque, corpus-scoped version tag. Only the adapter that produced it may read it."""


class ActId(BaseModel):
    """An act, scoped to the corpus that knows how to fetch it.

    Identity is `(corpus, key)` only. `display_name` is a label that rides along for output, so
    the same act named by two callers, one of which knows its title and one of which does not,
    is the same act in equality, in hashing and in every set and dict key downstream.
    """

    model_config = ConfigDict(frozen=True)

    corpus: str = Field(min_length=1, description="Adapter namespace, e.g. 'eu' or 'toy'.")
    key: str = Field(min_length=1, description="Opaque identifier within that corpus.")
    display_name: str | None = Field(
        default=None, description="Human title, for output only; never parsed, never identity."
    )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ActId):
            return NotImplemented
        return (self.corpus, self.key) == (other.corpus, other.key)

    def __hash__(self) -> int:
        return hash((self.corpus, self.key))

    def __str__(self) -> str:
        return f"{self.corpus}:{self.key}"


class VersionDescriptor(BaseModel):
    """One version of an act, as `discover_versions` reports it.

    `version_date` is the date the version is keyed by in its corpus (for a consolidated text,
    the date it speaks as of). `languages` lists the language codes the adapter saw offered,
    which is not a promise that fetching will succeed: a version can exist with no
    machine-readable text at all (verified 2026-08-05), which is why `fetch_version` may still
    answer with an `Unavailable` state.
    """

    model_config = ConfigDict(frozen=True)

    act: ActId
    version: VersionId
    version_date: date | None = None
    languages: tuple[str, ...] = ()

    def has_language(self, language: str) -> bool:
        return language.upper() in {code.upper() for code in self.languages}


class ProvisionRef(BaseModel):
    """A provision in a specific version of a specific act."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    version: VersionId
    location: ProvisionLocation

    @property
    def human(self) -> str:
        return self.location.human

    def __str__(self) -> str:
        return f"{self.act}@{self.version} {self.location.canonical}"
