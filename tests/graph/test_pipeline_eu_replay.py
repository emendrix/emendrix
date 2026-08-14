"""The flagship, through the whole loop: the AI Act as the Digital Omnibus left it.

`tests/diff/test_eu_ai_act.py` proves the diff reproduces the validated numbers. This proves
the *rest of the loop does not lose them*: the 45 changes the diff finds are the 45 changes the
gate settles and the 45 changes the report emits, each with a citation URL in the format
verified against the live endpoint.

Two things are deliberately not asserted here.

**Explanation quality.** The model is `stub_engine.citing_offered`, a `FunctionModel` that
copies a key back out of the prompt. It is driven through the real `ExplainEngine`, so the
prompt, the semaphore, the usage accounting and the retry path are all genuine, but what it
*says* is a placeholder. Nothing below reads a sentence's text. The committed cassettes would
serve no better here: they cover four pinned changes rather than forty-five
(`tests/explain/test_engine_replay.py`).

**The network.** `FixtureResponseCache` has no code path to a socket, so a document nobody
pinned fails naming the request. That is what makes this an offline test rather than a test
that happens to have been offline.
"""

from __future__ import annotations

import asyncio
import re

import pytest
from pydantic_ai.models.function import FunctionModel

from emendrix.core import ActId, ChangeType, ProvisionTree, VersionId
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex, act_id
from emendrix.eu.signals import EuSignalSource
from emendrix.gate import GateOutcome
from emendrix.graph import PipelineDeps, PipelineState, RunReport, build_pipeline, run_pipeline
from emendrix.watch.events import AmendmentEvent
from eu_pins import AI_ACT, AI_ACT_V2, OBSERVED_ON
from stub_engine import citing_nothing_real, citing_offered, engine

AI_ACT_OJ = AI_ACT
"""The act as published in the Official Journal is its own version tag (`eu/identifiers.py`)."""

TOUCHED_UNITS = 45
"""7 inserted · 38 modified · 0 deleted, annexes included (`tests/diff/test_eu_ai_act.py`)."""

TOUCHED_ARTICLES = 42
"""The headline number, asserted here too, through the whole pipeline."""

CITATION = re.compile(
    r"^https://eur-lex\.europa\.eu/legal-content/EN/TXT/HTML/\?uri=CELEX:[0-9A-Z-]+#\S+$"
)
"""Provision-level ELI URIs 404 (verified 2026-08-06), so citations are EUR-Lex anchors, in
the shape `eu/links.py` documents. A citation that stopped matching this would not resolve."""


@pytest.fixture
def adapter(client: CellarClient) -> EuCorpusAdapter:
    return EuCorpusAdapter(client)


@pytest.fixture
def event() -> AmendmentEvent:
    return AmendmentEvent(
        act=_act(),
        target_version=VersionId(AI_ACT_V2),
        new_version=VersionId(AI_ACT_V2),
        previous_version=VersionId(AI_ACT_OJ),
        trigger="fixture:digital-omnibus",
        observed_on=OBSERVED_ON,
    )


@pytest.fixture
def report(adapter: EuCorpusAdapter, event: AmendmentEvent) -> RunReport:
    return _run(adapter, event, citing_offered())


def _act() -> ActId:
    return act_id(Celex.parse(AI_ACT))


def _run(adapter: EuCorpusAdapter, event: AmendmentEvent, model: FunctionModel) -> RunReport:
    deps = PipelineDeps(
        adapter=adapter,
        engine=engine(model),
        observed_on=OBSERVED_ON,
        signals=EuSignalSource(adapter.client),
    )
    final = asyncio.run(
        run_pipeline(
            build_pipeline(deps, watch=False),
            PipelineState(observed_on=OBSERVED_ON, events=(event,)),
        )
    )
    assert final.report is not None
    return final.report


# ------------------------------------------------------------------ nothing is lost


def test_the_flagship_transition_reaches_the_report_whole(report: RunReport) -> None:
    assert len(report.deltas) == 1
    emitted = report.deltas[0]
    assert str(emitted.from_version) == AI_ACT_OJ
    assert str(emitted.to_version) == AI_ACT_V2
    assert emitted.summary.touched_units == TOUCHED_UNITS
    assert len(emitted.changes) == TOUCHED_UNITS
    assert report.skipped == ()


def test_the_headline_article_count_survives_the_whole_pipeline(report: RunReport) -> None:
    """42, the validated figure, measured at the far end of the loop."""
    articles = {
        change.change.unit.canonical
        for change in report.deltas[0].changes
        if change.change.unit.canonical.startswith("AR ")
    }
    assert len(articles) == TOUCHED_ARTICLES


