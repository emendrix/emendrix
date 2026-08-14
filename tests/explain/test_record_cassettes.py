"""Regenerating the committed cassettes. Excluded from every default run.

    # against the pinned model — costs money, needs a key, hits the network
    OPENROUTER_API_KEY=sk-or-v1-... uv run pytest -m "record and live" tests/explain

    # offline, deterministic, produces cassettes marked `synthetic: true`
    uv run pytest -m "record and live" tests/explain

Same command either way, and the difference is the environment rather than a flag, so it is
impossible to *think* you recorded against the real model and be wrong: the cassette says what
produced it, `Cassette.synthetic` says whether to believe it, and that flag rides all the way
into `RunStats.synthetic` so no published metric can mix the two.

The synthetic path exists because a stub model is still a real exercise of the record path
(key derivation, JSON envelope, byte-stable serialisation, replay), and shipping the replay
machinery untested until someone has an API key would be worse. What it is *not* is evidence
about explanation quality, and nothing here pretends otherwise. The synthetic sentences are
whatever `TestModel` generates from the schema (the placeholder `"a"`); no human wrote a
plausible-looking legal sentence and committed it as a model's answer.

Marked `live` as well as `record` because with a key present this genuinely hits a provider,
and every test that can reach a network is behind that marker, which the default run and CI
both exclude.
"""

from __future__ import annotations

import asyncio

import pytest
from pinned_cases import pinned_cases

from emendrix.eu.cellar import CellarClient
from emendrix.explain import (
    CassetteMode,
    CassetteStore,
    ExplainedChange,
    ExplainEngine,
    ExplainSettings,
)
from eu_pins import FIXTURE_DIR
from recording import stub_when_unkeyed

CASSETTE_DIR = FIXTURE_DIR.parents[1] / "cassettes"
"""`tests/cassettes`: beside the fixtures, committed, and diffed like any other source."""


@pytest.mark.record
@pytest.mark.live
def test_record_the_pinned_cassettes(client: CellarClient) -> None:
    """Rewrite every cassette the replay test depends on, from the pinned fixture changes."""
    settings = ExplainSettings(cassette_mode=CassetteMode.RECORD, cassette_dir=CASSETTE_DIR)
    model, synthetic = stub_when_unkeyed(settings)
    engine = ExplainEngine(
        settings, cassettes=CassetteStore(CASSETTE_DIR), model=model, synthetic=synthetic
    )

    async def record() -> list[ExplainedChange]:
        return [
            await engine.explain_change(case.change, case.context) for case in pinned_cases(client)
        ]

    results = asyncio.run(record())
    assert results, "the pinned subset is empty"
    for result in results:
        assert result.ok, f"{result.provision.location.canonical}: {result.unavailable}"
        assert result.synthetic is synthetic
        assert CassetteStore(CASSETTE_DIR).load(settings.model_id, result.cassette_key) is not None
