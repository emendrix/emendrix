"""The composition root shared by the commands that drive the loop.

Constructing the EU adapter, the signal source and the explain engine is where the concrete
choices are allowed to be named, and it deliberately sits outside `graph/`: every module under
`graph/` except its own CLI is asserted free of `emendrix.eu` by `tests/test_architecture.py`,
which is what lets the whole loop run over a corpus that is not law. Every command needs the
same four steps, so they live here once rather than once per command.

Nothing here reads a clock. `observed_on` arrives from whichever command is running, exactly
as it does everywhere else in the project.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from emendrix.core import ActId, VersionId
from emendrix.corroborate.sources import SignalSource
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureResponseCache, ResponseCache
from emendrix.eu.signals import EuSignalSource
from emendrix.explain import CassetteMode, ExplainEngine, ExplainSettings
from emendrix.graph.build import build_pipeline, run_pipeline
from emendrix.graph.deps import PipelineDeps, WatchSource
from emendrix.graph.report import RunReport
from emendrix.graph.state import PipelineState
from emendrix.watch.events import AmendmentEvent

__all__ = ["adapter_for", "deps_for", "execute", "manual_event"]


def adapter_for(
    fixture_dir: Path | None, observed_on: date, *, polite_delay_s: float | None = None
) -> EuCorpusAdapter:
    """The EU adapter, reading a pinned fixture set instead of the network when asked.

    `polite_delay_s` is how long to wait between network calls, and `None` means "whatever the
    environment says, or the default". A backfill passes its flag; every other command lets the
    environment answer.
    """
    cache: ResponseCache | None = None if fixture_dir is None else FixtureResponseCache(fixture_dir)
    return EuCorpusAdapter.build(
        observed_on=observed_on, cache=cache, polite_delay_s=polite_delay_s
    )


def deps_for(
    adapter: EuCorpusAdapter,
    observed_on: date,
    cassettes: CassetteMode | None,
    *,
    watcher: WatchSource | None = None,
) -> PipelineDeps:
    """Who supplies each stage. The signal source rides on the same client, so it stays offline."""
    settings = ExplainSettings.from_env()
    if cassettes is not None:
        settings = settings.model_copy(update={"cassette_mode": cassettes})
    signals: SignalSource = EuSignalSource(adapter.client)
    return PipelineDeps(
        adapter=adapter,
        engine=ExplainEngine(settings),
        observed_on=observed_on,
        signals=signals,
        watcher=watcher,
    )


def manual_event(
    act: ActId, from_version: str, to_version: str, observed_on: date, *, trigger: str
) -> AmendmentEvent:
    """The event the feed would have produced, asserted by the operator instead.

    `trigger` names the command that asserted it, so a reader is never left wondering which
    poll found something that no poll found.
    """
    return AmendmentEvent(
        act=act,
        target_version=VersionId(to_version),
        new_version=VersionId(to_version),
        previous_version=VersionId(from_version),
        trigger=trigger,
        observed_on=observed_on,
    )


def execute(deps: PipelineDeps, state: PipelineState, *, watch: bool) -> RunReport:
    """Build the graph, run it to completion, and insist it produced its report.

    `asyncio.run` here and nowhere deeper: the explain stage awaits a model under a semaphore,
    so the loop is owned at the boundary rather than started inside a node.
    """
    final = asyncio.run(run_pipeline(build_pipeline(deps, watch=watch), state))
    if final.report is None:  # pragma: no cover - EMIT writes it unconditionally
        raise RuntimeError("the pipeline finished without an emitted report")
    return final.report
