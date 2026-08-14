"""The seam has two implementors: `ToyCorpusAdapter` satisfies `CorpusAdapter`."""

from datetime import date

import pytest

from emendrix.core.adapter import AmendingActDoc, CorpusAdapter
from emendrix.core.changes import ChangeType
from emendrix.core.identifiers import ActId, ProvisionRef, VersionId
from emendrix.core.location import ProvisionLocation
from emendrix.core.location_codes import UnknownCode
from emendrix.core.provisions import ProvisionTree
from emendrix.core.states import ConsolidationPending, EnglishUnavailable
from toy_corpus import AMENDMENT, HOUSE_RULES, V1, V2, V3_PENDING, ToyCorpusAdapter

OBSERVED_ON = date(2026, 8, 5)


@pytest.fixture
def adapter() -> ToyCorpusAdapter:
    return ToyCorpusAdapter(observed_on=OBSERVED_ON)


def test_toy_adapter_satisfies_the_protocol(adapter: ToyCorpusAdapter) -> None:
    assert isinstance(adapter, CorpusAdapter)


def test_the_protocol_is_the_only_thing_the_engine_needs(adapter: ToyCorpusAdapter) -> None:
    """Consume the adapter through the Protocol type alone: no toy-specific attributes."""
    corpus: CorpusAdapter = adapter
    versions = corpus.discover_versions(HOUSE_RULES)
    assert [descriptor.version for descriptor in versions] == [V1, V2, V3_PENDING]

    tree = corpus.fetch_version(HOUSE_RULES, V2)
    assert isinstance(tree, ProvisionTree)
    citation = corpus.render_citation(
        ProvisionRef(act=HOUSE_RULES, version=V2, location=tree.roots[0].location)
    )
    assert citation.url.startswith("https://example.invalid/house-rules/v2#")
    assert citation.label == "Art. 1, v2"


def test_versions_differ_exactly_where_the_toy_says(adapter: ToyCorpusAdapter) -> None:
    first = adapter.fetch_version(HOUSE_RULES, V1)
    second = adapter.fetch_version(HOUSE_RULES, V2)
    assert isinstance(first, ProvisionTree)
    assert isinstance(second, ProvisionTree)

    old = {location.canonical for location in first.unit_locations()}
    new = {location.canonical for location in second.unit_locations()}
    assert new - old == {"AR 4"}
    assert old - new == {"AR 3"}

    unchanged = first.find("AR 1")
    assert unchanged is not None
    assert second.find("AR 1") == unchanged

    modified_before = first.find("AR 2")
    modified_after = second.find("AR 2")
    assert modified_before is not None
    assert modified_after is not None
    assert modified_before.comparison_text != modified_after.comparison_text


def test_an_alien_corpus_still_produces_core_types(adapter: ToyCorpusAdapter) -> None:
    tree = adapter.fetch_version(HOUSE_RULES, V1)
    assert isinstance(tree, ProvisionTree)
    slot = tree.find("AN I SLOT 2")
    assert slot is not None
    assert slot.location.segments[1].code == UnknownCode(raw="SLOT")
    assert slot.location.is_within(ProvisionLocation.parse("AN I"))


def test_a_missing_version_is_a_state_not_an_exception(adapter: ToyCorpusAdapter) -> None:
    pending = adapter.fetch_version(HOUSE_RULES, V3_PENDING)
    assert isinstance(pending, ConsolidationPending)
    assert pending.state == "consolidation_pending"
    assert pending.observed_on == OBSERVED_ON


def test_a_missing_language_is_a_state_not_an_exception() -> None:
    adapter = ToyCorpusAdapter(observed_on=OBSERVED_ON, language="LOL")
    unavailable = adapter.fetch_version(HOUSE_RULES, V1)
    assert isinstance(unavailable, EnglishUnavailable)
    assert unavailable.requested_language == "LOL"
    assert unavailable.available_languages == ("ENG",)


def test_amending_document_quotes_what_it_changes(adapter: ToyCorpusAdapter) -> None:
    doc = adapter.parse_amending_act(AMENDMENT)
    assert isinstance(doc, AmendingActDoc)
    assert doc.amends == (HOUSE_RULES,)
    assert [quoted.stated_change_type for quoted in doc.quoted] == [
        ChangeType.MODIFIED,
        ChangeType.DELETED,
        ChangeType.INSERTED,
    ]
    inserted = doc.quoted[-1]
    assert inserted.location is None, "amending prose omits the identifier it inserts"
    assert inserted.text


def test_unknown_acts_are_a_programming_error_not_a_state(adapter: ToyCorpusAdapter) -> None:
    with pytest.raises(ValueError, match="unknown toy act"):
        adapter.discover_versions(ActId(corpus="toy", key="nope"))
    with pytest.raises(ValueError, match="unknown toy version"):
        adapter.fetch_version(HOUSE_RULES, VersionId("v9"))
