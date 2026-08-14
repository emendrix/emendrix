"""`EuCorpusAdapter`: the seam and the states that flow through it.

What is under test here is the adapter's own job, which is to read identifiers, discover
versions, pass first-class states through untouched and render citations, so the parser is
injected as a recording stub and the markup stays out of it. That the *real* parser is what an
adapter built with no arguments uses is asserted below and exercised end to end in
`test_formex_parse.py`. `test_adapter_contract.py` runs the shared Protocol test over this
adapter and the toy one together.
"""

from __future__ import annotations

import pytest

from emendrix.core import (
    ActId,
    AmendingActDoc,
    ConsolidationPending,
    CorpusAdapter,
    EnglishUnavailable,
    ProvisionLocation,
    ProvisionRef,
    ProvisionTree,
    StructuredTextUnavailable,
    VersionId,
)
from emendrix.eu.adapter import EuCorpusAdapter
from emendrix.eu.cellar import CellarClient
from emendrix.eu.formex import Formex4Parser
from emendrix.eu.identifiers import Celex, act_id
from eu_pins import AI_ACT, AI_ACT_V1, AI_ACT_V2, DIGITAL_OMNIBUS, OBSERVED_ON
from eu_stub_parser import RecordingParser

AI_ACT_ID = act_id(Celex.parse(AI_ACT))
OMNIBUS_ID = act_id(Celex.parse(DIGITAL_OMNIBUS))


@pytest.fixture
def parser() -> RecordingParser:
    return RecordingParser()


@pytest.fixture
def adapter(client: CellarClient, parser: RecordingParser) -> EuCorpusAdapter:
    return EuCorpusAdapter(client, parser=parser)


def test_it_satisfies_the_protocol(adapter: EuCorpusAdapter) -> None:
    assert isinstance(adapter, CorpusAdapter)


def test_discovery_speaks_only_core_types(adapter: EuCorpusAdapter) -> None:
    corpus: CorpusAdapter = adapter
    versions = corpus.discover_versions(AI_ACT_ID)
    assert [str(descriptor.version) for descriptor in versions] == [AI_ACT, AI_ACT_V1, AI_ACT_V2]
    assert all(descriptor.act == AI_ACT_ID for descriptor in versions)


def test_a_fetched_version_reaches_the_parser_with_its_provenance(
    adapter: EuCorpusAdapter, parser: RecordingParser
) -> None:
    tree = adapter.fetch_version(AI_ACT_ID, VersionId(AI_ACT_V2))
    assert isinstance(tree, ProvisionTree)
    package = parser.packages[0]
    assert package.served_version == VersionId(AI_ACT_V2)
    assert package.source_url.startswith("https://publications.europa.eu/")
    assert package.consolidation is not None


def test_states_pass_through_the_adapter_untouched(adapter: EuCorpusAdapter) -> None:
    pending = adapter.fetch_version(AI_ACT_ID, VersionId("02024R1689-20991231"))
    assert isinstance(pending, ConsolidationPending)
    assert pending.observed_on == OBSERVED_ON


def test_an_amending_act_is_read_as_published_never_as_a_consolidation(
    adapter: EuCorpusAdapter, parser: RecordingParser
) -> None:
    doc = adapter.parse_amending_act(OMNIBUS_ID)
    assert isinstance(doc, AmendingActDoc)
    package = parser.packages[0]
    assert package.served_version == VersionId(DIGITAL_OMNIBUS)
    assert package.source_url.endswith("/oj/L_202601744.ENG.fmx4")


def test_citations_come_out_of_the_adapter_ready_to_click(adapter: EuCorpusAdapter) -> None:
    citation = adapter.render_citation(
        ProvisionRef(
            act=AI_ACT_ID,
            version=VersionId(AI_ACT_V2),
            location=ProvisionLocation.parse("AR 5"),
        )
    )
    assert citation.url.endswith("?uri=CELEX:02024R1689-20260727#art_5")


def test_the_default_parser_is_the_real_formex_one(client: CellarClient) -> None:
    """No stub, no placeholder: an adapter built with no parser parses Formex 4."""
    adapter = EuCorpusAdapter(client)
    assert isinstance(adapter.parser, Formex4Parser)
    tree = adapter.fetch_version(AI_ACT_ID, VersionId(AI_ACT_V2))
    assert isinstance(tree, ProvisionTree)
    assert tree.find("AR 4a") is not None


def test_an_act_from_another_corpus_is_a_programming_error(adapter: EuCorpusAdapter) -> None:
    with pytest.raises(ValueError, match="not an EU act"):
        adapter.discover_versions(ActId(corpus="toy", key="house-rules"))


def test_a_missing_english_version_still_answers_with_a_state(
    client: CellarClient, parser: RecordingParser
) -> None:
    """With the OJ fallback off, `fetch_formex` answers `EnglishUnavailable`."""
    state = client.fetch_formex(
        Celex.parse(AI_ACT), VersionId(AI_ACT_V1), allow_original_fallback=False
    )
    assert isinstance(state, EnglishUnavailable)
    assert parser.packages == []


def test_a_package_holding_no_readable_act_answers_a_state_not_an_empty_tree(
    client: CellarClient,
) -> None:
    """A version whose package yields no provisions is unavailable, never silently empty.

    Measured on REACH, 2026-08-11: `02006R1907-20150513` and `02006R1907-20150601` return a
    Formex package, parse without raising and yield no provisions at all, because the corpus
    ships those archives with member names that do not describe their contents and the act's
    own document lands on a member named `.tif`. An empty tree is indistinguishable from a
    repeal once it reaches the diff, so answering with one reports all 158 units of REACH
    deleted and then re-inserted, with a zero exit status and no marker anywhere.

    Refusing here is what makes that a counted first-class state, like the six REACH versions
    that offer no Formex at all, rather than confident wrong output nothing downstream can
    catch.
    """
    adapter = EuCorpusAdapter(client, parser=RecordingParser(finds_nothing=True))
    state = adapter.fetch_version(AI_ACT_ID, VersionId(AI_ACT_V2))
    assert isinstance(state, StructuredTextUnavailable)
    assert state.version == VersionId(AI_ACT_V2)
    assert state.observed_on == OBSERVED_ON
    assert "no provisions" in state.detail


def test_the_adapter_releases_its_connection_pool(adapter: EuCorpusAdapter) -> None:
    """The watcher and the loop hold an adapter for a whole run; closing it twice is fine."""
    with adapter as held:
        assert held is adapter
    adapter.close()
