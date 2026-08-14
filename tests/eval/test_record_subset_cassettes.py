"""Regenerating the model layer's committed cassettes. Excluded from every default run.

    # against the pinned models: costs money, needs a key, hits the network
    OPENROUTER_API_KEY=sk-or-v1-... uv run pytest -m "record and live" tests/eval

    # offline, deterministic, produces cassettes marked `synthetic: true`
    uv run pytest -m "record and live" tests/eval

Same command either way, exactly as `tests/explain/test_record_cassettes.py` intends: the
difference is the environment rather than a flag, so it is impossible to *think* you recorded
against a real model and be wrong. Every cassette says what produced it and `synthetic` says
whether to believe it, and that flag rides into the report, where it withholds the faithfulness
rate outright.

Two sets are written here, because the model layer has two model calls in it:

- `tests/cassettes-eval/`: one explain exchange per pinned change, plus one per revision the
  gate asks for. The recorder runs the *whole* shipped explain → gate → revise → settle path,
  so the retries it records are the retries the replay will need.
- `tests/cassettes-judge/`: one judgement per sampled triple, from a different model.

The recording is deliberately driven through `run_subset` rather than through a loop of its own:
a recorder that builds its own prompts records prompts nothing will ever ask for again.

**The judge set can be re-recorded on its own**, replaying the committed explanations instead of
paying for them again:

    uv run pytest -m "record and live" -k judgements tests/eval

Two reasons that is worth its own entry point. A judgement is *about* one explanation, so a run
that regenerates both at once can never be compared with the one before it; and the judge prompt
changes for reasons of its own (it did on 2026-08-08, when the two texts it shows were made the
texts the model actually read), which invalidates 20 judgements without touching a single
explanation. Judge keys are taken over the prompt, so a changed prompt writes new files rather
than overwriting the old ones, and the files it replaced have to be deleted by hand: nothing
will ever ask for them again, and a stale judgement that still replays is a number about a
prompt the project does not send.
"""

from __future__ import annotations

import asyncio

import pytest

from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cache import FixtureResponseCache
from emendrix.eu.cellar import CellarClient
from emendrix.eu.http import CellarHttp
from emendrix.eval_.corpus import load_corpus
from emendrix.eval_.faithfulness import record
from emendrix.eval_.judge import judge_model, sample
from emendrix.eval_.judgements import JUDGE_CASSETTE_DIR, JudgeCassetteStore
from emendrix.eval_.model_metrics import SUBSET_CASSETTE_DIR
from emendrix.eval_.model_run import SubsetRun, run_subset
from emendrix.eval_.runner import CorpusReader
from emendrix.explain import (
    CassetteMode,
    CassetteStore,
    ExplainEngine,
    ExplainSettings,
)
from eu_pins import FIXTURE_DIR, OBSERVED_ON
from recording import stub_when_unkeyed


def _subset(mode: CassetteMode) -> SubsetRun:
    """The pinned subset through the shipped pipeline, recording or replaying the explanations."""
    settings = ExplainSettings(cassette_mode=mode, cassette_dir=SUBSET_CASSETTE_DIR)
    model, synthetic = stub_when_unkeyed(settings)
    engine = ExplainEngine(
        settings,
        cassettes=CassetteStore(SUBSET_CASSETTE_DIR),
        model=model,
        synthetic=synthetic,
    )
    corpus = load_corpus()
    http = CellarHttp(cache=FixtureResponseCache(FIXTURE_DIR))
    with http:
        client = CellarClient(http, observed_on=OBSERVED_ON)
        return asyncio.run(
            run_subset(
                CorpusReader(client),
                corpus,
                engine=engine,
                adapter=EuCorpusAdapter(client),
                observed_on=OBSERVED_ON,
            )
        )


def _check_subset(run: SubsetRun) -> None:
    subset = load_corpus().explain_subset
    assert subset is not None, "no explanation subset is pinned; run `emendrix eval build-subset`"
    assert run.metrics.settled.changes == subset.changes
    assert run.metrics.missing_units == 0


def _record_judgements(run: SubsetRun) -> None:
    triples = sample(run.triples)
    assert triples, "the subset produced no judgeable triple"
    judge = judge_model()
    model, synthetic = stub_when_unkeyed(ExplainSettings(model_id=judge))
    report = asyncio.run(
        record(
            triples,
            model_id=judge,
            store=JudgeCassetteStore(JUDGE_CASSETTE_DIR),
            model=model,
            synthetic=synthetic,
        )
    )
    assert report.judged == len(triples)
    assert report.synthetic == (len(triples) if synthetic else 0)


@pytest.mark.record
@pytest.mark.live
def test_record_the_pinned_subset() -> None:
    """Rewrite every cassette the model-layer replay depends on, explain and judge alike."""
    run = _subset(CassetteMode.RECORD)
    _check_subset(run)
    _record_judgements(run)


@pytest.mark.record
@pytest.mark.live
def test_record_the_judgements_over_the_committed_explanations() -> None:
    """The judge set alone, replaying the explanations rather than paying for them again.

    Select it with `-k judgements`. Replay is the point: these judgements are then judgements
    *of the committed prose*, so the faithfulness rate and the explanations a reader can open
    describe the same run.
    """
    run = _subset(CassetteMode.REPLAY)
    _check_subset(run)
    _record_judgements(run)
