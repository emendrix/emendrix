"""`build_store`: every listed version of every act, written once into the text store.

Generic over any source with the two listing and fetching methods of the corpus seam, so the
toy corpus builds a store exactly as the EU adapter does. Per act, versions are taken in the
order the source lists them; a version already on disk is skipped unless `rebuild` is asked
for; a tree is written and a state is recorded in `states.json`.

A version answered with a state is asked again on the next run, because a pending
consolidation resolves and a missing language can appear; an unchanged answer leaves
`states.json` byte-identical. An exception from the fetching layer (an unexpected HTTP status,
a pinned fixture set that lacks the document, a connection that never answered) is not an
answer the corpus gave about the version: it is counted as `fetch_failed` with its message,
written nowhere, and retried by the next run.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from emendrix.core import ActId, ProvisionTree, Unavailable, VersionDescriptor, VersionId
from emendrix.texts.model import StoredState
from emendrix.texts.store import TextStore

__all__ = ["ActBuild", "BuildSummary", "TextSource", "build_store"]

_FETCH_FAILURES = (LookupError, ConnectionError)
"""What the fetching layer raises when it has no answer: `LookupError` covers an unexpected
status and a fixture set lacking the document, `ConnectionError` a source that never replied."""


class TextSource(Protocol):
    """The part of the corpus seam a build needs. Every `CorpusAdapter` satisfies it."""

    def discover_versions(self, act: ActId) -> list[VersionDescriptor]: ...

    def fetch_version(self, act: ActId, version: VersionId) -> ProvisionTree | Unavailable: ...


class ActBuild(BaseModel):
    """What one run did for one act, or, under `total`, for all of them."""

    model_config = ConfigDict(frozen=True)

    act: str = Field(description="`corpus:key`, or `total` for the sum over every act.")
    listed: int = Field(default=0, description="Versions the source listed.")
    already_stored: int = Field(default=0, description="Listed versions already on disk.")
    written: int = Field(default=0, description="Version files written by this run.")
    states: dict[str, int] = Field(
        default_factory=dict, description="Versions answered with a state, by the state's tag."
    )
    fetch_failed: int = Field(default=0, description="Fetches that raised; retried next run.")
    left: int = Field(
        default=0, description="Versions not fetched: left by `--dry-run` or past `--limit`."
    )
    listing_failed: int = Field(default=0, description="Acts whose versions could not be listed.")
    failures: tuple[str, ...] = Field(
        default=(),
        description="Each failed listing or fetch, with its message; empty under `total`.",
    )


class BuildSummary(BaseModel):
    """One run of `texts build`, per act and in total."""

    model_config = ConfigDict(frozen=True)

    dry_run: bool = Field(description="True when nothing was fetched and nothing written.")
    rebuild: bool = Field(description="True when stored versions were fetched and written again.")
    reading: str = Field(default="", description="What the source read: fixtures, or the cache.")
    acts: tuple[ActBuild, ...] = Field(description="One record per act, in the order asked for.")
    total: ActBuild = Field(description="The sum over `acts`.")


@dataclass
class _Budget:
    """How many more files this run may write; `None` is no limit."""

    remaining: int | None

    @property
    def spent(self) -> bool:
        return self.remaining == 0

    def spend(self) -> None:
        if self.remaining is not None:
            self.remaining -= 1


def build_store(
    source: TextSource,
    store: TextStore,
    acts: Sequence[ActId],
    *,
    limit: int | None = None,
    dry_run: bool = False,
    rebuild: bool = False,
) -> BuildSummary:
    """Fill `store` from `source`, act by act, stopping writes after `limit` files."""
    records: list[ActBuild] = []
    budget = _Budget(limit)
    for act in acts:
        records.append(_build_act(source, store, act, budget, dry_run=dry_run, rebuild=rebuild))
    return BuildSummary(dry_run=dry_run, rebuild=rebuild, acts=tuple(records), total=_sum(records))


def _build_act(
    source: TextSource,
    store: TextStore,
    act: ActId,
    budget: _Budget,
    *,
    dry_run: bool,
    rebuild: bool,
) -> ActBuild:
    name = f"{act.corpus}:{act.key}"
    try:
        listing = source.discover_versions(act)
    except _FETCH_FAILURES as error:
        return ActBuild(act=name, listing_failed=1, failures=(f"listing: {error}",))
    already = written = failed = left = 0
    states: list[StoredState] = []
    failures: list[str] = []
    for descriptor in listing:
        version = str(descriptor.version)
        if not rebuild and store.has(act.corpus, act.key, version):
            already += 1
            continue
        if dry_run or budget.spent:
            left += 1
            continue
        try:
            fetched = source.fetch_version(act, descriptor.version)
        except _FETCH_FAILURES as error:
            failed += 1
            failures.append(f"{version}: {error}")
            continue
        if isinstance(fetched, ProvisionTree):
            store.write(fetched, version=version)
            written += 1
            budget.spend()
        else:
            states.append(StoredState(version=version, state=fetched.state, detail=fetched.detail))
    if not dry_run:
        store.record_states(act.corpus, act.key, states)
    return ActBuild(
        act=name,
        listed=len(listing),
        already_stored=already,
        written=written,
        states=dict(sorted(Counter(state.state for state in states).items())),
        fetch_failed=failed,
        left=left,
        failures=tuple(failures),
    )


def _sum(records: Sequence[ActBuild]) -> ActBuild:
    states: Counter[str] = Counter()
    for record in records:
        states.update(record.states)
    return ActBuild(
        act="total",
        listed=sum(record.listed for record in records),
        already_stored=sum(record.already_stored for record in records),
        written=sum(record.written for record in records),
        states=dict(sorted(states.items())),
        fetch_failed=sum(record.fetch_failed for record in records),
        left=sum(record.left for record in records),
        listing_failed=sum(record.listing_failed for record in records),
    )