def test_the_inserted_articles_are_the_ones_the_digital_omnibus_published(
    report: RunReport,
) -> None:
    """`4a`, `60a` and `75a` to `75d`, the six the Digital Omnibus inserts. No hand-authored
    content: these come from the corpus through the parser and the diff, and are only
    *checked* here."""
    inserted = sorted(
        change.change.unit.canonical
        for change in report.deltas[0].changes
        if change.change.change_type is ChangeType.INSERTED
        and change.change.unit.canonical.startswith("AR ")
    )
    assert inserted == ["AR 4a", "AR 60a", "AR 75a", "AR 75b", "AR 75c", "AR 75d"]


def test_the_gate_settles_every_change_it_was_given(report: RunReport) -> None:
    gate = report.deltas[0].gate
    assert gate.changes == TOUCHED_UNITS
    assert gate.settled == TOUCHED_UNITS, "every change has a final answer"
    assert gate.passed_first + gate.passed_on_retry + gate.fallback + gate.unexplained == (
        TOUCHED_UNITS
    )
    assert report.gate.changes == gate.changes, "the run totals are the sum of the deltas'"


def test_a_grounded_run_passes_everything_on_the_first_attempt(report: RunReport) -> None:
    gate = report.deltas[0].gate
    assert gate.passed_first == TOUCHED_UNITS
    assert gate.retries == 0
    assert gate.citations_rejected == 0
    assert gate.citations == gate.sentences, "one citation per sentence, from this stub"


# ------------------------------------------------------------------ the citations


def test_every_emitted_citation_is_a_eur_lex_anchor_in_the_verified_format(
    report: RunReport,
) -> None:
    """A provision-level ELI would 404, so the anchor format is the claim being made."""
    urls = [
        citation.url
        for change in report.deltas[0].changes
        for sentence in change.sentences
        for citation in sentence.citations
    ]
    assert len(urls) == TOUCHED_UNITS, "one sentence citing one key, per change"
    for url in urls:
        assert CITATION.match(url), url


def test_a_citation_names_the_version_its_sentence_was_offered(report: RunReport) -> None:
    """The key was `location@version`; the URL has to point at that same consolidation."""
    for change in report.deltas[0].changes:
        for sentence in change.sentences:
            for citation in sentence.citations:
                assert str(citation.ref.version) in (AI_ACT_OJ, AI_ACT_V2)
                assert f"CELEX:{citation.ref.version}" in citation.url


# ------------------------------------------------------------------ corroboration rides along


def test_the_corroboration_report_reaches_the_output(report: RunReport) -> None:
    """The three-way story is part of the emitted document, not a side channel."""
    corroboration = report.deltas[0].corroboration
    assert corroboration is not None
    assert report.deltas[0].explain is not None
    assert report.deltas[0].explain.changes == TOUCHED_UNITS


def test_the_run_is_byte_stable(adapter: EuCorpusAdapter, event: AmendmentEvent) -> None:
    """Forty-five changes explained concurrently under a semaphore, and still one output file."""
    first = _run(adapter, event, citing_offered())
    second = _run(adapter, event, citing_offered())
    assert first.model_dump_json(indent=2) == second.model_dump_json(indent=2)


# ------------------------------------------------------------------ the ugly path


def test_a_model_that_cannot_cite_still_ships_all_forty_five_changes(
    adapter: EuCorpusAdapter, event: AmendmentEvent
) -> None:
    """The promise, at flagship scale: never drop a change, never let an ungrounded one through."""
    report = _run(adapter, event, citing_nothing_real())
    emitted = report.deltas[0]

    assert len(emitted.changes) == TOUCHED_UNITS
    assert emitted.gate.fallback == TOUCHED_UNITS
    assert emitted.gate.retries == TOUCHED_UNITS
    assert emitted.gate.settled == TOUCHED_UNITS
    for change in emitted.changes:
        assert change.outcome is GateOutcome.FALLBACK
        assert len(change.sentences) == 1
        assert change.sentences[0].fallback
        assert CITATION.match(change.sentences[0].citations[0].url)


def test_the_fixtures_really_are_the_source_and_the_network_is_absent(
    adapter: EuCorpusAdapter,
) -> None:
    """A guard on the premise: these are the pinned trees, fetched through the fixture cache."""
    for version in (AI_ACT_OJ, AI_ACT_V2):
        tree = adapter.fetch_version(_act(), VersionId(version))
        assert isinstance(tree, ProvisionTree)
        assert str(tree.version) == version
