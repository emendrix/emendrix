"""One contract test, two implementors: an abstraction validated against one is not one.

The toy corpus is a flat's house rules; the EU corpus is 68 consolidated versions of REACH
behind content negotiation. Everything below is written against `CorpusAdapter` alone: if a
line here needs to know which one it is holding, the seam has leaked.

It lives under `tests/eu/` only because that is where the fixture-backed client is wired up.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from emendrix.core import (
    ActId,
    ConsolidationPending,
    CorpusAdapter,
    ProvisionLocation,
    ProvisionRef,
    ProvisionTree,
    VersionId,
)
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cellar import CellarClient
from emendrix.eu.identifiers import Celex, act_id
from eu_pins import AI_ACT, AI_ACT_V2, OBSERVED_ON
from eu_stub_parser import RecordingParser
from toy_corpus import HOUSE_RULES, V2, ToyCorpusAdapter

FIRST_ARTICLE = ProvisionLocation.parse("AR 1")
"""Both corpora number their first unit this way; the location vocabulary is shared."""


@dataclass(frozen=True)
class Case:
    """One implementor, and the three coordinates every adapter test needs."""

    adapter: CorpusAdapter
    act: ActId
    version: VersionId
    absent_version: VersionId


@pytest.fixture(params=["toy", "eu"])
def case(request: pytest.FixtureRequest, client: CellarClient) -> Case:
    if request.param == "toy":
        return Case(
            adapter=ToyCorpusAdapter(observed_on=OBSERVED_ON),
            act=HOUSE_RULES,
            version=V2,
            absent_version=VersionId("v3"),
        )
    return Case(
        adapter=EuCorpusAdapter(client, parser=RecordingParser()),
        act=act_id(Celex.parse(AI_ACT)),
        version=VersionId(AI_ACT_V2),
        absent_version=VersionId("02024R1689-20991231"),
    )


def test_every_implementor_satisfies_the_protocol(case: Case) -> None:
    assert isinstance(case.adapter, CorpusAdapter)


def test_versions_are_descriptors_of_the_act_they_were_asked_about(case: Case) -> None:
    versions = case.adapter.discover_versions(case.act)
    assert versions
    assert all(descriptor.act == case.act for descriptor in versions)
    dated = [item.version_date for item in versions if item.version_date is not None]
    assert dated == sorted(dated), "oldest first"
    assert case.version in {descriptor.version for descriptor in versions}


def test_fetching_a_version_yields_a_tree_of_the_act_it_was_asked_about(case: Case) -> None:
    tree = case.adapter.fetch_version(case.act, case.version)
    assert isinstance(tree, ProvisionTree)
    assert tree.act == case.act


def test_a_version_that_is_not_there_is_a_state_not_an_exception(case: Case) -> None:
    unavailable = case.adapter.fetch_version(case.act, case.absent_version)
    assert isinstance(unavailable, ConsolidationPending)
    assert unavailable.observed_on == OBSERVED_ON, "the date is passed in, never clock-read"


def test_citations_are_clickable_and_labelled(case: Case) -> None:
    citation = case.adapter.render_citation(
        ProvisionRef(act=case.act, version=case.version, location=FIRST_ARTICLE)
    )
    assert citation.url.startswith("https://")
    assert citation.label
    assert citation.ref.version == case.version
