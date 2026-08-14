"""Which transitions a backfill covers: consecutive readable versions, oldest first.

Pure selection over what `discover_versions` reported. No I/O, no network and no clock read:
the cutoff arrives as a value from the CLI boundary exactly as the poll window does, which is
what lets this module be exercised against a corpus that is not law.

**An unreadable version is bridged over rather than ending the chain.** "What changed since the
last text a reader could see?" is the question worth asking, and the metadata window folds in
every amending act between the two endpoints correctly either way. The bridge is never silent:
the versions stepped over are named on the transition that steps over them.

**A cutoff excludes an undated transition.** A cutoff is a promise about how far back a run
reaches, and a version the corpus does not date cannot honour it. With no cutoff set the
question never arises and every pair is kept, undated ones included.

Version order is the adapter's to establish: `CorpusAdapter.discover_versions` reports oldest
first, and this module preserves that order rather than re-deriving it from dates that a
corpus is free to leave blank.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from itertools import pairwise
from typing import Final

from pydantic import BaseModel, ConfigDict

from emendrix.core import ActId, VersionDescriptor, VersionId

__all__ = ["DEFAULT_LANGUAGE", "Transition", "TransitionPlan", "plan_transitions"]

DEFAULT_LANGUAGE: Final = "ENG"
"""The language a transition must be readable in to be worth running the loop over."""


class Transition(BaseModel):
    """One pair of versions to run the loop over, and what it stepped past to get there."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    from_version: VersionId
    to_version: VersionId
    to_date: date | None = None
    bridged: tuple[VersionId, ...] = ()

    @property
    def key(self) -> str:
        """Ledger identity: stable across runs, and readable in the file it is written to."""
        return f"{self.act}|{self.from_version}|{self.to_version}"

    @property
    def label(self) -> str:
        """One line for an operator watching a long run."""
        return f"{self.act} {self.from_version} -> {self.to_version}"


class TransitionPlan(BaseModel):
    """Every transition of one act, and what a cutoff left out of it."""

    model_config = ConfigDict(frozen=True)

    act: ActId
    versions: int = 0
    readable: int = 0
    transitions: tuple[Transition, ...] = ()
    before_cutoff: tuple[Transition, ...] = ()


def plan_transitions(
    act: ActId,
    versions: Sequence[VersionDescriptor],
    *,
    language: str = DEFAULT_LANGUAGE,
    not_before: date | None = None,
) -> TransitionPlan:
    """Consecutive readable versions, oldest first, minus anything the cutoff excludes."""
    readable = [item for item in versions if item.has_language(language)]
    pairs = tuple(
        Transition(
            act=act,
            from_version=before.version,
            to_version=after.version,
            to_date=after.version_date,
            bridged=_bridged(versions, before.version, after.version),
        )
        for before, after in pairwise(readable)
    )
    return TransitionPlan(
        act=act,
        versions=len(versions),
        readable=len(readable),
        transitions=tuple(item for item in pairs if _within(item, not_before)),
        before_cutoff=tuple(item for item in pairs if not _within(item, not_before)),
    )


def _within(transition: Transition, not_before: date | None) -> bool:
    """Whether a cutoff keeps this transition. No cutoff keeps everything."""
    if not_before is None:
        return True
    return transition.to_date is not None and transition.to_date >= not_before


def _bridged(
    versions: Sequence[VersionDescriptor], before: VersionId, after: VersionId
) -> tuple[VersionId, ...]:
    """The versions a pair steps over because the corpus offers no readable text for them.

    Walked over the full descriptor list rather than the readable sublist: the two endpoints
    are consecutive among the readable versions, so everything between them is precisely what
    was stepped over, and looking at the readable sublist could never find anything at all.
    """
    inside = False
    skipped: list[VersionId] = []
    for item in versions:
        if item.version == before:
            inside = True
            continue
        if item.version == after:
            break
        if inside:
            skipped.append(item.version)
    return tuple(skipped)
