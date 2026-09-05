"""Today's parse of a transition that is already published, and the reason where there is none.

This is the one part of `repair/` that reaches the corpus, and it does so through the adapter's
own cache, exactly as the loop's FETCH stage does. It exists because the question the evidence
repair asks cannot be answered from a payload: a payload states the text it was written with,
and what is wanted is the text today's parser produces for the same two versions.

**A version that cannot be produced is a value.** A package the cache does not hold, a version
the corpus offers no readable English for, a socket that closed: each is counted and named, and
the entry it belongs to is left exactly as it is. Nothing here raises on a document.

**What is re-derived is the structural diff, held against the signals the payload carries.**
The other two signals round-trip out of the committed document field for field, so a re-derived
delta is merged with exactly the signals that were published rather than with a fresh reading of
them: reading those again is a different repair, and it has a verb of its own.

**A derivation whose identifiers moved is refused rather than used.** The act and the two
version identifiers are what a permalink and a feed id are built from, so a tree served under a
different version than the one asked for would silently republish an entry at another address.
The corpus answering with a different document is a coverage gap like any other and is counted.

One parse per version, not one per entry: consecutive entries of an act share a consolidation
as the later side of one transition and the earlier side of the next, so the cache is what makes
a whole-repository pass affordable. It is deliberately no wider than one act, because the trees
are large and nothing beyond an act's own entries asks for them again.

Core types and the corpus seam. No model, no clock, no EU vocabulary.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, CorpusAdapter, Delta, ProvisionTree, VersionId
from emendrix.corroborate import CorroborationReport, corroborate
from emendrix.diff import compute_delta
from emendrix.output import ChangelogEntry
from emendrix.repair.corroborate import instructions_of, signals_of
from emendrix.repair.entry import RepairTarget
from emendrix.repair.staleness import EvidencePlan, compare

__all__ = ["Derivation", "Rederived", "Trees", "corroborated", "derive", "read"]

_MOVED = "the corpus served {act} {from_version} to {to_version} for this transition"
"""Said where a re-parse would move the identifiers a permalink is derived from."""


class Derivation(BaseModel):
    """Today's parse of one transition: both trees and the delta, or why there is neither."""

    model_config = ConfigDict(frozen=True)

    before: ProvisionTree | None = None
    after: ProvisionTree | None = None
    delta: Delta | None = None
    note: str = Field(default="", description="Why there is no delta. Empty when there is one.")

    @property
    def derived(self) -> bool:
        return self.delta is not None


class Trees:
    """The provision trees of one act, parsed once each however many entries ask for them."""

    def __init__(self, adapter: CorpusAdapter) -> None:
        self._adapter = adapter
        self._act: ActId | None = None
        self._trees: dict[str, ProvisionTree | str] = {}

    def of(self, act: ActId, version: VersionId) -> ProvisionTree | str:
        """One version's tree, or the stated reason there is none to compare against."""
        if act != self._act:
            self._act, self._trees = act, {}
        found = self._trees.get(str(version))
        if found is None:
            found = self._fetched(act, version)
            self._trees[str(version)] = found
        return found

    def _fetched(self, act: ActId, version: VersionId) -> ProvisionTree | str:
        try:
            answer = self._adapter.fetch_version(act, version)
        except (OSError, LookupError, ValueError) as error:
            return f"{type(error).__name__} fetching {version}"
        return answer if isinstance(answer, ProvisionTree) else answer.state


def derive(entry: ChangelogEntry, trees: Trees) -> Derivation:
    """Re-parse both versions of one published transition and diff them as the loop would.

    The structural diff alone: what the other two signals said is a fact the payload already
    carries, and re-reading them here would be a different repair.
    """
    before = trees.of(entry.act, entry.from_version)
    if isinstance(before, str):
        return Derivation(note=f"{entry.from_version}: {before}")
    after = trees.of(entry.act, entry.to_version)
    if isinstance(after, str):
        return Derivation(note=f"{entry.to_version}: {after}")
    delta = compute_delta(before, after)
    if (delta.act, delta.from_version, delta.to_version) != (
        entry.act,
        entry.from_version,
        entry.to_version,
    ):
        return Derivation(
            note=_MOVED.format(
                act=delta.act.key, from_version=delta.from_version, to_version=delta.to_version
            )
        )
    return Derivation(before=before, after=after, delta=delta)


class Rederived(BaseModel):
    """One published entry against today's parse: the trees, the merged delta, and the verdict.

    Built only where both versions parsed and the identifiers held, so every field is an
    answer rather than a maybe, and a transition that could not be re-derived is a note
    instead of an instance of this.
    """

    model_config = ConfigDict(frozen=True)

    derivation: Derivation
    delta: Delta = Field(description="Today's diff, merged with the signals the payload holds.")
    report: CorroborationReport | None = None
    plan: EvidencePlan


def corroborated(entry: ChangelogEntry, delta: Delta) -> tuple[Delta, CorroborationReport | None]:
    """Today's diff merged with the two signals the payload already carries.

    An entry that carries no corroboration at all had none to merge and keeps having none.
    """
    if entry.corroboration is None:
        return delta, None
    found = corroborate(delta, metadata=signals_of(entry), instructions=instructions_of(entry))
    return found.delta, found.report


def read(target: RepairTarget, trees: Trees) -> tuple[Rederived | None, str]:
    """One entry re-derived, merged and compared, or the stated reason there is no comparison."""
    found = derive(target.entry, trees)
    if found.delta is None:
        return None, f"{target.entry.act.key} {target.entry.to_version}: {found.note}"
    delta, report = corroborated(target.entry, found.delta)
    return (
        Rederived(
            derivation=found,
            delta=delta,
            report=report,
            plan=compare(target.entry, delta.changes),
        ),
        "",
    )
