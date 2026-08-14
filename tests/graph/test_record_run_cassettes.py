"""Recording the cassettes `emendrix explain` replays offline. Excluded from every default run.

    # offline, deterministic, produces cassettes marked `synthetic: true`
    uv run pytest -m "record and live" tests/graph

    # against the pinned model — costs money, needs a key, hits the network
    OPENROUTER_API_KEY=sk-or-v1-... uv run pytest -m "record and live" tests/graph

`tests/cassettes/` holds four cassettes for four prompt *shapes*. This records a whole
*transition*, so the shipped command has something to replay: `emendrix explain 32017R0745 …`
runs end to end with no network and no API key, which is what the CI job and the demo both
need.

The MDR postponement is the transition, because it is the smallest real one in the fixture set
(9 changes) and the cassettes are committed artifacts that a reader has to be able to scroll
past. The AI Act's 45 changes would be ten times the bytes to prove the same thing.

**Recorded through the graph, not beside it.** The prompts depend on the *corroborated* delta
(a disputed change carries an extra line) and the revision prompts depend on the gate's own
complaint. Recording by any other route would key cassettes the pipeline then misses. So this
runs the actual pipeline in `RECORD` mode and lets it ask for exactly what it will ask for
again on replay, including the retry.

**What the recording says about model quality: nothing.** With no key the model is pydantic-ai's
`TestModel`, whose citations are schema placeholders, so every change fails containment, is
revised once, fails again, and ships the verbatim quotation. That is the *correct* handling of
a model that cannot cite, and the replay test asserts exactly that and nothing about prose.
"""

from __future__ import annotations

import asyncio

import pytest

from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cellar import CellarClient
from emendrix.eu.signals import EuSignalSource
from emendrix.explain import CassetteMode, CassetteStore, ExplainEngine, ExplainSettings
from emendrix.graph import PipelineDeps, PipelineState, build_pipeline, run_pipeline
from recording import stub_when_unkeyed
from run_pins import RUN_CASSETTE_DIR, TRANSITION, manual_event


@pytest.mark.record
@pytest.mark.live
def test_record_the_transition_cassettes(client: CellarClient) -> None:
    """Run the whole loop in RECORD mode; every prompt it builds lands on disk."""
    settings = ExplainSettings(cassette_mode=CassetteMode.RECORD, cassette_dir=RUN_CASSETTE_DIR)
    model, synthetic = stub_when_unkeyed(settings)
    adapter = EuCorpusAdapter(client)
    engine = ExplainEngine(
        settings,
        cassettes=CassetteStore(RUN_CASSETTE_DIR),
        model=model,
        synthetic=synthetic,
    )
    deps = PipelineDeps(
        adapter=adapter,
        engine=engine,
        observed_on=TRANSITION.observed_on,
        signals=EuSignalSource(client),
    )
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps, watch=False),
            PipelineState(observed_on=TRANSITION.observed_on, events=(manual_event(),)),
        )
    )
    assert final.report is not None
    emitted = final.report.deltas[0]
    assert len(emitted.changes) == TRANSITION.changes, "the delta moved; re-pin before recording"
    assert emitted.gate.settled == emitted.gate.changes

    recorded = sorted(RUN_CASSETTE_DIR.rglob("*.json"))
    assert recorded, "the record run wrote nothing"
